"""ML 5 - Phân lớp: dự đoán khách mua lần đầu có quay lại trong 365 ngày không (Q4).

Đầu vào : ml.ml_first_order_features (grain khách hàng, chỉ thông tin của đơn đầu)
Chia    : theo cohort - train 2020-2021, test 2022 (không chia ngẫu nhiên)
Mô hình : DecisionTreeClassifier (entropy ~ C4.5, cây nông để đọc được luật) và Naive Bayes
          (CategoricalNB trên đặc trưng rời rạc hóa) - hai thuật toán phân lớp của Slide 5
Đầu ra  : ml.repeat_classifier_metrics, ml.repeat_scores, ml.repeat_by_first_discount,
          ml.repeat_tree_rules, ml.model_registry
          results/tables/B4.19_*.csv, results/figures/H4.12_*.png, H4.13_*.png
"""

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (confusion_matrix, f1_score, precision_score, recall_score,
                             roc_auc_score)
from sklearn.naive_bayes import CategoricalNB
from sklearn.preprocessing import OrdinalEncoder
from sklearn.tree import DecisionTreeClassifier, export_text

from common import MODEL_DIR, TABLES_DIR, connect, register_model, update_key_numbers
from style import PALETTE, apply_style, save

SEED = 42
NUM = ["first_sales", "first_quantity", "first_lines", "first_discount", "first_n_categories"]
CAT = ["first_main_category", "market", "segment", "gender", "age_group", "income_band",
       "occupation", "education_level", "is_home_owner"]

apply_style()
con = connect()
df = con.execute("select * from ml.ml_first_order_features").df()
df["is_home_owner"] = df["is_home_owner"].astype(str)
df["y"] = df["returned_365d"].astype(int)
for c in CAT:
    df[c] = df[c].astype(str)
train, test = df[df.split == "train"].reset_index(drop=True), df[df.split == "test"].reset_index(drop=True)
base_rate = test.y.mean()
print(f"train={len(train):,} (quay lại {train.y.mean():.1%})  test={len(test):,} (quay lại {base_rate:.1%})")

# ---------- Decision Tree (entropy) ----------
enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1).fit(df[CAT])


def tree_X(d):
    return pd.DataFrame(np.c_[d[NUM].astype(float).values, enc.transform(d[CAT])], columns=NUM + CAT)


tree = DecisionTreeClassifier(criterion="entropy", max_depth=4, min_samples_leaf=150,
                              class_weight="balanced", random_state=SEED)
tree.fit(tree_X(train), train.y)
p_tree = tree.predict_proba(tree_X(test))[:, 1]

# ---------- Naive Bayes: rời rạc hóa đặc trưng số rồi dùng CategoricalNB ----------
bins = {
    "first_sales": [-1, 50, 100, 200, 400, 1e9],
    "first_quantity": [-1, 3, 6, 10, 20, 1e9],
    "first_lines": [-1, 1, 2, 3, 1e9],
    "first_discount": [-0.01, 0, 0.10, 0.20, 0.30, 0.50, 1],
    "first_n_categories": [-1, 1, 2, 1e9],
}


def nb_frame(d):
    out = d[CAT].copy()
    for c, b in bins.items():
        out[c] = pd.cut(d[c].astype(float), b, labels=False).astype(str)
    return out


nb_enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1).fit(nb_frame(df))
nb = CategoricalNB(alpha=1.0, min_categories=[len(c) for c in nb_enc.categories_])
nb.fit(nb_enc.transform(nb_frame(train)), train.y)
p_nb = nb.predict_proba(nb_enc.transform(nb_frame(test)))[:, 1]


def metrics(name, y, p, thr=0.5):
    pred = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
    top = np.argsort(-p)[: int(len(p) * 0.2)]
    return {"model": name, "AUC": roc_auc_score(y, p), "F1": f1_score(y, pred),
            "precision": precision_score(y, pred), "recall": recall_score(y, pred),
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "return_rate_top20": y.iloc[top].mean() if hasattr(y, "iloc") else y[top].mean(),
            "lift_top20": (y.iloc[top].mean()) / y.mean()}


# Naive Bayes cho xác suất lệch về lớp đa số -> dùng ngưỡng = tỷ lệ quay lại của tập train
met = pd.DataFrame([
    metrics("Decision Tree (entropy, sâu 4)", test.y, p_tree, 0.5),
    metrics("Naive Bayes (Categorical)", test.y, p_nb, train.y.mean()),
])
met["base_rate"] = base_rate
print(met.round(3).to_string())
met.to_csv(TABLES_DIR / "B4.19_repeat_classifier_metrics.csv", index=False, encoding="utf-8-sig")
con.execute("create or replace table ml.repeat_classifier_metrics as select * from met")

