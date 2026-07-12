{{ config(materialized='table') }}

SELECT 
    silver_base_docentes_ifg_id                     AS gold_master_dim_docentes_id,
    silver_base_docentes_ifg_siape                  AS gold_master_dim_docentes_siape,
    silver_base_docentes_ifg_nome                   AS gold_master_dim_docentes_nome,
    silver_base_docentes_ifg_campus                 AS gold_master_dim_docentes_campus,
    silver_base_docentes_ifg_disciplina             AS gold_master_dim_docentes_disciplina,
    silver_base_docentes_ifg_disciplina_primary     AS gold_master_dim_docentes_disciplina_primary,
    silver_base_docentes_ifg_disciplina_secondary   AS gold_master_dim_docentes_disciplina_secondary,
    regexp_replace(
        regexp_replace(trim(silver_base_docentes_ifg_nome), '\\s+', ' '),
        '^(.*) (\\S+)$',
        '$2, $1'
    ) AS gold_master_dim_docentes_nome_citacao
FROM
    {{ ref('silver_base_docentes_ifg')}}
;