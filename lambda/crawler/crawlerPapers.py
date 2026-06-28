import os
import re
import json
import boto3
import hashlib
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from html import unescape
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError


s3 = boto3.client("s3")

DEFAULT_S3_BUCKET = os.environ.get("S3_BUCKET")
DEFAULT_S3_PREFIX = os.environ.get("S3_PREFIX", "ifg/papers")

"""
input
{
  "url": "http://repositorio.ifg.edu.br/handle/prefix/2700",
  "bucket": "paperclusterpapers",
  "prefix": "ifg_papers"
}
"""
class HTMLTableParser(HTMLParser):
    """
    Parser simples para extrair tabelas HTML sem depender de BeautifulSoup.
    Extrai todas as tags <table>, <tr>, <td> e <th>.


    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []

        self._table_depth = 0
        self._current_table = None
        self._current_row = None
        self._current_cell = None
        self._inside_cell = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []

        if self._table_depth <= 0:
            return

        if tag == "tr":
            self._current_row = []

        elif tag in ("td", "th"):
            self._inside_cell = True
            self._current_cell = []

        elif tag == "br" and self._inside_cell:
            self._current_cell.append("\n")

    def handle_data(self, data):
        if self._table_depth > 0 and self._inside_cell and self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()

        if self._table_depth <= 0:
            return

        if tag in ("td", "th") and self._inside_cell:
            cell_text = clean_text("".join(self._current_cell))

            if self._current_row is not None:
                self._current_row.append(cell_text)

            self._current_cell = None
            self._inside_cell = False

        elif tag == "tr":
            if self._current_row:
                cleaned_row = [cell for cell in self._current_row if cell != ""]
                if cleaned_row:
                    self._current_table.append(cleaned_row)

            self._current_row = None

        elif tag == "table":
            if self._table_depth == 1:
                if self._current_table:
                    self.tables.append(self._current_table)

                self._current_table = None

            self._table_depth -= 1


def clean_text(value):
    """
    Limpa espaços extras, tabs e quebras de linha.
    Mantém quebras de linha relevantes dentro de uma célula.
    """
    if value is None:
        return ""

    value = unescape(value)
    lines = value.splitlines()

    cleaned_lines = []
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def fetch_html(url):
    """
    Baixa o HTML da URL informada.

    Observação:
    O site do repositório IFG pode apresentar problema de cadeia SSL
    no ambiente da AWS Lambda. Por isso, para este caso específico,
    usamos um contexto SSL sem verificação.
    """

    import ssl

    ssl_context = ssl._create_unverified_context()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 IFG-Repository-Scraper/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
        context=ssl_context
    ) as response:
        content_type = response.headers.get("Content-Type", "")
        charset = response.headers.get_content_charset() or "utf-8"
        html_bytes = response.read()

    html_text = html_bytes.decode(charset, errors="replace")

    return {
        "html": html_text,
        "content_type": content_type,
        "charset": charset,
    }

def extract_title(html):
    """
    Extrai o conteúdo da tag <title>, se existir.
    """
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)

    if not match:
        return None

    return clean_text(match.group(1))


def parse_tables(html):
    """
    Extrai todas as tabelas do HTML.
    """
    parser = HTMLTableParser()
    parser.feed(html)
    return parser.tables


def normalize_label(label):
    """
    Normaliza o nome do campo da tabela.
    Exemplo:
    'Título:' -> 'Título'
    'Data do documento:' -> 'Data do documento'
    """
    label = clean_text(label)
    label = re.sub(r":+$", "", label).strip()
    return label


def table_to_json(table):
    """
    Converte uma tabela HTML extraída em dois formatos:
    1. rows: preserva as linhas e colunas originais.
    2. fields: transforma linhas de 2+ colunas em chave/valor.
    
    Importante:
    Se o mesmo campo aparecer mais de uma vez, ele vira lista.
    Exemplo:
    Autor: João
    Autor: Maria

    Resultado:
    "Autor": ["João", "Maria"]
    """
    rows = []
    fields = {}

    for row in table:
        rows.append({
            "columns": row
        })

        if len(row) >= 2:
            key = normalize_label(row[0])
            value = clean_text(" | ".join(row[1:]))

            if key:
                if key not in fields:
                    fields[key] = []

                fields[key].append(value)

    return {
        "rows": rows,
        "fields": fields
    }


def choose_main_table(tables):
    """
    Escolhe a tabela mais provável de conter os metadados do paper.

    Critério:
    - prioriza tabelas com várias linhas de 2 ou mais colunas.
    """
    if not tables:
        return None

    def score(table):
        two_column_rows = sum(1 for row in table if len(row) >= 2)
        total_cells = sum(len(row) for row in table)
        return two_column_rows * 10 + total_cells

    return max(tables, key=score)


def make_s3_key(url, prefix):
    """
    Gera um nome de arquivo estável para o S3 com base na URL.
    Exemplo:
    https://repositorio.ifg.edu.br/handle/prefix/2700

    vira algo como:
    ifg/papers/handle_prefix_2700_a1b2c3d4.json
    """
    parsed = urllib.parse.urlparse(url)

    path = parsed.path.strip("/")
    path = path.replace("/", "_")
    path = re.sub(r"[^A-Za-z0-9_.=-]", "_", path)

    if not path:
        path = "index"

    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]

    prefix = prefix.strip("/")

    return f"{prefix}/{path}_{url_hash}.json"


def save_json_to_s3(bucket, key, payload):
    """
    Salva o JSON no S3.
    """
    body = json.dumps(payload, ensure_ascii=False, indent=2)

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/json; charset=utf-8",
    )


def parse_lambda_event(event):
    """
    Aceita eventos em alguns formatos diferentes:

    Formato direto:
    {
      "url": "https://repositorio.ifg.edu.br/handle/prefix/2700",
      "bucket": "meu-bucket",
      "prefix": "ifg/papers"
    }

    Ou via API Gateway:
    {
      "body": "{\"url\":\"https://repositorio.ifg.edu.br/handle/prefix/2700\"}"
    }
    """
    if isinstance(event, str):
        event = json.loads(event)

    if "body" in event:
        body = event["body"]

        if isinstance(body, str):
            body = json.loads(body)

        if isinstance(body, dict):
            event = body

    url = event.get("url")
    bucket = event.get("bucket") or DEFAULT_S3_BUCKET
    prefix = event.get("prefix") or DEFAULT_S3_PREFIX

    if not url:
        raise ValueError("O campo 'url' é obrigatório no input da Lambda.")

    if not bucket:
        raise ValueError(
            "O bucket S3 não foi informado. Passe 'bucket' no evento ou configure a variável de ambiente S3_BUCKET."
        )

    return url, bucket, prefix


def lambda_handler(event, context):
    try:
        url, bucket, prefix = parse_lambda_event(event)

        fetched = fetch_html(url)
        html = fetched["html"]

        title = extract_title(html)
        tables = parse_tables(html)

        if not tables:
            raise ValueError("Nenhuma tabela HTML foi encontrada na página informada.")

        main_table = choose_main_table(tables)

        all_tables_json = []
        for index, table in enumerate(tables):
            all_tables_json.append({
                "table_index": index,
                "table": table_to_json(table)
            })

        output = {
            "source_url": url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "page_title": title,
            "content_type": fetched["content_type"],
            "charset": fetched["charset"],
            "main_table": table_to_json(main_table),
            "all_tables": all_tables_json
        }

        s3_key = make_s3_key(url, prefix)

        save_json_to_s3(
            bucket=bucket,
            key=s3_key,
            payload=output
        )

        response = {
            "status": "success",
            "source_url": url,
            "s3_bucket": bucket,
            "s3_key": s3_key,
            "data": output
        }

        return {
            "statusCode": 200,
            "body": json.dumps(response, ensure_ascii=False)
        }

    except HTTPError as error:
        return {
            "statusCode": error.code,
            "body": json.dumps({
                "status": "error",
                "message": f"Erro HTTP ao acessar a página: {error}",
            }, ensure_ascii=False)
        }

    except URLError as error:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": f"Erro de rede ao acessar a página: {error}",
            }, ensure_ascii=False)
        }

    except Exception as error:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": str(error),
            }, ensure_ascii=False)
        }