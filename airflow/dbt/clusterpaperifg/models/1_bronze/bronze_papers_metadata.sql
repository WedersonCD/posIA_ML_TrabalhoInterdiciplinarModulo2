{{ config(materialized='view') }}

{{ dbt_utils.union_relations(
    relations=[
        source('bronze','papers_metadata_2015_2016'),
        source('bronze','papers_metadata_2017_2018'),
        source('bronze','papers_metadata_2019_2020'),
        source('bronze','papers_metadata_2021_2022'),
        source('bronze','papers_metadata_2023_2024'),
        source('bronze','papers_metadata_2025_2026')
    ],
    source_column_name="__table_source"
) }}