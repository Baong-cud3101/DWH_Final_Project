-- Silver: khu vực địa lý; market_group gom Europe + Africa thành EMEA.
select
    trim(region_code)                       as region_code,
    trim(city)                              as city,
    trim(state)                             as state,
    trim(country)                           as country,
    try_cast(country_latitude as double)    as country_latitude,
    try_cast(country_longitude as double)   as country_longitude,
    trim(region)                            as region,
    trim(market)                            as market,
    case
        when trim(market) in ('Europe', 'Africa') then 'EMEA'
        when trim(market) = 'Asia Pacific' then 'APAC'
        else trim(market)
    end                                     as market_group
from {{ source('bronze', 'region') }}
