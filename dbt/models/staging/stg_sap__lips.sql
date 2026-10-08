with source as (

    select * from {{ source('raw', 'LIPS') }}

),

cleaned as (

    select
        {{ sap_text('VBELN') }} as delivery_id,
        {{ sap_text('POSNR') }} as item_no,
        {{ sap_text('VGBEL') }} as sales_order_id,
        {{ sap_text('VGPOS') }} as sales_order_item_no,
        {{ sap_text('MATNR') }} as material_id,
        {{ sap_quantity('LFIMG') }} as shipped_qty,
        {{ sap_text('VRKME') }} as sales_unit,
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
            partition by delivery_id, item_no
            order by coalesce(changed_on, created_on) desc nulls last, _loaded_at desc, _source_file desc
        ) as row_num
    from cleaned

)

select * exclude (row_num, _loaded_at, _source_file)
from latest
where row_num = 1
