import io

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import sklearn
import streamlit as st

from lib import C_LOSS, C_NEUTRAL, C_PROFIT, C_REVENUE, cursor, page_header, pct, q, source, usd

page_header(
    "Dự đoán trực tiếp",
    "Nhập thông tin, ứng dụng nạp mô hình đã huấn luyện từ kho (bảng ml.model_artifacts trên MotherDuck) "
    "và dự đoán ngay trên máy chủ. Mô hình được GitHub Actions huấn luyện lại mỗi lần pipeline chạy.",
)

if source() != "motherduck":
    st.info("Trang này cần kết nối MotherDuck để nạp mô hình. Bản snapshot trong repo không chứa mô hình.")
    st.stop()

LABELS = {
    "category": "Ngành hàng", "subcategory": "Nhóm sản phẩm", "market": "Thị trường", "segment": "Phân khúc",
    "gender": "Giới tính", "age_group": "Nhóm tuổi", "occupation": "Nghề nghiệp",
    "education_level": "Học vấn", "marital_status": "Hôn nhân", "is_home_owner": "Có nhà riêng",
    "discount": "Chiết khấu", "quantity": "Số lượng", "prior_orders": "Số đơn trước đó",
    "lines_in_order": "Số dòng trong đơn", "annual_income": "Thu nhập năm (USD)", "month": "Tháng",
    "year": "Năm",
    "first_main_category": "Ngành hàng chính đơn đầu", "income_band": "Nhóm thu nhập",
    "first_sales": "Giá trị đơn đầu (USD)", "first_quantity": "Số lượng đơn đầu",
    "first_lines": "Số dòng đơn đầu", "first_discount": "Chiết khấu TB đơn đầu",
    "first_n_categories": "Số ngành hàng trong đơn đầu",
}


@st.cache_resource(ttl=3600, show_spinner="Đang nạp mô hình từ kho...")
def load_model(version: str):
    cur = cursor()
    try:
        row = cur.execute("SELECT artifact, sklearn_version, published_at FROM model_artifacts "
                          "WHERE model_version = ?", [version]).fetchone()
    finally:
        cur.close()
    if row is None:
        return None, None, None
    return joblib.load(io.BytesIO(row[0])), row[1], row[2]


def options(view: str) -> dict[str, list[str]]:
    df = q(f"SELECT feature, value, n FROM {view} WHERE value <> 'Unknown' ORDER BY feature, n DESC")
    return {f: g.value.tolist() for f, g in df.groupby("feature")}


def defaults(view: str) -> dict[str, pd.Series]:
    return {r.feature: r for r in q(f"SELECT * FROM {view}").itertuples()}


def version_note(ver, published):
    if ver and ver != sklearn.__version__:
        st.warning(f"Mô hình huấn luyện bằng scikit-learn {ver}, ứng dụng đang dùng {sklearn.__version__}.")
    st.caption(f"Mô hình xuất bản lúc {str(published)[:16]} UTC · scikit-learn {ver}")


tab_margin, tab_repeat = st.tabs(["Biên lợi nhuận của một dòng hàng", "Khách mới có quay lại không"])

