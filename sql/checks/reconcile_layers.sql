-- Đối chiếu Bronze -> Silver -> Gold (sinh tự động bởi scripts/09_checks.py)

-- Số dòng giao dịch
select count(*) from bronze.ecom_sales;
select count(*) from silver.silver_sales_integrated;
select count(*) from gold.fact_sales;

-- Tổng sales (USD)
select sum(sales::decimal(14,2)) from bronze.ecom_sales;
select sum(sales) from silver.silver_sales_integrated;
select sum(sales) from gold.fact_sales;

-- Tổng profit (USD)
select sum(profit::decimal(14,2)) from bronze.ecom_sales;
select sum(profit) from silver.silver_sales_integrated;
select sum(profit) from gold.fact_sales;

-- Số đơn hàng (order_id phân biệt)
select count(distinct order_id) from bronze.ecom_sales;
select count(distinct order_id) from silver.silver_sales_integrated;
select count(distinct order_id) from gold.fact_sales;

-- Số khách hàng
select count(*) from bronze.customer;
select count(*) from silver.silver_customer;
select count(*) from gold.dim_customer where customer_key <> -1;

-- Dòng fact rơi vào product Unknown (-1)
select count(*) from gold.fact_sales where product_key = -1;

-- Dòng fact rơi vào region Unknown (-1)
select count(*) from gold.fact_sales where region_key = -1;

-- Dòng fact rơi vào customer Unknown (-1)
select count(*) from gold.fact_sales where customer_key = -1;

-- Dòng fact có khóa NULL
select count(*) from gold.fact_sales where customer_key is null or product_key is null or region_key is null or segment_key is null or flag_key is null or date_key is null;
