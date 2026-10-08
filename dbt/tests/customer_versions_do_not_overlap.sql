-- Each customer's SCD2 versions must not overlap in time.
-- Returns customers whose version periods overlap; the test passes when it returns no rows.
select
    a.customer_id,
    a.customer_key,
    b.customer_key as overlapping_customer_key
from {{ ref('dim_customer') }} as a
join {{ ref('dim_customer') }} as b
    on a.customer_id = b.customer_id
    and a.customer_key < b.customer_key
where a.valid_from <= b.valid_to
  and b.valid_from <= a.valid_to
