-- ML: bảng đặc trưng dạng wide (grain row_id) cho mô hình hồi quy biên lợi nhuận.
-- Chỉ dùng đặc trưng biết trước khi bán; KHÔNG dùng sales, profit, implied_cost làm đặc trưng
-- (chúng chỉ được giữ làm nhãn và để đánh giá). Chia theo thời gian: train 2020-2022, test 2023.
with w as (
    select * from {{ ref('int_sales_wide') }}
),

prior as (
    -- số đơn khách đã mua TRƯỚC đơn hiện tại (không nhìn tương lai)
    select
        order_id,
        customer_key,
        dense_rank() over (partition by customer_key order by order_date, order_id) - 1 as prior_orders
    from (select distinct order_id, customer_key, order_date from w)
),

order_size as (
    select order_id, count(*) as lines_in_order
    from w
    group by order_id
)

select
    w.row_id,
    w.order_date,
    w.year,
    w.month,
    case when w.year <= 2022 then 'train' else 'test' end  as split,
    -- đặc trưng số
    cast(w.discount as double)                              as discount,
    w.quantity,
    p.prior_orders,
    o.lines_in_order,
    w.annual_income,
    -- đặc trưng phân loại
    w.category,
    w.subcategory,
    w.market,
    w.segment,
    w.gender,
    w.age_group,
    w.occupation,
    w.education_level,
    w.marital_status,
    w.is_home_owner,
    -- nhãn (không phải đặc trưng)
    cast(w.profit as double) / nullif(cast(w.sales as double), 0) as target_margin,
    cast(w.sales as double)                                 as label_sales,
    cast(w.profit as double)                                as label_profit
from w
join prior as p on w.order_id = p.order_id and w.customer_key = p.customer_key
join order_size as o on w.order_id = o.order_id
order by w.order_date, w.row_id
