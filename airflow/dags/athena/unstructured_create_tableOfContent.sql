CREATE EXTERNAL TABLE IF NOT EXISTS unstructured.table_of_content (
  paper_id string,
  table_of_content string
)
ROW FORMAT SERDE 'org.openx.data.jsonserde.JsonSerDe'
WITH SERDEPROPERTIES (
  'case.insensitive' = 'false',
  'mapping.paper_id' = 'paper_id',
  'mapping.table_of_content' = 'tableOfContent'
)
STORED AS TEXTFILE
LOCATION 's3://cluster-paper-ifg/TableOfContent/'
TBLPROPERTIES (
  'classification' = 'json'
);