import plotly.express as px
import streamlit as st

from lib import num, page_header, pct, q

page_header(
    "Chất lượng dữ liệu",
    "Profiling, đối chiếu Bronze = Silver = Gold, các cờ chất lượng trong gold.dim_flags và nhật ký chạy dbt.",
)

recon = q("SELECT * FROM quality_gold_recon")
flags = q("SELECT * FROM quality_flags")
audit = q("SELECT * FROM audit_log ORDER BY run_at DESC")

matched = recon["Khớp"].dropna()
total_lines = flags.lines.sum()
c = st.columns(4)
c[0].metric("Đối chiếu 3 lớp", f"{(matched == 'Có').sum()}/{len(matched)} khớp")
c[1].metric("Dòng giao dịch Gold", num(total_lines))
c[2].metric("Dòng lỗ (giữ lại)", num(flags[flags.is_loss].lines.sum()),
            pct(flags[flags.is_loss].lines.sum() / total_lines) + " tổng dòng", delta_color="off")
if not audit.empty:
    a = audit.iloc[0]
    c[3].metric("Lần dbt build gần nhất", f"{a.ok}/{a.nodes} nút đạt", str(a.run_at)[:16], delta_color="off")

st.subheader("Đối chiếu Bronze, Silver, Gold")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Bronze → Silver** (B4.2)")
    st.dataframe(q("SELECT * FROM quality_bronze_silver"), hide_index=True, width="stretch")
with col2:
    st.markdown("**Bronze = Silver = Gold** (B4.3)")
    st.dataframe(recon.fillna(""), hide_index=True, width="stretch")

st.subheader("Profiling theo chiều chất lượng (B2.4)")
st.dataframe(q("SELECT * FROM quality_profiling"), hide_index=True, width="stretch")

st.subheader("Cờ chất lượng trên bảng fact (gold.dim_flags)")
summary = {
    "Mã sản phẩm không khớp (product_key = -1)": flags[~flags.is_valid_product].lines.sum(),
    "Mã vùng không khớp (region_key = -1)": flags[~flags.is_valid_region].lines.sum(),
    "Chiết khấu sâu (> 30%)": flags[flags.is_deep_discount].lines.sum(),
    "Lợi nhuận âm": flags[flags.is_loss].lines.sum(),
}
st.dataframe(
    [{"Cờ": k, "Số dòng": int(v), "Tỷ lệ": v / total_lines} for k, v in summary.items()],
    hide_index=True, width="stretch",
    column_config={"Tỷ lệ": st.column_config.NumberColumn(format="percent")},
)
st.caption("Theo quy tắc của đồ án: không xóa dòng lỗ; mã không khớp được giữ lại, gắn cờ và trỏ về khóa -1.")

band = (flags.groupby(["discount_band_order", "discount_band", "is_loss"], as_index=False).lines.sum()
        .sort_values("discount_band_order"))
band["Loại dòng"] = band.is_loss.map({True: "Lỗ", False: "Lãi/hòa"})
fig = px.bar(band, x="discount_band", y="lines", color="Loại dòng", barmode="stack",
             color_discrete_map={"Lỗ": "#D1495B", "Lãi/hòa": "#2A9D6F"},
             title="Số dòng lãi và lỗ theo mức chiết khấu")
fig.update_layout(height=360, xaxis_title="Mức chiết khấu", yaxis_title="Số dòng")
st.plotly_chart(fig, width="stretch")

st.subheader("Kiến trúc kho: số dòng theo schema")
tc = q("SELECT * FROM table_counts ORDER BY table_schema, table_name")
order = ["bronze", "silver", "gold", "mart", "ml", "main"]
col1, col2 = st.columns([2, 3])
with col1:
    per = tc.groupby("table_schema", as_index=False).agg(tables=("table_name", "count"), rows=("row_count", "sum"))
    per["o"] = per.table_schema.map({s: i for i, s in enumerate(order)})
    st.dataframe(per.sort_values("o").drop(columns="o"), hide_index=True, width="stretch",
                 column_config={"table_schema": "Schema", "tables": "Số bảng",
                                "rows": st.column_config.NumberColumn("Tổng số dòng", format="%,d")})
with col2:
    sch = st.selectbox("Xem bảng trong schema", [s for s in order if s in set(tc.table_schema)])
    st.dataframe(tc[tc.table_schema == sch].drop(columns="table_schema"), hide_index=True,
                 width="stretch",
                 column_config={"row_count": st.column_config.NumberColumn("Số dòng", format="%,d")})
st.caption("Số dòng đếm trên kho đầy đủ (warehouse/xomecom.duckdb) lúc tạo dữ liệu cho ứng dụng.")

with st.expander("Nhật ký chạy dbt (main.audit_run_log)"):
    st.dataframe(audit, hide_index=True, width="stretch")
