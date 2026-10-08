with source as (

    select * from {{ source('raw', 'VBRK') }}

),

cleaned as (

    select
        {{ sap_text('VBELN') }} as billing_id,
        {{ sap_text('FKART') }} as billing_type,
        {{ sap_date('FKDAT') }} as billing_date,
        {{ sap_text('KUNRG') }} as payer_id,
        {{ sap_text('WAERK') }} as currency,
        {{ sap_amount('NETWR') }} as net_value,
        -- Cancelled invoices are flagged, not removed (see design: fct_billing_items).
        coalesce(trim(FKSTO) = 'X', false) as is_cancelled,
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
            partition by billing_id
            order by coalesce(changed_on, created_on) desc nulls last, _loaded_at desc, _source_file desc
        ) as row_num
    from cleaned

)

select * exclude (row_num, _loaded_at, _source_file)
from latest
where row_num = 1
