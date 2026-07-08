import os
import re
import json
import ssl
import boto3
import urllib.request
import urllib.parse
from urllib.error import HTTPError, URLError
from boto3.s3.transfer import TransferConfig


s3 = boto3.client("s3")

DEFAULT_S3_BUCKET = os.environ.get("S3_BUCKET")
DEFAULT_S3_PREFIX = os.environ.get("S3_PREFIX", "ifg_papers")

SSL_CONTEXT = ssl._create_unverified_context()

TRANSFER_CONFIG = TransferConfig(
    multipart_threshold=8 * 1024 * 1024,
    multipart_chunksize=8 * 1024 * 1024,
    max_concurrency=4,
    use_threads=True
)


def make_s3_key(prefix, file_name):
    prefix = (prefix or "").strip("/")

    if prefix:
        return f"{prefix}/{file_name}"

    return file_name


def extract_id_from_url(url):
    parsed = urllib.parse.urlparse(url)

    match = re.search(r"/handle/[^/]+/(\d+)", parsed.path)
    if match:
        return match.group(1)

    match = re.search(r"/bitstream/[^/]+/(\d+)/", parsed.path)
    if match:
        return match.group(1)

    numbers = re.findall(r"\d+", parsed.path)

    if numbers:
        return numbers[-1]

    raise ValueError("Missing id and could not extract id from URL.")


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

    pdf_url = event.get("pdf_url") or event.get("url")
    item_id = event.get("id")
    bucket = event.get("bucket") or DEFAULT_S3_BUCKET
    prefix = event.get("prefix") or DEFAULT_S3_PREFIX

    if not pdf_url:
        raise ValueError("Missing required field: pdf_url")

    if not item_id:
        item_id = extract_id_from_url(pdf_url)

    if not bucket:
        raise ValueError("Missing bucket. Send bucket or configure S3_BUCKET.")

    return item_id, pdf_url, bucket, prefix


def upload_pdf_url_to_s3(pdf_url, bucket, key):
    request = urllib.request.Request(
        pdf_url,
        headers={
            "User-Agent": "Mozilla/5.0 IFG-PDF-Lambda/2.0",
            "Accept": "application/pdf,*/*;q=0.8",
            "Connection": "close"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=25,
        context=SSL_CONTEXT
    ) as response:
        source_content_type = response.headers.get("Content-Type", "")
        source_content_length = response.headers.get("Content-Length")

        s3.upload_fileobj(
            Fileobj=response,
            Bucket=bucket,
            Key=key,
            ExtraArgs={
                "ContentType": "application/pdf"
            },
            Config=TRANSFER_CONFIG
        )

    return {
        "source_content_type": source_content_type,
        "source_content_length": source_content_length
    }


def lambda_handler(event, context):
    try:
        item_id, pdf_url, bucket, prefix = parse_event(event)

        pdf_key = make_s3_key(prefix, f"{item_id}.pdf")

        upload_result = upload_pdf_url_to_s3(
            pdf_url=pdf_url,
            bucket=bucket,
            key=pdf_key
        )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "success",
                "id": item_id,
                "pdf_s3_bucket": bucket,
                "pdf_s3_key": pdf_key,
                "pdf_source_url": pdf_url,
                "source_content_type": upload_result["source_content_type"],
                "source_content_length": upload_result["source_content_length"]
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