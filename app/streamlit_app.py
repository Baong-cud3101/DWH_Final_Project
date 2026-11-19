"""Ứng dụng Streamlit cho kho dữ liệu Xóm E-Com.

Chạy cục bộ:  streamlit run app/streamlit_app.py
Dữ liệu:      app/data/xomecom_app.duckdb (tạo bằng scripts/12_build_app_data.py)
"""

import streamlit as st

st.set_page_config(page_title="Xóm E-Com | Data Warehouse", page_icon="📊", layout="wide")

pages = [
    st.Page("views/1_tong_quan.py", title="Tổng quan KPI", icon="📈", default=True),
    st.Page("views/2_san_pham_chiet_khau.py", title="Sản phẩm & Chiết khấu", icon="🏷️"),
    st.Page("views/3_dia_ly.py", title="Địa lý", icon="🌍"),
    st.Page("views/4_khach_hang.py", title="Khách hàng", icon="👥"),
    st.Page("views/5_hoc_may.py", title="Học máy", icon="🤖"),
    st.Page("views/6_chat_luong.py", title="Chất lượng dữ liệu", icon="✅"),
]

nav = st.navigation(pages)

with st.sidebar:
    st.markdown("### Xóm E-Com DWH")
    st.caption(
        "Kho Medallion trên DuckDB + dbt, học máy bằng Python. "
        "Ứng dụng đọc bản rút gọn của kho (chỉ bảng tổng hợp, không có dữ liệu cá nhân)."
    )
    st.divider()

nav.run()

st.sidebar.divider()
st.sidebar.caption("Nhóm 6 · BIM5021 Nhà kho dữ liệu và tích hợp · UEL")
