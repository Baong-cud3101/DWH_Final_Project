-- Đối chiếu: tổng sales và profit khớp tuyệt đối giữa Bronze, Silver, fact_sales và fact_monthly_snapshot.
with t as (
    select 'bronze' as layer, sum(cast(sales as decimal(14,2))) as sales, sum(cast(profit as decimal(14,2))) as profit from {{ source('bronze', 'ecom_sales') }}
    union all select 'silver', sum(sales), sum(profit) from {{ ref('silver_sales_integrated') }}
    union all select 'fact_sales', sum(sales), sum(profit) from {{ ref('fact_sales') }}
    union all select 'snapshot', sum(revenue), sum(profit) from {{ ref('fact_monthly_snapshot') }}
)
select * from t
where sales <> (select sales from t where layer = 'bronze')
   or profit <> (select profit from t where layer = 'bronze')
