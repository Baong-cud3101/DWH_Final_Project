-- Gold: dimension khách hàng (SCD Type 1, không có lịch sử thay đổi thuộc tính).
-- Che dữ liệu cá nhân: băm email (md5), bỏ họ tên và ngày sinh gốc, chỉ giữ nhóm tuổi.
with c as (
    select * from {{ ref('silver_customer') }}
),

seg as (
    -- mỗi khách thuộc đúng một phân khúc (đã kiểm tra ở profiling)
    select customer_id, min(segment) as segment
    from {{ ref('silver_sales_integrated') }}
    group by customer_id
)

select
    row_number() over (order by c.customer_id)          as customer_key,
    c.customer_id,
    md5(c.email_address)                                as email_hash,
    c.gender,
    c.is_gender_imputed,
    c.age,
    case
        when c.age < 30 then '23-29'
        when c.age < 40 then '30-39'
        when c.age < 50 then '40-49'
        when c.age < 60 then '50-59'
        else '60+'
    end                                                 as age_group,
    c.marital_status,
    c.annual_income,
    case
        when c.annual_income < 40000 then '< 40K'
        when c.annual_income < 70000 then '40K-70K'
        when c.annual_income < 100000 then '70K-100K'
        else '>= 100K'
    end                                                 as income_band,
    c.education_level,
    c.occupation,
    c.is_home_owner,
    coalesce(seg.segment, 'Unknown')                    as segment
from c
left join seg on c.customer_id = seg.customer_id

union all

select
    -1, 'UNKNOWN', null, 'Unknown', false, null, 'Unknown', 'Unknown', null,
    'Unknown', 'Unknown', 'Unknown', null, 'Unknown'
