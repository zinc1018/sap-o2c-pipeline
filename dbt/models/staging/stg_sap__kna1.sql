with source as (
    select * from {{ source('sap', 'KNA1') }}
),

renamed as (
    select
        KUNNR as customer_id,
        NAME1 as customer_name,
        ORT01 as city,
        REGIO as region,
        LAND1 as country_code,
        strptime(ERDAT, '%Y%m%d')::date as created_on,
        -- KNA1 has no change date, so the extract date in the file name orders versions
        strptime(regexp_extract(_source_file, '(\d{8})', 1), '%Y%m%d')::date as extracted_on,
        _loaded_at
    from source
),

latest as (
    select *
    from renamed
    qualify row_number() over (
        partition by customer_id
        order by extracted_on desc, _loaded_at desc
    ) = 1
)

select * from latest
