import json

from math import ceil as math_ceil

from airflow.sdk import dag, task,task_group
from datetime import datetime
from airflow.providers.amazon.aws.operators.lambda_function import (
    LambdaInvokeFunctionOperator
)
from airflow.operators.python import get_current_context

@dag(
    schedule=None,
    start_date=datetime(2026,7,5),
    catchup=False,
    tags=["clusterPaperIFG"],
    params={
        "run_mode": "PUBLISH_DATE",#PUBLISH_DATE DIRECT_LINK
        "papers_direct_link": "https://repositorio.ifg.edu.br/simple-search?filterquery=Acesso+Aberto&filtername=access&filtertype=equals&rpp=9999",
        "papers_publish_date":"2026-06-03",
        "aws_bucket_name": "cluster-paper-ifg"
    }
)
def crawlerUnstructuredData():
    aws_conn_id     = 'AWS_LAB'

    @task
    def build_crawlerLinks_payload():
        linkURL=""
        
        context = get_current_context()
        params = context["params"]
        run_mode = params["run_mode"]

        #If direct_link is included, use it. If not build the link using the date.
        if run_mode == "PUBLISH_DATE":
            linkURL = f"https://repositorio.ifg.edu.br/simple-search?location=&query=&filter_field_1=dateIssued&filter_type_1=equals&filter_value_1={params["papers_publish_date"]}&rpp=9999"

        elif run_mode == "DIRECT_LINK":
            linkURL = params["papers_direct_link"]

        return json.dumps({"url": linkURL})
    
    crawlerLinks_payload = build_crawlerLinks_payload()

    invoke_lambda_crawlerLinks = LambdaInvokeFunctionOperator(
        aws_conn_id=aws_conn_id,
        task_id="invoke_lambda_crawlerLinks",
        function_name="clusterPaperIFG_crawlerLinks",
        invocation_type="RequestResponse",
        payload=crawlerLinks_payload,
    )

    @task
    def parse_lambda_response(response):

        if isinstance(response, bytes):
            response = response.decode("utf-8")

        if isinstance(response, str):
            response = json.loads(response)

        if not isinstance(response, dict):
            return response

        if response.get("statusCode") != 200:
            raise ValueError(f"Lambda returned non-200 response: {response}")

        body = response.get("body")

        if body is None:
            raise ValueError(f"Lambda response has no body: {response}")

        if isinstance(body, str):
            body = json.loads(body)


        return body

    @task
    def build_crawlerPaper_payload(link):
        context     = get_current_context()
        params      = context["params"]
        
        return json.dumps({
            "url": link,
            "bucket": params["aws_bucket_name"],
            "prefix": "Metadata"

        })

    @task
    def build_crawlerPDF_payload(paper):
        context     = get_current_context()
        params      = context["params"]

        return json.dumps({
            "id": paper["id"],
            "pdf_url": paper["pdf_url"],
            "bucket": params["aws_bucket_name"],
            "prefix": "PDF"
        })
    
    @task
    def build_crawlerTableOfContent_payload(PDF):
        return json.dumps({
            "paper_id": PDF["id"],
            "pdf_s3_uri": f"s3://cluster-paper-ifg/{PDF["pdf_s3_key"]}",
            "output_prefix": "TableOfContent"
        })
    
    @task
    def print_test(link):
        print("Object:>>>",type(link))
        print("Object:>>>",link)
    
    @task_group
    def process_paper(link):

        #PAPER
        crawlerPaper_payload = build_crawlerPaper_payload(link)     
        crawlerPaperResponse = LambdaInvokeFunctionOperator(
                aws_conn_id=aws_conn_id,
                task_id="invoke_lambda_crawlerPaper",
                function_name="clusterPaperIFG_crawlerPapers",
                invocation_type="RequestResponse",
                payload=crawlerPaper_payload,
                pool="lambda_pool"
            )
               
        crawlerPaperResponse_parsed = parse_lambda_response.override(
            task_id="parse_lambda_response_crawlerPaper"
        )(crawlerPaperResponse.output)      
        

        #PDF
        crawlerPDF_payload = build_crawlerPDF_payload(crawlerPaperResponse_parsed)      
        
        crawlerPDFResponse = LambdaInvokeFunctionOperator(
            aws_conn_id=aws_conn_id,
            task_id="invoke_lambda_crawlerPDF",
            function_name="clusterPaperIFG_crawlerPDF",
            invocation_type="RequestResponse",
            payload=crawlerPDF_payload,
            pool="lambda_pool"
        )       
        
        crawlerPDFResponse_parsed = parse_lambda_response.override(
            task_id="parse_lambda_response_crawlerPDF"
        )(crawlerPDFResponse.output)        
        
        
        #TABLE OF CONTENT
        crawlerTableOfContent_payload = build_crawlerTableOfContent_payload(crawlerPDFResponse_parsed)      
        
        crawlerTableOfContentResponse = LambdaInvokeFunctionOperator(
            aws_conn_id=aws_conn_id,
            task_id="invoke_lambda_crawlerTableOfContent",
            function_name="clusterPaperIFG_crawlerTableOfContent",
            invocation_type="RequestResponse",
            payload=crawlerTableOfContent_payload,
            pool="lambda_pool"
        )
        """
        crawlerTableOfContentResponse_parsed = parse_lambda_response.override(
            task_id="parse_lambda_response_crawlerTableOfContent"
        )(crawlerTableOfContentResponse.output)     
        print_test(crawlerTableOfContentResponse_parsed)
        """

        return None


    parsed_links  = parse_lambda_response.override(task_id="parse_lambda_response_crawlerLinks")(invoke_lambda_crawlerLinks.output)
    #paper_batches = create_papers_batches(parsed_links)

    process_paper.expand(link=parsed_links)

crawlerUnstructuredData()
