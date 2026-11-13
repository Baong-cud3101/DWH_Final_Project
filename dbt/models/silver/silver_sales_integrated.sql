-- Silver: giao dịch đã ép kiểu, tích hợp với 3 bảng danh mục.
-- Quy tắc đã chốt:
--   * Giữ nguyên dòng lợi nhuận âm (giao dịch lỗ thật).
--   * order_id lặp là hợp lệ (nhiều dòng mỗi đơn), không khử trùng.
--   * Mã product/region không khớp: giữ mã gốc, gắn cờ is_valid_*, không xóa.
--   * Trục thời gian duy nhất là order_date (năm trong order_id bị lệch).
--   * Chi phí ngầm = sales - profit.
with sales as (
    select
        try_cast(row_id as integer)             as row_id,
        trim(order_id)                          as order_id,
        try_cast(order_date as date)            as order_date,
        trim(customer_id)                       as customer_id,
        trim(segment)                           as segment,
        trim(region_code)                       as region_code,
        trim(product_code)                      as product_code,
        try_cast(quantity as integer)           as quantity,
        try_cast(sales as decimal(12, 2))       as sales,
        try_cast(discount as decimal(5, 2))     as discount,
        try_cast(profit as decimal(12, 2))      as profit
    from {{ source('bronze', 'ecom_sales') }}
)

select
    s.row_id,
    s.order_id,
    s.order_date,
    year(s.order_date)                          as order_year,
    s.customer_id,
    s.segment,
    s.product_code,
    s.region_code,
    p.product_code is not null                  as is_valid_product,
    r.region_code is not null                   as is_valid_region,
    coalesce(p.category, 'Unknown')             as category,
    coalesce(p.subcategory, 'Unknown')          as subcategory,
    coalesce(r.country, 'Unknown')              as country,
    coalesce(r.market, 'Unknown')               as market,
    s.quantity,
    s.sales,
    s.discount,
    s.profit,
    s.sales - s.profit                          as implied_cost,
    s.profit < 0                                as is_loss,
    {{ discount_band('s.discount') }}           as discount_band,
    {{ discount_band_order('s.discount') }}     as discount_band_order
from sales as s
left join {{ ref('silver_product') }} as p on s.product_code = p.product_code
left join {{ ref('silver_region') }} as r on s.region_code = r.region_code
