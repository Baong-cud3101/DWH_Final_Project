{# Nhóm chiết khấu dùng thống nhất ở Silver, Gold và data mart #}
{% macro discount_band(col) -%}
    case
        when {{ col }} = 0 then '0%'
        when {{ col }} <= 0.10 then '(0%, 10%]'
        when {{ col }} <= 0.20 then '(10%, 20%]'
        when {{ col }} <= 0.30 then '(20%, 30%]'
        when {{ col }} <= 0.50 then '(30%, 50%]'
        else '> 50%'
    end
{%- endmacro %}

{% macro discount_band_order(col) -%}
    case
        when {{ col }} = 0 then 1
        when {{ col }} <= 0.10 then 2
        when {{ col }} <= 0.20 then 3
        when {{ col }} <= 0.30 then 4
        when {{ col }} <= 0.50 then 5
        else 6
    end
{%- endmacro %}
