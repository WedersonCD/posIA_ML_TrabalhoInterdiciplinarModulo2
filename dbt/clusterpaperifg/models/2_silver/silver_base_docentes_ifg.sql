{{ config(materialized='table')}}

with source as (
    select * from {{ ref('bronze_base_docentes_ifg')}}
),
src_fix_nome_da_disciplina as (
    SELECT 
        *,
        IF(EndsWith({{ general_text_cleaning('nome_da_disciplina') }},' I'),LEFT({{ general_text_cleaning('nome_da_disciplina') }},LEN({{ general_text_cleaning('nome_da_disciplina') }})-2),
        IF(EndsWith({{ general_text_cleaning('nome_da_disciplina') }},' II'),LEFT({{ general_text_cleaning('nome_da_disciplina') }},LEN({{ general_text_cleaning('nome_da_disciplina') }})-3),
        IF(EndsWith({{ general_text_cleaning('nome_da_disciplina') }},' III'),LEFT({{ general_text_cleaning('nome_da_disciplina') }},LEN({{ general_text_cleaning('nome_da_disciplina') }})-4),
        IF(EndsWith({{ general_text_cleaning('nome_da_disciplina') }},' IV'),LEFT({{ general_text_cleaning('nome_da_disciplina') }},LEN({{ general_text_cleaning('nome_da_disciplina') }})-3),
        {{ general_text_cleaning('nome_da_disciplina') }}))))
              as disciplina
    FROM
        source
)

SELECT * FROM src_fix_nome_da_disciplina;

