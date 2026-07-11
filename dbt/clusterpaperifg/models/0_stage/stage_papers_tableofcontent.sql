{% set papers_year = var('stage_papers_year', '2019_2020') %}
{% set papers_table = 'papers_tableofcontent_' ~ papers_year %}

{{ config(materialized='table') }}

DROP TABLE IF EXISTS {{ papers_table }};

CREATE TABLE {{ papers_table }}
USING DELTA
TBLPROPERTIES (
  'delta.columnMapping.mode' = 'name'
);

COPY INTO {{ papers_table }}
FROM 's3://cluster-paper-ifg/TableOfContent/'
WITH (
  CREDENTIAL (
    AWS_ACCESS_KEY = '*',
    AWS_SECRET_KEY = '*',
    AWS_SESSION_TOKEN = '*'
  )
)
FILEFORMAT = JSON
FORMAT_OPTIONS (
  'multiLine' = 'false',
  'mergeSchema' = 'true'
)
COPY_OPTIONS (
  'mergeSchema' = 'true'
);