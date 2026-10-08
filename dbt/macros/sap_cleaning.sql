-- SAP extracts store empty text as '' and empty dates as '00000000'.
-- These macros turn those into NULL and cast to proper types.

{% macro sap_text(column) -%}
    nullif(trim({{ column }}), '')
{%- endmacro %}

{% macro sap_date(column) -%}
    case
        when trim({{ column }}) in ('', '00000000') then null
        else strptime(trim({{ column }}), '%Y%m%d')::date
    end
{%- endmacro %}

{% macro sap_amount(column) -%}
    try_cast(nullif(trim({{ column }}), '') as decimal(18, 2))
{%- endmacro %}

{% macro sap_quantity(column) -%}
    try_cast(nullif(trim({{ column }}), '') as decimal(18, 3))
{%- endmacro %}
