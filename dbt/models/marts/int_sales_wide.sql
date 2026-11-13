-- Bảng trung gian (ephemeral, không lưu): fact_sales nối đủ 6 dimension, làm đầu vào cho các data mart.
{{ config(materialized='ephemeral') }}

select
    f.row_id,
    f.order_id,
    f.order_date,
    d.year,
    d.month,
    d.month_start,
    f.customer_key,
    c.customer_id,
    c.gender,
    c.age_group,
    c.income_band,
    c.annual_income,
    c.occupation,
    c.education_level,
    c.marital_status,
    c.is_home_owner,
    f.product_key,
    p.product_code,
    p.product_name,
    p.subcategory,
    p.category,
    f.region_key,
    r.country,
    r.region,
    r.market,
    r.market_group,
    r.country_latitude,
    r.country_longitude,
    sg.segment_name                 as segment,
    fl.discount_band,
    fl.discount_band_order,
    fl.is_deep_discount,
    fl.is_loss,
    fl.is_valid_product,
    fl.is_valid_region,
    f.quantity,
    f.sales,
    f.discount,
    f.profit,
    f.implied_cost
from {{ ref('fact_sales') }} as f
join {{ ref('dim_date') }} as d      on f.date_key = d.date_key
join {{ ref('dim_customer') }} as c  on f.customer_key = c.customer_key
join {{ ref('dim_product') }} as p   on f.product_key = p.product_key
join {{ ref('dim_region') }} as r    on f.region_key = r.region_key
join {{ ref('dim_segment') }} as sg  on f.segment_key = sg.segment_key
join {{ ref('dim_flags') }} as fl    on f.flag_key = fl.flag_key
