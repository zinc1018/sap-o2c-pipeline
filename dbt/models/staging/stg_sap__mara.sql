with source as (

    select * from {{ source('raw', 'MARA') }}

),

cleaned as (

    select
        {{ sap_text('MATNR') }} as material_id,
        {{ sap_text('MTART') }} as material_type,
        {{ sap_text('MATKL') }} as material_group,
        {{ sap_text('MEINS') }} as base_unit,
        {{ sap_date('ERSDA') }} as created_on,
        {{ sap_date('LAEDA') }} as changed_on,
        _loaded_at,
        _source_file
    from source

),

latest as (

    select
        *,
        row_number() over (
            partition by material_id
            order by coalesce(changed_on, created_on) desc nulls last, _loaded_at desc, _source_file desc
        ) as row_num
    from cleaned

)

select * exclude (row_num, _loaded_at, _source_file)
from latest
where row_num = 1
