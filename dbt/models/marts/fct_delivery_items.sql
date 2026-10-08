-- Delivery items: quantity shipped against each sales order item.
-- Customer is the ship-to version valid on the delivery date (point-in-time SCD2 join).

select
    md5(d.delivery_id || '|' || d.item_no) as delivery_item_key,
    d.delivery_id,
    d.item_no,
    h.delivery_date,
    c.customer_key,
    o.sales_order_item_key,
    d.sales_order_id,
    d.sales_order_item_no,
    d.material_id,
    d.shipped_qty,
    d.sales_unit,
    o.order_date,
    {{ days_between('h.delivery_date', 'o.order_date') }} as days_order_to_delivery
from {{ ref('stg_sap__lips') }} as d
join {{ ref('stg_sap__likp') }} as h
    on h.delivery_id = d.delivery_id
left join {{ ref('fct_sales_order_items') }} as o
    on o.sales_order_id = d.sales_order_id
    and o.item_no = d.sales_order_item_no
left join {{ ref('dim_customer') }} as c
    on c.customer_id = h.ship_to_customer_id
    and h.delivery_date between c.valid_from and c.valid_to
