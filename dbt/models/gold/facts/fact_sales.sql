-- Gold: transaction fact. Grain: một dòng sản phẩm trong một đơn hàng (row_id).
-- order_id giữ trong fact như degenerate dimension.
-- Bảng được sắp xếp vật lý theo order_date để DuckDB bỏ qua row group nhanh khi lọc theo thời gian.

with s as (
    select * from {{ ref('silver_sales_integrated') }}
)

select
    s.row_id,
    s.order_id,                                                 -- degenerate dimension
    cast(strftime(s.order_date, '%Y%m%d') as integer)           as date_key,
    s.order_date,
    coalesce(c.customer_key, -1)                                as customer_key,
    coalesce(p.product_key, -1)                                 as product_key,
    coalesce(r.region_key, -1)                                  as region_key,
    coalesce(sg.segment_key, -1)                                as segment_key,
    f.flag_key,
    s.product_code                                              as source_product_code,
    s.region_code                                               as source_region_code,
    s.quantity,
    s.sales,
    s.discount,
    s.profit,
    s.implied_cost
from s
left join {{ ref('dim_customer') }} as c  on s.customer_id = c.customer_id
left join {{ ref('dim_product') }} as p   on s.product_code = p.product_code
left join {{ ref('dim_region') }} as r    on s.region_code = r.region_code
left join {{ ref('dim_segment') }} as sg  on s.segment = sg.segment_name
left join {{ ref('dim_flags') }} as f
    on  f.is_valid_product = s.is_valid_product
    and f.is_valid_region = s.is_valid_region
    and f.discount_band_order = s.discount_band_order
    and f.is_loss = s.is_loss
order by s.order_date, s.row_id
