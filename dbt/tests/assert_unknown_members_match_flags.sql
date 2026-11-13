-- Đối chiếu: số dòng rơi vào thành viên Unknown đúng bằng số dòng có mã không khớp ở Silver.
with s as (
    select
        count(*) filter (where not is_valid_product) as invalid_product_rows,
        count(*) filter (where not is_valid_region)  as invalid_region_rows
    from {{ ref('silver_sales_integrated') }}
),
g as (
    select
        count(*) filter (where product_key = -1) as unknown_product_rows,
        count(*) filter (where region_key = -1)  as unknown_region_rows,
        count(*) filter (where customer_key = -1 or segment_key = -1 or flag_key is null) as other_unknown_rows
    from {{ ref('fact_sales') }}
)
select * from s cross join g
where invalid_product_rows <> unknown_product_rows
   or invalid_region_rows <> unknown_region_rows
   or other_unknown_rows <> 0
