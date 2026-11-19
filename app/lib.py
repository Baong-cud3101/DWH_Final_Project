"""Hàm dùng chung cho ứng dụng Streamlit: kết nối kho, truy vấn có cache, định dạng số.

Nguồn dữ liệu:
- Có secret MOTHERDUCK_TOKEN: truy vấn trực tiếp schema app của kho trên MotherDuck
  (số liệu của lần pipeline GitHub Actions gần nhất).
- Không có: đọc bản snapshot app/data/xomecom_app.duckdb (chạy offline, không có mô hình).
"""

import decimal
import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).parent / "data" / "xomecom_app.duckdb"
CACHE_TTL = 600  # giây; sau mỗi lần pipeline chạy, tối đa 10 phút app sẽ thấy số mới


def secret(name: str, default=None):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:  # không có file secrets
        pass
    return os.getenv(name, default)


def _clean_token(raw) -> str | None:
    """Bỏ khoảng trắng, xuống dòng, ngoặc kép/đơn/cong dư ở hai đầu (lỗi hay gặp khi dán)."""
    if not raw:
        return None
    tok = "".join(str(raw).split())  # token JWT không chứa khoảng trắng
    return tok.strip("\"'“”‘’") or None


MD_TOKEN = _clean_token(secret("MOTHERDUCK_TOKEN"))
MD_DB = secret("MOTHERDUCK_DB", "xomecom")


def token_info() -> str:
    """Mô tả token để chẩn đoán mà không lộ token."""
    raw = secret("MOTHERDUCK_TOKEN")
    if not raw:
        return "không có token"
    raw = str(raw)
    return (f"token dài {len(MD_TOKEN or '')} ký tự, bắt đầu '{(MD_TOKEN or '')[:3]}', "
            f"số dấu chấm {(MD_TOKEN or '').count('.')} (JWT đúng có 2)"
            + (", bản dán gốc có khoảng trắng/xuống dòng" if any(c.isspace() for c in raw) else ""))

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


MD_ERROR: list[str] = []  # lỗi kết nối MotherDuck gần nhất (hiện ở thanh bên)


@st.cache_resource(show_spinner="Đang kết nối MotherDuck...")
def _md_connection() -> duckdb.DuckDBPyConnection:
    """Chỉ được cache khi kết nối thành công; lỗi sẽ được thử lại ở lần truy cập sau."""
    con = duckdb.connect(f"md:{MD_DB}", config={"motherduck_token": MD_TOKEN})
    con.execute(f"USE {MD_DB}.app")
    con.execute("SELECT count(*) FROM kpi_overview").fetchone()
    return con


@st.cache_resource
def _snapshot_connection() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        st.error(f"Không kết nối được MotherDuck và không thấy {DB_PATH.name}.")
        st.stop()
    return duckdb.connect(str(DB_PATH), read_only=True)


def _connection() -> tuple[duckdb.DuckDBPyConnection, str]:
    if MD_TOKEN:
        try:
            con = _md_connection()
            MD_ERROR.clear()
            return con, "motherduck"
        except Exception as e:  # mất kết nối, token sai, kho chưa có schema app: dùng snapshot
            msg = str(e).replace(str(MD_TOKEN), "***")
            msg = msg.split("threw an exception:")[-1].strip()[:400]
            MD_ERROR[:] = [f"{msg} [{token_info()}]"]
    else:
        MD_ERROR[:] = ["Chưa khai báo secret MOTHERDUCK_TOKEN."]
    return _snapshot_connection(), "snapshot"


def source() -> str:
    """'motherduck' (kho trực tuyến) hoặc 'snapshot' (bản rút gọn trong repo)."""
    return _connection()[1]


def cursor() -> duckdb.DuckDBPyConnection:
    return _connection()[0].cursor()


def _to_float(df: pd.DataFrame) -> pd.DataFrame:
    """DECIMAL từ view trả về đối tượng Decimal: đổi sang float để tính toán và vẽ."""
    for c in df.columns:
        if df[c].dtype == object:
            first = df[c].dropna().head(1)
            if len(first) and isinstance(first.iloc[0], decimal.Decimal):
                df[c] = df[c].astype(float)
    return df


@st.cache_data(show_spinner=False, ttl=CACHE_TTL)
def q(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Chạy một câu SQL trên schema app và trả về DataFrame (cache 10 phút)."""
    cur = cursor()  # mỗi lần truy vấn một cursor riêng, an toàn khi nhiều phiên
    try:
        return _to_float(cur.execute(sql, list(params)).df())
    finally:
        cur.close()


def last_run() -> pd.Series | None:
    try:
        df = q("SELECT * FROM pipeline_runs ORDER BY run_at DESC LIMIT 1")
        return df.iloc[0] if len(df) else None
    except Exception:
        return None


def in_list(values) -> tuple[str, tuple]:
    """Tạo đoạn ' IN (?, ?, ...)' và tham số tương ứng."""
    values = tuple(values)
    if not values:
        return " IN (NULL)", ()
    return " IN (" + ", ".join("?" * len(values)) + ")", values


def usd(x: float, digits: int = 0) -> str:
    if pd.isna(x):
        return "-"
    sign, x = ("-" if x < 0 else ""), abs(x)
    if x >= 1e6:
        return f"{sign}${x / 1e6:,.2f}M"
    if x >= 1e4:
        return f"{sign}${x / 1e3:,.1f}K"
    return f"{sign}${x:,.{digits}f}"


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
