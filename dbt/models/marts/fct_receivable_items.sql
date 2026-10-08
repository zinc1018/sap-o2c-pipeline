-- Customer receivables: one row per accounting document item, open or cleared.
-- Customer is the version valid on the posting date (point-in-time SCD2 join).

with items as (

    select
        company_code,
        accounting_doc_id,
        fiscal_year,
        doc_item,
        customer_id,
        billing_id,
        posting_date,
        due_date,
        amount,
        currency
    from {{ ref('stg_sap__bsid') }}

),

cleared as (

    select
        company_code,
        accounting_doc_id,
        fiscal_year,
        doc_item,
        cleared_on,
        clearing_doc_id
    from {{ ref('stg_sap__bsad') }}

)

select
    md5(i.company_code || '|' || i.accounting_doc_id || '|' || i.fiscal_year || '|' || i.doc_item)
        as receivable_key,
    i.company_code,
    i.accounting_doc_id,
    i.fiscal_year,
    i.doc_item,
    i.billing_id,
    c.customer_key,
    i.posting_date,
    i.due_date,
    i.amount as amount_doc_currency,
    i.currency,
    round(i.amount * fx.rate_to_usd, 2) as amount_usd,
    cl.cleared_on,
    cl.clearing_doc_id,
    cl.cleared_on is not null as is_cleared,
    case when cl.cleared_on is null then 'open' else 'cleared' end as status,
    cl.cleared_on - i.posting_date as days_to_clear
from items as i
left join cleared as cl
    on cl.company_code = i.company_code
    and cl.accounting_doc_id = i.accounting_doc_id
    and cl.fiscal_year = i.fiscal_year
    and cl.doc_item = i.doc_item
left join {{ ref('dim_customer') }} as c
    on c.customer_id = i.customer_id
    and i.posting_date between c.valid_from and c.valid_to
left join {{ ref('exchange_rates') }} as fx
    on fx.currency = i.currency
