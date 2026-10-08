with source as (

    select * from {{ source('raw', 'LIKP') }}

),

cleaned as (

    select
        {{ sap_text('VBELN') }} as delivery_id,
        {{ sap_text('LFART') }} as delivery_type,
        {{ sap_text('KUNNR') }} as ship_to_customer_id,
        {{ sap_date('LFDAT') }} as delivery_date,
        {{ sap_date('ERDAT') }} as created_on,
        {{ sap_date('AEDAT') }} as changed_on,
        _loaded_at,
        _source_file
    from source

),

latest as (

    select
        *,
        row_number() over (
            partition by delivery_id
            order by coalesce(changed_on, created_on) desc nulls last, _loaded_at desc, _source_file desc
        ) as row_num
    from cleaned

)

select * exclude (row_num, _loaded_at, _source_file)
from latest
where row_num = 1
