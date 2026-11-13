"""Biểu đồ và bảng mô tả cho Chương 2 và Chương 4, đọc từ Gold và data mart (không đọc CSV).

Hình: H2.4, H2.5, H2.6, H2.7, H4.3, H4.4, H4.5
Bảng: B2.5_*, B4.5_* (P&L phân khúc, thị trường, biên theo năm)
"""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import TABLES_DIR, connect, update_key_numbers
from style import PALETTE, apply_style, fmt_usd, save

apply_style()
con = connect(read_only=True)
q = lambda s: con.execute(s).df()
PCT = matplotlib.ticker.PercentFormatter(1.0)
USD = matplotlib.ticker.FuncFormatter(fmt_usd)

# ---------- B2.5 / H2.4: doanh thu, lợi nhuận, biên theo năm ----------
kpi = q("select * from mart.mart_kpi_overview order by year")
kpi.to_csv(TABLES_DIR / "B2.5a_kpi_by_year.csv", index=False, encoding="utf-8-sig")
y = kpi[kpi.year > 0]
fig, ax = plt.subplots(figsize=(8.5, 4.8))
x = np.arange(len(y))
ax.bar(x - 0.2, y.revenue, 0.4, label="Doanh thu", color=PALETTE[0])
ax.bar(x + 0.2, y.profit, 0.4, label="Lợi nhuận", color=PALETTE[2])
ax.set_xticks(x, y.year.astype(str))
ax.yaxis.set_major_formatter(USD)
ax.set_ylabel("USD")
ax2 = ax.twinx()
ax2.plot(x, y.profit_margin, color=PALETTE[3], marker="o", lw=2, label="Biên lợi nhuận")
for xi, m in zip(x, y.profit_margin):
    ax2.annotate(f"{m:.1%}", (xi, m), textcoords="offset points", xytext=(0, 8), ha="center",
                 color=PALETTE[3], fontweight="bold")
ax2.set_ylim(0, 0.25)
ax2.yaxis.set_major_formatter(PCT)
ax2.grid(False)
ax2.spines["right"].set_visible(True)
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="upper left")
ax.set_title("Doanh thu, lợi nhuận và biên lợi nhuận theo năm (2020-2023)")
save(fig, "H2.4_revenue_profit_margin_by_year")

# ---------- B2.5b / H2.5: theo nhóm chiết khấu ----------
disc = q("""
    select discount_band_order, discount_band, sum(total_lines) lines, sum(revenue) revenue,
           sum(profit) profit, sum(profit)/sum(revenue) margin, sum(loss_lines)/sum(total_lines) loss_rate
    from mart.mart_discount_analysis group by 1, 2 order by 1
""")
disc["share_lines"] = disc.lines / disc.lines.sum()
disc.to_csv(TABLES_DIR / "B2.5b_discount_bands.csv", index=False, encoding="utf-8-sig")
fig, ax = plt.subplots(figsize=(8.5, 4.6))
colors = [PALETTE[2] if m >= 0 else PALETTE[3] for m in disc.margin]
ax.bar(disc.discount_band, disc.margin, color=colors)
ax.axhline(0, color="#333333", lw=1)
for i, (m, n) in enumerate(zip(disc.margin, disc.lines)):
    ax.text(i, m + (0.012 if m >= 0 else -0.03), f"{m:.1%}\n({n:,} dòng)".replace(",", "."),
            ha="center", fontsize=9)
ax.yaxis.set_major_formatter(PCT)
ax.set_ylim(disc.margin.min() - 0.08, disc.margin.max() + 0.08)
ax.set_xlabel("Nhóm chiết khấu")
ax.set_ylabel("Biên lợi nhuận")
ax.set_title("Biên lợi nhuận theo nhóm chiết khấu (toàn kỳ 2020-2023)")
save(fig, "H2.5_margin_by_discount_band")

# ---------- H2.6: cơ cấu theo ngành hàng, thị trường, phân khúc ----------
cat = q("""select category k, sum(revenue) revenue, sum(profit) profit from mart.mart_product_profitability
           where category <> 'Unknown' group by 1 order by 2 desc""")
mkt = q("""select market k, sum(revenue) revenue, sum(profit) profit from mart.mart_segment_profitability
           where market <> 'Unknown' group by 1 order by 2 desc""")
seg = q("""select segment k, sum(revenue) revenue, sum(profit) profit from mart.mart_segment_profitability
           group by 1 order by 2 desc""")
