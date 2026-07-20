
import json

import pendulum

from airflow.sdk import dag, task
from airflow.providers.standard.operators.bash import BashOperator
from airflow.providers.databricks.operators.databricks import DatabricksRunNowOperator



DBT_PROJECT_DIR = "/opt/dbt/clusterpaperifg"
DBT_PROFILES_DIR = "/opt/dbt_profiles"

DBT_COMMON_ARGUMENTS = (
    f"--project-dir {DBT_PROJECT_DIR} "
    f"--profiles-dir {DBT_PROFILES_DIR} "
    "--target dev"
)

DBT_ENV = {
    "DBT_DATABRICKS_HOST": (
        "{{ conn.get('DATABRICKS_DBT').host }}"
    ),
    "DBT_DATABRICKS_HTTP_PATH": (
        "{{ conn.get('DATABRICKS_DBT').extra_dejson.http_path }}"
    ),
    "DBT_ENV_SECRET_DATABRICKS_TOKEN": (
        "{{ conn.get('DATABRICKS_DBT').extra_dejson.token }}"
    ),
    "DBT_DATABRICKS_DATABASE": (
        "{{ conn.get('DATABRICKS_DBT').extra_dejson.catalog }}"
    ),
    "DBT_DATABRICKS_THREADS": (
        "{{ conn.get('DATABRICKS_DBT').extra_dejson.threads }}"
    ),
    "DBT_DATABRICKS_SCHEMA": (
        "{{ conn.get('DATABRICKS_DBT').schema }}"
    ),
        "DBT_DATABRICKS_AUTH_TYPE": (
        "{{ conn.get('DATABRICKS_DBT').extra_dejson.auth_type }}"
    ),
}



@dag(
    schedule=None,
    start_date=pendulum.datetime(2026, 7, 16, tz="UTC"),
    catchup=False,
    tags=["clusterPaperIFG","dbt"],
)
def dbt_databricks_pipeline():
    #"""

    dbt_deps = BashOperator (
        task_id="dbt_deps",
        bash_command=f"dbt deps {DBT_COMMON_ARGUMENTS}",
        env=DBT_ENV,
        append_env=True
    )

    dbt_compile = BashOperator (
        task_id="dbt_compile",
        bash_command=f"dbt compile {DBT_COMMON_ARGUMENTS}",
        env=DBT_ENV,
        append_env=True
    )

    dbt_build_silver = BashOperator (
        task_id="dbt_build_silver",
        bash_command=f"dbt build --select tag:silver {DBT_COMMON_ARGUMENTS}",
        env=DBT_ENV,
        append_env=True
    )

    dbt_build_gold = BashOperator (
        task_id="dbt_build_gold",
        bash_command=f"dbt build --select tag:gold {DBT_COMMON_ARGUMENTS}",
        env=DBT_ENV,
        append_env=True
    )
    #"""
    databricks_moveToS3 = DatabricksRunNowOperator (
        task_id="export_publishingAnalysis_s3",
        databricks_conn_id='DATABRICKS_DBT',
        job_id='788836989915187',
        wait_for_termination=True,
    )



    dbt_deps >> dbt_compile >> dbt_build_silver >> dbt_build_gold >> databricks_moveToS3
    

dbt_databricks_pipeline()