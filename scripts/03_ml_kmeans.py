"""ML 1 - Phân cụm khách hàng RFM + lợi nhuận bằng K-Means (trả lời Q4).

Đầu vào : mart.mart_customer_value
Đầu ra  : ml.customer_clusters, ml.cluster_profile, ml.kmeans_k_selection, ml.model_registry
          results/figures/H4.7_kmeans_k_selection.png, H4.7b_cluster_scatter.png
          results/tables/B4.7_cluster_profile.csv
"""

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from common import MODEL_DIR, TABLES_DIR, connect, register_model, update_key_numbers
from style import apply_style, save

SEED = 42
VERSION = "kmeans_rfm_v1"
FEATURES = ["recency_days", "frequency", "monetary", "profit"]
K_FINAL = 4

apply_style()
con = connect()
cust = con.execute("select * from mart.mart_customer_value").df()


def signed_log(x):
    # log có dấu: giữ thứ tự cho profit âm, nén đuôi dài của monetary/frequency
    return np.sign(x) * np.log1p(np.abs(x))


X = cust[FEATURES].astype(float).values
prep = make_pipeline(FunctionTransformer(signed_log), StandardScaler())
Xs = prep.fit_transform(X)

# Chọn k: silhouette (cao tốt) và Davies-Bouldin (thấp tốt)
rows = []
for k in range(2, 7):
    km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Xs)
    rows.append({
        "k": k,
        "silhouette": silhouette_score(Xs, km.labels_, sample_size=8000, random_state=SEED),
        "davies_bouldin": davies_bouldin_score(Xs, km.labels_),
        "inertia": km.inertia_,
    })
ksel = pd.DataFrame(rows)
print(ksel.round(4).to_string())
con.execute("create schema if not exists ml")
con.execute("create or replace table ml.kmeans_k_selection as select * from ksel")
ksel.to_csv(TABLES_DIR / "B4.7a_k_selection.csv", index=False, encoding="utf-8-sig")

fig, ax1 = plt.subplots(figsize=(8, 4.5))
ax1.plot(ksel["k"], ksel["silhouette"], marker="o", color="#1f4e79", label="Silhouette (cao tốt)")
ax1.set_xlabel("Số cụm k")
ax1.set_ylabel("Silhouette")
ax2 = ax1.twinx()
ax2.plot(ksel["k"], ksel["davies_bouldin"], marker="s", color="#e67e22", label="Davies-Bouldin (thấp tốt)")
ax2.set_ylabel("Davies-Bouldin")
ax2.grid(False)
ax1.axvline(K_FINAL, color="#7f8c8d", ls=":", lw=1)
lines = ax1.get_legend_handles_labels()[0] + ax2.get_legend_handles_labels()[0]
labels = ax1.get_legend_handles_labels()[1] + ax2.get_legend_handles_labels()[1]
ax1.legend(lines, labels, loc="upper right")
ax1.set_title("Chọn số cụm K-Means theo Silhouette và Davies-Bouldin")
save(fig, "H4.7_kmeans_k_selection")

# Mô hình cuối: k = 4 (dễ diễn giải); lưu kèm bước tiền xử lý
model = make_pipeline(FunctionTransformer(signed_log), StandardScaler(),
                      KMeans(n_clusters=K_FINAL, n_init=10, random_state=SEED))
model.fit(X)
cust["cluster"] = model.predict(X)  # predict() để gán nhãn cụm

# Đặt tên cụm theo đặc điểm tâm cụm
prof = cust.groupby("cluster").agg(
    customers=("customer_key", "size"),
    recency_days=("recency_days", "mean"),
    frequency=("frequency", "mean"),
    monetary=("monetary", "mean"),
    profit=("profit", "mean"),
    total_profit=("profit", "sum"),
    total_revenue=("monetary", "sum"),
    avg_discount=("avg_discount", "mean"),
    annual_income=("annual_income", "median"),
).reset_index()
prof["margin"] = prof["total_profit"] / prof["total_revenue"]


