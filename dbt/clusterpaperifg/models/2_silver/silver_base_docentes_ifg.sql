{{ config(materialized='table')}}

with source AS (
    select * from {{ ref('bronze_base_docentes_ifg')}}
),
src_fix_nome_da_disciplina AS (
    SELECT 
        siape                               AS id,
        siape,
        {{ general_text_cleaning('nome') }}     AS nome,
        {{ general_text_cleaning('campus') }}   AS campus,
        IF(EndsWith({{ general_text_cleaning('nome_da_disciplina') }},' I'),LEFT({{ general_text_cleaning('nome_da_disciplina') }},LEN({{ general_text_cleaning('nome_da_disciplina') }})-2),
        IF(EndsWith({{ general_text_cleaning('nome_da_disciplina') }},' II'),LEFT({{ general_text_cleaning('nome_da_disciplina') }},LEN({{ general_text_cleaning('nome_da_disciplina') }})-3),
        IF(EndsWith({{ general_text_cleaning('nome_da_disciplina') }},' III'),LEFT({{ general_text_cleaning('nome_da_disciplina') }},LEN({{ general_text_cleaning('nome_da_disciplina') }})-4),
        IF(EndsWith({{ general_text_cleaning('nome_da_disciplina') }},' IV'),LEFT({{ general_text_cleaning('nome_da_disciplina') }},LEN({{ general_text_cleaning('nome_da_disciplina') }})-3),
        {{ general_text_cleaning('nome_da_disciplina') }}))))
              AS disciplina
    FROM
        source
),
split_disciplina AS (
    SELECT 
        *,
        btrim(split_part(replace(replace(replace(disciplina,' E ','/'),':','/'),',','/'),'/',1))    AS disciplina_primary,
        btrim(split_part(replace(replace(replace(disciplina,' E ','/'),':','/'),',','/'),'/',2))    AS disciplina_secondary
    FROM
        src_fix_nome_da_disciplina
)

SELECT 
    id                      AS silver_base_docentes_ifg_id
    ,siape                  AS silver_base_docentes_ifg_siape
    ,nome                   AS silver_base_docentes_ifg_nome
    ,campus                 AS silver_base_docentes_ifg_campus
    ,disciplina             AS silver_base_docentes_ifg_disciplina
    ,disciplina_primary     AS silver_base_docentes_ifg_disciplina_primary
    ,disciplina_secondary   AS silver_base_docentes_ifg_disciplina_secondary
FROM
     split_disciplina;