# ---------------- Biên lợi nhuận ----------------
with tab_margin:
    model, ver, published = load_model("margin_hgb_full_v1")
    if model is None:
        st.error("Chưa có mô hình margin_hgb_full_v1 trong ml.model_artifacts. Chạy pipeline trên GitHub Actions.")
        st.stop()
    opt = options("margin_options")
    dft = defaults("margin_defaults")
    prods = q("SELECT * FROM product_options WHERE category <> 'Unknown' ORDER BY 1, 2")

    st.markdown("Mô hình HistGradientBoosting dự đoán **biên lợi nhuận (profit/sales)** của một dòng giao dịch "
                "từ chiết khấu, sản phẩm, thị trường và hồ sơ khách. Không dùng sales hay profit làm đặc trưng.")
    with st.form("margin_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Sản phẩm & giao dịch**")
            cat = st.selectbox(LABELS["category"], sorted(prods.category.unique()))
            sub = st.selectbox(LABELS["subcategory"], prods[prods.category == cat].subcategory.tolist())
            discount = st.slider(LABELS["discount"], 0.0, 0.8, 0.2, 0.05, format="%.2f")
            quantity = st.number_input(LABELS["quantity"], 1, 200, int(dft["quantity"].median))
            lines = st.number_input(LABELS["lines_in_order"], 1, 20, int(dft["lines_in_order"].median))
            sales = st.number_input("Giá trị dòng (USD, chỉ để quy ra lợi nhuận)", 1.0, 10000.0, 250.0, 10.0)
        with c2:
            st.markdown("**Thị trường & thời gian**")
            market = st.selectbox(LABELS["market"], opt["market"])
            segment = st.selectbox(LABELS["segment"], opt["segment"])
            year = st.selectbox(LABELS["year"], [2023, 2022, 2021, 2020])
            month = st.slider(LABELS["month"], 1, 12, 6)
            prior = st.number_input(LABELS["prior_orders"], 0, 50, int(dft["prior_orders"].median))
        with c3:
            st.markdown("**Hồ sơ khách**")
            gender = st.selectbox(LABELS["gender"], opt["gender"])
            age = st.selectbox(LABELS["age_group"], sorted(opt["age_group"]))
            occ = st.selectbox(LABELS["occupation"], opt["occupation"])
            edu = st.selectbox(LABELS["education_level"], opt["education_level"])
            marital = st.selectbox(LABELS["marital_status"], opt["marital_status"])
            home = st.radio(LABELS["is_home_owner"], ["True", "False"], horizontal=True,
                            format_func=lambda v: "Có" if v == "True" else "Không")
            income = st.number_input(LABELS["annual_income"], 0, 500000, int(dft["annual_income"].median), 5000)
        submitted = st.form_submit_button("Dự đoán", type="primary")

    row = {"discount": discount, "quantity": quantity, "prior_orders": prior, "lines_in_order": lines,
           "annual_income": income, "month": month, "year": year, "category": cat, "subcategory": sub,
           "market": market, "segment": segment, "gender": gender, "age_group": age, "occupation": occ,
           "education_level": edu, "marital_status": marital, "is_home_owner": home}
    grid = np.round(np.arange(0, 0.801, 0.05), 2)
    batch = pd.DataFrame([{**row, "discount": d} for d in grid])
    curve = model.predict(batch)
    margin = float(model.predict(pd.DataFrame([row]))[0])

    c = st.columns(3)
    c[0].metric("Biên lợi nhuận dự đoán", pct(margin))
    c[1].metric("Lợi nhuận dự đoán của dòng", usd(margin * sales, 2))
    below = grid[curve < 0]
    c[2].metric("Chiết khấu bắt đầu lỗ", f"{below[0]:.0%}" if len(below) else "Không lỗ tới 80%")

    fig = go.Figure()
    fig.add_scatter(x=grid, y=curve, mode="lines+markers", name="Biên dự đoán", line=dict(color=C_REVENUE))
    fig.add_scatter(x=[discount], y=[margin], mode="markers", name="Lựa chọn hiện tại",
                    marker=dict(size=14, color=C_PROFIT if margin >= 0 else C_LOSS))
    fig.add_hline(y=0, line_color=C_LOSS, line_width=1)
    fig.update_layout(height=380, xaxis_tickformat=".0%", yaxis_tickformat=".0%", margin=dict(t=30),
                      xaxis_title="Chiết khấu", yaxis_title="Biên dự đoán",
                      title="Cùng hồ sơ này, biên thay đổi thế nào khi đổi chiết khấu",
                      legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig, width="stretch")
    version_note(ver, published)

