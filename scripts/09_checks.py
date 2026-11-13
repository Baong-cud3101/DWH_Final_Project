"""Đối chiếu số liệu giữa các tầng (B4.3) và số đếm đối tượng cho báo cáo.

Dừng với lỗi nếu bất kỳ đối chiếu nào không khớp.
Mọi câu SQL cũng được lưu trong sql/checks/ để kiểm tra lại bằng DuckDB CLI hoặc DBeaver.
"""

import pandas as pd

from common import ROOT, TABLES_DIR, connect, update_key_numbers

con = connect(read_only=True)
one = lambda s: con.execute(s).fetchone()[0]

CHECKS = {
    "rows": (
        "select count(*) from bronze.ecom_sales",
        "select count(*) from silver.silver_sales_integrated",
        "select count(*) from gold.fact_sales",
    ),
    "sales": (
        "select sum(sales::decimal(14,2)) from bronze.ecom_sales",
        "select sum(sales) from silver.silver_sales_integrated",
        "select sum(sales) from gold.fact_sales",
    ),
    "profit": (
        "select sum(profit::decimal(14,2)) from bronze.ecom_sales",
        "select sum(profit) from silver.silver_sales_integrated",
        "select sum(profit) from gold.fact_sales",
    ),
    "orders": (
        "select count(distinct order_id) from bronze.ecom_sales",
        "select count(distinct order_id) from silver.silver_sales_integrated",
        "select count(distinct order_id) from gold.fact_sales",
    ),
    "customers": (
        "select count(*) from bronze.customer",
        "select count(*) from silver.silver_customer",
        "select count(*) from gold.dim_customer where customer_key <> -1",
    ),
}
labels = {"rows": "Số dòng giao dịch", "sales": "Tổng sales (USD)", "profit": "Tổng profit (USD)",
          "orders": "Số đơn hàng (order_id phân biệt)", "customers": "Số khách hàng"}

rows, ok = [], True
sql_lines = ["-- Đối chiếu Bronze -> Silver -> Gold (sinh tự động bởi scripts/09_checks.py)\n"]
for key, (b, s, g) in CHECKS.items():
    vb, vs, vg = one(b), one(s), one(g)
    match = vb == vs == vg
    ok &= match
    rows.append({"Chỉ tiêu": labels[key], "Bronze": vb, "Silver": vs, "Gold": vg,
                 "Khớp": "Có" if match else "KHÔNG"})
    sql_lines += [f"-- {labels[key]}", b + ";", s + ";", g + ";", ""]

unk = [
    ("Dòng fact rơi vào product Unknown (-1)", "select count(*) from gold.fact_sales where product_key = -1"),
    ("Dòng fact rơi vào region Unknown (-1)", "select count(*) from gold.fact_sales where region_key = -1"),
    ("Dòng fact rơi vào customer Unknown (-1)", "select count(*) from gold.fact_sales where customer_key = -1"),
    ("Dòng fact có khóa NULL", "select count(*) from gold.fact_sales where customer_key is null or product_key is null or region_key is null or segment_key is null or flag_key is null or date_key is null"),
]
for label, sql in unk:
    rows.append({"Chỉ tiêu": label, "Bronze": None, "Silver": None, "Gold": one(sql), "Khớp": ""})
    sql_lines += [f"-- {label}", sql + ";", ""]

b43 = pd.DataFrame(rows)
print(b43.to_string())
b43.to_csv(TABLES_DIR / "B4.3_gold_reconciliation.csv", index=False, encoding="utf-8-sig")
(ROOT / "sql" / "checks" / "reconcile_layers.sql").write_text("\n".join(sql_lines), encoding="utf-8")

counts = con.execute("""
    select schema_name as table_schema, table_name, estimated_size
    from duckdb_tables() where schema_name in ('bronze','silver','gold','mart','ml','main')
    order by 1, 2
""").df()
counts["rows"] = [one(f'select count(*) from "{s}"."{t}"') for s, t in zip(counts.table_schema, counts.table_name)]
counts = counts.drop(columns="estimated_size")
counts.to_csv(TABLES_DIR / "B4.1_tables_per_schema.csv", index=False, encoding="utf-8-sig")
print(counts.to_string())

tests = con.execute("""
    select resource_type, status, count(*) n from main.audit_run_log
    where invocation_id = (select invocation_id from main.audit_run_log
                           where command = 'build' order by run_at desc limit 1)
    group by 1, 2 order by 1, 2
""").df()
print(tests.to_string())

