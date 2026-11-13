-- Data mart 5a - Customer Value (Q4): một dòng mỗi khách, RFM tính tại ngày tham chiếu cố định.
-- Frequency đếm theo số đơn (count distinct order_id), không theo số dòng.
with c as (
    select
        customer_key,
        min(segment)                        as segment,
        min(gender)                         as gender,
        min(age_group)                      as age_group,
        min(income_band)                    as income_band,
        min(annual_income)                  as annual_income,
        min(occupation)                     as occupation,
        min(education_level)                as education_level,
        min(marital_status)                 as marital_status,
        bool_or(is_home_owner)              as is_home_owner,
        min(order_date)                     as first_order_date,
        max(order_date)                     as last_order_date,
        year(min(order_date))               as cohort_year,
        count(distinct order_id)            as frequency,
        count(*)                            as total_lines,
        sum(quantity)                       as quantity,
        {{ kpi_revenue() }}                 as monetary,
        {{ kpi_profit() }}                  as profit,
        {{ kpi_profit_margin() }}           as profit_margin,
        avg(discount)                       as avg_discount,
        count(distinct category)            as n_categories,
        count(distinct market)              as n_markets
    from {{ ref('int_sales_wide') }}
    group by customer_key
),

scored as (
    select
        *,
        date_diff('day', last_order_date, date '{{ var("reference_date") }}')   as recency_days,
        date_diff('day', first_order_date, date '{{ var("reference_date") }}')  as tenure_days,
        6 - ntile(5) over (order by date_diff('day', last_order_date, date '{{ var("reference_date") }}'), customer_key) as r_score,
        -- Frequency có rất nhiều giá trị trùng (đa số khách 1 đơn) nên chấm điểm theo ngưỡng, không dùng ntile
        case when frequency >= 5 then 5 when frequency = 4 then 4 when frequency = 3 then 3
             when frequency = 2 then 2 else 1 end                                 as f_score,
        ntile(5) over (order by monetary, customer_key)                           as m_score
    from c
)

select
    *,
    frequency >= 2                                      as is_repeat_customer,
    case
        when r_score >= 4 and f_score >= 3 and m_score >= 4 then 'Champions'
        when f_score >= 2 and r_score >= 3                  then 'Loyal'
        when f_score >= 2 and r_score <= 2                  then 'At Risk'
        when f_score = 1 and r_score >= 4                   then 'New'
        when f_score = 1 and m_score >= 4                   then 'Big One-time'
        else 'Hibernating'
    end                                                 as rfm_segment
from scored
order by customer_key
