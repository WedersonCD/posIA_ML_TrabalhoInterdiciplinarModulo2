import os
import re
import json
import ssl
import boto3
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from html import unescape
from urllib.error import HTTPError, URLError


s3 = boto3.client("s3")

DEFAULT_S3_BUCKET = os.environ.get("S3_BUCKET")
DEFAULT_S3_PREFIX = os.environ.get("S3_PREFIX", "ifg_papers")

SSL_CONTEXT = ssl._create_unverified_context()


def clean_text(value):
    if value is None:
        return ""

    value = unescape(str(value))
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_label(label):
    label = clean_text(label)
    label = re.sub(r":+$", "", label).strip()
    return label


def add_value(target, key, value):
    key = normalize_label(key)
    value = clean_text(value)

    if not key or not value:
        return

    if key not in target:
        target[key] = value
        return

    if isinstance(target[key], list):
        if value not in target[key]:
            target[key].append(value)
        return

    if target[key] != value:
        target[key] = [target[key], value]


class DSpaceItemParser(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)

        self.base_url = base_url
        self.tables = []
        self.page_title = ""

        self._inside_title = False
        self._title_parts = []

        self._inside_heading = False
        self._heading_parts = []
        self._last_heading = ""

        self._table_depth = 0
        self._current_table = None
        self._current_row = None
        self._current_cell = None

        self._inside_cell = False
        self._inside_link = False
        self._current_link_href = None
        self._current_link_text = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        attrs_dict = {
            str(k).lower(): (v or "")
            for k, v in attrs
            if k is not None
        }

        if tag == "title":
            self._inside_title = True
            self._title_parts = []
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._inside_heading = True
            self._heading_parts = []
            return

        if tag == "table":
            self._table_depth += 1

            if self._table_depth == 1:
                self._current_table = {
                    "heading": self._last_heading,
                    "attrs": attrs_dict,
                    "rows": []
                }

            return

        if self._table_depth <= 0:
            return

        if tag == "tr":
            self._current_row = []

        elif tag in ("td", "th"):
            self._inside_cell = True
            self._current_cell = {
                "text": [],
                "links": [],
                "attrs": attrs_dict
            }

        elif tag == "br" and self._inside_cell:
            self._current_cell["text"].append(" ")

        elif tag == "a" and self._inside_cell:
            href = attrs_dict.get("href")

            if href:
                self._inside_link = True
                self._current_link_href = urllib.parse.urljoin(self.base_url, href)
                self._current_link_href, _ = urllib.parse.urldefrag(self._current_link_href)
                self._current_link_text = []

    def handle_data(self, data):
        if self._inside_title:
            self._title_parts.append(data)

        if self._inside_heading:
            self._heading_parts.append(data)

        if self._inside_cell and self._current_cell is not None:
            self._current_cell["text"].append(data)

        if self._inside_link:
            self._current_link_text.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "title":
            self.page_title = clean_text(" ".join(self._title_parts))
            self._inside_title = False
            return

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            heading = clean_text(" ".join(self._heading_parts))

            if heading:
                self._last_heading = heading

            self._inside_heading = False
            return

        if self._table_depth <= 0:
            return

        if tag == "a" and self._inside_link:
            if self._current_cell is not None:
                self._current_cell["links"].append({
                    "href": self._current_link_href,
                    "text": clean_text(" ".join(self._current_link_text))
                })

            self._inside_link = False
            self._current_link_href = None
            self._current_link_text = []
            return

        if tag in ("td", "th") and self._inside_cell:
            if self._current_row is not None and self._current_cell is not None:
                self._current_row.append({
                    "text": clean_text(" ".join(self._current_cell["text"])),
                    "links": self._current_cell["links"],
                    "attrs": self._current_cell["attrs"]
                })

            self._inside_cell = False
            self._current_cell = None
            return

        if tag == "tr":
            if self._current_row and self._current_table is not None:
                non_empty = [
                    cell for cell in self._current_row
                    if cell["text"] or cell["links"]
                ]

                if non_empty:
                    self._current_table["rows"].append(non_empty)

            self._current_row = None
            return

        if tag == "table":
            if self._table_depth == 1 and self._current_table:
                if self._current_table["rows"]:
                    self.tables.append(self._current_table)

                self._current_table = None

            self._table_depth -= 1


