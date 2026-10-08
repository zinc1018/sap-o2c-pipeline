with source as (

    select * from {{ source('raw', 'VBAK') }}

),

cleaned as (

    select
        {{ sap_text('VBELN') }} as sales_order_id,
        {{ sap_text('AUART') }} as order_type,
        {{ sap_text('KUNNR') }} as customer_id,
        {{ sap_date('AUDAT') }} as order_date,
        {{ sap_text('WAERK') }} as currency,
        {{ sap_amount('NETWR') }} as net_value,
        {{ sap_date('ERDAT') }} as created_on,
        {{ sap_date('AEDAT') }} as changed_on,
        _loaded_at,
        _source_file
    from source

),

-- Keep the newest version of each order: latest change date, then latest load.
latest as (

    select
        *,
        row_number() over (
            partition by sales_order_id
            order by coalesce(changed_on, created_on) desc nulls last, _loaded_at desc, _source_file desc
        ) as row_num
    from cleaned

)

select * exclude (row_num, _loaded_at, _source_file)
from latest
where row_num = 1
