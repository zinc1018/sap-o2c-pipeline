-- Sales order items: ordered quantity and value, one row per order item.
-- Customer is the version valid on the order date (point-in-time SCD2 join).

select
    md5(i.sales_order_id || '|' || i.item_no) as sales_order_item_key,
    i.sales_order_id,
    i.item_no,
    h.order_date,
    c.customer_key,
    i.material_id,
    h.order_type,
    i.ordered_qty,
    i.sales_unit,
    i.currency,
    i.net_value as net_value_doc_currency,
    round(i.net_value * fx.rate_to_usd, 2) as net_value_usd,
    i.rejection_reason,
    i.rejection_reason is not null as is_rejected
from {{ ref('stg_sap__vbap') }} as i
join {{ ref('stg_sap__vbak') }} as h
    on h.sales_order_id = i.sales_order_id
left join {{ ref('dim_customer') }} as c
    on c.customer_id = h.customer_id
    and h.order_date between c.valid_from and c.valid_to
left join {{ ref('exchange_rates') }} as fx
    on fx.currency = i.currency
