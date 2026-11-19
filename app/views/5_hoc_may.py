import json

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from lib import C_LOSS, C_NEUTRAL, C_PROFIT, C_REVENUE, MARKETS, page_header, pct, q, usd

page_header(
    "Học máy",
    "Kết quả các mô hình trong schema ml: what-if chiết khấu (HistGradientBoosting), dự báo chuỗi thời gian "
    "(ETS, SARIMA), dự đoán khách quay lại (cây quyết định, Naive Bayes), luật kết hợp (Apriori). "
    "Ứng dụng đọc kết quả mô hình đã tính sẵn trong kho, không huấn luyện lại.",
)

tab_wi, tab_ts, tab_rep, tab_basket, tab_reg = st.tabs(
    ["What-if chiết khấu", "Dự báo & bất thường", "Khách quay lại", "Giỏ hàng", "Sổ mô hình"]
)

# ---------------- What-if ----------------
with tab_wi:
    st.markdown(
        "Mô hình dự đoán **biên lợi nhuận của từng dòng giao dịch** (đặc trưng không gồm sales/profit). "
        "Kịch bản: giữ nguyên các dòng năm 2023, chỉ đổi mức chiết khấu, rồi cộng lợi nhuận dự đoán."
    )
    wi = q("SELECT * FROM whatif ORDER BY discount_level")
    cats = sorted(wi.category.unique())
    col1, col2, col3 = st.columns([2, 2, 3])
    with col1:
        sel_c = st.multiselect("Ngành hàng", cats, default=cats, key="wi_c") or cats
    with col2:
        sel_m = st.multiselect("Thị trường", MARKETS, default=MARKETS, key="wi_m") or MARKETS
    with col3:
        level = st.select_slider("Mức chiết khấu áp cho mọi dòng", options=sorted(wi.discount_level.unique()),
                                 value=0.2, format_func=lambda v: f"{v:.0%}")
    sub = wi[wi.category.isin(sel_c) & wi.market.isin(sel_m)]
    agg = sub.groupby("discount_level", as_index=False)[["sales", "pred_profit"]].sum()
    agg["pred_margin"] = agg.pred_profit / agg.sales
    row, base = agg[agg.discount_level == level].iloc[0], agg[agg.discount_level == 0].iloc[0]

    c = st.columns(3)
    c[0].metric("Doanh thu 2023 trong phạm vi", usd(row.sales))
    c[1].metric(f"Lợi nhuận dự đoán ở mức {level:.0%}", usd(row.pred_profit),
                f"{usd(row.pred_profit - base.pred_profit)} so với 0%")
    c[2].metric("Biên lợi nhuận dự đoán", pct(row.pred_margin),
                f"{(row.pred_margin - base.pred_margin) * 100:+.1f} điểm % so với 0%")

    by_cat = sub.groupby(["discount_level", "category"], as_index=False)[["sales", "pred_profit"]].sum()
    by_cat["pred_margin"] = by_cat.pred_profit / by_cat.sales
    fig = px.line(by_cat, x="discount_level", y="pred_margin", color="category", markers=True,
                  title="Biên lợi nhuận dự đoán theo mức chiết khấu")
    fig.add_vline(x=level, line_dash="dash", line_color=C_NEUTRAL)
    fig.add_hline(y=0, line_color=C_LOSS, line_width=1)
    fig.update_layout(height=420, xaxis_tickformat=".0%", yaxis_tickformat=".0%", legend_title="",
                      xaxis_title="Mức chiết khấu", yaxis_title="Biên dự đoán")
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Kịch bản đặt trần chiết khấu cho các dòng năm 2023** (bảng ml.whatif_discount_cap)")
    cap = q("SELECT * FROM whatif_cap ORDER BY cap")
    col1, col2 = st.columns([3, 2])
    with col1:
        fig = px.bar(cap.assign(label=[f"Trần {c:.0%}" for c in cap.cap]), x="label", y="uplift",
                     text=[f"+{usd(u)} ({p:.0%})" for u, p in zip(cap.uplift, cap.uplift_pct)],
                     color_discrete_sequence=[C_PROFIT])
        fig.update_layout(height=340, xaxis_title="", yaxis_title="Lợi nhuận tăng thêm (USD)", margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
    with col2:
        st.dataframe(cap, hide_index=True, width="stretch", column_config={
            "cap": st.column_config.NumberColumn("Trần", format="percent"),
            "rows_affected": st.column_config.NumberColumn("Dòng bị ảnh hưởng", format="%,d"),
            "pred_profit_baseline": st.column_config.NumberColumn("LN dự đoán hiện tại", format="$%,.0f"),
            "pred_profit_capped": st.column_config.NumberColumn("LN dự đoán có trần", format="$%,.0f"),
            "uplift": None, "uplift_pct": st.column_config.NumberColumn("Tăng", format="percent"),
            "pred_margin_capped": st.column_config.NumberColumn("Biên có trần", format="percent"),
        })

    with st.expander("Chất lượng mô hình biên lợi nhuận và mức quan trọng của đặc trưng"):
        st.dataframe(q("SELECT * FROM margin_metrics"), hide_index=True, width="stretch")
        imp = q("SELECT * FROM margin_importance ORDER BY importance DESC LIMIT 10")
        fig = px.bar(imp.iloc[::-1], x="importance", y="feature", orientation="h", error_x="std",
                     title="Permutation importance (mức giảm R² trên tập test 2023)")
        fig.update_layout(height=360, yaxis_title="", xaxis_type="log")
        st.plotly_chart(fig, width="stretch")
        drift = q("SELECT * FROM margin_drift ORDER BY ym")
        fig = go.Figure()
        fig.add_scatter(x=drift.ym, y=drift.actual_margin, name="Biên thực tế", line=dict(color=C_REVENUE))
        fig.add_scatter(x=drift.ym, y=drift.predicted_margin, name="Biên dự đoán (học 2020-2022)",
                        line=dict(color=C_NEUTRAL, dash="dash"))
        fig.update_layout(height=320, yaxis_tickformat=".0%", title="Model drift theo tháng",
                          legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, width="stretch")

# ---------------- Dự báo ----------------
with tab_ts:
    target = st.radio("Chỉ tiêu", ["revenue", "profit"], horizontal=True,
                      format_func=lambda t: {"revenue": "Doanh thu", "profit": "Lợi nhuận"}[t])
    fc = q("SELECT * FROM forecast ORDER BY month_start")
    an = q("SELECT * FROM anomalies ORDER BY month_start")
    act, fut = fc[fc.kind == "actual"], fc[fc.kind == "forecast"]
    fig = go.Figure()
    fig.add_scatter(x=act.month_start, y=act[target], name="Thực tế", line=dict(color=C_REVENUE))
    fig.add_scatter(x=fut.month_start, y=fut[target], name="Dự báo ETS 01-06/2024",
                    line=dict(color=C_PROFIT, dash="dash"), mode="lines+markers")
    if target == "profit":
        fig.add_scatter(x=an.month_start, y=an.lower_95, name="Cận dưới 95% (SARIMA học 2020-2022)",
                        line=dict(color=C_NEUTRAL, dash="dot"))
        a = an[an.is_anomaly]
        fig.add_scatter(x=a.month_start, y=a.profit, name="Tháng bất thường", mode="markers",
                        marker=dict(color=C_LOSS, size=11, symbol="x"))
    fig.update_layout(height=440, legend=dict(orientation="h", y=-0.15), yaxis_title="USD")
    st.plotly_chart(fig, width="stretch")

    met = q("SELECT * FROM ts_metrics")
    st.dataframe(met[met.target == target], hide_index=True, width="stretch", column_config={
        "MAPE_2023": st.column_config.NumberColumn("MAPE 2023", format="percent"),
        "forecast_total_2023": st.column_config.NumberColumn("Tổng dự báo 2023", format="$%,.0f"),
        "actual_total_2023": st.column_config.NumberColumn("Tổng thực tế 2023", format="$%,.0f"),
        "gap_pct": st.column_config.NumberColumn("Thực tế/dự báo - 1", format="percent"),
    })
    if target == "profit":
        st.caption("Tháng bất thường: phần dư ETS chuẩn hóa |z| > 2, hoặc lợi nhuận 2023 thấp hơn cận dưới 95% "
                   "của mô hình học trên 2020-2022.")
        st.dataframe(an[an.is_anomaly][["month_start", "revenue", "profit", "margin", "z_score", "lower_95"]],
                     hide_index=True, width="stretch")

# ---------------- Khách quay lại ----------------
with tab_rep:
    st.markdown(
        "Dự đoán khách mua lần đầu có quay lại trong 365 ngày hay không, chỉ dựa trên thông tin đơn đầu "
        "và nhân khẩu học. Train: cohort 2020-2021, test: cohort 2022."
    )
    rm = q("SELECT * FROM repeat_metrics")
    st.dataframe(rm, hide_index=True, width="stretch", column_config={
        c: st.column_config.NumberColumn(c, format="%.3f") for c in ["AUC", "F1", "precision", "recall", "lift_top20"]
    } | {"return_rate_top20": st.column_config.NumberColumn("Tỷ lệ quay lại top 20%", format="percent"),
         "base_rate": st.column_config.NumberColumn("Tỷ lệ nền", format="percent")})

    col1, col2 = st.columns(2)
    with col1:
        dec = q("SELECT * FROM repeat_deciles ORDER BY decile")
        base_rate = float(rm.base_rate.iloc[0])
        fig = px.bar(dec, x="decile", y="return_rate", text_auto=".0%",
                     title="Tỷ lệ quay lại thực tế theo nhóm điểm (1 = điểm cao nhất)",
                     color_discrete_sequence=[C_REVENUE])
        fig.add_hline(y=base_rate, line_dash="dash", line_color=C_LOSS, annotation_text=f"Nền {base_rate:.0%}")
        fig.update_layout(height=380, yaxis_tickformat=".0%", xaxis=dict(type="category", title="Thập phân vị"))
        st.plotly_chart(fig, width="stretch")
    with col2:
        rb = q("SELECT * FROM repeat_by_discount ORDER BY first_discount_band_order")
        fig = px.bar(rb, x="first_discount_band", y="return_rate", text_auto=".1%",
                     title="Tỷ lệ quay lại theo chiết khấu đơn đầu", color_discrete_sequence=[C_PROFIT])
        fig.update_layout(height=380, yaxis_tickformat=".0%", xaxis_title="Chiết khấu đơn đầu")
        st.plotly_chart(fig, width="stretch")

    st.markdown("**Luật từ cây quyết định (sâu 4)**")
    st.dataframe(q("SELECT * FROM repeat_rules ORDER BY return_rate_train DESC"), hide_index=True,
                 width="stretch", column_config={
                     "rule": st.column_config.TextColumn("Luật", width="large"),
                     "customers_train": st.column_config.NumberColumn("Số khách (train)", format="%,d"),
                     "return_rate_train": st.column_config.NumberColumn("Tỷ lệ quay lại", format="percent"),
                     "prediction": "Dự đoán",
                 })

# ---------------- Giỏ hàng ----------------
with tab_basket:
    st.markdown("Luật kết hợp giữa các nhóm sản phẩm trong cùng đơn hàng (Apriori).")
    ar = q("SELECT * FROM apriori_rules ORDER BY lift DESC")
    fig = px.scatter(ar, x="support", y="confidence", size="lift", color="lift", hover_data=["antecedent", "consequent"],
                     color_continuous_scale="Blues", size_max=30)
    fig.update_layout(height=360, xaxis_tickformat=".2%", yaxis_tickformat=".0%")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(ar, hide_index=True, width="stretch", column_config={
        "support": st.column_config.NumberColumn("Support", format="%.4f"),
        "confidence": st.column_config.NumberColumn("Confidence", format="percent"),
        "lift": st.column_config.NumberColumn("Lift", format="%.2f"),
    })
    st.caption("Lift > 1: hai nhóm sản phẩm xuất hiện cùng nhau nhiều hơn mức ngẫu nhiên.")

# ---------------- Sổ mô hình ----------------
with tab_reg:
    st.markdown("**ml.model_registry**: phiên bản, tham số và chỉ số của từng mô hình.")
    reg = q("SELECT * FROM model_registry ORDER BY model_name")
    st.dataframe(reg[["model_name", "model_version", "algorithm", "trained_at"]], hide_index=True,
                 width="stretch")
    pick = st.selectbox("Xem chi tiết", reg.model_name + " · " + reg.model_version)
    r = reg.iloc[(reg.model_name + " · " + reg.model_version).tolist().index(pick)]
    col1, col2 = st.columns(2)
    col1.markdown("Tham số")
    col1.json(json.loads(r.params))
    col2.markdown("Chỉ số")
    col2.json(json.loads(r.metrics))
    with st.expander("Chọn số cụm K cho K-Means"):
        ks = q("SELECT * FROM k_selection ORDER BY k")
        st.dataframe(ks, hide_index=True, width="stretch")
