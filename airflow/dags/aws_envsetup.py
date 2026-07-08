import zipfile, subprocess, tempfile, sys, os, shutil

from datetime import datetime
from io import BytesIO
from pathlib import Path

from airflow.sdk import dag, task

from airflow.providers.amazon.aws.operators.athena import AthenaOperator

from airflow.providers.amazon.aws.operators.lambda_function import (
    LambdaCreateFunctionOperator
)
from airflow.providers.amazon.aws.operators.s3 import (
    S3CreateBucketOperator,
)

def get_file_content(fileDir):
    with open(fileDir,"r") as file:
        return file.read()

def create_zip(filePath):
    with BytesIO() as zip_output:
        with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as zip_file:
            content = get_file_content(filePath)
            info = zipfile.ZipInfo("lambda_function.py")
            info.external_attr = 0o777 << 16
            zip_file.writestr(info, content)
        zip_output.seek(0)
        return zip_output.read()

def create_lambda_zip_with_dependencies(lambda_file_path: str) -> bytes:

    with tempfile.TemporaryDirectory() as temp_dir:
        build_dir = Path(temp_dir) / "build"
        build_dir.mkdir(parents=True, exist_ok=True)

        # Instala a dependência dentro da pasta build.
        subprocess.check_call([
            sys.executable,
            "-m",
            "pip",
            "install",
            "pypdf",
            "-t",
            str(build_dir),
            "--no-cache-dir"
        ])

        # Copia seu código para a raiz do pacote com o nome esperado pelo handler.
        shutil.copyfile(
            lambda_file_path,
            build_dir / "lambda_function.py"
        )

        zip_path = Path(temp_dir) / "lambda_package.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in build_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(build_dir)
                    zip_file.write(file_path, arcname)

        return zip_path.read_bytes()

@dag(
    schedule=None,
    start_date=datetime(2026,7,3),
    catchup=False,
    tags=["clusterPaperIFG"],
)
def aws_envsetup():
    aws_conn_id='AWS_LAB'
    aws_account_role="arn:aws:iam::619893207681:role/LabRole"

    s3_athenaLog_bucket="cluster-paper-ifg-athena-log"

    athena_database_name="unstructured"
    athena_queryOutput_bucket=f"s3://{s3_athenaLog_bucket}/"

    airflow_containerFolder="/opt/airflow/dags"

    create_bucket_clusterPaperIFG =    S3CreateBucketOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_bucket_clusterPaperIFG",
        bucket_name='cluster-paper-ifg'
    )
    create_bucket_athenaLog =    S3CreateBucketOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_bucket_athenaLog",
        bucket_name=s3_athenaLog_bucket
    )

    create_lambda_function_crawlerLinks = LambdaCreateFunctionOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_lambda_function_crawlerLinks",
        function_name="clusterPaperIFG_crawlerLinks",
        runtime="python3.14",
        timeout=60,
        role=aws_account_role,
        handler="lambda_function.lambda_handler",
        code={
            "ZipFile": create_zip(f"{airflow_containerFolder}/lambda/crawler/crawlerLinks.py"),
        },
    )

    create_lambda_function_crawlerPapers = LambdaCreateFunctionOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_lambda_function_crawlerPapers",
        function_name="clusterPaperIFG_crawlerPapers",
        runtime="python3.14",
        role=aws_account_role,
        handler="lambda_function.lambda_handler",
        code={
            "ZipFile": create_zip(f"{airflow_containerFolder}/lambda/crawler/crawlerPapers.py"),
        },
    )

    create_lambda_function_crawlerPDF = LambdaCreateFunctionOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_lambda_function_crawlerPDF",
        function_name="clusterPaperIFG_crawlerPDF",
        runtime="python3.14",
        role=aws_account_role,
        timeout=60,
        handler="lambda_function.lambda_handler",
        code={
            "ZipFile": create_zip(f"{airflow_containerFolder}/lambda/crawler/crawlerPDF.py"),
        },
    )

    create_lambda_function_crawlerTableOfContent = LambdaCreateFunctionOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_lambda_function_crawlerTableOfContent",
        function_name="clusterPaperIFG_crawlerTableOfContent",
        runtime="python3.14",
        role=aws_account_role,
        handler="lambda_function.lambda_handler",
        timeout=60,
        code={
            "ZipFile": create_lambda_zip_with_dependencies(f"{airflow_containerFolder}/lambda/crawler/crawlerTableOfContent.py"),
        },
    )

    create_athena_database = AthenaOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_athena_database",
        query=f"CREATE DATABASE IF NOT EXISTS {athena_database_name}",
        database=athena_database_name,
        output_location=athena_queryOutput_bucket,
        sleep_time=1
    )

    create_athena_table_metadata = AthenaOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_athena_table_metadata",
        query=get_file_content(f"{airflow_containerFolder}/athena/unstructured_create_metadata.sql"),
        database=athena_database_name,
        output_location=athena_queryOutput_bucket
    )

    create_athena_table_tableOfContent = AthenaOperator(
        aws_conn_id=aws_conn_id,
        task_id="create_athena_table_tableOfContent",
        query=get_file_content(f"{airflow_containerFolder}/athena/unstructured_create_tableOfContent.sql"),
        database=athena_database_name,
        output_location=athena_queryOutput_bucket
    )

    #chain
    [
        create_bucket_athenaLog,
        create_bucket_clusterPaperIFG,
        create_lambda_function_crawlerTableOfContent,
        create_lambda_function_crawlerLinks,
        create_lambda_function_crawlerPapers,
        create_lambda_function_crawlerPDF,
    ] >> create_athena_database >> [
        create_athena_table_metadata,
        create_athena_table_tableOfContent,
    ]

aws_envsetup()
