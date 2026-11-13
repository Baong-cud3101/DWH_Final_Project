-- Data mart 3 - Geographic Performance (Q3): năm x quốc gia x region, kèm market và tăng trưởng so với năm trước.
with g as (
    select
        year,
        market_group,
        market,
        region,
        country,
        avg(country_latitude)               as country_latitude,
        avg(country_longitude)              as country_longitude,
        {{ kpi_revenue() }}                 as revenue,
        {{ kpi_profit() }}                  as profit,
        {{ kpi_profit_margin() }}           as profit_margin,
        {{ kpi_total_orders() }}            as total_orders,
        count(distinct customer_key)        as customers,
        avg(discount)                       as avg_discount,
        {{ kpi_deep_discount_share() }}     as deep_discount_share,
        {{ kpi_loss_line_rate() }}          as loss_line_rate
    from {{ ref('int_sales_wide') }}
    group by year, market_group, market, region, country
)

select
    *,
    lag(revenue) over (partition by country, region order by year)  as revenue_prev_year,
    {{ safe_divide('revenue - lag(revenue) over (partition by country, region order by year)',
                   'lag(revenue) over (partition by country, region order by year)') }} as revenue_yoy_growth
from g
order by year, market, revenue desc
