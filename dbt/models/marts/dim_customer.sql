-- Customer dimension with full history (SCD type 2).
--
-- Built from every version in raw, not from staging, because staging keeps only
-- the latest version. A version starts on the date of the extract file it first
-- appears in, and ends the day before the next changed version starts.

with versions as (

    select
        {{ sap_text('KUNNR') }} as customer_id,
        {{ sap_text('NAME1') }} as customer_name,
        {{ sap_text('ORT01') }} as city,
        {{ sap_text('REGIO') }} as region,
        {{ sap_text('LAND1') }} as country_code,
        {{ date_from_file_name('_source_file') }} as valid_from,
        _loaded_at,
        coalesce({{ sap_text('NAME1') }}, '') || '|' || coalesce({{ sap_text('ORT01') }}, '')
            || '|' || coalesce({{ sap_text('REGIO') }}, '')
            || '|' || coalesce({{ sap_text('LAND1') }}, '') as attributes
    from {{ source('raw', 'KNA1') }}

),

-- A customer can appear in several files on the same day; keep one row per day.
one_per_day as (

    select
        *,
        row_number() over (
            partition by customer_id, valid_from
            order by _loaded_at desc
        ) as row_num
    from versions

),

-- Keep only the days a customer's attributes actually changed.
changes as (

    select
        customer_id,
        customer_name,
        city,
        region,
        country_code,
        valid_from,
        attributes,
        lag(attributes) over (partition by customer_id order by valid_from) as previous_attributes
    from one_per_day
    where row_num = 1

),

versions_with_changes as (

    select * from changes
    where previous_attributes is null or previous_attributes <> attributes

)

select
    md5(customer_id || '|' || cast(valid_from as varchar)) as customer_key,
    customer_id,
    customer_name,
    city,
    region,
    country_code,
    valid_from,
    coalesce(
        {{ add_days('lead(valid_from) over (partition by customer_id order by valid_from)', -1) }},
        date '9999-12-31'
    ) as valid_to,
    lead(valid_from) over (partition by customer_id order by valid_from) is null as is_current
from versions_with_changes
