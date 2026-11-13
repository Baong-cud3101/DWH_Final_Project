-- Các con số dẫn trong phần chữ của báo cáo (sinh tự động bởi scripts/09_checks.py)

-- Số dòng giảm giá sâu (> 30%) (dòng)
select count(*) from gold.fact_sales where discount > 0.30;

-- Tỷ trọng dòng giảm giá sâu (%)
select avg((discount > 0.30)::int) from gold.fact_sales;

-- Doanh thu của dòng giảm giá sâu (USD)
select sum(sales) from gold.fact_sales where discount > 0.30;

-- Tỷ trọng doanh thu của dòng giảm giá sâu (%)
select sum(sales) filter (where discount > 0.30) / sum(sales) from gold.fact_sales;

-- Lợi nhuận ròng của dòng giảm giá sâu (USD)
select sum(profit) from gold.fact_sales where discount > 0.30;

-- Lỗ của dòng giảm sâu so với tổng lợi nhuận (%)
select -sum(profit) filter (where discount > 0.30) / sum(profit) from gold.fact_sales;

-- Số dòng giảm từ 80% trở lên (dòng)
select count(*) from gold.fact_sales where discount >= 0.80;

-- Lợi nhuận trung bình dòng giảm từ 80% (USD/dòng)
select avg(profit) from gold.fact_sales where discount >= 0.80;

-- Số dòng giảm đúng 50% (dòng)
select count(*) from gold.fact_sales where discount = 0.50;

-- Số dòng giảm đúng 50% bị lỗ (dòng)
select count(*) from gold.fact_sales where discount = 0.50 and profit < 0;

-- Số dòng giảm trên 50% (dòng)
select count(*) from gold.fact_sales where discount > 0.50;

-- Số dòng giảm trên 50% bị lỗ (dòng)
select count(*) from gold.fact_sales where discount > 0.50 and profit < 0;

-- Số mức chiết khấu khác nhau (mức)
select count(distinct discount) from gold.fact_sales;

-- Tỷ trọng dòng không giảm giá (%)
select avg((discount = 0)::int) from gold.fact_sales;

-- Tỷ trọng 6 mức 10/20/40/50/60/70% trong dòng có giảm giá (%)
select avg((discount in (0.10, 0.20, 0.40, 0.50, 0.60, 0.70))::int) from gold.fact_sales where discount > 0;

-- Số dòng có mã sản phẩm hoặc khu vực không khớp (dòng)
select count(*) from gold.fact_sales where product_key = -1 or region_key = -1;

-- Doanh thu của các dòng có mã không khớp (USD)
select sum(sales) from gold.fact_sales where product_key = -1 or region_key = -1;

-- Số khách chỉ mua 1 đơn (khách)
select count(*) from mart.mart_customer_value where frequency = 1;

-- Tỷ trọng khách chỉ mua 1 đơn (%)
select avg((frequency = 1)::int) from mart.mart_customer_value;

-- Số đơn trung bình mỗi khách (đơn)
select avg(frequency) from mart.mart_customer_value;

-- Số dòng trung bình mỗi đơn (dòng)
select count(*) / count(distinct order_id) from gold.fact_sales;

-- Tỷ trọng doanh thu của Mỹ (%)
select sum(sales) filter (where r.country = 'United States') / sum(sales) from gold.fact_sales f join gold.dim_region r using (region_key);

-- Tỷ trọng đơn có từ 2 subcategory (%)
select avg((n >= 2)::int) from (select order_id, count(distinct p.subcategory) n from gold.fact_sales f join gold.dim_product p using (product_key) group by 1);

-- Năm trong order_id lệch so với năm order_date (năm)
select min(year(order_date::date) - split_part(order_id, '-', 2)::int) from bronze.ecom_sales;

-- Số order_id gắn nhiều ngày hoặc nhiều khách (đơn)
select count(*) from (select order_id from bronze.ecom_sales group by 1 having count(distinct order_date) > 1 or count(distinct customer_id) > 1);

-- Tăng trưởng doanh thu 2023 so với 2022 (%)
select max(revenue) filter (where year = 2023) / max(revenue) filter (where year = 2022) - 1 from mart.mart_kpi_overview;

-- Thay đổi lợi nhuận 2023 so với 2022 (%)
select max(profit) filter (where year = 2023) / max(profit) filter (where year = 2022) - 1 from mart.mart_kpi_overview;