# Các con số lẻ được dẫn trong phần chữ của báo cáo: lưu kèm câu SQL để kiểm tra lại
F = "gold.fact_sales"
EXTRA = [
    ("Số dòng giảm giá sâu (> 30%)", "dòng", f"select count(*) from {F} where discount > 0.30"),
    ("Tỷ trọng dòng giảm giá sâu", "%", f"select avg((discount > 0.30)::int) from {F}"),
    ("Doanh thu của dòng giảm giá sâu", "USD", f"select sum(sales) from {F} where discount > 0.30"),
    ("Tỷ trọng doanh thu của dòng giảm giá sâu", "%", f"select sum(sales) filter (where discount > 0.30) / sum(sales) from {F}"),
    ("Lợi nhuận ròng của dòng giảm giá sâu", "USD", f"select sum(profit) from {F} where discount > 0.30"),
    ("Lỗ của dòng giảm sâu so với tổng lợi nhuận", "%", f"select -sum(profit) filter (where discount > 0.30) / sum(profit) from {F}"),
    ("Số dòng giảm từ 80% trở lên", "dòng", f"select count(*) from {F} where discount >= 0.80"),
    ("Lợi nhuận trung bình dòng giảm từ 80%", "USD/dòng", f"select avg(profit) from {F} where discount >= 0.80"),
    ("Số dòng giảm đúng 50%", "dòng", f"select count(*) from {F} where discount = 0.50"),
    ("Số dòng giảm đúng 50% bị lỗ", "dòng", f"select count(*) from {F} where discount = 0.50 and profit < 0"),
    ("Số dòng giảm trên 50%", "dòng", f"select count(*) from {F} where discount > 0.50"),
    ("Số dòng giảm trên 50% bị lỗ", "dòng", f"select count(*) from {F} where discount > 0.50 and profit < 0"),
    ("Số mức chiết khấu khác nhau", "mức", f"select count(distinct discount) from {F}"),
    ("Tỷ trọng dòng không giảm giá", "%", f"select avg((discount = 0)::int) from {F}"),
    ("Tỷ trọng 6 mức 10/20/40/50/60/70% trong dòng có giảm giá", "%",
     f"select avg((discount in (0.10, 0.20, 0.40, 0.50, 0.60, 0.70))::int) from {F} where discount > 0"),
    ("Số dòng có mã sản phẩm hoặc khu vực không khớp", "dòng",
     f"select count(*) from {F} where product_key = -1 or region_key = -1"),
    ("Doanh thu của các dòng có mã không khớp", "USD",
     f"select sum(sales) from {F} where product_key = -1 or region_key = -1"),
    ("Số khách chỉ mua 1 đơn", "khách", "select count(*) from mart.mart_customer_value where frequency = 1"),
    ("Tỷ trọng khách chỉ mua 1 đơn", "%", "select avg((frequency = 1)::int) from mart.mart_customer_value"),
    ("Số đơn trung bình mỗi khách", "đơn", "select avg(frequency) from mart.mart_customer_value"),
    ("Số dòng trung bình mỗi đơn", "dòng", f"select count(*) / count(distinct order_id) from {F}"),
    ("Tỷ trọng doanh thu của Mỹ", "%",
     f"select sum(sales) filter (where r.country = 'United States') / sum(sales) from {F} f join gold.dim_region r using (region_key)"),
    ("Tỷ trọng đơn có từ 2 subcategory", "%",
     f"select avg((n >= 2)::int) from (select order_id, count(distinct p.subcategory) n from {F} f join gold.dim_product p using (product_key) group by 1)"),
    ("Năm trong order_id lệch so với năm order_date", "năm",
     "select min(year(order_date::date) - split_part(order_id, '-', 2)::int) from bronze.ecom_sales"),
    ("Số order_id gắn nhiều ngày hoặc nhiều khách", "đơn",
     "select count(*) from (select order_id from bronze.ecom_sales group by 1 having count(distinct order_date) > 1 or count(distinct customer_id) > 1)"),
    ("Tăng trưởng doanh thu 2023 so với 2022", "%",
     "select max(revenue) filter (where year = 2023) / max(revenue) filter (where year = 2022) - 1 from mart.mart_kpi_overview"),
    ("Thay đổi lợi nhuận 2023 so với 2022", "%",
     "select max(profit) filter (where year = 2023) / max(profit) filter (where year = 2022) - 1 from mart.mart_kpi_overview"),
]
def show(v, unit):
    if unit == "%":
        return f"{v * 100:.1f}%".replace(".", ",")
    if float(v).is_integer():
        return f"{int(v):,}".replace(",", ".")
    return f"{v:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


extra = pd.DataFrame([{"Chỉ tiêu": n, "Đơn vị": u, "Giá trị": float(one(s)), "SQL": s} for n, u, s in EXTRA])
extra.insert(3, "Hiển thị", [show(v, u) for v, u in zip(extra["Giá trị"], extra["Đơn vị"])])
extra.to_csv(TABLES_DIR / "B_extra_numbers.csv", index=False, encoding="utf-8-sig")
(ROOT / "sql" / "checks" / "extra_numbers.sql").write_text(
    "-- Các con số dẫn trong phần chữ của báo cáo (sinh tự động bởi scripts/09_checks.py)\n\n"
    + "\n\n".join(f"-- {n} ({u})\n{s};" for n, u, s in EXTRA) + "\n", encoding="utf-8")
print(extra[["Chỉ tiêu", "Giá trị"]].to_string())

update_key_numbers("checks", {
    "extra_numbers": dict(zip(extra["Chỉ tiêu"], extra["Giá trị"])),
    "all_reconciled": bool(ok),
    "reconciliation": b43.astype(str).to_dict(orient="records"),
    "tables_per_schema": counts.to_dict(orient="records"),
    "last_build": tests.to_dict(orient="records"),
    "n_dim_rows": {t: one(f"select count(*) from gold.{t}") for t in
                   ["dim_date", "dim_customer", "dim_product", "dim_region", "dim_segment", "dim_flags",
                    "fact_sales", "fact_monthly_snapshot"]},
})
con.close()
if not ok:
    raise SystemExit("ĐỐI CHIẾU KHÔNG KHỚP")
print("Đối chiếu: tất cả khớp.")
