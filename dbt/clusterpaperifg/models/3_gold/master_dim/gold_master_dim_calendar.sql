{{ config(materialized='table') }}

with date_spine as (

    select
        explode(
            sequence(
                date('2000-01-01'),
                date('2035-12-31'),
                interval 1 day
            )
        ) as calendar_date

),

calendar_attributes as (

    select
        calendar_date,

        cast(date_format(calendar_date, 'yyyyMMdd') as int) as calendar_date_id,

        year(calendar_date) as calendar_year,
        quarter(calendar_date) as calendar_quarter,
        month(calendar_date) as calendar_month,
        date_format(calendar_date, 'MMMM') as calendar_month_name,
        date_format(calendar_date, 'MMM') as calendar_month_short_name,

        weekofyear(calendar_date) as calendar_week_of_year,
        dayofmonth(calendar_date) as calendar_day_of_month,
        dayofyear(calendar_date) as calendar_day_of_year,

        date_format(calendar_date, 'E') as calendar_day_short_name,
        date_format(calendar_date, 'EEEE') as calendar_day_name,

        case
            when dayofweek(calendar_date) in (1, 7) then 1
            else 0
        end as calendar_is_weekend,

        date_trunc('MONTH', calendar_date) as calendar_month_start_date,
        last_day(calendar_date) as calendar_month_end_date,

        date_trunc('YEAR', calendar_date) as calendar_year_start_date,
        add_months(date_trunc('YEAR', calendar_date), 12) - interval 1 day as calendar_year_end_date,

        concat(year(calendar_date), '-', lpad(month(calendar_date), 2, '0')) as calendar_year_month,
        concat(year(calendar_date), '-Q', quarter(calendar_date)) as calendar_year_quarter

    from date_spine

)

select
    calendar_date_id                    as gold_master_dim_calendar_date_id,
    calendar_date                       as gold_master_dim_calendar_date,

    calendar_year                       as gold_master_dim_calendar_year,
    calendar_quarter                    as gold_master_dim_calendar_quarter,
    calendar_month                      as gold_master_dim_calendar_month,
    calendar_month_name                 as gold_master_dim_calendar_month_name,
    calendar_month_short_name           as gold_master_dim_calendar_month_short_name,

    calendar_week_of_year               as gold_master_dim_calendar_week_of_year,
    calendar_day_of_month               as gold_master_dim_calendar_day_of_month,
    calendar_day_of_year                as gold_master_dim_calendar_day_of_year,

    calendar_day_short_name             as gold_master_dim_calendar_day_short_name,
    calendar_day_name                   as gold_master_dim_calendar_day_name,

    calendar_is_weekend                 as gold_master_dim_calendar_is_weekend,

    calendar_month_start_date           as gold_master_dim_calendar_month_start_date,
    calendar_month_end_date             as gold_master_dim_calendar_month_end_date,

    calendar_year_start_date            as gold_master_dim_calendar_year_start_date,
    calendar_year_end_date              as gold_master_dim_calendar_year_end_date,

    calendar_year_month                 as gold_master_dim_calendar_year_month,
    calendar_year_quarter               as gold_master_dim_calendar_year_quarter
from 
    calendar_attributes    