fig, axes = plt.subplots(1, 3, figsize=(14, 4.6))
for ax, d, title in ((axes[0], cat, "Ngành hàng"), (axes[1], mkt, "Thị trường"), (axes[2], seg, "Phân khúc")):
    d["margin"] = d.profit / d.revenue
    d["share"] = d.revenue / d.revenue.sum()
    ax.bar(d.k, d.revenue, color=PALETTE[0])
    ax.yaxis.set_major_formatter(USD)
    ax.set_title(f"{title}: doanh thu và biên")
    ax.tick_params(axis="x", rotation=30)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    ax2 = ax.twinx()
    ax2.plot(d.k, d.margin, color=PALETTE[3], marker="o")
    ax2.set_ylim(0, 0.3)
    ax2.yaxis.set_major_formatter(PCT)
    ax2.grid(False)
    for i, m in enumerate(d.margin):
        ax2.annotate(f"{m:.1%}", (i, m), textcoords="offset points", xytext=(0, 7), ha="center",
                     fontsize=8, color=PALETTE[3])
    d.to_csv(TABLES_DIR / f"B2.5c_mix_{title}.csv", index=False, encoding="utf-8-sig")
save(fig, "H2.6_mix_category_market_segment")

# ---------- H2.7: bản đồ doanh thu theo quốc gia (bong bóng theo tọa độ) ----------
geo = q("""select country, market, avg(country_latitude) lat, avg(country_longitude) lon,
                  sum(revenue) revenue, sum(profit)/sum(revenue) margin
           from mart.mart_geographic_performance where market <> 'Unknown' group by 1, 2""")
fig, ax = plt.subplots(figsize=(11, 5.5))
for i, (mk, g) in enumerate(geo.groupby("market")):
    ax.scatter(g.lon, g.lat, s=g.revenue / 1500, alpha=0.6, label=mk, color=PALETTE[i], edgecolor="white")
for _, r in geo.nlargest(8, "revenue").iterrows():
    ax.annotate(r.country, (r.lon, r.lat), fontsize=8, ha="center", va="bottom")
ax.set_xlim(-180, 180)
ax.set_ylim(-60, 80)
ax.set_xlabel("Kinh độ")
ax.set_ylabel("Vĩ độ")
ax.set_title(f"Doanh thu theo quốc gia ({geo.country.nunique()} quốc gia; kích thước bong bóng = doanh thu)")
ax.legend(markerscale=0.4, loc="lower left")
save(fig, "H2.7_country_bubble_map")
geo.nlargest(15, "revenue").to_csv(TABLES_DIR / "B2.5d_top15_countries.csv", index=False, encoding="utf-8-sig")

# ---------- H4.3: biên theo từng mức chiết khấu, đường 0 ----------
lvl = q("""select discount, sum(total_lines) lines, sum(revenue) revenue, sum(profit) profit,
                  sum(profit)/sum(revenue) margin, sum(loss_lines)/sum(total_lines) loss_rate
           from mart.mart_discount_analysis group by 1 order by 1""")
lvl.to_csv(TABLES_DIR / "B4.3_margin_by_discount_level.csv", index=False, encoding="utf-8-sig")
fig, ax = plt.subplots(figsize=(10, 4.8))
ax.bar(lvl.discount.astype(float), lvl.margin, width=0.035,
       color=[PALETTE[2] if m >= 0 else PALETTE[3] for m in lvl.margin])
ax.axhline(0, color="#333333", lw=1.2)
ax2 = ax.twinx()
ax2.plot(lvl.discount.astype(float), lvl.loss_rate, color=PALETTE[1], marker="o", ms=4,
         label="Tỷ lệ dòng lỗ")
ax2.yaxis.set_major_formatter(PCT)
ax2.set_ylim(0, 1.05)
ax2.grid(False)
ax2.legend(loc="upper right")
ax.xaxis.set_major_formatter(PCT)
ax.yaxis.set_major_formatter(PCT)
ax.set_xlabel("Mức chiết khấu")
ax.set_ylabel("Biên lợi nhuận")
ax.set_title("Biên lợi nhuận và tỷ lệ dòng lỗ theo từng mức chiết khấu")
save(fig, "H4.3_margin_by_discount_level")

# ---------- B4.5: P&L theo phân khúc và theo năm ----------
pl = q("""select segment, year, sum(revenue) revenue, sum(implied_cost) implied_cost, sum(profit) profit,
                 sum(profit)/sum(revenue) margin, sum(total_orders) orders,
                 sum(loss_amount) loss_amount
          from mart.mart_segment_profitability group by 1, 2 order by 1, 2""")
