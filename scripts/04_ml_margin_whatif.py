"""ML 2 + 3 - Hồi quy biên lợi nhuận và what-if mức chiết khấu (trả lời Q1, hỗ trợ Q5).

Đầu vào : ml.ml_features (grain row_id; không có sales/profit trong đặc trưng)
Chia    : train 2020-2022, test 2023 (theo thời gian, không ngẫu nhiên)
Mô hình : LinearRegression (one-hot) và HistGradientBoostingRegressor
Đầu ra  : ml.margin_model_metrics, ml.margin_feature_importance, ml.whatif_discount,
          ml.whatif_discount_cap, ml.margin_drift_by_month, ml.model_registry
          results/tables/B4.8_*.csv, results/figures/H4.8_*.png, H4.9_*.png, H4.9b_*.png
"""

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder

from common import MODEL_DIR, TABLES_DIR, connect, register_model, update_key_numbers
from style import apply_style, save

SEED = 42
NUM = ["discount", "quantity", "prior_orders", "lines_in_order", "annual_income", "month"]
CAT = ["category", "subcategory", "market", "segment", "gender", "age_group",
       "occupation", "education_level", "marital_status", "is_home_owner"]
FEATURES = NUM + CAT
LEVELS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]

apply_style()
con = connect()
df = con.execute("select * from ml.ml_features").df()
df["is_home_owner"] = df["is_home_owner"].astype(str)
for c in CAT:
    df[c] = df[c].astype(str)

train = df[df.split == "train"].reset_index(drop=True)
test = df[df.split == "test"].reset_index(drop=True)
print(f"train={len(train):,}  test={len(test):,}")


def make_linear():
    pre = ColumnTransformer([
        ("num", "passthrough", NUM),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CAT),
    ])
    return Pipeline([("pre", pre), ("model", LinearRegression())])


def make_hgb(num=NUM):
    feats = num + CAT
    pre = ColumnTransformer([
        ("num", "passthrough", num),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CAT),
    ], verbose_feature_names_out=False)
    cat_mask = [False] * len(num) + [True] * len(CAT)
    # Ràng buộc đơn điệu: chiết khấu tăng thì biên không tăng (đúng logic kinh doanh, giúp what-if mượt)
    mono = [-1] + [0] * (len(feats) - 1)
    model = HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
        categorical_features=cat_mask, monotonic_cst=mono, random_state=SEED)
    return Pipeline([("pre", pre), ("model", model)])


models = {"LinearRegression": make_linear(), "HistGradientBoosting": make_hgb()}
metrics = []
for name, m in models.items():
    m.fit(train[FEATURES], train.target_margin)
    for split, d in (("train 2020-2022", train), ("test 2023", test)):
        p = m.predict(d[FEATURES])
        metrics.append({
            "model": name, "split": split,
            "R2": r2_score(d.target_margin, p),
            "MAE": mean_absolute_error(d.target_margin, p),
            "mean_actual_margin": d.target_margin.mean(),
            "mean_predicted_margin": p.mean(),
            # sai lệch biên có trọng số doanh thu = biên dự báo - biên thực tế ở cấp tổng
            "weighted_margin_bias": (np.sum(p * d.label_sales) - d.label_profit.sum()) / d.label_sales.sum(),
        })
met = pd.DataFrame(metrics)
print(met.round(4).to_string())
met.to_csv(TABLES_DIR / "B4.8_margin_model_metrics.csv", index=False, encoding="utf-8-sig")
con.execute("create or replace table ml.margin_model_metrics as select * from met")

# Model drift: mô hình học trên 2020-2022 dự báo biên từng tháng 2023 so với thực tế
hgb = models["HistGradientBoosting"]
df["pred_margin_v1"] = hgb.predict(df[FEATURES])
drift = (df.assign(pred_profit=df.pred_margin_v1 * df.label_sales)
           .assign(ym=pd.to_datetime(df.order_date).dt.to_period("M").dt.to_timestamp())
           .groupby("ym").agg(sales=("label_sales", "sum"), profit=("label_profit", "sum"),
                              pred_profit=("pred_profit", "sum"))
           .reset_index())
drift["actual_margin"] = drift.profit / drift.sales
drift["predicted_margin"] = drift.pred_profit / drift.sales
drift["gap"] = drift.actual_margin - drift.predicted_margin
con.execute("create or replace table ml.margin_drift_by_month as select * from drift")

fig, ax = plt.subplots(figsize=(10, 4.5))
ax.plot(drift.ym, drift.actual_margin, label="Biên thực tế", color="#1f4e79", lw=2)
ax.plot(drift.ym, drift.predicted_margin, label="Biên dự báo (mô hình học trên 2020-2022)",
        color="#e67e22", lw=2, ls="--")
