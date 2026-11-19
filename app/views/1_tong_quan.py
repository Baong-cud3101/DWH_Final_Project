import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from lib import (C_LOSS, C_PROFIT, C_REVENUE, MARKETS, SEGMENTS, in_list, market_filter,
                 num, page_header, pct, q, segment_filter, usd)

page_header(
    "Tổng quan KPI",
    "Doanh thu, lợi nhuận, biên lợi nhuận 2020-2023. Nguồn: mart.mart_kpi_overview, "
    "gold.fact_monthly_snapshot, mart.mart_segment_profitability.",
)

# ---------- Thẻ KPI ----------
kpi = q("SELECT * FROM kpi_overview ORDER BY year")
choice = st.segmented_control(
    "Kỳ xem KPI", ["Toàn kỳ", "2020", "2021", "2022", "2023"], default="2023"
) or "Toàn kỳ"
year = 0 if choice == "Toàn kỳ" else int(choice)
cur = kpi[kpi.year == year].iloc[0]
prev = kpi[kpi.year == year - 1].iloc[0] if year > 2020 else None


def delta(col, kind="rel"):
    if prev is None:
        return None
    if kind == "pp":
        return f"{(cur[col] - prev[col]) * 100:+.1f} điểm %"
    return f"{(cur[col] / prev[col] - 1) * 100:+.1f}% so với {year - 1}"


c = st.columns(4)
c[0].metric("Doanh thu", usd(cur.revenue), delta("revenue"))
c[1].metric("Lợi nhuận", usd(cur.profit), delta("profit"))
c[2].metric("Biên lợi nhuận", pct(cur.profit_margin), delta("profit_margin", "pp"))
c[3].metric("Số đơn hàng", num(cur.total_orders), delta("total_orders"))
c = st.columns(4)
c[0].metric("Giá trị TB/đơn (AOV)", usd(cur.avg_order_value, 1), delta("avg_order_value"))
c[1].metric("Tỷ lệ dòng lỗ", pct(cur.loss_line_rate), delta("loss_line_rate", "pp"), delta_color="inverse")
c[2].metric("Tỷ lệ giảm giá sâu (>30%)", pct(cur.deep_discount_share), delta("deep_discount_share", "pp"),
            delta_color="inverse")
c[3].metric("Khách hoạt động", num(cur.active_customers), delta("active_customers"))

st.divider()

# ---------- Xu hướng theo tháng ----------
st.subheader("Xu hướng theo tháng")
markets = market_filter("kpi_m")
segments = segment_filter("kpi_s")
m_in, m_p = in_list(markets)
s_in, s_p = in_list(segments)
monthly = q(
    f"""SELECT month_start, sum(revenue) AS revenue, sum(profit) AS profit,
               sum(profit) / sum(revenue) AS margin
        FROM monthly WHERE market{m_in} AND segment{s_in}
        GROUP BY 1 ORDER BY 1""",
    m_p + s_p,
)
fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_bar(x=monthly.month_start, y=monthly.revenue, name="Doanh thu", marker_color=C_REVENUE)
fig.add_bar(x=monthly.month_start, y=monthly.profit, name="Lợi nhuận", marker_color=C_PROFIT)
fig.add_scatter(x=monthly.month_start, y=monthly.margin, name="Biên lợi nhuận", mode="lines+markers",
                line=dict(color=C_LOSS), secondary_y=True)
fig.update_layout(barmode="group", height=420, legend=dict(orientation="h", y=1.1), margin=dict(t=30))
fig.update_yaxes(title_text="USD", secondary_y=False)
fig.update_yaxes(title_text="Biên lợi nhuận", tickformat=".0%", secondary_y=True)
st.plotly_chart(fig, width="stretch")
st.caption(f"Lọc theo {len(markets)}/{len(MARKETS)} thị trường, {len(segments)}/{len(SEGMENTS)} phân khúc (thanh bên trái).")

# ---------- Phân khúc x thị trường ----------
st.subheader("Biên lợi nhuận theo phân khúc và thị trường")
col1, col2 = st.columns([3, 2])
seg = q(
    f"""SELECT segment, market, sum(revenue) AS revenue, sum(profit) AS profit,
               sum(profit) / sum(revenue) AS margin
        FROM segment WHERE market{m_in} AND segment{s_in} AND year IN (SELECT unnest(?))
        GROUP BY ALL""",
    m_p + s_p + ([2020, 2021, 2022, 2023] if year == 0 else [year],),
)
with col1:
    heat = seg.pivot(index="segment", columns="market", values="margin")
    fig = px.imshow(heat, text_auto=".1%", color_continuous_scale="RdYlGn", aspect="auto",
                    labels=dict(color="Biên LN", x="Thị trường", y="Phân khúc"))
    fig.update_layout(height=320, margin=dict(t=10))
    st.plotly_chart(fig, width="stretch")
with col2:
    by_seg = seg.groupby("segment", as_index=False)[["revenue", "profit"]].sum()
    fig = px.pie(by_seg, names="segment", values="revenue", hole=0.5, title="Tỷ trọng doanh thu")
    fig.update_layout(height=320, margin=dict(t=40))
    st.plotly_chart(fig, width="stretch")
st.caption(f"Kỳ: {choice}.")

with st.expander("Danh mục KPI (main.metric_catalog, định nghĩa trong dbt/macros/metrics.sql)"):
    st.dataframe(q("SELECT kpi_code, kpi_name, formula, unit, dbt_macro, description FROM metric_catalog"),
                 hide_index=True, width="stretch")
