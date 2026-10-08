with source as (

    select * from {{ source('raw', 'BSID') }}

),

cleaned as (

    select
        {{ sap_text('BUKRS') }} as company_code,
        {{ sap_text('BELNR') }} as accounting_doc_id,
        {{ sap_text('GJAHR') }} as fiscal_year,
        {{ sap_text('BUZEI') }} as doc_item,
        {{ sap_text('KUNNR') }} as customer_id,
        {{ sap_text('BLART') }} as doc_type,
        {{ sap_date('BUDAT') }} as posting_date,
        {{ sap_date('FAEDT') }} as due_date,
        {{ sap_text('ZTERM') }} as payment_terms,
        {{ sap_amount('WRBTR') }} as amount,
        {{ sap_text('WAERS') }} as currency,
        {{ sap_text('ZUONR') }} as billing_id,
        _loaded_at,
        _source_file
    from source

),

-- Open items are not changed in place, so the latest load wins.
latest as (

    select
        *,
        row_number() over (
            partition by company_code, accounting_doc_id, fiscal_year, doc_item
            order by _loaded_at desc, _source_file desc
        ) as row_num
    from cleaned

)

select * exclude (row_num, _loaded_at, _source_file)
from latest
where row_num = 1
