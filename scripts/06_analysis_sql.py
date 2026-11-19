"""Phân tích bổ sung bằng SQL: giỏ hàng (B4.6), cohort (H4.6), sắp xếp theo order_date (B4.4).

Đầu ra: results/tables/B4.6_market_basket.csv, B4.4_sort_benchmark.csv, B4.4b_explain_*.txt,
        results/figures/H4.6_cohort_heatmap.png
"""

import statistics
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common import IS_MOTHERDUCK, ROOT, TABLES_DIR, connect, update_key_numbers
from style import apply_style, save

apply_style()
con = connect()
SQL_DIR = ROOT / "sql" / "analysis"

# 1) Giỏ hàng
basket = con.execute((SQL_DIR / "market_basket_subcategory.sql").read_text(encoding="utf-8")).df()
basket.to_csv(TABLES_DIR / "B4.6_market_basket.csv", index=False, encoding="utf-8-sig")
multi = con.execute("""
    select avg((n_sub >= 2)::int) from (
      select order_id, count(distinct p.subcategory) n_sub
      from gold.fact_sales f join gold.dim_product p using (product_key) group by 1)
""").fetchone()[0]
print(basket.head(10).round(4).to_string())

# 1b) Apriori theo đúng các bước của Slide 5: L1 -> sinh C2 -> tỉa theo tính chất Apriori -> đếm -> L2 -> L3,
#     sau đó sinh luật X => Y và lọc theo minconf. Item = subcategory, giao dịch = order_id.
from itertools import combinations

tx = (con.execute("""
        select f.order_id, list(distinct p.subcategory) items
        from gold.fact_sales f join gold.dim_product p using (product_key)
        where p.product_key <> -1 group by f.order_id""").df()["items"].map(frozenset).tolist())
N_TX = len(tx)


def apriori(transactions, minsup, max_k=3):
    """Trả về {itemset: support} của mọi tập phổ biến kích thước 1..max_k."""
    counts = {}
    for t in transactions:
        for i in t:
            counts[frozenset([i])] = counts.get(frozenset([i]), 0) + 1
    level = {s: c / N_TX for s, c in counts.items() if c / N_TX >= minsup}
    freq, k, stats = dict(level), 2, [{"k": 1, "candidates": len(counts), "frequent": len(level)}]
    while level and k <= max_k:
        prev = list(level)
        cand = {a | b for a, b in combinations(prev, 2) if len(a | b) == k}
        # tính chất Apriori: mọi tập con (k-1) phải phổ biến
        cand = {c for c in cand if all(frozenset(s) in level for s in combinations(c, k - 1))}
        cnt = dict.fromkeys(cand, 0)
        for t in transactions:
            if len(t) >= k:
                for c in cand:
                    if c <= t:
                        cnt[c] += 1
        level = {s: c / N_TX for s, c in cnt.items() if c / N_TX >= minsup}
        stats.append({"k": k, "candidates": len(cand), "frequent": len(level)})
        freq.update(level)
        k += 1
    return freq, stats


def rules_from(freq, minconf):
    rows = []
    for s, sup in freq.items():
        if len(s) < 2:
            continue
        for r in range(1, len(s)):
            for x in combinations(s, r):
                x = frozenset(x)
                y = s - x
                conf = sup / freq[x]
                if conf >= minconf:
                    rows.append({"antecedent": ", ".join(sorted(x)), "consequent": ", ".join(sorted(y)),
                                 "support": sup, "confidence": conf, "lift": conf / freq[y]})
    return pd.DataFrame(rows, columns=["antecedent", "consequent", "support", "confidence", "lift"])


import pandas as pd

ap_rows = []
ap_detail = {}
for minsup in (0.01, 0.005, 0.002):
    freq, stats = apriori(tx, minsup)
    for st in stats:
        ap_rows.append({"minsup": minsup, **st})
    for minconf in (0.8, 0.5, 0.2):
        r = rules_from(freq, minconf)
        ap_rows.append({"minsup": minsup, "k": "luật", "minconf": minconf, "rules": len(r),
                        "max_lift": r.lift.max() if len(r) else None})
    ap_detail[minsup] = (freq, rules_from(freq, 0.0))
ap = pd.DataFrame(ap_rows)
print(ap.to_string())
ap.to_csv(TABLES_DIR / "B4.6d_apriori_summary.csv", index=False, encoding="utf-8-sig")

# Bảng tóm tắt gọn cho báo cáo: mỗi minsup một dòng
summ = []
for minsup, (freq, allrules) in ap_detail.items():
    summ.append({
        "minsup": minsup, "min_orders": int(np.ceil(minsup * N_TX)),
        "L1": sum(len(s) == 1 for s in freq), "L2": sum(len(s) == 2 for s in freq),
        "L3": sum(len(s) == 3 for s in freq),
        "rules_conf80": int((allrules.confidence >= 0.8).sum()),
        "rules_conf50": int((allrules.confidence >= 0.5).sum()),
        "rules_conf20": int((allrules.confidence >= 0.2).sum()),
        "max_conf": allrules.confidence.max() if len(allrules) else None,
        "max_lift": allrules.lift.max() if len(allrules) else None,
    })