def fetch_html(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 IFG-CrawlerPaper/1.1",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(request, timeout=20, context=SSL_CONTEXT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def build_full_record_url(url):
    parsed = urllib.parse.urlparse(url)

    query = urllib.parse.parse_qs(parsed.query)
    query["show"] = ["full"]

    return urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urllib.parse.urlencode(query, doseq=True),
        parsed.fragment
    ))


def extract_item_id(url):
    parsed = urllib.parse.urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]

    if not parts:
        raise ValueError("Could not extract paper id from URL.")

    return parts[-1]


def make_s3_key(prefix, file_name):
    prefix = (prefix or "").strip("/")

    if prefix:
        return f"{prefix}/{file_name}"

    return file_name


def table_text(table):
    values = []

    for row in table.get("rows", []):
        for cell in row:
            if cell.get("text"):
                values.append(cell["text"])

            for link in cell.get("links", []):
                values.append(link.get("href", ""))
                values.append(link.get("text", ""))

    return " ".join(values).lower()


def is_files_table(table):
    heading = clean_text(table.get("heading", "")).lower()
    summary = clean_text(table.get("attrs", {}).get("summary", "")).lower()
    text = table_text(table)

    if "arquivos associados a este item" in heading:
        return True

    if "files in this item" in heading:
        return True

    if "files associated" in summary:
        return True

    if "arquivos associados" in summary:
        return True

    if "arquivo" in text and "formato" in text and ("pdf" in text or "bitstream" in text):
        return True

    return False


def find_pdf_url_from_tables(tables):
    preferred_tables = [table for table in tables if is_files_table(table)]

    if not preferred_tables:
        preferred_tables = tables

    for table in preferred_tables:
        for row in table.get("rows", []):
            row_text = " ".join(cell.get("text", "") for cell in row).lower()

            for cell in row:
                for link in cell.get("links", []):
                    href = link.get("href", "")

                    if not href:
                        continue

                    href_lower = href.lower()

                    if href_lower.endswith(".pdf"):
                        return href

                    if ".pdf" in href_lower:
                        return href

                    if "/bitstream/" in href_lower and "pdf" in row_text:
                        return href

                    if "/bitstream/" in href_lower:
                        return href

    return None


def find_pdf_url_from_html(html, base_url):
    hrefs = re.findall(
        r'href=["\']([^"\']*?/bitstream/[^"\']+)["\']',
        html,
        flags=re.IGNORECASE
    )

    for href in hrefs:
        absolute_url = urllib.parse.urljoin(base_url, unescape(href))
        absolute_url, _ = urllib.parse.urldefrag(absolute_url)
        return absolute_url

    return None


def is_metadata_row(row):
    if len(row) < 2:
        return False

    first_cell = row[0]
    key = normalize_label(first_cell.get("text", ""))

    if not key:
        return False

    cell_class = first_cell.get("attrs", {}).get("class", "").lower()

    if "metadatafieldlabel" in cell_class:
        return True

    if key.endswith(":"):
        return True

    known_terms = (
        "tipo",
        "type",
        "título",
        "title",
        "autor",
        "author",
        "orientador",
        "advisor",
        "data",
        "date",
        "resumo",
        "abstract",
        "palavras",
        "keywords",
        "uri",
        "citation",
        "publisher",
        "instituição",
        "language",
        "dc."
    )

    key_lower = key.lower()

    return any(term in key_lower for term in known_terms)


def is_probably_metadata_table(table):
    if is_files_table(table):
        return False

    rows = table.get("rows", [])
    metadata_rows = sum(1 for row in rows if is_metadata_row(row))

    return metadata_rows >= 2


def choose_metadata_table(tables):
    candidates = [table for table in tables if is_probably_metadata_table(table)]

    if not candidates:
        return None

    def score(table):
        rows = table.get("rows", [])
        metadata_rows = sum(1 for row in rows if is_metadata_row(row))
        total_rows = len(rows)

        return metadata_rows * 10 + total_rows

    return max(candidates, key=score)


