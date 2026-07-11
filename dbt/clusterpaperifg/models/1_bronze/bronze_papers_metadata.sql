{{ config(materialized='view') }}

select *, NULL AS `Identificador DOI`,NULL AS `metadata.dc.contributor.referee5` from {{source('bronze', 'papers_metadata_2015_2016')}}
UNION
select * from {{source('bronze', 'papers_metadata_2017_2018')}}
UNION
select *, NULL AS `Segundo Orientador` from {{source('bronze', 'papers_metadata_2019_2020')}}
UNION
select *, NULL AS `Segundo Orientador` from {{source('bronze', 'papers_metadata_2021_2022')}}
UNION
select *, NULL AS `Segundo Orientador` from {{source('bronze', 'papers_metadata_2023_2024')}}
UNION
select *, NULL AS `Segundo Orientador` from {{source('bronze', 'papers_metadata_2025_2026')}}
