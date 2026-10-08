-- One row per calendar day, covering every order and billing date in staging.

with bounds as (

    select
        least(
            (select min(order_date) from {{ ref('stg_sap__vbak') }}),
            (select min(billing_date) from {{ ref('stg_sap__vbrk') }})
        ) as first_day,
        greatest(
            (select max(order_date) from {{ ref('stg_sap__vbak') }}),
            (select max(billing_date) from {{ ref('stg_sap__vbrk') }})
        ) as last_day

),

days as (

    select cast(unnest(generate_series(first_day, last_day, interval 1 day)) as date) as date_day
    from bounds

)

select
    date_day,
    year(date_day) as year,
    quarter(date_day) as quarter,
    month(date_day) as month_number,
    monthname(date_day) as month_name,
    dayname(date_day) as day_name,
    isodow(date_day) in (6, 7) as is_weekend
from days
