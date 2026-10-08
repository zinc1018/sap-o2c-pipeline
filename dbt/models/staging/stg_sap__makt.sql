with source as (

    select * from {{ source('raw', 'MAKT') }}

),

cleaned as (

    select
        {{ sap_text('MATNR') }} as material_id,
        {{ sap_text('SPRAS') }} as language_key,
        {{ sap_text('MAKTX') }} as material_description,
        _loaded_at,
        _source_file
    from source

),

-- Descriptions have no change date, so the latest load wins.
latest as (

    select
        *,
        row_number() over (
            partition by material_id, language_key
            order by _loaded_at desc, _source_file desc
        ) as row_num
    from cleaned

)

select * exclude (row_num, _loaded_at, _source_file)
from latest
where row_num = 1
