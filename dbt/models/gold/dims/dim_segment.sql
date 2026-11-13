-- Gold: dimension phân khúc khách hàng.
select
    row_number() over (order by segment)    as segment_key,
    segment                                 as segment_name,
    case segment
        when 'Consumer' then 'Khách hàng cá nhân'
        when 'Corporate' then 'Khách hàng doanh nghiệp (B2B)'
        when 'Self-Employed' then 'Khách hàng tự kinh doanh'
    end                                     as segment_description
from (select distinct segment from {{ ref('silver_sales_integrated') }})

union all

select -1, 'Unknown', 'Không xác định'
