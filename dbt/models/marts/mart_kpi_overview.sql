-- KPI tổng quan theo năm (và toàn kỳ, year = 0), dùng đủ 9 KPI trong metric catalog.
with lines as (
    select
        coalesce(year, 0) as year,
        {{ kpi_revenue() }}             as revenue,
        {{ kpi_profit() }}              as profit,
        {{ kpi_profit_margin() }}       as profit_margin,
        {{ kpi_implied_cost() }}        as implied_cost,
        {{ kpi_total_orders() }}        as total_orders,
        {{ kpi_aov() }}                 as avg_order_value,
        {{ kpi_loss_line_rate() }}      as loss_line_rate,
        {{ kpi_deep_discount_share() }} as deep_discount_share,
        count(*)                        as total_lines,
        count(distinct customer_key)    as active_customers
    from {{ ref('int_sales_wide') }}
    group by rollup (year)
),

cust as (
    -- Repeat Customer Rate tính trên số đơn của khách trong từng năm (và toàn kỳ)
    select
        coalesce(year, 0) as year,
        {{ kpi_repeat_customer_rate('n_orders') }} as repeat_customer_rate
    from (
        select year, customer_key, count(distinct order_id) as n_orders
        from {{ ref('int_sales_wide') }}
        group by year, customer_key
        union all
        select null, customer_key, count(distinct order_id)
        from {{ ref('int_sales_wide') }}
        group by customer_key
    )
    group by year
)

select l.*, c.repeat_customer_rate
from lines as l
join cust as c on l.year = c.year
order by l.year
