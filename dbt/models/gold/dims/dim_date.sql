-- Gold: dimension ngày, phủ toàn bộ giai đoạn 2020-01-01 đến 2023-12-31.
with days as (
    select cast(d as date) as full_date
    from generate_series(date '2020-01-01', date '2023-12-31', interval 1 day) as t(d)
)

select
    cast(strftime(full_date, '%Y%m%d') as integer)  as date_key,
    full_date,
    year(full_date)                                 as year,
    quarter(full_date)                              as quarter,
    'Q' || quarter(full_date)                       as quarter_name,
    month(full_date)                                as month,
    strftime(full_date, '%Y-%m')                    as year_month,
    cast(date_trunc('month', full_date) as date)    as month_start,
    monthname(full_date)                            as month_name,
    weekofyear(full_date)                           as week_of_year,
    isodow(full_date)                               as day_of_week,
    dayname(full_date)                              as day_name,
    isodow(full_date) in (6, 7)                     as is_weekend
from days