# ---------------- Khách quay lại ----------------
with tab_repeat:
    bundle, ver, published = load_model("repeat_tree_bundle_v1")
    if bundle is None:
        st.error("Chưa có mô hình repeat_tree_bundle_v1 trong ml.model_artifacts. Chạy pipeline trên GitHub Actions.")
        st.stop()
    tree, enc, NUM, CAT = bundle["model"], bundle["encoder"], bundle["num"], bundle["cat"]
    opt = options("repeat_options")
    dft = defaults("repeat_defaults")
    base = float(q("SELECT base_rate FROM repeat_metrics LIMIT 1").base_rate.iloc[0])

    st.markdown("Cây quyết định (entropy, sâu 4) dự đoán khách **mua lần đầu có quay lại trong 365 ngày** "
                "hay không, chỉ dựa vào đơn đầu tiên và nhân khẩu học.")
    with st.form("repeat_form"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Đơn hàng đầu tiên**")
            vals = {
                "first_sales": st.number_input(LABELS["first_sales"], 1.0, 10000.0, float(dft["first_sales"].median), 10.0),
                "first_quantity": st.number_input(LABELS["first_quantity"], 1, 200, int(dft["first_quantity"].median)),
                "first_lines": st.number_input(LABELS["first_lines"], 1, 20, int(dft["first_lines"].median)),
                "first_discount": st.slider(LABELS["first_discount"], 0.0, 0.8, 0.0, 0.05, format="%.2f"),
                "first_n_categories": st.number_input(LABELS["first_n_categories"], 1, 6,
                                                      int(dft["first_n_categories"].median)),
            }
            vals["first_main_category"] = st.selectbox(LABELS["first_main_category"], opt["first_main_category"])
        with c2:
            st.markdown("**Khách hàng**")
            for f in ["market", "segment", "gender", "age_group", "income_band", "occupation", "education_level"]:
                choices = sorted(opt[f]) if f in ("age_group", "income_band") else opt[f]
                vals[f] = st.selectbox(LABELS[f], choices, key=f"r_{f}")
            vals["is_home_owner"] = st.radio(LABELS["is_home_owner"], ["True", "False"], horizontal=True,
                                             format_func=lambda v: "Có" if v == "True" else "Không", key="r_home")
        st.form_submit_button("Dự đoán", type="primary")

    d = pd.DataFrame([vals])
    X = pd.DataFrame(np.c_[d[NUM].astype(float).values, enc.transform(d[CAT].astype(str))], columns=NUM + CAT)
    prob = float(tree.predict_proba(X)[0, 1])

    c = st.columns(3)
    c[0].metric("Điểm quay lại (cây quyết định)", f"{prob:.2f}")
    c[1].metric("Dự đoán", "Quay lại" if prob >= 0.5 else "Không quay lại")
    c[2].metric("Tỷ lệ quay lại chung (tập test)", pct(base))
    st.caption("Cây học với class_weight='balanced' nên điểm 0,5 là ngưỡng phân lớp, không phải xác suất thực tế.")

    # Đường đi trong cây: giải thích vì sao ra kết quả
    t = tree.tree_
    steps = []
    for node in tree.decision_path(X).indices:
        if t.children_left[node] == -1:
            continue
        fi = t.feature[node]
        f, thr, v = (NUM + CAT)[fi], t.threshold[node], X.iloc[0, fi]
        left = v <= thr
        if f in NUM:
            fmt = (lambda x: f"{x:.0%}") if f == "first_discount" else (lambda x: f"{x:,.1f}")
            cond = f"{LABELS[f]} {'≤' if left else '>'} {fmt(thr)}  (giá trị: {fmt(v)})"
        else:
            cats = enc.categories_[CAT.index(f)]
            chosen = [str(c) for i, c in enumerate(cats) if (i <= thr) == left]
            shown = ", ".join(chosen[:6]) + (" ..." if len(chosen) > 6 else "")
            cond = f"{LABELS[f]} ∈ {{{shown}}}  (giá trị: {d[f].iloc[0]})"
        steps.append(cond)
    st.markdown("**Đường đi trong cây quyết định**")
    for i, s in enumerate(steps, 1):
        st.markdown(f"{i}. {s}")
    leaf = tree.apply(X)[0]
    st.caption(f"Lá cuối: {int(t.n_node_samples[leaf]):,} khách trong tập huấn luyện (cohort 2020-2021).")
    version_note(ver, published)
