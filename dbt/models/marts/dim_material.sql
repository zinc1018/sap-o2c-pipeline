-- One row per material, with its English description.

select
    m.material_id,
    d.material_description,
    m.material_type,
    m.material_group,
    m.base_unit,
    m.created_on,
    m.changed_on
from {{ ref('stg_sap__mara') }} as m
left join {{ ref('stg_sap__makt') }} as d
    on d.material_id = m.material_id
    and d.language_key = 'E'
