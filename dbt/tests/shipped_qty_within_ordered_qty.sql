-- Shipped quantity should not exceed the ordered quantity for the same item.
-- Known source issue: some orders are reduced after goods have shipped. Warn, don't fail.
{{ config(severity='warn') }}
select
    d.delivery_item_key,
    d.shipped_qty,
    o.ordered_qty
from {{ ref('fct_delivery_items') }} as d
join {{ ref('fct_sales_order_items') }} as o
    on o.sales_order_item_key = d.sales_order_item_key
where d.shipped_qty > o.ordered_qty