pl_tot = q("""select segment, 0 as year, sum(revenue) revenue, sum(implied_cost) implied_cost, sum(profit) profit,
                     sum(profit)/sum(revenue) margin, sum(total_orders) orders, sum(loss_amount) loss_amount
              from mart.mart_segment_profitability group by 1 order by 1""")
pl_all = pd.concat([pl, pl_tot])
pl_all["share_revenue"] = pl_all.revenue / pl_all.groupby("year").revenue.transform("sum")
pl_all["share_profit"] = pl_all.profit / pl_all.groupby("year").profit.transform("sum")
pl_all.to_csv(TABLES_DIR / "B4.5_segment_pnl.csv", index=False, encoding="utf-8-sig")
seg_cust = q("""select segment, count(*) customers, avg(frequency) avg_orders, avg(monetary) avg_monetary,
                       avg(profit) avg_profit_per_customer, avg(avg_discount) avg_discount,
                       sum(monetary)/sum(frequency) aov
                from mart.mart_customer_value group by 1""")
seg_disc = q("""select segment, avg(discount) avg_discount,
                       avg((discount > 0.3)::int) deep_share
                from (select segment_name as segment, discount from gold.fact_sales f
                      join gold.dim_segment s using (segment_key)) group by 1""")
seg_cust = seg_cust.merge(seg_disc, on="segment", suffixes=("_cust", ""))
seg_cust.to_csv(TABLES_DIR / "B4.5d_segment_customers.csv", index=False, encoding="utf-8-sig")

# ---------- H4.4 + B4.5b: thị trường 2022 vs 2023 ----------
mk = q("""select market, year, sum(revenue) revenue, sum(profit) profit, sum(profit)/sum(revenue) margin
          from mart.mart_segment_profitability where market <> 'Unknown' group by 1, 2""")
deep = q("""select r.market, d.year, avg((f.discount > 0.3)::int) deep_share, avg(f.discount) avg_discount
            from gold.fact_sales f join gold.dim_region r using (region_key) join gold.dim_date d using (date_key)
            where r.market <> 'Unknown' group by 1, 2""")
mk = mk.merge(deep, on=["market", "year"])
mk = mk.sort_values(["market", "year"])
mk["growth"] = mk.groupby("market").revenue.pct_change()
mk.to_csv(TABLES_DIR / "B4.5b_market_by_year.csv", index=False, encoding="utf-8-sig")
w = mk[mk.year.isin([2022, 2023])].pivot(index="market", columns="year",
                                          values=["growth", "margin", "deep_share", "revenue"])
w = w.sort_values(("revenue", 2023), ascending=False)
fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
x = np.arange(len(w))
for ax, metric, title in ((axes[0], "growth", "Tăng trưởng doanh thu so với năm trước"),
                          (axes[1], "margin", "Biên lợi nhuận")):
    b1 = ax.bar(x - 0.2, w[(metric, 2022)], 0.4, label="2022", color=PALETTE[0])
    b2 = ax.bar(x + 0.2, w[(metric, 2023)], 0.4, label="2023", color=PALETTE[1])
    ax.bar_label(b1, labels=[f"{v:.1%}" for v in w[(metric, 2022)]], fontsize=8)
    ax.bar_label(b2, labels=[f"{v:.1%}" for v in w[(metric, 2023)]], fontsize=8)
    ax.set_xticks(x, w.index)
    ax.yaxis.set_major_formatter(PCT)
    ax.set_title(title)
    ax.legend()
fig.suptitle("Thị trường: tăng trưởng và biên lợi nhuận 2022 so với 2023", fontweight="bold")
save(fig, "H4.4_market_growth_margin")

# ---------- H4.5 + B4.5c: biên theo năm, dòng không giảm giá vs có giảm giá ----------
nd = q("""select year, (discount_band_order = 1) as no_discount, sum(revenue) revenue, sum(profit) profit,
                 sum(profit)/sum(revenue) margin, sum(total_lines) lines
          from mart.mart_discount_analysis group by 1, 2 order by 2 desc, 1""")
