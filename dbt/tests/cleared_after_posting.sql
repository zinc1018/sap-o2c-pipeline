-- A receivable can't clear before it was posted.
-- Returns the receivables that do; the test passes when it returns no rows.
select
    receivable_key,
    posting_date,
    cleared_on
from {{ ref('fct_receivable_items') }}
where cleared_on < posting_date
