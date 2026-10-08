-- Billed quantity must never exceed the ordered quantity for the same order item.
-- Returns the offending billing items; the test passes when it returns no rows.
select
    b.billing_item_key,
    b.billed_qty,
    o.ordered_qty
from {{ ref('fct_billing_items') }} as b
join {{ ref('fct_sales_order_items') }} as o
    on o.sales_order_id = b.sales_order_id
    and o.item_no = b.sales_order_item_no
where b.billed_qty > o.ordered_qty
