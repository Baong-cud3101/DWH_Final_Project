-- Gold: periodic snapshot fact. Grain: tháng x market x segment.
-- Lưới đầy đủ 48 tháng x 5 market x 3 segment (ô không có giao dịch = 0) để so sánh cùng kỳ.
-- Dòng market 'Unknown' (mã khu vực không khớp) được giữ riêng để tổng vẫn khớp fact_sales.
with base as (
    select
        d.month_start,
        r.market,
        sg.segment_name                                     as segment,
        f.order_id,
        f.customer_key,
        f.quantity,
        f.sales,
        f.profit,
        f.implied_cost,
        f.discount,
        fl.is_deep_discount,
        fl.is_loss
    from {{ ref('fact_sales') }} as f
    join {{ ref('dim_date') }} as d     on f.date_key = d.date_key
    join {{ ref('dim_region') }} as r   on f.region_key = r.region_key
    join {{ ref('dim_segment') }} as sg on f.segment_key = sg.segment_key
    join {{ ref('dim_flags') }} as fl   on f.flag_key = fl.flag_key
),

actual as (
    select
        month_start,
        market,
        segment,
        sum(sales)                                          as revenue,
        sum(profit)                                         as profit,
        sum(implied_cost)                                   as implied_cost,
        count(distinct order_id)                            as total_orders,
        count(*)                                            as total_lines,
        count(distinct customer_key)                        as active_customers,
        sum(quantity)                                       as quantity,
        avg(discount)                                       as avg_discount,
        count(*) filter (where is_deep_discount)            as deep_discount_lines,
        count(*) filter (where is_loss)                     as loss_lines
    from base
    group by month_start, market, segment
),

grid as (
    select m.month_start, mk.market, sg.segment_name as segment
    from (select distinct month_start from {{ ref('dim_date') }}) as m
    cross join (select distinct market from {{ ref('dim_region') }} where region_key <> -1) as mk
    cross join (select segment_name from {{ ref('dim_segment') }} where segment_key <> -1) as sg
    union
    select month_start, market, segment from actual
),

snap as (
    select
        g.month_start,
        year(g.month_start)                                 as year,
        month(g.month_start)                                as month,
        g.market,
        g.segment,
        coalesce(a.revenue, 0)                              as revenue,
        coalesce(a.profit, 0)                               as profit,
        coalesce(a.implied_cost, 0)                         as implied_cost,
        coalesce(a.total_orders, 0)                         as total_orders,
        coalesce(a.total_lines, 0)                          as total_lines,
        coalesce(a.active_customers, 0)                     as active_customers,
        coalesce(a.quantity, 0)                             as quantity,
        a.avg_discount,
        coalesce(a.deep_discount_lines, 0)                  as deep_discount_lines,
        coalesce(a.loss_lines, 0)                           as loss_lines
    from grid as g
    left join actual as a
        on g.month_start = a.month_start and g.market = a.market and g.segment = a.segment
)

select
    cast(strftime(month_start, '%Y%m') as integer)          as month_key,
    *,
    {{ safe_divide('profit', 'revenue') }}                  as profit_margin,
    lag(revenue, 12) over w                                 as revenue_same_month_last_year,
    lag(profit, 12) over w                                  as profit_same_month_last_year,
    {{ safe_divide('revenue - lag(revenue, 12) over w', 'lag(revenue, 12) over w') }}
                                                            as revenue_yoy_growth
from snap
window w as (partition by market, segment order by month_start)
order by month_start, market, segment
