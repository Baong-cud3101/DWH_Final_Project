-- Data mart 1 - Segment Profitability (Q2): P&L theo năm x phân khúc x thị trường.
select
    year,
    segment,
    market,
    {{ kpi_revenue() }}                 as revenue,
    {{ kpi_implied_cost() }}            as implied_cost,
    {{ kpi_profit() }}                  as profit,
    {{ kpi_profit_margin() }}           as profit_margin,
    {{ kpi_total_orders() }}            as total_orders,
    count(*)                            as total_lines,
    count(distinct customer_key)        as customers,
    sum(quantity)                       as quantity,
    {{ kpi_aov() }}                     as avg_order_value,
    avg(discount)                       as avg_discount,
    {{ kpi_loss_line_rate() }}          as loss_line_rate,
    {{ kpi_deep_discount_share() }}     as deep_discount_share,
    sum(profit) filter (where profit < 0) as loss_amount
from {{ ref('int_sales_wide') }}
group by year, segment, market
order by year, segment, market
