{{ config(materialized='table',tags=['dim']) }}



SELECT  DISTINCT
    gold_master_dim_docentes_id AS gold_datamart_publishing_analysis_dim_orientador_id,
    gold_master_dim_docentes_siape  AS gold_datamart_publishing_analysis_dim_orientador_siape,
    gold_master_dim_docentes_nome   AS gold_datamart_publishing_analysis_dim_orientador_nome,
    gold_master_dim_docentes_campus AS gold_datamart_publishing_analysis_dim_orientador_campus,
    gold_master_dim_docentes_disciplina AS gold_datamart_publishing_analysis_dim_orientador_disciplina,
    gold_master_dim_docentes_disciplina_primary AS gold_datamart_publishing_analysis_dim_orientador_disciplina_primary,
    gold_master_dim_docentes_disciplina_secondary   AS gold_datamart_publishing_analysis_dim_orientador_disciplina_secondary,
    gold_master_dim_docentes_nome_citacao   AS gold_datamart_publishing_analysis_dim_orientador_nome_citacao
FROM
    {{ ref('gold_master_dim_docente') }}