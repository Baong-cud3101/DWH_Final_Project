-- Data mart 5b - Customer Value / Cohort (Q4): khách theo năm mua đầu tiên x năm hoạt động.
with first_year as (
    select customer_key, min(year) as cohort_year
    from {{ ref('int_sales_wide') }}
    group by customer_key
),

activity as (
    select distinct customer_key, year as active_year
    from {{ ref('int_sales_wide') }}
),

cohort as (
    select
        f.cohort_year,
        a.active_year,
        a.active_year - f.cohort_year               as years_since_first,
        count(distinct a.customer_key)              as active_customers
    from first_year as f
    join activity as a on f.customer_key = a.customer_key
    group by f.cohort_year, a.active_year
)

select
    c.*,
    s.cohort_size,
    c.active_customers / s.cohort_size              as retention_rate
from cohort as c
join (
    select cohort_year, count(*) as cohort_size from first_year group by cohort_year
) as s on c.cohort_year = s.cohort_year
order by c.cohort_year, c.active_year
