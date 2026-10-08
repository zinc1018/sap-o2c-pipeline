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

    {{ date_spine('(select first_day from bounds)', '(select last_day from bounds)') }}

)

select
    date_day,
    year(date_day) as year,
    quarter(date_day) as quarter,
    month(date_day) as month_number,
    {{ month_name('date_day') }} as month_name,
    {{ day_name('date_day') }} as day_name,
    {{ is_weekend('date_day') }} as is_weekend
from days