summ = pd.DataFrame(summ)
print(summ.to_string())
summ.to_csv(TABLES_DIR / "B4.6e_apriori_thresholds.csv", index=False, encoding="utf-8-sig")
top_rules = ap_detail[0.002][1].sort_values("confidence", ascending=False).head(8)
top_rules.to_csv(TABLES_DIR / "B4.6f_apriori_top_rules.csv", index=False, encoding="utf-8-sig")
con.execute("create schema if not exists ml")
con.execute("create or replace table ml.apriori_rules as select * from (select * from top_rules)")
n_items = len({i for t in tx for i in t})
avg_items = float(np.mean([len(t) for t in tx]))

# 2) Cohort
coh = con.execute("select * from mart.mart_customer_cohort order by cohort_year, active_year").df()
piv = coh.pivot(index="cohort_year", columns="years_since_first", values="retention_rate")
sizes = coh.groupby("cohort_year").cohort_size.first()
fig, ax = plt.subplots(figsize=(7.5, 4))
im = ax.imshow(piv.values, cmap="Blues", vmin=0, vmax=0.3)
for i in range(piv.shape[0]):
    for j in range(piv.shape[1]):
        v = piv.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0%}", ha="center", va="center",
                    color="white" if v > 0.6 else "#1a1a1a", fontsize=10)
ax.set_xticks(range(piv.shape[1]), [f"Năm +{c}" for c in piv.columns])
ax.set_yticks(range(piv.shape[0]), [f"{y} (n={sizes[y]:,})".replace(",", ".") for y in piv.index])
ax.set_xlabel("Số năm kể từ năm mua đầu tiên")
ax.set_ylabel("Cohort (năm mua đầu tiên)")
ax.set_title("Tỷ lệ khách quay lại theo cohort năm mua đầu tiên")
ax.grid(False)
fig.colorbar(im, ax=ax, format=matplotlib.ticker.PercentFormatter(1.0))
save(fig, "H4.6_cohort_heatmap")
coh.to_csv(TABLES_DIR / "B4.6b_cohort.csv", index=False, encoding="utf-8-sig")

# Benchmark đo bố cục lưu trữ của file DuckDB cục bộ; trên MotherDuck (chạy ở GitHub Actions)
# thì bỏ qua và giữ kết quả benchmark cũ.
bdf = None
if not IS_MOTHERDUCK:
    # 3) Sắp xếp theo order_date: so sánh bảng sắp xếp và không sắp xếp, ở quy mô thật (x1)
    #    và quy mô nhân bản x20 (~1 triệu dòng) vì DuckDB chia row group 122.880 dòng.
    query_tpl = (SQL_DIR / "explain_sort_benchmark.sql").read_text(encoding="utf-8")
    con.execute("create schema if not exists bench")
    con.execute("set threads = 1")
    bench = []
    for scale in (1, 20):
        con.execute(f"""create or replace table bench.sorted_x{scale} as
                        select f.* from gold.fact_sales f, range({scale}) order by order_date""")
        con.execute(f"""create or replace table bench.unsorted_x{scale} as
                        select f.* from gold.fact_sales f, range({scale}) order by hash(row_id, range)""")
        con.execute("checkpoint")
        for kind in ("unsorted", "sorted"):
            tbl = f"bench.{kind}_x{scale}"
            q = query_tpl.replace("{table}", tbl)
            for _ in range(3):
                con.execute(q).fetchall()
            times = []
            for _ in range(15):
                t0 = time.perf_counter()
                con.execute(q).fetchall()
                times.append((time.perf_counter() - t0) * 1000)
            plan = con.execute("explain analyze " + q).fetchall()
            plan_txt = "\n".join(r[1] for r in plan)
            (TABLES_DIR / f"B4.4b_explain_{kind}_x{scale}.txt").write_text(plan_txt, encoding="utf-8")
            rows = con.execute(f"select count(*) from {tbl}").fetchone()[0]
            matched = con.execute(
                f"select count(*) from {tbl} where order_date between date '2023-10-01' and date '2023-12-31'"
            ).fetchone()[0]
            bench.append({"scale": f"x{scale}", "table_rows": rows, "layout": kind,
                          "rows_matching_filter": matched,
                          "median_ms": statistics.median(times), "min_ms": min(times)})
    con.execute("set threads = 4")
    import pandas as pd

    bdf = pd.DataFrame(bench)
    bdf["speedup_vs_unsorted"] = bdf.groupby("scale").median_ms.transform("max") / bdf.median_ms
    print(bdf.round(2).to_string())
    bdf.to_csv(TABLES_DIR / "B4.4_sort_benchmark.csv", index=False, encoding="utf-8-sig")
    con.execute("drop schema bench cascade")

top = basket.head(5)
update_key_numbers("analysis_sql", {
    "share_orders_multi_subcategory": float(multi),
    "basket_top5": top.round(4).to_dict(orient="records"),
    "basket_max_lift": float(basket.lift.max()) if len(basket) else None,
    "apriori_n_transactions": N_TX,
    "apriori_n_items": n_items,
    "apriori_avg_items_per_order": avg_items,
    "apriori_thresholds": summ.round(4).to_dict(orient="records"),
    "apriori_top_rules": top_rules.round(4).to_dict(orient="records"),
    "cohort": coh.round(4).to_dict(orient="records"),
    **({"sort_benchmark": bdf.round(3).to_dict(orient="records")} if bdf is not None else {}),
})
con.close()
