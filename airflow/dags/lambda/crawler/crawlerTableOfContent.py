import os
import re
import json
import time
import signal
import boto3
from urllib.parse import urlparse
from pypdf import PdfReader


s3 = boto3.client("s3")

DEFAULT_OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET")
DEFAULT_OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX")

MAX_PAGES_TO_SCAN = int(os.environ.get("MAX_PAGES_TO_SCAN", "35"))
MIN_EXTRACTED_TEXT_CHARS = int(os.environ.get("MIN_EXTRACTED_TEXT_CHARS", "500"))
MIN_SUMARIO_CHARS = int(os.environ.get("MIN_SUMARIO_CHARS", "100"))
PAGE_EXTRACT_TIMEOUT_SECONDS = int(os.environ.get("PAGE_EXTRACT_TIMEOUT_SECONDS", "2"))
TEXT_LAYER_CHECK_PAGES = int(os.environ.get("TEXT_LAYER_CHECK_PAGES", "5"))

DEBUG_MODE_ENV = os.environ.get("DEBUG_MODE", "false").lower() == "true"


class PageExtractTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise PageExtractTimeout("page extract timeout")


class Logger:
    def __init__(self, debug=False, context=None):
        self.debug = debug
        self.context = context
        self.start = time.perf_counter()
        self.last = self.start

    def log(self, step, always=True, **kwargs):
        if not always and not self.debug:
            return

        now = time.perf_counter()

        payload = {
            "debug": self.debug,
            "step": step,
            "total_ms": round((now - self.start) * 1000, 2),
            "step_ms": round((now - self.last) * 1000, 2),
            **kwargs
        }

        self.last = now

        if self.context:
            try:
                payload["remaining_ms"] = self.context.get_remaining_time_in_millis()
            except Exception:
                pass

        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def parse_s3_uri(s3_uri):
    parsed = urlparse(s3_uri)

    if parsed.scheme != "s3":
        raise ValueError("Invalid s3_uri. Expected format: s3://bucket/key.pdf")

    bucket = parsed.netloc
    key = parsed.path.lstrip("/")

    if not bucket or not key:
        raise ValueError("Invalid s3_uri. Bucket or key is empty.")

    return bucket, key


def extract_paper_id_from_key(key):
    file_name = key.split("/")[-1]
    match = re.search(r"(\d+)", file_name)

    if not match:
        raise ValueError("Could not extract paper_id from file name. Send paper_id explicitly.")

    return match.group(1)


def get_parent_prefix(key):
    parts = key.split("/")

    if len(parts) <= 1:
        return ""

    return "/".join(parts[:-1])


def parse_event(event, logger):
    logger.log("parse_event_start")

    if isinstance(event, str):
        event = json.loads(event)

    if not isinstance(event, dict):
        raise ValueError("Invalid event. Expected JSON object.")

    if "body" in event and event["body"]:
        body = event["body"]

        if isinstance(body, str):
            body = json.loads(body)

        if isinstance(body, dict):
            event = body

    if event.get("pdf_s3_uri"):
        bucket, key = parse_s3_uri(event["pdf_s3_uri"])
    else:
        bucket = event.get("bucket")
        key = event.get("key")

    if not bucket:
        raise ValueError("Missing bucket or pdf_s3_uri.")

    if not key:
        raise ValueError("Missing key or pdf_s3_uri.")

    paper_id = event.get("paper_id") or extract_paper_id_from_key(key)

    output_bucket = event.get("output_bucket") or DEFAULT_OUTPUT_BUCKET or bucket

    output_prefix = event.get("output_prefix")

    if output_prefix is None:
        output_prefix = DEFAULT_OUTPUT_PREFIX

    if output_prefix is None:
        output_prefix = get_parent_prefix(key)

    params = {
        "bucket": bucket,
        "key": key,
        "paper_id": paper_id,
        "output_bucket": output_bucket,
        "output_prefix": output_prefix
    }

    logger.log("parse_event_end", params=params)

    return params


