{{ config(materialized='view') }}

select * from {{source('bronze', 'papers_tableofcontent_2015_2016')}}
UNION
select * from {{source('bronze', 'papers_tableofcontent_2017_2018')}}
UNION
select * from {{source('bronze', 'papers_tableofcontent_2021_2022')}}
UNION
select * from {{source('bronze', 'papers_tableofcontent_2023_2024')}}
UNION
select * from {{source('bronze', 'papers_tableofcontent_2025_2026')}}
