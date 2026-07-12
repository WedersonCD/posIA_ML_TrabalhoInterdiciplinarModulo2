WITH month_map AS (
  SELECT *
  FROM VALUES
    ('Jan', '01'),
    ('Fev', '02'),
    ('Mar', '03'),
    ('Abr', '04'),
    ('Mai', '05'),
    ('Jun', '06'),
    ('Jul', '07'),
    ('Ago', '08'),
    ('Set', '09'),
    ('Out', '10'),
    ('Nov', '11'),
    ('Dez', '12')
  AS month_map(month_pt, month_num)
),

parsed AS (
  SELECT
    *,
    CASE
      WHEN b.`Data do documento` RLIKE '^[0-9]{1,2}-[A-Za-z]{3}-[0-9]{4}$'
        THEN regexp_extract(b.`Data do documento`, '^([0-9]{1,2})-', 1)

      WHEN b.`Data do documento` RLIKE '^[A-Za-z]{3}-[0-9]{4}$'
        THEN '1'
    END AS parsed_day_part,

    CASE
      WHEN b.`Data do documento` RLIKE '^[0-9]{1,2}-[A-Za-z]{3}-[0-9]{4}$'
        THEN regexp_extract(b.`Data do documento`, '^[0-9]{1,2}-([A-Za-z]{3})-[0-9]{4}$', 1)

      WHEN b.`Data do documento` RLIKE '^[A-Za-z]{3}-[0-9]{4}$'
        THEN regexp_extract(b.`Data do documento`, '^([A-Za-z]{3})-[0-9]{4}$', 1)
    END AS parsed_month_pt,

    regexp_extract(b.`Data do documento`, '([0-9]{4})$', 1) AS parsed_year_part

  FROM 
    {{ ref('bronze_papers_metadata')}} as b
),
final_date as (
    SELECT
        *,
        to_date(concat(
            parsed_year_part,
            '-',
            m.month_num,
            '-',
            lpad(parsed_day_part, 2, '0')
        ),'yyyy-MM-dd') AS data_do_documento
    FROM
        parsed p
        LEFT JOIN month_map m ON p.parsed_month_pt = m.month_pt

),

table_of_content as (
    SELECT
        paper_id,
        tableOfContent
    FROM
        {{ ref('bronze_papers_tableofcontent')}}
),
joinTableOfContent as (
    select 
        *
    FROM
        final_date
        LEFT JOIN table_of_content on final_date._id = table_of_content.paper_id
),
renaming_odd_chart_columns as (
    SELECT 
        *,
        `Aparece nas coleções`     AS aparece_nas_colecoes,
        `Título(s) alternativo(s)` AS titulos_alternativos,
        `Título` as titulo,
        `Autor(es)`   as autores,
        `Citação`       as citacoes,
        `País` as pais,
        `Palavras-chave`    as palavra_chave,
        `Primeiro Orientador`   as primeiro_orientador,
        `Segundo Orientador`    as segundo_orientador,
        `Sigla da Instituição`  as sigla_da_instituicao,
        `Tipo de Acesso`    as tipo_de_acesso,
        `Identificador DOI` as identificador_doi,
        `metadata.dc.contributor.advisor-co1` as    metadata_dc_contributor_advisor_co1,
        `metadata.dc.contributor.advisor-co2` as    metadata_dc_contributor_advisor_co2,
        `metadata.dc.contributor.referee1` as       metadata_dc_contributor_referee1,
        `metadata.dc.contributor.referee2` as       metadata_dc_contributor_referee2,
        `metadata.dc.contributor.referee3` as       metadata_dc_contributor_referee3,
        `metadata.dc.contributor.referee4` as       metadata_dc_contributor_referee4,
        `metadata.dc.publisher.department` as       metadata_dc_publisher_department,
        `metadata.dc.publisher.program` as          metadata_dc_publisher_program,
        `metadata.dc.contributor.referee5` as       metadata_dc_contributor_referee5
        
    FROM
         joinTableOfContent
)


SELECT
  _id                                   AS silver_paper_id,
    data_do_documento                   AS silver_paper_data_do_documento,
    if(isnull(tableOfContent),0,1)      AS silver_paper_has_tableOfContent,
  {{ general_text_cleaning('tableOfContent')}}                      AS silver_paper_table_of_content,
  {{ general_text_cleaning('Abstract') }}                           AS silver_paper_abstract,
  {{ general_text_cleaning('aparece_nas_colecoes') }}               AS silver_paper_aparece_nas_colecoes,
  {{ general_text_cleaning('autores') }}                          AS silver_paper_autores,
  {{ general_text_cleaning('CNPq') }}                               AS silver_paper_cnpq,
  {{ general_text_cleaning('citacoes') }}                            AS silver_paper_citacao,
  {{ general_text_cleaning('Editor')}}                              AS silver_paper_editor,
  {{ general_text_cleaning('Idioma')}}                              AS silver_paper_idioma,
  {{ general_text_cleaning('palavra_chave')}}                      AS silver_paper_palavras_chave,
  {{ general_text_cleaning('pais')}}                                AS silver_paper_pais,
  {{ general_text_cleaning('primeiro_orientador')}}                 AS silver_paper_primeiro_orientador,
  {{ general_text_cleaning('Resumo')}}                              AS silver_paper_resumo,
  {{ general_text_cleaning('segundo_orientador')}}                  AS silver_paper_segundo_orientador,
  {{ general_text_cleaning('sigla_da_instituicao')}}                AS silver_paper_sigla_da_instituicao,
  {{ general_text_cleaning('Tipo')}}                                AS silver_paper_tipo,
  {{ general_text_cleaning('tipo_de_acesso')}}                      AS silver_paper_tipo_de_acesso,
  {{ general_text_cleaning('titulo')}}                              AS silver_paper_titulo,
  {{ general_text_cleaning('titulos_alternativos') }}         AS silver_paper_titulos_alternativos,
  {{ general_text_cleaning('URI')}}                                 AS silver_paper_uri,
  {{ general_text_cleaning('_pdf_url')}}                            AS silver_paper_pdf_url,
  {{ general_text_cleaning('_source_url')}}                         AS silver_paper_source_url,
  {{ general_text_cleaning('identificador_doi')}}                   AS silver_paper_identificador_doi,
  {{ general_text_cleaning('metadata_dc_contributor_advisor_co1') }} AS silver_paper_metadata_dc_contributor_advisor_co1,
  {{ general_text_cleaning('metadata_dc_contributor_advisor_co2') }} AS silver_paper_metadata_dc_contributor_advisor_co2,
  {{ general_text_cleaning('metadata_dc_contributor_referee1' ) }} AS silver_paper_metadata_dc_contributor_referee1,
  {{ general_text_cleaning('metadata_dc_contributor_referee2' ) }} AS silver_paper_metadata_dc_contributor_referee2,
  {{ general_text_cleaning('metadata_dc_contributor_referee3' ) }} AS silver_paper_metadata_dc_contributor_referee3,
  {{ general_text_cleaning('metadata_dc_contributor_referee4' ) }} AS silver_paper_metadata_dc_contributor_referee4,
  {{ general_text_cleaning('metadata_dc_publisher_department' ) }} AS silver_paper_metadata_dc_publisher_department,
  {{ general_text_cleaning('metadata_dc_publisher_program' ) }} AS silver_paper_metadata_dc_publisher_program,
  {{ general_text_cleaning('metadata_dc_contributor_referee5' ) }} AS silver_paper_metadata_dc_contributor_referee5
FROM 
    renaming_odd_chart_columns