def validate_pdf_s3_object(bucket, key, logger):
    if not key.lower().endswith(".pdf"):
        raise ValueError(f"error 0: Input file is not a PDF. Received key: {key}")

    logger.log("s3_head_object_start", bucket=bucket, key=key)

    head = s3.head_object(
        Bucket=bucket,
        Key=key
    )

    content_type = head.get("ContentType", "")
    content_length = head.get("ContentLength")

    logger.log(
        "s3_head_object_end",
        content_length=content_length,
        content_type=content_type
    )

    if content_length is not None and content_length < 1000:
        raise ValueError(f"error 0: PDF file is too small. Size: {content_length} bytes")

    return head


def download_pdf_to_tmp(bucket, key, paper_id, logger):
    local_path = f"/tmp/{paper_id}.pdf"

    validate_pdf_s3_object(bucket, key, logger)

    logger.log("s3_download_start", bucket=bucket, key=key, local_path=local_path)

    s3.download_file(
        Bucket=bucket,
        Key=key,
        Filename=local_path
    )

    file_size = os.path.getsize(local_path)

    logger.log("s3_download_end", local_path=local_path, file_size=file_size)

    return local_path


def dereference_pdf_object(obj):
    try:
        return obj.get_object()
    except Exception:
        return obj


def page_has_text_layer_hint(page):
    try:
        resources = dereference_pdf_object(page.get("/Resources"))

        if not resources:
            return False

        fonts = dereference_pdf_object(resources.get("/Font"))

        if fonts:
            return True

        xobjects = dereference_pdf_object(resources.get("/XObject"))

        if xobjects:
            for obj in xobjects.values():
                xobject = dereference_pdf_object(obj)

                if not xobject:
                    continue

                xobject_resources = dereference_pdf_object(xobject.get("/Resources"))

                if not xobject_resources:
                    continue

                xobject_fonts = dereference_pdf_object(xobject_resources.get("/Font"))

                if xobject_fonts:
                    return True

        return False

    except Exception:
        return True


def normalize_text(text):
    text = text.replace("\x00", " ")
    text = text.replace("\ufeff", " ")
    text = text.replace("\u2026", "...")
    text = text.replace("·", ".")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n +", "\n", text)
    return text.strip()


