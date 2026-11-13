{# Lay tu repo tham khao (macros/math_macros.sql): chia an toan, tranh chia cho 0 #}
{% macro safe_divide(numerator, denominator) -%}
    case when ({{ denominator }}) is null or ({{ denominator }}) = 0 then null
         else ({{ numerator }}) / ({{ denominator }}) end
{%- endmacro %}