# Đặt tên theo thứ hạng đặc điểm tâm cụm (quy tắc tất định, tên không trùng):
#   biên thấp nhất -> nhóm gây lỗ; tần suất cao nhất -> nhóm trung thành;
#   hai cụm còn lại phân theo monetary.
name_map = {}
rest = prof.copy()
c_loss = rest.loc[rest.margin.idxmin(), "cluster"]
name_map[c_loss] = "Săn giảm giá, gây lỗ"
rest = rest[rest.cluster != c_loss]
c_loyal = rest.loc[rest.frequency.idxmax(), "cluster"]
name_map[c_loyal] = "Trung thành, giá trị cao"
rest = rest[rest.cluster != c_loyal].sort_values("monetary", ascending=False)
labels_rest = ["Mua một lần, giá trị cao", "Mua một lần, giá trị thấp", "Khác"]
for lbl, cl in zip(labels_rest, rest.cluster):
    name_map[cl] = lbl
prof["cluster_name"] = prof["cluster"].map(name_map)
cust["cluster_name"] = cust["cluster"].map(name_map)

# Thuộc tính nhân khẩu học nổi bật mỗi cụm
def top_share(col):
    t = cust.groupby("cluster")[col].agg(lambda s: s.value_counts(normalize=True).idxmax())
    return t


prof["top_occupation"] = prof["cluster"].map(top_share("occupation"))
prof["top_segment"] = prof["cluster"].map(top_share("segment"))
prof["share_customers"] = prof["customers"] / prof["customers"].sum()
prof["share_profit"] = prof["total_profit"] / prof["total_profit"].sum()
prof["repeat_rate"] = prof["cluster"].map(cust.groupby("cluster")["is_repeat_customer"].mean())
prof = prof.sort_values("total_profit", ascending=False)
print(prof.round(3).to_string())

out = cust[["customer_key", "cluster", "cluster_name"]].copy()
out["model_version"] = VERSION
con.execute("create or replace table ml.customer_clusters as select * from out")
con.execute("create or replace table ml.cluster_profile as select * from prof")

b47 = prof[["cluster", "cluster_name", "customers", "share_customers", "recency_days", "frequency",
            "monetary", "profit", "margin", "repeat_rate", "avg_discount", "annual_income",
            "top_occupation", "top_segment", "share_profit"]]
b47.to_csv(TABLES_DIR / "B4.7_cluster_profile.csv", index=False, encoding="utf-8-sig")

# Hình phân tán: recency vs monetary, tô màu theo cụm
fig, ax = plt.subplots(figsize=(8.5, 5))
sample = cust.sample(min(6000, len(cust)), random_state=SEED)
for cl, g in sample.groupby("cluster_name"):
    ax.scatter(g["recency_days"], g["monetary"], s=6, alpha=0.5, label=cl)
ax.set_yscale("log")
ax.set_xlabel("Recency (ngày kể từ đơn cuối đến 31/12/2023)")
ax.set_ylabel("Monetary (USD, thang log)")
ax.set_title(f"Phân cụm khách hàng K-Means (k = {K_FINAL}), mẫu 6.000 khách")
ax.legend(markerscale=3, fontsize=8, loc="lower left")
save(fig, "H4.7b_cluster_scatter")

artifact = MODEL_DIR / f"{VERSION}.joblib"
joblib.dump(model, artifact)
best = ksel.loc[ksel.silhouette.idxmax()]
final = ksel.set_index("k").loc[K_FINAL]
register_model(con, "customer_kmeans", VERSION, "KMeans + StandardScaler",
               {"k": K_FINAL, "features": FEATURES, "transform": "signed_log", "seed": SEED},
               {"silhouette": final.silhouette, "davies_bouldin": final.davies_bouldin},
               str(artifact.relative_to(MODEL_DIR.parent)))

update_key_numbers("kmeans", {
    "k_best_silhouette": int(best.k),
    "silhouette_best": round(float(best.silhouette), 3),
    "k_final": K_FINAL,
    "silhouette_k_final": round(float(final.silhouette), 3),
    "db_k_final": round(float(final.davies_bouldin), 3),
    "clusters": b47.round(4).to_dict(orient="records"),
})
con.close()