def normalize_line(line):
    line = normalize_text(line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_sumario_marker(line):
    return re.fullmatch(r"SUM[ÁA]RIO", normalize_line(line), flags=re.IGNORECASE) is not None


def is_noise_line(line):
    line = normalize_line(line)

    if not line:
        return True

    # Roman page numbers: ix, x, xi, xiv...
    if re.fullmatch(r"[ivxlcdm]{1,8}", line.lower()):
        return True

    # Numeric isolated page number.
    if re.fullmatch(r"\d{1,3}", line):
        return True

    return False


def is_toc_entry_line(line):
    line = normalize_line(line)

    if not line or is_noise_line(line):
        return False

    upper = line.upper()

    # Dot leaders or repeated separator characters.
    if re.search(r"(\.{3,}|_{3,}|-{3,})", line):
        return True

    # Ends with a page number or roman numeral.
    if re.search(r"\s+(\d{1,4}|[IVXLCDM]{1,8})$", line, flags=re.IGNORECASE):
        return True

    # Common TOC labels.
    toc_terms = [
        "INTRODUÇÃO",
        "INTRODUCAO",
        "CAPÍTULO",
        "CAPITULO",
        "CONSIDERAÇÕES FINAIS",
        "CONSIDERACOES FINAIS",
        "CONCLUSÃO",
        "CONCLUSAO",
        "CONCLUSÕES",
        "CONCLUSOES",
        "REFERÊNCIAS",
        "REFERENCIAS",
        "RESUMO",
        "ABSTRACT",
        "LISTA DE",
        "AGRADECIMENTOS",
        "DEDICATÓRIA",
        "DEDICATORIA",
        "EPÍGRAFE",
        "EPIGRAFE",
        "FICHA CATALOGRÁFICA",
        "FICHA CATALOGRAFICA",
        "FOLHA DE APROVAÇÃO",
        "FOLHA DE APROVACAO"
    ]

    if any(term in upper for term in toc_terms):
        return True

    # Numbered headings: 1., 1.1, 2.3.4 etc.
    if re.match(r"^\d+(\.\d+)*\.?\s+", line):
        return True

    return False


def page_looks_like_sumario_page(text):
    lines = [normalize_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line and not is_noise_line(line)]

    if not lines:
        return False

    toc_like_count = sum(1 for line in lines if is_toc_entry_line(line))
    ratio = toc_like_count / max(len(lines), 1)

    has_page_number_endings = sum(
        1 for line in lines
        if re.search(r"\s+(\d{1,4}|[IVXLCDM]{1,8})$", line, flags=re.IGNORECASE)
    )

    has_leaders = sum(
        1 for line in lines
        if re.search(r"(\.{3,}|_{3,}|-{3,})", line)
    )

    return toc_like_count >= 3 or has_page_number_endings >= 3 or has_leaders >= 2 or ratio >= 0.45


def extract_page_text_with_timeout(reader, page_index, logger):
    logger.log("pdf_page_extract_start", page_index=page_index + 1)

    page_start = time.perf_counter()

    try:
        signal.alarm(PAGE_EXTRACT_TIMEOUT_SECONDS)

        page = reader.pages[page_index]
        page_text = page.extract_text() or ""

        signal.alarm(0)

    except PageExtractTimeout:
        signal.alarm(0)

        logger.log(
            "pdf_page_extract_timeout",
            page_index=page_index + 1,
            timeout_seconds=PAGE_EXTRACT_TIMEOUT_SECONDS
        )

        raise ValueError("error 1: No enough text")

    elapsed_ms = round((time.perf_counter() - page_start) * 1000, 2)

    logger.log(
        "pdf_page_extract_end",
        page_index=page_index + 1,
        page_elapsed_ms=elapsed_ms,
        page_chars=len(page_text.strip()),
        has_sumario="SUMÁRIO" in page_text.upper() or "SUMARIO" in page_text.upper(),
        looks_like_sumario_page=page_looks_like_sumario_page(page_text)
    )

    return page_text


def extract_sumario_text_from_pdf(local_pdf_path, max_pages, logger):
    logger.log("pdf_reader_open_start", local_pdf_path=local_pdf_path)

    reader = PdfReader(local_pdf_path)

    logger.log("pdf_reader_open_end")

    total_pages = len(reader.pages)
    pages_to_scan = min(total_pages, max_pages)
    pages_to_check = min(pages_to_scan, TEXT_LAYER_CHECK_PAGES)

    logger.log(
        "pdf_text_layer_check_start",
        total_pages=total_pages,
        pages_to_scan=pages_to_scan,
        pages_to_check=pages_to_check
    )

    text_layer_found = False

    for page_index in range(pages_to_check):
        has_text_hint = page_has_text_layer_hint(reader.pages[page_index])

        logger.log(
            "pdf_text_layer_check_page",
            page_index=page_index + 1,
            has_text_layer_hint=has_text_hint
        )

        if has_text_hint:
            text_layer_found = True

    if not text_layer_found:
        logger.log(
            "pdf_text_layer_check_fail",
            reason="no_font_resources_found_in_first_pages"
        )
        raise ValueError("error 1: No enough text")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)

    sumario_started = False
    sumario_lines = []
    pages_used = []

    extracted_chars_total = 0

    try:
        for page_index in range(pages_to_scan):
            page = reader.pages[page_index]

            if not page_has_text_layer_hint(page):
                logger.log(
                    "pdf_page_skipped_no_text_layer_hint",
                    page_index=page_index + 1
                )
                continue

            page_text = extract_page_text_with_timeout(reader, page_index, logger)
            page_text = normalize_text(page_text)
            extracted_chars_total += len(page_text)

            lines = [normalize_line(line) for line in page_text.splitlines()]
            lines = [line for line in lines if line and not is_noise_line(line)]

            if not sumario_started:
                marker_index = None

                for idx, line in enumerate(lines):
                    if is_sumario_marker(line):
                        marker_index = idx
                        break

                if marker_index is None:
                    continue

                sumario_started = True
                pages_used.append(page_index + 1)

                logger.log(
                    "sumario_marker_found",
                    page_index=page_index + 1
                )

                selected_lines = lines[marker_index:]
                sumario_lines.extend(selected_lines)
                continue

            # After SUMÁRIO started:
            # Continue while the next page still looks like TOC.
            if page_looks_like_sumario_page(page_text):
                pages_used.append(page_index + 1)
                sumario_lines.extend(lines)
                logger.log(
                    "sumario_page_appended",
                    page_index=page_index + 1
                )
                continue

            # First non-TOC page after sumário means the table of contents ended.
            logger.log(
                "sumario_end_detected",
                page_index=page_index + 1,
                reason="next_page_does_not_look_like_sumario"
            )
            break

    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    logger.log(
        "pdf_extract_total",
        extracted_chars_total=extracted_chars_total
    )

    if extracted_chars_total < MIN_EXTRACTED_TEXT_CHARS:
        raise ValueError("error 1: No enough text")

    if not sumario_started:
        raise ValueError("error 2: SUMÁRIO marker not found")

    sumario = clean_sumario("\n".join(sumario_lines))

    logger.log(
        "sumario_extract_end",
        sumario_chars=len(sumario),
        pages_used=pages_used,
        preview=sumario[:500]
    )

    if len(sumario) < MIN_SUMARIO_CHARS:
        raise ValueError("error 3: Extracted SUMÁRIO is too short")

    return sumario, pages_used


