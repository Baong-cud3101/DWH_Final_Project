-- Đối chiếu: số dòng giữ nguyên 100% từ Bronze -> Silver -> Gold (không mất, không nhân bản khi nối dimension).
with c as (
    select
        (select count(*) from {{ source('bronze', 'ecom_sales') }})      as bronze_rows,
        (select count(*) from {{ ref('silver_sales_integrated') }})     as silver_rows,
        (select count(*) from {{ ref('fact_sales') }})                  as gold_rows,
        (select count(distinct row_id) from {{ ref('fact_sales') }})    as gold_distinct_rows
)
select * from c
where not (bronze_rows = silver_rows and silver_rows = gold_rows and gold_rows = gold_distinct_rows)