# Luật if-then của cây (đọc được như luật C4.5)
rules = export_text(tree, feature_names=NUM + CAT, decimals=3, show_weights=False)
(TABLES_DIR / "B4.19b_tree_rules.txt").write_text(rules, encoding="utf-8")
cat_levels = {c: list(enc.categories_[i]) for i, c in enumerate(CAT)}
NUM_LABEL = {"first_sales": "doanh thu đơn đầu", "first_quantity": "số lượng đơn đầu",
             "first_lines": "số dòng đơn đầu", "first_discount": "chiết khấu đơn đầu",
             "first_n_categories": "số ngành hàng đơn đầu"}


def readable_rules(model):
    """Duyệt cây, đổi mã thứ tự của biến phân loại về tên thật; mỗi lá là một luật IF-THEN."""
    t = model.tree_
    names = NUM + CAT
    out = []

    def fmt(f, v):
        return f"{v:.1%}" if f == "first_discount" else f"{v:,.1f}"

    def render(cond):
        parts = []
        for f, c in cond.items():
            if f in CAT:
                vals = c
                if len(vals) < len(cat_levels[f]):
                    parts.append(f"{f} ∈ {{{', '.join(vals)}}}")
            else:
                lo, hi = c
                lab = NUM_LABEL.get(f, f)
                if lo is not None and hi is not None:
                    parts.append(f"{fmt(f, lo)} < {lab} ≤ {fmt(f, hi)}")
                elif lo is not None:
                    parts.append(f"{lab} > {fmt(f, lo)}")
                elif hi is not None:
                    parts.append(f"{lab} ≤ {fmt(f, hi)}")
        return " VÀ ".join(parts) if parts else "(mọi khách)"

    def walk(node, cond):
        if t.children_left[node] == -1:
            ys = train.y.values[leaf_ids == node]
            out.append({"rule": render(cond), "customers_train": len(ys), "return_rate_train": ys.mean(),
                        "prediction": "Quay lại" if t.value[node][0].argmax() == 1 else "Không quay lại"})
            return
        f, thr = names[t.feature[node]], t.threshold[node]
        left, right = dict(cond), dict(cond)
        if f in CAT:
            cur = cond.get(f, cat_levels[f])
            left[f] = [v for v in cur if cat_levels[f].index(v) <= thr]
            right[f] = [v for v in cur if cat_levels[f].index(v) > thr]
        else:
            lo, hi = cond.get(f, (None, None))
            left[f] = (lo, thr if hi is None else min(hi, thr))
            right[f] = (thr if lo is None else max(lo, thr), hi)
        walk(t.children_left[node], left)
        walk(t.children_right[node], right)

    leaf_ids = model.apply(tree_X(train))
    walk(0, {})
    return pd.DataFrame(out)


# Gộp các nhánh trùng dự đoán chỉ để đọc; giữ nguyên toàn bộ lá
rule_df = readable_rules(tree).sort_values("return_rate_train", ascending=False)
rule_df.to_csv(TABLES_DIR / "B4.19b_tree_rules.csv", index=False, encoding="utf-8-sig")
con.execute("create or replace table ml.repeat_tree_rules as select * from rule_df")
print(rule_df.round(3).to_string())
mkt = df.groupby("market").agg(customers=("y", "size"), return_rate=("y", "mean"),
                               avg_first_discount=("first_discount", "mean")).reset_index() \
        .sort_values("return_rate", ascending=False)
mkt.to_csv(TABLES_DIR / "B4.19f_repeat_by_market.csv", index=False, encoding="utf-8-sig")

# Mức quan trọng đặc trưng của cây (information gain)
fi = pd.DataFrame({"feature": NUM + CAT, "importance": tree.feature_importances_}) \
    .sort_values("importance", ascending=False)
fi.to_csv(TABLES_DIR / "B4.19c_tree_importance.csv", index=False, encoding="utf-8-sig")
print(fi.round(3).to_string())

# Tỷ lệ quay lại theo nhóm chiết khấu của đơn đầu (toàn bộ khách có đủ 365 ngày quan sát)
disc = (df.groupby(["first_discount_band_order", "first_discount_band"])
          .agg(customers=("y", "size"), returned=("y", "sum"), return_rate=("y", "mean"),
               avg_first_sales=("first_sales", "mean"))
          .reset_index())
disc.to_csv(TABLES_DIR / "B4.19d_repeat_by_first_discount.csv", index=False, encoding="utf-8-sig")
con.execute("create or replace table ml.repeat_by_first_discount as select * from disc")
print(disc.round(3).to_string())

