with source as (

    select * from {{ source('raw', 'KNA1') }}

),

cleaned as (

    select
        {{ sap_text('KUNNR') }} as customer_id,
        {{ sap_text('NAME1') }} as customer_name,
        {{ sap_text('ORT01') }} as city,
        {{ sap_text('REGIO') }} as region,
        {{ sap_text('LAND1') }} as country_code,
        {{ sap_date('ERDAT') }} as created_on,
        _loaded_at,
        _source_file
    from source

),

-- Customer master has no change date, so the latest load wins.
latest as (

    select
        *,
        row_number() over (
            partition by customer_id
            order by _loaded_at desc, _source_file desc
        ) as row_num
    from cleaned

)

select * exclude (row_num, _loaded_at, _source_file)
from latest
where row_num = 1
