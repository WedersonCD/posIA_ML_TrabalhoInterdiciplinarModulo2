from datetime import datetime
import pendulum

from airflow.sdk import dag, task
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.python import get_current_context

@dag(
    schedule=None,
    start_date=datetime(2026,7,5),
    catchup=False,
    tags=["clusterPaperIFG"],
    params={
        "date_start":"2026-06-01",
        "date_end":"2026-06-30",
        "days_per_batch":10,
        "aws_bucket_name": "cluster-paper-ifg"
    }
)
def aws_crawlerUnstructuredData_full():

    @task
    def build_child_dag_confs():
        context = get_current_context()
        params = context["params"]

        start_date = pendulum.parse(params["date_start"])
        end_date = pendulum.parse(params["date_end"])

        if end_date < start_date:
            raise ValueError("date_end must be >= date_start")

        confs = []
        current_date = start_date

        while current_date <= end_date:

            confs.append({
                "conf": {
                    "run_mode": "PUBLISH_DATE",
                    "papers_publish_date": current_date.to_date_string(),
                    "aws_bucket_name": params["aws_bucket_name"],
                }
            })

            current_date = current_date.add(days=1)

        print(f"Created {len(confs)} child DAG runs.")

        return confs
    
    child_confs = build_child_dag_confs()

    TriggerDagRunOperator.partial(
        task_id="trigger_crawlerUnstructuredData",
        trigger_dag_id="crawlerUnstructuredData",
        wait_for_completion=True,
        poke_interval=10,
        max_active_tis_per_dag=10,
    ).expand_kwargs(child_confs)
    
aws_crawlerUnstructuredData_full()