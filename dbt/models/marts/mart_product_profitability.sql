-- Data mart 2 - Product Profitability (Q1, Q5): năm x sản phẩm, kèm subcategory và category.
select
    year,
    category,
    subcategory,
    product_key,
    product_code,
    product_name,
    {{ kpi_revenue() }}                 as revenue,
    {{ kpi_profit() }}                  as profit,
    {{ kpi_profit_margin() }}           as profit_margin,
    {{ kpi_total_orders() }}            as total_orders,
    count(*)                            as total_lines,
    sum(quantity)                       as quantity,
    avg(discount)                       as avg_discount,
    {{ kpi_loss_line_rate() }}          as loss_line_rate,
    {{ safe_divide('sum(sales)', 'sum(quantity)') }} as avg_unit_price
from {{ ref('int_sales_wide') }}
group by year, category, subcategory, product_key, product_code, product_name
order by year, revenue desc
