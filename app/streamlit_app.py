"""Ứng dụng Streamlit cho kho dữ liệu Xóm E-Com.

Chạy cục bộ:  streamlit run app/streamlit_app.py
Dữ liệu:      schema app của kho trên MotherDuck (secret MOTHERDUCK_TOKEN),
              hoặc snapshot app/data/xomecom_app.duckdb nếu không có token.
"""

import streamlit as st

st.set_page_config(page_title="Xóm E-Com | Data Warehouse", page_icon="📊", layout="wide")

from lib import MD_ERROR, last_run, source  # noqa: E402  (sau set_page_config)

pages = {
    "Phân tích": [
        st.Page("views/1_tong_quan.py", title="Tổng quan KPI", icon="📈", default=True),
        st.Page("views/2_san_pham_chiet_khau.py", title="Sản phẩm & Chiết khấu", icon="🏷️"),
        st.Page("views/3_dia_ly.py", title="Địa lý", icon="🌍"),
        st.Page("views/4_khach_hang.py", title="Khách hàng", icon="👥"),
        st.Page("views/5_hoc_may.py", title="Học máy", icon="🤖"),
        st.Page("views/6_chat_luong.py", title="Chất lượng dữ liệu", icon="✅"),
    ],
    "Trực tiếp": [
        st.Page("views/7_du_doan.py", title="Dự đoán trực tiếp", icon="🎯"),
        st.Page("views/8_sql.py", title="SQL Playground", icon="🧮"),
    ],
}

nav = st.navigation(pages)

with st.sidebar:
    st.markdown("### Xóm E-Com DWH")
    if source() == "motherduck":
        run = last_run()
        st.success("Kết nối trực tiếp kho trên **MotherDuck**", icon="🟢")
        if run is not None:
            st.caption(f"Pipeline gần nhất: {str(run.run_at)[:16]} UTC · {run.source}"
                       + (f" · commit {run.commit_sha}" if run.commit_sha else ""))
    else:
        st.info("Đang dùng bản snapshot trong repo (không kết nối MotherDuck).", icon="📦")
        if MD_ERROR:
            st.caption(f"Lý do: {MD_ERROR[0]}")
    st.divider()

nav.run()

st.sidebar.divider()
st.sidebar.caption("Nhóm 6 · BIM5021 Nhà kho dữ liệu và tích hợp · UEL")
