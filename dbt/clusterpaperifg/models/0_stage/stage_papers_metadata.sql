{% set papers_year = var('stage_papers_year', '2019_2020') %}
{% set papers_table = 'papers_metadata_' ~ papers_year %}

{{ config(materialized='table') }}

DROP TABLE IF EXISTS clusterpaperifg.bronze.{{ papers_table }};

CREATE TABLE clusterpaperifg.bronze.{{ papers_table }}
USING DELTA
TBLPROPERTIES (
  'delta.columnMapping.mode' = 'name'
);

COPY INTO clusterpaperifg.bronze.{{ papers_table }}
FROM 's3://cluster-paper-ifg/Metadata/'
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