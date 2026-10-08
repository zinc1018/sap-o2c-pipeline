-- Each receivable's amount should equal the net value of its invoice.
-- Returns the receivables that don't; the test passes when it returns no rows.
select
    r.receivable_key,
    r.amount_doc_currency,
    b.net_value
from {{ ref('fct_receivable_items') }} as r
join {{ ref('stg_sap__vbrk') }} as b
    on b.billing_id = r.billing_id
where r.amount_doc_currency <> b.net_value
