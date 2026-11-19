import plotly.express as px
import streamlit as st

from lib import num, page_header, pct, q, usd

page_header(
    "Khách hàng",
    "RFM, phân cụm K-Means, cohort giữ chân và chân dung khách hàng. Nguồn: mart.mart_customer_value, "
    "mart.mart_customer_cohort, ml.cluster_profile (chỉ số liệu tổng hợp theo nhóm, mỗi nhóm có ít nhất 10 khách).",
)

kpi = q("SELECT * FROM kpi_overview WHERE year = 0").iloc[0]
c = st.columns(3)
c[0].metric("Tổng số khách", num(kpi.active_customers))
c[1].metric("Tỷ lệ khách quay lại (≥2 đơn)", pct(kpi.repeat_customer_rate))
c[2].metric("Doanh thu bình quân/khách", usd(kpi.revenue / kpi.active_customers, 1))

tab_rfm, tab_cluster, tab_cohort, tab_demo = st.tabs(["Phân nhóm RFM", "Phân cụm K-Means", "Cohort", "Chân dung"])

with tab_rfm:
    rfm = q("SELECT * FROM rfm_summary ORDER BY revenue DESC")
    rfm["profit_share"] = rfm.profit / rfm.profit.sum()
    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(rfm, x="rfm_segment", y="customers", title="Số khách theo nhóm RFM", text_auto=",")
        fig.update_layout(height=380, xaxis_title="", yaxis_title="Khách")
        st.plotly_chart(fig, width="stretch")
    with col2:
        fig = px.bar(rfm, x="rfm_segment", y="profit", title="Lợi nhuận theo nhóm RFM", text_auto=",.0f")
        fig.update_layout(height=380, xaxis_title="", yaxis_title="USD")
        st.plotly_chart(fig, width="stretch")
    st.dataframe(
        rfm, hide_index=True, width="stretch",
        column_config={
            "recency_days": st.column_config.NumberColumn("Recency TB (ngày)", format="%.0f"),
            "frequency": st.column_config.NumberColumn("Số đơn TB", format="%.2f"),
            "monetary": st.column_config.NumberColumn("Chi tiêu TB", format="$%.0f"),
            "revenue": st.column_config.NumberColumn("Doanh thu", format="$%,.0f"),
            "profit": st.column_config.NumberColumn("Lợi nhuận", format="$%,.0f"),
            "profit_share": st.column_config.NumberColumn("Tỷ trọng LN", format="percent"),
        },
    )
    st.caption("Điểm R, F, M tính theo ngày tham chiếu 2023-12-31; quy tắc gán nhóm nằm trong mart_customer_value.")

with tab_cluster:
    cl = q("SELECT * FROM cluster_profile ORDER BY total_profit DESC")
    fig = px.scatter(
        cl, x="frequency", y="margin", size="customers", color="cluster_name", text="cluster_name",
        hover_data={"customers": ":,", "monetary": ":,.0f", "avg_discount": ":.1%", "repeat_rate": ":.1%"},
        size_max=70, title="Bốn cụm khách: số đơn TB × biên lợi nhuận (kích thước = số khách)",
    )
    fig.update_traces(textposition="top center")
    fig.update_layout(height=440, yaxis_tickformat=".0%", showlegend=False,
                      xaxis_title="Số đơn trung bình", yaxis_title="Biên lợi nhuận")
    st.plotly_chart(fig, width="stretch")
    show = cl[["cluster_name", "customers", "share_customers", "share_profit", "recency_days", "frequency",
               "monetary", "avg_discount", "margin", "repeat_rate"]]
    st.dataframe(
        show, hide_index=True, width="stretch",
        column_config={
            "cluster_name": "Cụm",
            "customers": st.column_config.NumberColumn("Số khách", format="%,d"),
            "share_customers": st.column_config.NumberColumn("% khách", format="percent"),
            "share_profit": st.column_config.NumberColumn("% lợi nhuận", format="percent"),
            "recency_days": st.column_config.NumberColumn("Recency (ngày)", format="%.0f"),
            "frequency": st.column_config.NumberColumn("Số đơn TB", format="%.2f"),
            "monetary": st.column_config.NumberColumn("Chi tiêu TB", format="$%.0f"),
            "avg_discount": st.column_config.NumberColumn("Chiết khấu TB", format="percent"),
            "margin": st.column_config.NumberColumn("Biên LN", format="percent"),
            "repeat_rate": st.column_config.NumberColumn("Tỷ lệ quay lại", format="percent"),
        },
    )
    bad = cl[cl.total_profit < 0]
    if not bad.empty:
        b = bad.iloc[0]
        st.warning(
            f"Cụm **{b.cluster_name}**: {pct(b.share_customers)} số khách, chiết khấu TB {pct(b.avg_discount)}, "
            f"làm mất {usd(-b.total_profit)} lợi nhuận ({pct(b.share_profit)} tổng lợi nhuận)."
        )

with tab_cohort:
    co = q("SELECT * FROM cohort ORDER BY cohort_year, years_since_first")
    heat = co.pivot(index="cohort_year", columns="years_since_first", values="retention_rate")
    fig = px.imshow(heat, text_auto=".1%", color_continuous_scale="Blues", aspect="auto",
                    labels=dict(x="Số năm kể từ lần mua đầu", y="Năm mua đầu", color="Tỷ lệ giữ chân"))
    fig.update_layout(height=360, margin=dict(t=10))
    fig.update_yaxes(type="category")
    st.plotly_chart(fig, width="stretch")
    st.caption("Tỷ lệ giữ chân = số khách của cohort có mua trong năm đó / quy mô cohort.")

with tab_demo:
    demo = q("SELECT * FROM customer_demo")
    dim = st.selectbox("Chiều phân tích", sorted(demo.dimension.unique()))
    d = demo[demo.dimension == dim].copy()
    d["margin"] = d.profit / d.revenue
    d["revenue_per_customer"] = d.revenue / d.customers
    metric = st.radio("Chỉ số", ["Số khách", "Doanh thu/khách", "Biên lợi nhuận", "Tỷ lệ quay lại"], horizontal=True)
    col = {"Số khách": "customers", "Doanh thu/khách": "revenue_per_customer", "Biên lợi nhuận": "margin",
           "Tỷ lệ quay lại": "repeat_rate"}[metric]
    fig = px.bar(d.sort_values(col, ascending=False), x="value", y=col, text_auto=".3s" if col in
                 ("customers", "revenue_per_customer") else ".1%")
    fig.update_layout(height=400, xaxis_title=dim, yaxis_title=metric)
    if col in ("margin", "repeat_rate"):
        fig.update_yaxes(tickformat=".0%")
    st.plotly_chart(fig, width="stretch")
