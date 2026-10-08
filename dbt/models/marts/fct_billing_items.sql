-- Billing items, one row per billing item. Cancelled invoices are flagged, not removed.
-- Customer is the version valid on the billing date (point-in-time SCD2 join).

select
    md5(b.billing_id || '|' || b.item_no) as billing_item_key,
    b.billing_id,
    b.item_no,
    h.billing_date,
    c.customer_key,
    b.sales_order_id,
    b.sales_order_item_no,
    b.material_id,
    h.billing_type,
    b.billed_qty,
    b.sales_unit,
    h.currency,
    b.net_value as net_value_doc_currency,
    round(b.net_value * fx.rate_to_usd, 2) as net_value_usd,
    h.is_cancelled,
    -- Source issue: some billing items point at order items that don't exist.
    -- Flagged here so reports can show or exclude them.
    not exists (
        select 1
        from {{ ref('stg_sap__vbap') }} as o
        where o.sales_order_id = b.sales_order_id
          and o.item_no = b.sales_order_item_no
    ) as is_orphan_item
from {{ ref('stg_sap__vbrp') }} as b
join {{ ref('stg_sap__vbrk') }} as h
    on h.billing_id = b.billing_id
left join {{ ref('dim_customer') }} as c
    on c.customer_id = h.payer_id
    and h.billing_date between c.valid_from and c.valid_to
left join {{ ref('exchange_rates') }} as fx
    on fx.currency = h.currency
