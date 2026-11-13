-- Truy vấn mẫu dùng để đo tác động của việc sắp xếp bảng theo order_date (B4.4).
-- {table} được thay bằng bảng đã sắp xếp hoặc chưa sắp xếp.
select r.market, sum(f.sales) as revenue, sum(f.profit) as profit
from {table} f
join gold.dim_region r on f.region_key = r.region_key
where f.order_date between date '2023-10-01' and date '2023-12-31'
group by r.market
order by revenue desc
