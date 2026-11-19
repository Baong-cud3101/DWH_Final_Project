"""Hàm dùng chung cho ứng dụng Streamlit: kết nối DuckDB, truy vấn có cache, định dạng số."""

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "data" / "xomecom_app.duckdb"

YEARS = [2020, 2021, 2022, 2023]
MARKETS = ["Africa", "Asia Pacific", "Europe", "LATAM", "USCA"]
SEGMENTS = ["Consumer", "Corporate", "Self-Employed"]

# Màu dùng thống nhất cho toàn bộ ứng dụng
C_REVENUE = "#2E6FBA"
C_PROFIT = "#2A9D6F"
C_LOSS = "#D1495B"
C_NEUTRAL = "#8C8C8C"
SEQ_SCALE = "Blues"
DIV_SCALE = "RdYlGn"


@st.cache_resource
def _connection() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        st.error(
            f"Không thấy {DB_PATH.name}. Chạy `python scripts/12_build_app_data.py` để tạo dữ liệu cho ứng dụng."
        )
        st.stop()
    return duckdb.connect(str(DB_PATH), read_only=True)


@st.cache_data(show_spinner=False)
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Chạy một câu SQL trên kho rút gọn và trả về DataFrame (có cache)."""
    cur = _connection().cursor()  # mỗi lần truy vấn một cursor riêng, an toàn khi nhiều phiên
    try:
        return cur.execute(sql, list(params)).df()
    finally:
        cur.close()


def in_list(values) -> tuple[str, tuple]:
    """Tạo đoạn ' IN (?, ?, ...)' và tham số tương ứng."""
    values = tuple(values)
    if not values:
        return " IN (NULL)", ()
    return " IN (" + ", ".join("?" * len(values)) + ")", values


def usd(x: float, digits: int = 0) -> str:
    if pd.isna(x):
        return "-"
    if abs(x) >= 1e6:
        return f"${x / 1e6:,.2f}M"
    if abs(x) >= 1e4:
        return f"${x / 1e3:,.1f}K"
    return f"${x:,.{digits}f}"


def pct(x: float, digits: int = 1) -> str:
    return "-" if pd.isna(x) else f"{x * 100:.{digits}f}%"


def num(x: float) -> str:
    return "-" if pd.isna(x) else f"{x:,.0f}"


def page_header(title: str, caption: str) -> None:
    st.title(title)
    st.caption(caption)


def year_filter(key: str, default=None, label="Năm") -> list[int]:
    return st.sidebar.multiselect(label, YEARS, default=default or YEARS, key=key) or YEARS


def market_filter(key: str) -> list[str]:
    return st.sidebar.multiselect("Thị trường", MARKETS, default=MARKETS, key=key) or MARKETS


def segment_filter(key: str) -> list[str]:
    return st.sidebar.multiselect("Phân khúc", SEGMENTS, default=SEGMENTS, key=key) or SEGMENTS
