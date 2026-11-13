"""Profiling chất lượng dữ liệu theo 4 chiều (đầy đủ, duy nhất/chính xác, nhất quán, kịp thời).

Đầu ra:
  results/tables/B2.4_profiling.csv      bảng profiling trên Bronze
  results/tables/B4.2_bronze_vs_silver.csv  đối chiếu trước và sau xử lý Silver
  results/figures/H2.2_quality_rules.png  số dòng vi phạm theo quy tắc
  results/figures/H2.3_profit_discount_hist.png
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from common import FIG_DIR, TABLES_DIR, connect, update_key_numbers
from style import apply_style, save

apply_style()
con = connect(read_only=True)


def one(sql: str):
    return con.execute(sql).fetchone()[0]


# Bronze: mọi cột VARCHAR, ép kiểu tại chỗ để kiểm tra
S = "bronze.ecom_sales"
rules = [
    # chiều, kiểm tra, câu SQL đếm số dòng vi phạm, ghi chú xử lý
    ("Đầy đủ", "NULL ở 11 cột giao dịch",
     f"select count(*) from {S} where row_id is null or order_id is null or order_date is null "
     f"or customer_id is null or segment is null or region_code is null or product_code is null "
     f"or quantity is null or sales is null or discount is null or profit is null",
     "Không cần xử lý"),
    ("Đầy đủ", "customer.gender NULL",
     "select count(*) from bronze.customer where gender is null", "Gán 'Unknown', giữ bản ghi"),
    ("Đầy đủ", "NULL ở các cột customer khác",
     "select count(*) from bronze.customer where birth_date is null or email_address is null "
     "or annual_income is null or occupation is null or education_level is null",
     "Không cần xử lý"),
    ("Duy nhất", "row_id trùng",
     f"select count(*) - count(distinct row_id) from {S}", "Không cần xử lý"),
    ("Duy nhất", "customer_id / product_code / region_code trùng",
     "select (select count(*) - count(distinct customer_id) from bronze.customer)"
     " + (select count(*) - count(distinct product_code) from bronze.product)"
     " + (select count(*) - count(distinct region_code) from bronze.region)",
     "Không cần xử lý"),
    ("Duy nhất", "Khách trùng theo email hoặc (họ tên + ngày sinh)",
     "select (select count(*) - count(distinct lower(email_address)) from bronze.customer)"
     " + (select count(*) - count(distinct (first_name, last_name, birth_date)) from bronze.customer)",
     "Không cần xử lý"),
    ("Chính xác", "quantity <= 0, sales <= 0, discount ngoài [0, 1]",
     f"select count(*) from {S} where quantity::int <= 0 or sales::double <= 0 "
     f"or discount::double < 0 or discount::double > 1",
     "Không cần xử lý"),
    ("Chính xác", "profit < 0",
     f"select count(*) from {S} where profit::double < 0", "Giữ nguyên (giao dịch lỗ thật)"),
    ("Chính xác", "profit > sales",
     f"select count(*) from {S} where profit::double > sales::double", "Không cần xử lý"),
    ("Nhất quán", "customer_id không có trong customer",
     f"select count(*) from {S} s left join bronze.customer c using (customer_id) where c.customer_id is null",
     "Không cần xử lý"),
    ("Nhất quán", "product_code không có trong product",
     f"select count(*) from {S} s left join bronze.product p using (product_code) where p.product_code is null",
     "Giữ mã gốc, cờ is_valid_product, product_key = -1"),
    ("Nhất quán", "region_code không có trong region",
     f"select count(*) from {S} s left join bronze.region r using (region_code) where r.region_code is null",
     "Giữ mã gốc, cờ is_valid_region, region_key = -1"),
    ("Nhất quán", "Năm trong order_id khác năm của order_date",
     f"select count(*) from {S} where split_part(order_id, '-', 2) <> substr(order_date, 1, 4)",
     "Bỏ qua; order_date là trục thời gian duy nhất"),
    ("Nhất quán", "Khách thuộc > 1 phân khúc",
     f"select count(*) from (select customer_id from {S} group by 1 having count(distinct segment) > 1)",
     "Không cần xử lý"),
    ("Kịp thời", "order_date ngoài 2020-01-01 .. 2023-12-31",
     f"select count(*) from {S} where order_date::date < date '2020-01-01' or order_date::date > date '2023-12-31'",
     "Không cần xử lý"),
    ("Nhất quán", "order_id gắn với nhiều ngày hoặc nhiều khách",
     f"select count(*) from (select order_id from {S} group by 1 "
     f"having count(distinct order_date) > 1 or count(distinct customer_id) > 1)",
     "Giữ nguyên; ghi chú hạn chế khi đếm đơn"),
]

rows = []
for dim, check, sql, action in rules:
    rows.append({"Chiều": dim, "Kiểm tra": check, "Số vi phạm": one(sql), "Xử lý": action})
prof = pd.DataFrame(rows)
prof.to_csv(TABLES_DIR / "B2.4_profiling.csv", index=False, encoding="utf-8-sig")
print(prof.to_string())

# Số mã không khớp (distinct) và số dòng chịu ảnh hưởng
bad_prod_codes = one(f"select count(distinct product_code) from {S} s left join bronze.product p using (product_code) where p.product_code is null")
bad_reg_codes = one(f"select count(distinct region_code) from {S} s left join bronze.region r using (region_code) where r.region_code is null")
gender_rows = one(f"select count(*) from {S} s join bronze.customer c using (customer_id) where c.gender is null")

# B4.2: đối chiếu trước (Bronze) và sau (Silver)
SV = "silver.silver_sales_integrated"
b42 = pd.DataFrame([
    ("Dòng giao dịch", one(f"select count(*) from {S}"), one(f"select count(*) from {SV}")),
    ("row_id phân biệt", one(f"select count(distinct row_id) from {S}"), one(f"select count(distinct row_id) from {SV}")),
    ("Tổng sales (USD)", one(f"select sum(sales::decimal(14,2)) from {S}"), one(f"select sum(sales) from {SV}")),
    ("Tổng profit (USD)", one(f"select sum(profit::decimal(14,2)) from {S}"), one(f"select sum(profit) from {SV}")),
    ("Khách thiếu gender", one("select count(*) from bronze.customer where gender is null"),
     one("select count(*) from silver.silver_customer where gender is null")),
    ("Khách gán 'Unknown'", 0, one("select count(*) from silver.silver_customer where gender = 'Unknown'")),
    ("Dòng không khớp product", rules and prof.loc[10, "Số vi phạm"], one(f"select count(*) from {SV} where not is_valid_product")),
    ("Dòng không khớp region", prof.loc[11, "Số vi phạm"], one(f"select count(*) from {SV} where not is_valid_region")),
    ("Dòng lợi nhuận âm", prof.loc[7, "Số vi phạm"], one(f"select count(*) from {SV} where is_loss")),
], columns=["Chỉ tiêu", "Trước xử lý (Bronze)", "Sau xử lý (Silver)"])
b42.to_csv(TABLES_DIR / "B4.2_bronze_vs_silver.csv", index=False, encoding="utf-8-sig")
print(b42.to_string())

update_key_numbers("profiling", {
    "null_transaction_cells": int(prof.loc[0, "Số vi phạm"]),
    "gender_null_customers": int(prof.loc[1, "Số vi phạm"]),
    "gender_null_rows_affected": int(gender_rows),
    "bad_product_codes": int(bad_prod_codes),
    "bad_region_codes": int(bad_reg_codes),
    "bad_product_rows": int(prof.loc[10, "Số vi phạm"]),
    "bad_region_rows": int(prof.loc[11, "Số vi phạm"]),
    "loss_rows": int(prof.loc[7, "Số vi phạm"]),
    "orderid_year_mismatch_rows": int(prof.loc[12, "Số vi phạm"]),
    "dup_customer_email_or_name": int(prof.loc[5, "Số vi phạm"]),
    "orderid_year_offset": int(one(f"select min(year(order_date::date) - split_part(order_id, '-', 2)::int) from {S}")),
    "orderid_year_offset_max": int(one(f"select max(year(order_date::date) - split_part(order_id, '-', 2)::int) from {S}")),
    "order_ids_multi_date_or_customer": int(prof.loc[15, "Số vi phạm"]),
})

# H2.2: số dòng vi phạm theo quy tắc (chỉ các quy tắc có vi phạm + một số quy tắc đạt để đối chứng)
fig, ax = plt.subplots(figsize=(10, 5.5))
p = prof.copy()
p["Nhãn"] = p["Chiều"] + ": " + p["Kiểm tra"]
p = p.iloc[::-1]
colors = ["#c0392b" if v > 0 else "#7f8c8d" for v in p["Số vi phạm"]]
ax.barh(p["Nhãn"], p["Số vi phạm"], color=colors)
ax.set_xscale("symlog", linthresh=10)
for i, v in enumerate(p["Số vi phạm"]):
    ax.text(v if v > 0 else 0.1, i, f" {v:,}".replace(",", "."), va="center", fontsize=9)
ax.set_xlabel("Số dòng vi phạm (thang log)")
ax.set_title("Số dòng vi phạm theo từng quy tắc chất lượng (dữ liệu Bronze)")
save(fig, "H2.2_quality_rules")

# H2.3: phân phối profit và discount
df = con.execute(f"select profit::double profit, discount::double discount from {S}").df()
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
axes[0].hist(df["profit"].clip(-300, 600), bins=60, color="#2e86c1")
axes[0].axvline(0, color="#c0392b", lw=1.5, ls="--")
axes[0].set_title("Phân phối lợi nhuận mỗi dòng (cắt ở -300 và 600 USD)")
axes[0].set_xlabel("Profit (USD)")
axes[0].set_ylabel("Số dòng")
axes[1].hist(df["discount"], bins=[i / 20 for i in range(19)], color="#28b463", rwidth=0.9)
axes[1].set_title("Phân phối mức chiết khấu")
axes[1].set_xlabel("Discount")
axes[1].xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
save(fig, "H2.3_profit_discount_hist")
con.close()
