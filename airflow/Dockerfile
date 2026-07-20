FROM apache/airflow:latest-python3.12

ARG AIRFLOW_VERSION=3.3.0

COPY requirements-dbt.txt /tmp/requirements-dbt.txt

RUN pip install \
    --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    -r /tmp/requirements-dbt.txt

RUN pip install \
    --no-cache-dir \
    "apache-airflow-providers-databricks[google]"