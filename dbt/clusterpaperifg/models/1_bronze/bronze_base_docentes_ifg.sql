{{ config(materialized='view') }}

select * from {{source('bronze', 'base_docentes_ifg')}}