# Điểm của mô hình cây cho tập test (dùng để chọn khách cần chăm sóc)
scores = test[["customer_key", "cohort_year", "y"]].copy()
scores["score_tree"] = p_tree
scores["score_nb"] = p_nb
scores["decile"] = pd.qcut(scores.score_tree.rank(method="first"), 10, labels=False)
scores["decile"] = 10 - scores["decile"]  # 1 = điểm cao nhất
con.execute("create or replace table ml.repeat_scores as select * from scores")
dec = scores.groupby("decile").agg(customers=("y", "size"), return_rate=("y", "mean")).reset_index()
dec["lift"] = dec.return_rate / base_rate
dec.to_csv(TABLES_DIR / "B4.19e_decile_lift.csv", index=False, encoding="utf-8-sig")

# H4.12: tỷ lệ quay lại theo nhóm chiết khấu đơn đầu
fig, ax = plt.subplots(figsize=(8.5, 4.5))
bars = ax.bar(disc.first_discount_band, disc.return_rate,
              color=[PALETTE[2] if r > disc.return_rate.iloc[0] else PALETTE[0] for r in disc.return_rate])
ax.axhline(df.y.mean(), color=PALETTE[3], ls="--", lw=1.2, label=f"Trung bình {df.y.mean():.1%}")
ax.bar_label(bars, labels=[f"{r:.1%}\n(n={n:,})".replace(",", ".") for r, n in zip(disc.return_rate, disc.customers)],
             fontsize=8)
ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
ax.set_ylim(0, disc.return_rate.max() * 1.3)
ax.set_xlabel("Mức chiết khấu của đơn hàng đầu tiên")
ax.set_ylabel("Tỷ lệ quay lại trong 365 ngày")
ax.set_title("Tỷ lệ khách quay lại theo mức chiết khấu của đơn đầu (cohort 2020-2022)")
ax.legend(loc="upper right")
save(fig, "H4.12_repeat_by_first_discount")

# H4.13: ma trận nhầm lẫn của cây + lift theo decile
fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
cm = confusion_matrix(test.y, (p_tree >= 0.5).astype(int))
axes[0].imshow(cm, cmap="Blues")
for i in range(2):
    for j in range(2):
        axes[0].text(j, i, f"{cm[i, j]:,}".replace(",", "."), ha="center", va="center",
                     color="white" if cm[i, j] > cm.max() / 2 else "#1a1a1a", fontsize=12)
axes[0].set_xticks([0, 1], ["Dự đoán: không", "Dự đoán: quay lại"])
axes[0].set_yticks([0, 1], ["Thực tế: không", "Thực tế: quay lại"])
axes[0].grid(False)
axes[0].set_title("Ma trận nhầm lẫn - Decision Tree (test 2022)")
axes[1].bar(dec.decile.astype(str), dec.return_rate, color=PALETTE[0])
axes[1].axhline(base_rate, color=PALETTE[3], ls="--", lw=1.2, label=f"Tỷ lệ chung {base_rate:.1%}")
axes[1].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
axes[1].set_xlabel("Nhóm 10% theo điểm dự đoán (1 = điểm cao nhất)")
axes[1].set_ylabel("Tỷ lệ quay lại thực tế")
axes[1].set_title("Tỷ lệ quay lại theo decile điểm dự đoán")
axes[1].legend()
save(fig, "H4.13_classifier_confusion_lift")

# Lưu mô hình + registry
for name, m, ver, mm in (("repeat_tree", tree, "repeat_tree_v1", met.iloc[0]),
                         ("repeat_nb", nb, "repeat_nb_v1", met.iloc[1])):
    path = MODEL_DIR / f"{ver}.joblib"
    joblib.dump(m, path)
    register_model(con, name, ver, type(m).__name__,
                   {"features": NUM + CAT, "train": "cohort 2020-2021", "test": "cohort 2022"},
                   {"AUC": mm.AUC, "F1": mm.F1, "lift_top20": mm.lift_top20},
                   str(path.relative_to(MODEL_DIR.parent)))

update_key_numbers("classification", {
    "n_train": len(train), "n_test": len(test),
    "return_rate_train": float(train.y.mean()), "return_rate_test": float(base_rate),
    "return_rate_all": float(df.y.mean()),
    "metrics": met.round(4).to_dict(orient="records"),
    "tree_importance": fi.head(5).round(4).to_dict(orient="records"),
    "repeat_by_first_discount": disc.round(4).to_dict(orient="records"),
    "repeat_by_market": mkt.round(4).to_dict(orient="records"),
    "tree_rules": rule_df.round(4).to_dict(orient="records"),
    "decile_lift": dec.round(4).to_dict(orient="records"),
})
con.close()
