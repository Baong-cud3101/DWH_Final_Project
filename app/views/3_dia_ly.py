import plotly.express as px
import streamlit as st

from lib import C_PROFIT, C_REVENUE, in_list, market_filter, num, page_header, pct, q, usd, year_filter

page_header(
    "Địa lý",
    "Hiệu quả theo thị trường và quốc gia. Nguồn: mart.mart_geographic_performance.",
)

years = year_filter("geo_y")
markets = market_filter("geo_m")
y_in, y_p = in_list(years)
m_in, m_p = in_list(markets)
where, params = f"year{y_in} AND market{m_in}", y_p + m_p

country = q(
    f"""SELECT country, market, any_value(country_latitude) AS lat, any_value(country_longitude) AS lon,
               sum(revenue) AS revenue, sum(profit) AS profit, sum(profit) / sum(revenue) AS margin,
               sum(total_orders) AS orders,
               sum(avg_discount * total_orders) / sum(total_orders) AS avg_discount
        FROM geo WHERE {where} AND country <> 'Unknown' GROUP BY 1, 2""",
    params,
)

c = st.columns(4)
c[0].metric("Số quốc gia", num(len(country)))
c[1].metric("Doanh thu", usd(country.revenue.sum()))
c[2].metric("Lợi nhuận", usd(country.profit.sum()))
c[3].metric("Quốc gia lỗ", num((country.profit < 0).sum()))

st.subheader("Bản đồ doanh thu và biên lợi nhuận")
fig = px.scatter_geo(
    country, lat="lat", lon="lon", size="revenue", color="margin", hover_name="country",
    hover_data={"market": True, "revenue": ":,.0f", "profit": ":,.0f", "margin": ":.1%", "lat": False, "lon": False},
    color_continuous_scale="RdYlGn", color_continuous_midpoint=0, size_max=40, projection="natural earth",
)
fig.update_layout(height=520, margin=dict(t=0, l=0, r=0, b=0), coloraxis_colorbar=dict(title="Biên LN", tickformat=".0%"))
st.plotly_chart(fig, width="stretch")
st.caption("Kích thước điểm = doanh thu; màu = biên lợi nhuận. Tọa độ là tâm quốc gia (dim_region).")

st.subheader("Theo thị trường qua các năm")
mk = q(
    f"""SELECT year, market, sum(revenue) AS revenue, sum(profit) AS profit,
               sum(profit) / sum(revenue) AS margin
        FROM geo WHERE {where} GROUP BY 1, 2 ORDER BY 1, 2""",
    params,
)
col1, col2 = st.columns(2)
with col1:
    fig = px.bar(mk, x="year", y="revenue", color="market", barmode="group", title="Doanh thu (USD)")
    fig.update_layout(height=380, xaxis=dict(type="category", title="Năm"), yaxis_title="USD", legend_title="")
    st.plotly_chart(fig, width="stretch")
with col2:
    fig = px.line(mk, x="year", y="margin", color="market", markers=True, title="Biên lợi nhuận")
    fig.update_layout(height=380, xaxis=dict(type="category"), yaxis_tickformat=".0%", legend_title="",
                      xaxis_title="Năm", yaxis_title="Biên LN")
    st.plotly_chart(fig, width="stretch")

st.subheader("Xếp hạng quốc gia")
col1, col2 = st.columns([1, 3])
with col1:
    sort_by = st.radio("Sắp xếp theo", ["Doanh thu", "Lợi nhuận", "Biên LN thấp nhất"])
    n = st.number_input("Số quốc gia", 5, 50, 15)
order = {"Doanh thu": ("revenue", False), "Lợi nhuận": ("profit", False), "Biên LN thấp nhất": ("margin", True)}[sort_by]
top = country.sort_values(order[0], ascending=order[1]).head(int(n))
with col2:
    fig = px.bar(top.iloc[::-1], x=order[0], y="country", orientation="h", color="margin",
                 color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                 hover_data={"revenue": ":,.0f", "profit": ":,.0f", "margin": ":.1%"})
    fig.update_layout(height=max(350, 24 * int(n)), margin=dict(t=10), yaxis_title="",
                      xaxis_title={"revenue": "Doanh thu (USD)", "profit": "Lợi nhuận (USD)", "margin": "Biên LN"}[order[0]],
                      coloraxis_colorbar=dict(title="Biên LN", tickformat=".0%"))
    if order[0] == "margin":
        fig.update_xaxes(tickformat=".0%")
    st.plotly_chart(fig, width="stretch")

with st.expander("Bảng chi tiết quốc gia"):
    st.dataframe(
        country.drop(columns=["lat", "lon"]).sort_values("revenue", ascending=False),
        hide_index=True, width="stretch",
        column_config={
            "revenue": st.column_config.NumberColumn("Doanh thu", format="$%,.0f"),
            "profit": st.column_config.NumberColumn("Lợi nhuận", format="$%,.0f"),
            "margin": st.column_config.NumberColumn("Biên LN", format="percent"),
            "avg_discount": st.column_config.NumberColumn("Chiết khấu TB", format="percent"),
        },
    )
