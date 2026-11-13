-- ML: đặc trưng đơn hàng ĐẦU TIÊN của mỗi khách (grain: khách hàng) cho bài toán phân lớp
-- "khách có quay lại mua trong 365 ngày không" (Q4).
-- Chỉ dùng thông tin biết tại thời điểm đơn đầu kết thúc; nhãn nhìn tối đa 365 ngày sau đó.
-- Chỉ lấy khách có đơn đầu <= 2022-12-31 để mọi khách đều có đủ 365 ngày quan sát (tránh censoring).
with w as (
    select * from {{ ref('int_sales_wide') }}
),

orders as (
    select
        customer_key,
        order_id,
        min(order_date)                                 as order_date
    from w
    group by customer_key, order_id
),

ranked as (
    select
        *,
        row_number() over (partition by customer_key order by order_date, order_id) as order_rank
    from orders
),

first_order as (
    select customer_key, order_id, order_date as first_order_date
    from ranked
    where order_rank = 1
),

first_lines as (
    select
        f.customer_key,
        f.first_order_date,
        sum(w.sales)                                    as first_sales,
        sum(w.quantity)                                 as first_quantity,
        count(*)                                        as first_lines,
        cast(sum(w.discount * w.sales) / sum(w.sales) as double) as first_discount,
        max(w.discount)                                 as first_max_discount,
        count(distinct w.category)                      as first_n_categories,
        arg_max(w.category, w.sales)                    as first_main_category,
        min(w.market)                                   as market,
        min(w.segment)                                  as segment,
        min(w.gender)                                   as gender,
        min(w.age_group)                                as age_group,
        min(w.income_band)                              as income_band,
        min(w.occupation)                               as occupation,
        min(w.education_level)                          as education_level,
        bool_or(w.is_home_owner)                        as is_home_owner
    from first_order as f
    join w on w.order_id = f.order_id and w.customer_key = f.customer_key
    group by f.customer_key, f.first_order_date
),

label as (
    select
        f.customer_key,
        count(r.order_id) > 0                           as returned_365d
    from first_order as f
    left join ranked as r
        on  r.customer_key = f.customer_key
        and r.order_rank > 1
        and r.order_date <= f.first_order_date + interval 365 day
    group by f.customer_key
)

select
    l.customer_key,
    l.first_order_date,
    year(l.first_order_date)                            as cohort_year,
    case when year(l.first_order_date) <= 2021 then 'train' else 'test' end as split,
    l.first_sales,
    l.first_quantity,
    l.first_lines,
    l.first_discount,
    l.first_max_discount,
    {{ discount_band('l.first_discount') }}             as first_discount_band,
    {{ discount_band_order('l.first_discount') }}       as first_discount_band_order,
    l.first_n_categories,
    l.first_main_category,
    l.market,
    l.segment,
    l.gender,
    l.age_group,
    l.income_band,
    l.occupation,
    l.education_level,
    l.is_home_owner,
    lb.returned_365d
from first_lines as l
join label as lb on l.customer_key = lb.customer_key
where l.first_order_date <= date '2022-12-31'
order by l.customer_key
