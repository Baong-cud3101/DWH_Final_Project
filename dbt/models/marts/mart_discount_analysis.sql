-- Data mart 4 - Discount Analysis (Q1, Q5): năm x nhóm chiết khấu x mức chiết khấu x ngành hàng x thị trường.
select
    year,
    discount_band_order,
    discount_band,
    discount,
    category,
    market,
    segment,
    count(*)                            as total_lines,
    sum(quantity)                       as quantity,
    {{ kpi_revenue() }}                 as revenue,
    {{ kpi_implied_cost() }}            as implied_cost,
    {{ kpi_profit() }}                  as profit,
    {{ kpi_profit_margin() }}           as profit_margin,
    count(*) filter (where is_loss)     as loss_lines,
    {{ kpi_loss_line_rate() }}          as loss_line_rate
from {{ ref('int_sales_wide') }}
group by year, discount_band_order, discount_band, discount, category, market, segment
order by year, discount, category, market, segment
