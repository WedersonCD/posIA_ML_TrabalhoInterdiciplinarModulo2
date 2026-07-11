{{ config(materialized='table')}}

with source AS (
    select * from {{ ref('bronze_base_docentes_ifg')}}
),
src_fix_nome_da_disciplina AS (
    SELECT 
        general_text_cleaning('nome') }     AS nome,
        general_text_cleaning('campus') }   AS campus,
        siape                               AS id,
        siape,
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
        split_part(replace(replace(disciplina,' E ','/'),':','/'),'/',1)    AS disciplina_primary,
        split_part(replace(replace(disciplina,' E ','/'),':','/'),'/',2)    AS disciplina_secondary
    FROM
        src_fix_nome_da_disciplina
)

SELECT * FROM src_fix_nome_da_disciplina;

