-- Gold: dimension khu vực, phân cấp city -> state -> country -> region -> market -> market_group.
select
    row_number() over (order by region_code)    as region_key,
    region_code,
    city,
    state,
    country,
    country_latitude,
    country_longitude,
    region,
    market,
    market_group
from {{ ref('silver_region') }}

union all

-- Thành viên Unknown cho mã khu vực không khớp danh mục
select -1, 'UNKNOWN', 'Unknown', 'Unknown', 'Unknown', null, null, 'Unknown', 'Unknown', 'Unknown'
