{{ config(materialized='table',tags=['fact']) }}

with map_orientador AS (
    SELECT  DISTINCT
        gold_datamart_publishing_analysis_dim_orientador_id,
        gold_datamart_publishing_analysis_dim_orientador_nome_citacao
    FROM
        {{ ref('gold_datamart_publishing_analysis_dim_orientador') }}
),
join_docente_id AS (
    SELECT
        *

    FROM
        {{ ref('silver_papers') }}
        LEFT JOIN   map_orientador ON gold_datamart_publishing_analysis_dim_orientador_nome_citacao = silver_papers_primeiro_orientador
)


SELECT
    silver_papers_id                              AS gold_datamart_publishing_analysis_fact_id,
    gold_datamart_publishing_analysis_dim_orientador_id,
    cast(date_format(silver_papers_data_publicacao, 'yyyyMMdd') AS int) AS gold_datamart_publishing_analysis_dim_publish_calendar_id,
    silver_papers_tipo                              AS gold_datamart_publishing_analysis_fact_type,
    silver_papers_has_table_of_content              AS gold_datamart_publishing_analysis_fact_has_table_of_content,
    silver_papers_titulo                            AS gold_datamart_publishing_analysis_fact_title,
    silver_papers_uri                               AS gold_datamart_publishing_analysis_fact_uri,
    silver_papers_cnpq                              AS gold_datamart_publishing_analysis_fact_cnpq,
    silver_papers_palavras_chave                     AS gold_datamart_publishing_analysis_fact_papers_palavras_chave,
    silver_papers_titulo                            AS gold_datamart_publishing_analysis_fact_papers_titulo,
    silver_papers_sigla_da_instituicao               AS gold_datamart_publishing_analysis_fact_paper_sigla_da_instituicao,

    1                                              AS gold_datamart_publishing_analysis_fact_qtd_publicacoes,
    if(isnull(gold_datamart_publishing_analysis_dim_orientador_id),0,1) AS gold_datamart_publishing_analysis_fact_qtd_publicacoes_com_orientador_identificado,
    if(silver_papers_has_table_of_content=1,1,0)   AS gold_datamart_publishing_analysis_fact_qtd_publicacoes_com_sumario
FROM
    join_docente_id