nd.to_csv(TABLES_DIR / "B4.5c_margin_nodiscount_vs_discount.csv", index=False, encoding="utf-8-sig")
fig, ax = plt.subplots(figsize=(8.5, 4.6))
for flag, label, col in ((True, "Dòng không giảm giá", PALETTE[2]), (False, "Dòng có giảm giá", PALETTE[3])):
    g = nd[nd.no_discount == flag]
    ax.plot(g.year.astype(str), g.margin, marker="o", lw=2.2, color=col, label=label)
    for yr, m in zip(g.year.astype(str), g.margin):
        ax.annotate(f"{m:.1%}", (yr, m), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
ax.axhline(0, color="#333333", lw=1)
ax.yaxis.set_major_formatter(PCT)
ax.set_title("Biên lợi nhuận theo năm: dòng không giảm giá và dòng có giảm giá")
ax.legend()
save(fig, "H4.5_margin_nodiscount_vs_discount")

# Biên theo năm ở mọi chiều (bằng chứng Q5: giảm ở mọi nơi)
dims = []
for dim, sql in (
    ("market", "select r.market k, d.year, sum(sales) s, sum(profit) p from gold.fact_sales f join gold.dim_region r using (region_key) join gold.dim_date d using (date_key) where r.market <> 'Unknown' group by 1, 2"),
    ("category", "select p.category k, d.year, sum(sales) s, sum(profit) p from gold.fact_sales f join gold.dim_product p using (product_key) join gold.dim_date d using (date_key) where p.category <> 'Unknown' group by 1, 2"),
    ("segment", "select s.segment_name k, d.year, sum(sales) s, sum(profit) p from gold.fact_sales f join gold.dim_segment s using (segment_key) join gold.dim_date d using (date_key) group by 1, 2"),
):
    t = q(sql)
    t["margin"] = t.p / t.s
    t["dimension"] = dim
    dims.append(t)
dm = pd.concat(dims).pivot_table(index=["dimension", "k"], columns="year", values="margin").reset_index()
dm["change_2023_vs_2022"] = dm[2023] - dm[2022]
dm.to_csv(TABLES_DIR / "B4.5e_margin_by_year_all_dims.csv", index=False, encoding="utf-8-sig")

# Giá bán bình quân và chiết khấu bình quân theo năm (Q5: không đổi)
price = q("""select d.year, sum(sales)/sum(quantity) avg_unit_price, avg(discount) avg_discount,
                    avg((discount > 0.3)::int) deep_share, sum(quantity)/count(distinct order_id) units_per_order,
                    sum(implied_cost)/sum(quantity) cost_per_unit,
                    sum(implied_cost) filter (where discount = 0) / sum(quantity) filter (where discount = 0) cost_per_unit_nodisc,
                    sum(sales) filter (where discount = 0) / sum(quantity) filter (where discount = 0) price_per_unit_nodisc
             from gold.fact_sales f join gold.dim_date d using (date_key) group by 1 order by 1""")
price.to_csv(TABLES_DIR / "B4.5f_price_discount_cost_by_year.csv", index=False, encoding="utf-8-sig")

rfm = q("""select rfm_segment, count(*) customers, count(*) / sum(count(*)) over () share_customers,
                  avg(recency_days) recency_days, avg(frequency) frequency, avg(monetary) monetary,
                  sum(profit) profit, sum(profit) / sum(sum(profit)) over () share_profit
           from mart.mart_customer_value group by 1 order by profit desc""")
rfm.to_csv(TABLES_DIR / "B4.6c_rfm_segments.csv", index=False, encoding="utf-8-sig")
seg_q = q("""select segment, sum(quantity) quantity, sum(total_lines) lines
             from mart.mart_segment_profitability group by 1""")
seg_q["share_quantity"] = seg_q.quantity / seg_q.quantity.sum()
seg_q["share_lines"] = seg_q.lines / seg_q.lines.sum()
seg_q.to_csv(TABLES_DIR / "B2.5e_segment_quantity_share.csv", index=False, encoding="utf-8-sig")

ov = kpi.set_index("year")
update_key_numbers("descriptive", {
    "kpi_by_year": kpi.round(4).to_dict(orient="records"),
    "discount_bands": disc.round(4).to_dict(orient="records"),
    "category_mix": cat.round(4).to_dict(orient="records"),
    "market_mix": mkt.round(4).to_dict(orient="records"),
    "segment_mix": seg.round(4).to_dict(orient="records"),
    "segment_pnl": pl_all.round(4).to_dict(orient="records"),
    "segment_customers": seg_cust.round(4).to_dict(orient="records"),
    "market_by_year": mk.round(4).to_dict(orient="records"),
    "nodiscount_vs_discount": nd.round(4).to_dict(orient="records"),
    "margin_by_year_all_dims": dm.round(4).to_dict(orient="records"),
    "price_by_year": price.round(4).to_dict(orient="records"),
    "n_countries": int(geo.country.nunique()),
    "n_products_sold": int(q("select count(distinct product_key) n from gold.fact_sales where product_key <> -1").n[0]),
    "top_countries": geo.nlargest(10, "revenue").round(4).to_dict(orient="records"),
})
con.close()
