import json
import re
import ssl
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError


TARGET_TABLE_SUMMARY = "This table browses all dspace content"


class DSpaceSearchTableLinkParser(HTMLParser):
    """
    Extracts paper links from the DSpace search result table.

    Target table:
    <table summary="This table browses all dspace content">

    Output:
    [
      "https://repositorio.ifg.edu.br/handle/prefix/2700",
      "https://repositorio.ifg.edu.br/handle/prefix/2699"
    ]
    """

    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)

        self.base_url = base_url
        self.links = []
        self._seen_links = set()

        self._inside_target_table = False
        self._target_table_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict = {key.lower(): value for key, value in attrs}

        if tag == "table":
            summary = (attrs_dict.get("summary") or "").strip()

            if self._inside_target_table:
                self._target_table_depth += 1

            elif summary == TARGET_TABLE_SUMMARY:
                self._inside_target_table = True
                self._target_table_depth = 1

            return

        if not self._inside_target_table:
            return

        if tag == "a":
            href = attrs_dict.get("href")

            if not href:
                return

            absolute_url = urllib.parse.urljoin(self.base_url, href)
            absolute_url, _fragment = urllib.parse.urldefrag(absolute_url)

            if self._is_paper_link(absolute_url):
                self._add_link(absolute_url)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "table" and self._inside_target_table:
            self._target_table_depth -= 1

            if self._target_table_depth <= 0:
                self._inside_target_table = False
                self._target_table_depth = 0

    def _is_paper_link(self, url):
        """
        Keeps only DSpace item links.

        Examples accepted:
        /handle/prefix/2700
        /handle/123456789/2700
        """
        parsed = urllib.parse.urlparse(url)

        return re.search(r"/handle/[^/]+/\d+", parsed.path) is not None

    def _add_link(self, url):
        """
        Avoid duplicated links while preserving order.
        """
        if url not in self._seen_links:
            self._seen_links.add(url)
            self.links.append(url)


def fetch_html(url):
    """
    Downloads the HTML.

    The IFG repository may fail SSL validation inside AWS Lambda because of
    certificate chain issues, so this function uses an unverified SSL context.
    """

    ssl_context = ssl._create_unverified_context()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 IFG-Repository-Search-Scraper/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
        context=ssl_context
    ) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        html_bytes = response.read()

    return html_bytes.decode(charset, errors="replace")


def parse_lambda_event(event):
    """
    Accepts different input formats.

    Direct Lambda test:
    {
      "url": "https://repositorio.ifg.edu.br/simple-search?location=&query=&rpp=9999&sort_by=dc.date.issued_dt&order=DESC&etal=0&submit_search=Atualizar"
    }

    API Gateway body:
    {
      "body": "{\"url\":\"https://repositorio.ifg.edu.br/simple-search?...\"}"
    }

    API Gateway query string:
    /lambda-url?url=https%3A%2F%2Frepositorio.ifg.edu.br%2Fsimple-search%3F...
    """

    if isinstance(event, str):
        event = json.loads(event)

    if not isinstance(event, dict):
        raise ValueError("Invalid event format.")

    query_params = event.get("queryStringParameters") or {}

    if query_params.get("url"):
        return query_params["url"]

    if "body" in event and event["body"]:
        body = event["body"]

        if isinstance(body, str):
            body = json.loads(body)

        if isinstance(body, dict) and body.get("url"):
            return body["url"]

    if event.get("url"):
        return event["url"]

    raise ValueError("The field 'url' is required.")


def extract_paper_links(search_page_url):
    html = fetch_html(search_page_url)

    parser = DSpaceSearchTableLinkParser(base_url=search_page_url)
    parser.feed(html)

    return parser.links


def lambda_handler(event, context):
    try:
        search_page_url = parse_lambda_event(event)

        links = extract_paper_links(search_page_url)

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json; charset=utf-8"
            },
            "body": json.dumps(links, ensure_ascii=False)
        }

    except HTTPError as error:
        return {
            "statusCode": error.code,
            "headers": {
                "Content-Type": "application/json; charset=utf-8"
            },
            "body": json.dumps({
                "status": "error",
                "message": f"HTTP error while accessing the page: {error}"
            }, ensure_ascii=False)
        }

    except URLError as error:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json; charset=utf-8"
            },
            "body": json.dumps({
                "status": "error",
                "message": f"Network error while accessing the page: {error}"
            }, ensure_ascii=False)
        }

    except Exception as error:
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json; charset=utf-8"
            },
            "body": json.dumps({
                "status": "error",
                "message": str(error)
            }, ensure_ascii=False)
        }