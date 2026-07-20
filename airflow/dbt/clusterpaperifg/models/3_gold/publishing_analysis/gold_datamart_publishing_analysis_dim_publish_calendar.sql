{{ config(materialized='table',tags=['dim']) }}

SELECT 
    gold_master_dim_calendar_date_id        AS gold_datamart_publishing_analysis_dim_publish_calendar_id
    ,gold_master_dim_calendar_date          AS gold_datamart_publishing_analysis_dim_publish_calendar_date
    ,gold_master_dim_calendar_year_month    AS gold_datamart_publishing_analysis_dim_publish_calendar_year_month
    ,gold_master_dim_calendar_year          AS gold_datamart_publishing_analysis_dim_publish_calendar_year
    ,gold_master_dim_calendar_month         AS gold_datamart_publishing_analysis_dim_publish_calendar_month
    ,gold_master_dim_calendar_month_name    AS gold_datamart_publishing_analysis_dim_publish_calendar_month_name    
FROM
    gold.gold_master_dim_calendar
WHERE
    gold_master_dim_calendar_year >= 2015
    and gold_master_dim_calendar_date <= current_date
;