ax.axvspan(pd.Timestamp("2023-01-01"), pd.Timestamp("2023-12-31"), color="#f5b7b1", alpha=0.3,
           label="Tập kiểm tra 2023")
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax.set_title("Model drift: biên lợi nhuận thực tế và dự báo theo tháng")
ax.legend(loc="lower left")
save(fig, "H4.8b_margin_drift")

# Permutation importance trên tập test (mẫu 6.000 dòng)
samp = test.sample(6000, random_state=SEED)
pi = permutation_importance(hgb, samp[FEATURES], samp.target_margin, n_repeats=5,
                            random_state=SEED, scoring="r2")
imp = (pd.DataFrame({"feature": FEATURES, "importance": pi.importances_mean, "std": pi.importances_std})
       .sort_values("importance", ascending=False))
print(imp.round(4).to_string())
imp.to_csv(TABLES_DIR / "B4.8b_feature_importance.csv", index=False, encoding="utf-8-sig")
con.execute("create or replace table ml.margin_feature_importance as select * from imp")

fig, ax = plt.subplots(figsize=(8, 5))
top = imp.head(12).iloc[::-1]
ax.barh(top.feature, top.importance, xerr=top["std"], color="#1f4e79")
ax.set_xlabel("Mức giảm R² khi xáo trộn đặc trưng")
ax.set_title("Mức quan trọng của đặc trưng (permutation importance, test 2023)")
save(fig, "H4.8_feature_importance")

# What-if: mô hình triển khai học trên toàn bộ 2020-2023, có thêm đặc trưng year để nắm mức biên
# riêng của 2023 (do drift), áp vào các dòng năm 2023
NUM_PROD = NUM + ["year"]
FEATURES_PROD = NUM_PROD + CAT
prod = make_hgb(NUM_PROD).fit(df[FEATURES_PROD], df.target_margin)
base = df[df.year == 2023].copy()
wi_rows = []
for lvl in LEVELS:
    sc = base.copy()
    sc["discount"] = lvl
    sc["pred_margin"] = prod.predict(sc[FEATURES_PROD])
    sc["pred_profit"] = sc.pred_margin * sc.label_sales
    for (cat, mkt), g in sc.groupby(["category", "market"]):
        wi_rows.append({"discount_level": lvl, "category": cat, "market": mkt,
                        "sales": g.label_sales.sum(), "pred_profit": g.pred_profit.sum()})
wi = pd.DataFrame(wi_rows)
wi = wi[(wi.category != "Unknown") & (wi.market != "Unknown")]
wi["pred_margin"] = wi.pred_profit / wi.sales
con.execute("create or replace table ml.whatif_discount as select * from wi")

by_cat = wi.groupby(["discount_level", "category"]).agg(sales=("sales", "sum"), pred_profit=("pred_profit", "sum")).reset_index()
by_cat["pred_margin"] = by_cat.pred_profit / by_cat.sales
piv = by_cat.pivot(index="category", columns="discount_level", values="pred_margin")
piv.to_csv(TABLES_DIR / "B4.9a_whatif_margin_by_category.csv", encoding="utf-8-sig")
by_mkt = wi.groupby(["discount_level", "market"]).agg(sales=("sales", "sum"), pred_profit=("pred_profit", "sum")).reset_index()
by_mkt["pred_margin"] = by_mkt.pred_profit / by_mkt.sales
piv_m = by_mkt.pivot(index="market", columns="discount_level", values="pred_margin")
piv_m.to_csv(TABLES_DIR / "B4.9b_whatif_margin_by_market.csv", encoding="utf-8-sig")
print(piv.round(3).to_string())
print(piv_m.round(3).to_string())

# Mức chiết khấu cao nhất mà biên dự báo còn dương (hòa vốn) theo ngành hàng
fine = []
for lvl in np.round(np.arange(0, 0.61, 0.025), 3):
    sc = base.copy()
    sc["discount"] = lvl
    sc["pred_profit"] = prod.predict(sc[FEATURES_PROD]) * sc.label_sales
    g = sc.groupby("category").agg(s=("label_sales", "sum"), p=("pred_profit", "sum"))
    for cat, r in g.iterrows():
        fine.append({"category": cat, "discount_level": lvl, "pred_margin": r.p / r.s})
fine = pd.DataFrame(fine)
breakeven = (fine[fine.pred_margin > 0].groupby("category").discount_level.max()
             .rename("max_discount_positive_margin").reset_index())
breakeven = breakeven[breakeven.category != "Unknown"]
print(breakeven.to_string())

fig, ax = plt.subplots(figsize=(9, 5))
for cat, g in fine[fine.category != "Unknown"].groupby("category"):
    ax.plot(g.discount_level, g.pred_margin, marker=".", label=cat)
