{#
  METRIC CATALOG - định nghĩa duy nhất của mọi KPI.
  Mọi data mart và báo cáo dùng các macro này, không viết lại công thức.
  Danh mục mô tả nằm ở seeds/metric_catalog.csv (bảng main.metric_catalog).
#}

{% macro kpi_revenue() -%} sum(sales) {%- endmacro %}

{% macro kpi_profit() -%} sum(profit) {%- endmacro %}

{% macro kpi_implied_cost() -%} sum(sales) - sum(profit) {%- endmacro %}

{% macro kpi_profit_margin() -%} {{ safe_divide('sum(profit)', 'sum(sales)') }} {%- endmacro %}

{% macro kpi_total_orders() -%} count(distinct order_id) {%- endmacro %}

{% macro kpi_aov() -%} {{ safe_divide('sum(sales)', 'count(distinct order_id)') }} {%- endmacro %}

{% macro kpi_loss_line_rate() -%}
    {{ safe_divide('count(*) filter (where profit < 0)', 'count(*)') }}
{%- endmacro %}

{% macro kpi_deep_discount_share() -%}
    {{ safe_divide('count(*) filter (where discount > ' ~ var('deep_discount_threshold') ~ ')', 'count(*)') }}
{%- endmacro %}

{# Repeat Customer Rate: dùng trên bảng cấp khách hàng có cột frequency (số đơn) #}
{% macro kpi_repeat_customer_rate(frequency_col='frequency') -%}
    {{ safe_divide('count(*) filter (where ' ~ frequency_col ~ ' >= 2)', 'count(*)') }}
{%- endmacro %}
