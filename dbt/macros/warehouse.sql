-- Warehouse-specific SQL. Each macro has a DuckDB version (default) and a Snowflake version,
-- so the same models run on both. The Snowflake versions are not yet verified against a live account.

{% macro date_from_sap_text(column) -%}
    {{ return(adapter.dispatch('date_from_sap_text', 'sap_o2c')(column)) }}
{%- endmacro %}

{% macro default__date_from_sap_text(column) -%}
    strptime(trim({{ column }}), '%Y%m%d')::date
{%- endmacro %}

{% macro snowflake__date_from_sap_text(column) -%}
    to_date(trim({{ column }}), 'YYYYMMDD')
{%- endmacro %}


{% macro date_from_file_name(column) -%}
    {{ return(adapter.dispatch('date_from_file_name', 'sap_o2c')(column)) }}
{%- endmacro %}

{% macro default__date_from_file_name(column) -%}
    strptime(regexp_extract({{ column }}, '[0-9]{8}'), '%Y%m%d')::date
{%- endmacro %}

{% macro snowflake__date_from_file_name(column) -%}
    to_date(regexp_substr({{ column }}, '[0-9]{8}'), 'YYYYMMDD')
{%- endmacro %}


{% macro days_between(later, earlier) -%}
    {{ return(adapter.dispatch('days_between', 'sap_o2c')(later, earlier)) }}
{%- endmacro %}

{% macro default__days_between(later, earlier) -%}
    date_diff('day', {{ earlier }}, {{ later }})
{%- endmacro %}

{% macro snowflake__days_between(later, earlier) -%}
    datediff(day, {{ earlier }}, {{ later }})
{%- endmacro %}


{% macro add_days(date_expr, days) -%}
    {{ return(adapter.dispatch('add_days', 'sap_o2c')(date_expr, days)) }}
{%- endmacro %}

{% macro default__add_days(date_expr, days) -%}
    cast({{ date_expr }} + {{ days }} as date)
{%- endmacro %}

{% macro snowflake__add_days(date_expr, days) -%}
    dateadd(day, {{ days }}, {{ date_expr }})
{%- endmacro %}


{% macro is_weekend(date_expr) -%}
    {{ return(adapter.dispatch('is_weekend', 'sap_o2c')(date_expr)) }}
{%- endmacro %}

{% macro default__is_weekend(date_expr) -%}
    isodow({{ date_expr }}) in (6, 7)
{%- endmacro %}

{% macro snowflake__is_weekend(date_expr) -%}
    dayofweekiso({{ date_expr }}) in (6, 7)
{%- endmacro %}


{% macro month_name(date_expr) -%}
    {{ return(adapter.dispatch('month_name', 'sap_o2c')(date_expr)) }}
{%- endmacro %}

{% macro default__month_name(date_expr) -%}
    strftime({{ date_expr }}, '%B')
{%- endmacro %}

{% macro snowflake__month_name(date_expr) -%}
    initcap(trim(to_char({{ date_expr }}, 'MMMM')))
{%- endmacro %}


{% macro day_name(date_expr) -%}
    {{ return(adapter.dispatch('day_name', 'sap_o2c')(date_expr)) }}
{%- endmacro %}

{% macro default__day_name(date_expr) -%}
    strftime({{ date_expr }}, '%A')
{%- endmacro %}

{% macro snowflake__day_name(date_expr) -%}
    initcap(trim(to_char({{ date_expr }}, 'DAY')))
{%- endmacro %}


-- One row per day from first to last, inclusive. Snowflake version covers up to 10,000 days.
{% macro date_spine(first_day, last_day) -%}
    {{ return(adapter.dispatch('date_spine', 'sap_o2c')(first_day, last_day)) }}
{%- endmacro %}

{% macro default__date_spine(first_day, last_day) -%}
    select cast(unnest(generate_series({{ first_day }}, {{ last_day }}, interval 1 day)) as date) as date_day
{%- endmacro %}

{% macro snowflake__date_spine(first_day, last_day) -%}
    select date_day
    from (
        select dateadd(day, seq4(), {{ first_day }}) as date_day
        from table(generator(rowcount => 10000))
    )
    where date_day <= {{ last_day }}
{%- endmacro %}