def clean_sumario(sumario):
    sumario = normalize_text(sumario)

    lines = []

    for line in sumario.splitlines():
        line = normalize_line(line)

        if not line or is_noise_line(line):
            continue

        # Normalize visual separators, but keep the page number.
        line = re.sub(r"[.·]{3,}", " ", line)
        line = re.sub(r"_{3,}", " ", line)
        line = re.sub(r"-{3,}", " ", line)
        line = re.sub(r"\s+", " ", line).strip()

        lines.append(line)

    # Remove duplicated consecutive lines.
    deduped = []

    for line in lines:
        if not deduped or deduped[-1] != line:
            deduped.append(line)

    return "\n".join(deduped).strip()


def make_output_key(prefix, paper_id):
    file_name = f"{paper_id}_tableOfContent.json"
    prefix = (prefix or "").strip("/")

    if prefix:
        return f"{prefix}/{file_name}"

    return file_name


def save_sumario_json(bucket, key, paper_id, sumario, logger):
    payload = {
        "paper_id": paper_id,
        "tableOfContent": sumario
    }

    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":")
    ).encode("utf-8")

    logger.log(
        "s3_put_sumario_start",
        bucket=bucket,
        key=key,
        body_bytes=len(body)
    )

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType="application/json; charset=utf-8"
    )

    logger.log("s3_put_sumario_end", bucket=bucket, key=key)

    return payload


def lambda_handler(event, context):
    debug_enabled = DEBUG_MODE_ENV

    if isinstance(event, dict):
        debug_enabled = bool(event.get("debug", DEBUG_MODE_ENV))

    logger = Logger(debug=debug_enabled, context=context)

    logger.log("lambda_start")

    try:
        params = parse_event(event, logger)

        local_pdf_path = download_pdf_to_tmp(
            bucket=params["bucket"],
            key=params["key"],
            paper_id=params["paper_id"],
            logger=logger
        )

        sumario, pages_used = extract_sumario_text_from_pdf(
            local_pdf_path=local_pdf_path,
            max_pages=MAX_PAGES_TO_SCAN,
            logger=logger
        )

        output_key = make_output_key(
            prefix=params["output_prefix"],
            paper_id=params["paper_id"]
        )

        payload = save_sumario_json(
            bucket=params["output_bucket"],
            key=output_key,
            paper_id=params["paper_id"],
            sumario=sumario,
            logger=logger
        )

        logger.log("lambda_success")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "success",
                "paper_id": params["paper_id"],
                "source_pdf_bucket": params["bucket"],
                "source_pdf_key": params["key"],
                "sumario_s3_bucket": params["output_bucket"],
                "sumario_s3_key": output_key,
                "sumario_length": len(sumario),
                "pages_used": pages_used,
                "data": payload
            }, ensure_ascii=False, separators=(",", ":"))
        }

    except ValueError as error:
        logger.log("lambda_value_error", error_message=str(error))

        return {
            "statusCode": 422,
            "body": json.dumps({
                "status": "error",
                "message": str(error)
            }, ensure_ascii=False, separators=(",", ":"))
        }

    except Exception as error:
        logger.log("lambda_unexpected_error", error_message=str(error))

        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": str(error)
            }, ensure_ascii=False, separators=(",", ":"))
        }