ax.axhline(0, color="#c0392b", lw=1.2, ls="--")
ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax.set_xlabel("Mức chiết khấu áp cho toàn bộ dòng năm 2023")
ax.set_ylabel("Biên lợi nhuận dự báo")
ax.set_title("What-if: biên lợi nhuận dự báo theo mức chiết khấu, mỗi ngành hàng một đường")
ax.legend()
save(fig, "H4.9_whatif_discount")

# Kịch bản trần chiết khấu: các dòng 2023 vượt trần được đưa về trần, giữ nguyên doanh thu
cap_rows = []
actual_2023 = base.label_profit.sum()
pred_actual = (prod.predict(base[FEATURES_PROD]) * base.label_sales).sum()
for cap in [0.2, 0.3, 0.4, 0.5]:
    sc = base.copy()
    sc["discount"] = sc.discount.clip(upper=cap)
    pp = (prod.predict(sc[FEATURES_PROD]) * sc.label_sales).sum()
    cap_rows.append({"cap": cap, "rows_affected": int((base.discount > cap).sum()),
                     "pred_profit_baseline": pred_actual, "pred_profit_capped": pp,
                     "uplift": pp - pred_actual, "uplift_pct": (pp - pred_actual) / pred_actual,
                     "pred_margin_capped": pp / base.label_sales.sum()})
cap_df = pd.DataFrame(cap_rows)
print(cap_df.round(3).to_string())
cap_df.to_csv(TABLES_DIR / "B4.9c_discount_cap_scenarios.csv", index=False, encoding="utf-8-sig")
con.execute("create or replace table ml.whatif_discount_cap as select * from cap_df")

fig, ax = plt.subplots(figsize=(7.5, 4.2))
ax.bar([f"Trần {int(c*100)}%" for c in cap_df.cap], cap_df.uplift, color="#28b463")
for i, (u, pct) in enumerate(zip(cap_df.uplift, cap_df.uplift_pct)):
    ax.text(i, u, f"+{u/1000:,.0f}K\n(+{pct:.0%})", ha="center", va="bottom", fontsize=9)
ax.set_ylabel("Lợi nhuận tăng thêm dự báo (USD)")
ax.set_title("Kịch bản trần chiết khấu năm 2023 (giữ nguyên doanh thu)")
ax.margins(y=0.2)
save(fig, "H4.9b_discount_cap")

# Lưu mô hình
for name, m, ver in (("margin_linear", models["LinearRegression"], "margin_lr_v1"),
                     ("margin_hgb", hgb, "margin_hgb_v1"),
                     ("margin_hgb_production", prod, "margin_hgb_full_v1")):
    path = MODEL_DIR / f"{ver}.joblib"
    joblib.dump(m, path)
    mm = met[met.model == ("LinearRegression" if "linear" in name else "HistGradientBoosting")]
    register_model(con, name, ver, type(m.named_steps["model"]).__name__,
                   {"features": FEATURES_PROD if "production" in name else FEATURES,
                    "train": "2020-2023" if "production" in name else "2020-2022"},
                   {r.split: {"R2": r.R2, "MAE": r.MAE} for r in mm.itertuples()},
                   str(path.relative_to(MODEL_DIR.parent)))

def pick(model, split, col):
    return float(met[(met.model == model) & (met.split == split)][col].iloc[0])

update_key_numbers("margin_model", {
    "n_train": len(train), "n_test": len(test),
    "lr_r2_train": pick("LinearRegression", "train 2020-2022", "R2"),
    "lr_r2_test": pick("LinearRegression", "test 2023", "R2"),
    "lr_mae_test": pick("LinearRegression", "test 2023", "MAE"),
    "hgb_r2_train": pick("HistGradientBoosting", "train 2020-2022", "R2"),
    "hgb_r2_test": pick("HistGradientBoosting", "test 2023", "R2"),
    "hgb_mae_train": pick("HistGradientBoosting", "train 2020-2022", "MAE"),
    "hgb_mae_test": pick("HistGradientBoosting", "test 2023", "MAE"),
    "hgb_bias_test": pick("HistGradientBoosting", "test 2023", "weighted_margin_bias"),
    "top_features": imp.head(5)[["feature", "importance"]].round(4).to_dict(orient="records"),
    "breakeven_discount_by_category": dict(zip(breakeven.category, breakeven.max_discount_positive_margin)),
    "whatif_margin_by_category": {str(k): {str(c): round(float(v), 4) for c, v in row.items()} for k, row in piv.iterrows()},
    "cap_scenarios": cap_df.round(4).to_dict(orient="records"),
    "actual_profit_2023": float(actual_2023),
    "drift_2023_actual_margin": float(drift[drift.ym.dt.year == 2023].profit.sum() / drift[drift.ym.dt.year == 2023].sales.sum()),
    "drift_2023_pred_margin": float(drift[drift.ym.dt.year == 2023].pred_profit.sum() / drift[drift.ym.dt.year == 2023].sales.sum()),
})
con.close()
