import plotly.express as px
import streamlit as st
from plotly.subplots import make_subplots

from lib import (C_LOSS, C_PROFIT, C_REVENUE, in_list, market_filter, page_header, pct, q,
                 segment_filter, usd, year_filter)

page_header(
    "Sản phẩm & Chiết khấu",
    "Chiết khấu ảnh hưởng thế nào đến biên lợi nhuận, và sản phẩm nào lãi hoặc lỗ. "
    "Nguồn: mart.mart_discount_analysis, mart.mart_product_profitability.",
)

years = year_filter("pd_y")
markets = market_filter("pd_m")
segments = segment_filter("pd_s")
cats = q("SELECT DISTINCT category FROM discount ORDER BY 1").category.tolist()
categories = st.sidebar.multiselect("Ngành hàng", cats, default=cats, key="pd_c") or cats

y_in, y_p = in_list(years)
m_in, m_p = in_list(markets)
s_in, s_p = in_list(segments)
c_in, c_p = in_list(categories)
where = f"year{y_in} AND market{m_in} AND segment{s_in} AND category{c_in}"
params = y_p + m_p + s_p + c_p

# ---------- Theo mức chiết khấu ----------
st.subheader("Doanh thu và biên lợi nhuận theo mức chiết khấu")
band = q(
    f"""SELECT discount_band_order, discount_band, sum(revenue) AS revenue, sum(profit) AS profit,
               sum(profit) / sum(revenue) AS margin, sum(loss_lines) / sum(total_lines) AS loss_rate,
               sum(total_lines) AS lines
        FROM discount WHERE {where} GROUP BY 1, 2 ORDER BY 1""",
    params,
)
fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_bar(x=band.discount_band, y=band.revenue, name="Doanh thu", marker_color=C_REVENUE)
fig.add_bar(x=band.discount_band, y=band.profit, name="Lợi nhuận",
            marker_color=[C_PROFIT if v >= 0 else C_LOSS for v in band.profit])
fig.add_scatter(x=band.discount_band, y=band.margin, name="Biên lợi nhuận", mode="lines+markers+text",
                text=[pct(v) for v in band.margin], textposition="top center",
                line=dict(color="#333"), secondary_y=True)
fig.update_layout(barmode="group", height=420, legend=dict(orientation="h", y=1.1), margin=dict(t=30),
                  xaxis_title="Mức chiết khấu")
fig.update_yaxes(title_text="USD", secondary_y=False)
fig.update_yaxes(title_text="Biên lợi nhuận", tickformat=".0%", secondary_y=True)
st.plotly_chart(fig, width="stretch")

deep = band[band.discount_band_order >= 5]
if not deep.empty and band.revenue.sum() > 0:
    st.info(
        f"Chiết khấu trên 30% chiếm {pct(deep.revenue.sum() / band.revenue.sum())} doanh thu nhưng "
        f"tạo ra lợi nhuận {usd(deep.profit.sum())}; tỷ lệ dòng lỗ ở nhóm này là "
        f"{pct(deep.loss_rate.mul(deep.lines).sum() / deep.lines.sum())}."
    )

st.subheader("Biên lợi nhuận: ngành hàng × mức chiết khấu")
cb = q(
    f"""SELECT category, discount_band_order, discount_band, sum(profit) / sum(revenue) AS margin
        FROM discount WHERE {where} GROUP BY ALL ORDER BY discount_band_order""",
    params,
)
heat = cb.pivot(index="category", columns="discount_band", values="margin")[band.discount_band.tolist()]
fig = px.imshow(heat, text_auto=".0%", color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                aspect="auto", labels=dict(color="Biên LN", x="Mức chiết khấu", y="Ngành hàng"))
fig.update_layout(height=380, margin=dict(t=10))
st.plotly_chart(fig, width="stretch")

st.divider()

# ---------- Sản phẩm ----------
st.subheader("Lợi nhuận theo sản phẩm")
st.caption("mart_product_profitability không có chiều thị trường và phân khúc, nên phần này chỉ lọc theo năm và ngành hàng.")
p_where = f"year{y_in} AND category{c_in}"
p_params = y_p + c_p

sub = q(
    f"""SELECT category, subcategory, sum(revenue) AS revenue, sum(profit) AS profit,
               sum(profit) / sum(revenue) AS margin
        FROM product WHERE {p_where} GROUP BY ALL""",
    p_params,
)
fig = px.treemap(sub, path=["category", "subcategory"], values="revenue", color="margin",
                 color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                 hover_data={"profit": ":,.0f", "margin": ":.1%"})
fig.update_layout(height=460, margin=dict(t=10, l=0, r=0, b=0))
st.plotly_chart(fig, width="stretch")
st.caption("Kích thước ô = doanh thu; màu = biên lợi nhuận (đỏ là lỗ).")

prod = q(
    f"""SELECT product_name, category, subcategory, sum(revenue) AS revenue, sum(profit) AS profit,
               sum(profit) / sum(revenue) AS margin, sum(quantity) AS quantity,
               sum(avg_discount * total_lines) / sum(total_lines) AS avg_discount
        FROM product WHERE {p_where} GROUP BY ALL""",
    p_params,
)
n = st.slider("Số sản phẩm hiển thị", 5, 30, 10)
cfg = {
    "revenue": st.column_config.NumberColumn("Doanh thu", format="$%,.0f"),
    "profit": st.column_config.NumberColumn("Lợi nhuận", format="$%,.0f"),
    "margin": st.column_config.NumberColumn("Biên LN", format="percent"),
    "avg_discount": st.column_config.NumberColumn("Chiết khấu TB", format="percent"),
    "quantity": st.column_config.NumberColumn("Số lượng", format="%,d"),
}
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**Top {n} sản phẩm lãi nhất**")
    st.dataframe(prod.nlargest(n, "profit"), hide_index=True, width="stretch", column_config=cfg)
with col2:
    st.markdown(f"**Top {n} sản phẩm lỗ nhất**")
    st.dataframe(prod.nsmallest(n, "profit"), hide_index=True, width="stretch", column_config=cfg)