def metadata_table_to_json(table):
    metadata = {}

    if not table:
        return metadata

    skip_keys = {
        "arquivo",
        "file",
        "descrição",
        "description",
        "tamanho",
        "size",
        "formato",
        "format",
        "visualizar",
        "view/open"
    }

    for row in table.get("rows", []):
        if len(row) < 2:
            continue

        key = normalize_label(row[0].get("text", ""))

        if not key:
            continue

        key_lower = key.lower().strip(":")

        if key_lower in skip_keys:
            continue

        value_parts = []

        for cell in row[1:]:
            text = clean_text(cell.get("text", ""))

            if text:
                value_parts.append(text)

            for link in cell.get("links", []):
                link_text = clean_text(link.get("text", ""))

                if link_text and link_text not in value_parts:
                    value_parts.append(link_text)

        value = clean_text(" | ".join(value_parts))

        add_value(metadata, key, value)

    return metadata


def parse_html(html, base_url):
    parser = DSpaceItemParser(base_url=base_url)
    parser.feed(html)

    metadata_table = choose_metadata_table(parser.tables)
    metadata = metadata_table_to_json(metadata_table)

    pdf_url = find_pdf_url_from_tables(parser.tables)

    if not pdf_url:
        pdf_url = find_pdf_url_from_html(html, base_url)

    return {
        "page_title": parser.page_title,
        "metadata": metadata,
        "pdf_url": pdf_url,
        "tables_found": len(parser.tables)
    }


def parse_event(event):
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

    url = event.get("url")
    bucket = event.get("bucket") or DEFAULT_S3_BUCKET
    prefix = event.get("prefix") or DEFAULT_S3_PREFIX

    if not url:
        raise ValueError("Missing required field: url")

    if not bucket:
        raise ValueError("Missing bucket. Send bucket or configure S3_BUCKET.")

    return url, bucket, prefix


def lambda_handler(event, context):
    try:
        url, bucket, prefix = parse_event(event)

        item_id = extract_item_id(url)

        html = fetch_html(url)
        parsed = parse_html(html, base_url=url)

        metadata = parsed["metadata"]
        pdf_url = parsed["pdf_url"]
        source_used = "default"

        # Fast path first. Only use ?show=full if the default page did not produce metadata.
        if not metadata:
            full_url = build_full_record_url(url)
            full_html = fetch_html(full_url)
            full_parsed = parse_html(full_html, base_url=full_url)

            metadata = full_parsed["metadata"]
            source_used = "show_full"

            if not pdf_url:
                pdf_url = full_parsed["pdf_url"]

            parsed["page_title"] = full_parsed["page_title"] or parsed["page_title"]
            parsed["tables_found"] = full_parsed["tables_found"]

        metadata["_id"] = item_id
        metadata["_source_url"] = url

        if pdf_url:
            metadata["_pdf_url"] = pdf_url

        if not metadata or len(metadata.keys()) <= 2:
            metadata["_parser_warning"] = "No metadata fields were found in default page or show=full page."

        json_key = make_s3_key(prefix, f"{item_id}.json")

        s3.put_object(
            Bucket=bucket,
            Key=json_key,
            Body=json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            ContentType="application/json; charset=utf-8"
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "success",
                "id": item_id,
                "json_s3_bucket": bucket,
                "json_s3_key": json_key,
                "pdf_url": pdf_url,
                "metadata_fields_count": len([
                    key for key in metadata.keys()
                    if not key.startswith("_")
                ]),
                "source_used": source_used,
                "tables_found": parsed["tables_found"],
                "metadata": metadata
            }, ensure_ascii=False, separators=(",", ":"))
        }

    except HTTPError as error:
        return {
            "statusCode": error.code,
            "body": json.dumps({
                "status": "error",
                "message": str(error)
            }, ensure_ascii=False, separators=(",", ":"))
        }

    except URLError as error:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": str(error)
            }, ensure_ascii=False, separators=(",", ":"))
        }

    except Exception as error:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": str(error)
            }, ensure_ascii=False, separators=(",", ":"))
        }