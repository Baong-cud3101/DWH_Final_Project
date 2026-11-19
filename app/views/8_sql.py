import threading
import time

import duckdb
import pandas as pd
import streamlit as st

from lib import MD_DB, cursor, page_header, source

page_header(
    "SQL Playground",
    "Gõ câu SQL (DuckDB) và chạy trên dữ liệu của kho. Câu lệnh chạy trong một vùng cách ly: "
    "chỉ đọc, chỉ một câu SELECT, không truy cập file hay mạng, tối đa 1.000 dòng và 15 giây.",
)

MAX_ROWS = 1000
TIMEOUT_S = 15

# Bảng được phép truy vấn. Bảng khách hàng chỉ giữ cột nhân khẩu học theo nhóm
# (không có customer_id, email_hash, tuổi và thu nhập chính xác).
ALLOWED = {
    "gold": {
        "fact_sales": "*", "fact_monthly_snapshot": "*", "dim_date": "*", "dim_product": "*",
        "dim_region": "*", "dim_segment": "*", "dim_flags": "*",
        "dim_customer": "customer_key, gender, age_group, income_band, education_level, occupation, "
                        "marital_status, is_home_owner, segment",
    },
    "mart": {
        "mart_kpi_overview": "*", "mart_segment_profitability": "*", "mart_product_profitability": "*",
        "mart_geographic_performance": "*", "mart_discount_analysis": "*", "mart_customer_cohort": "*",
        "mart_customer_value": "* EXCLUDE (annual_income)",
    },
    "ml": {
        "customer_clusters": "*", "cluster_profile": "*", "forecast_monthly": "*", "monthly_anomalies": "*",
        "whatif_discount": "*", "whatif_discount_cap": "*", "margin_model_metrics": "*",
        "margin_feature_importance": "*", "repeat_classifier_metrics": "*", "repeat_tree_rules": "*",
        "apriori_rules": "*", "ts_model_metrics": "*", "kmeans_k_selection": "*",
    },
    "main": {"metric_catalog": "*"},
}

EXAMPLES = {
    "Doanh thu, lợi nhuận theo năm": """SELECT d.year,
       sum(f.sales)                     AS revenue,
       sum(f.profit)                    AS profit,
       sum(f.profit) / sum(f.sales)     AS margin
FROM gold.fact_sales f
JOIN gold.dim_date d USING (date_key)
GROUP BY 1
ORDER BY 1;""",
    "Top 10 nhóm sản phẩm lỗ nhất năm 2023": """SELECT p.category, p.subcategory, sum(f.profit) AS profit
FROM gold.fact_sales f
JOIN gold.dim_product p USING (product_key)
WHERE year(f.order_date) = 2023
GROUP BY ALL
ORDER BY profit
LIMIT 10;""",
    "Biên lợi nhuận theo mức chiết khấu và thị trường": """SELECT fl.discount_band, r.market,
       round(sum(f.profit) / sum(f.sales), 3) AS margin
FROM gold.fact_sales f
JOIN gold.dim_flags  fl USING (flag_key)
JOIN gold.dim_region r  USING (region_key)
GROUP BY ALL
ORDER BY fl.discount_band, r.market;""",
    "Cụm khách K-Means × phân khúc": """SELECT c.cluster_name, cu.segment, count(*) AS customers
FROM ml.customer_clusters c
JOIN gold.dim_customer cu USING (customer_key)
GROUP BY ALL
ORDER BY 1, 3 DESC;""",
    "Danh mục KPI": "SELECT kpi_code, kpi_name, formula, dbt_macro FROM main.metric_catalog;",
}


@st.cache_resource(ttl=3600, show_spinner="Đang chuẩn bị vùng truy vấn cách ly...")
def sandbox() -> duckdb.DuckDBPyConnection:
    """Kho DuckDB trong bộ nhớ, chỉ chứa bảng được phép; không nối tới MotherDuck hay file nào."""
    mem = duckdb.connect(":memory:")
    cur = cursor()
    try:
        if source() == "motherduck":
            for schema, tables in ALLOWED.items():
                mem.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
                for t, cols in tables.items():
                    df = cur.execute(f"SELECT {cols} FROM {MD_DB}.{schema}.{t}").df()
                    mem.register("tmp_df", df)
                    mem.execute(f"CREATE TABLE {schema}.{t} AS SELECT * FROM tmp_df")
                    mem.unregister("tmp_df")
        else:  # snapshot: chỉ có các bảng tổng hợp của schema app
            mem.execute("CREATE SCHEMA app")
            for (t,) in cur.execute("SELECT table_name FROM duckdb_tables()").fetchall():
                mem.register("tmp_df", cur.execute(f'SELECT * FROM "{t}"').df())
                mem.execute(f'CREATE TABLE app."{t}" AS SELECT * FROM tmp_df')
                mem.unregister("tmp_df")
    finally:
        cur.close()
    for s in ("SET memory_limit = '512MB'", "SET threads = 2", "SET enable_external_access = false",
              "SET autoinstall_known_extensions = false", "SET autoload_known_extensions = false",
              "SET lock_configuration = true"):
        mem.execute(s)
    return mem


def run_sql(sql: str) -> tuple[pd.DataFrame, bool, float]:
    con = sandbox()
    stmts = con.extract_statements(sql)
    if len(stmts) != 1:
        raise ValueError("Chỉ chạy được đúng một câu lệnh mỗi lần.")
    if stmts[0].type != duckdb.StatementType.SELECT:
        raise ValueError(f"Chỉ cho phép truy vấn đọc (SELECT); câu lệnh này là {stmts[0].type.name}.")
    cur = con.cursor()
    timer = threading.Timer(TIMEOUT_S, cur.interrupt)
    t0 = time.perf_counter()
    timer.start()
    try:
        cur.execute(stmts[0].query)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchmany(MAX_ROWS + 1)
    finally:
        timer.cancel()
        cur.close()
    return pd.DataFrame(rows[:MAX_ROWS], columns=cols), len(rows) > MAX_ROWS, time.perf_counter() - t0


con = sandbox()
catalog = con.execute(
    "SELECT schema_name, table_name, string_agg(column_name || ' ' || lower(data_type), ', ' "
    "ORDER BY column_index) AS columns FROM duckdb_columns() WHERE database_name = 'memory' "
    "GROUP BY ALL ORDER BY 1, 2").df()

col1, col2 = st.columns([3, 2])
with col2:
    st.markdown("**Bảng có thể truy vấn**")
    for schema, g in catalog.groupby("schema_name", sort=False):
        with st.expander(f"{schema} ({len(g)} bảng)"):
            for r in g.itertuples():
                st.markdown(f"`{schema}.{r.table_name}`")
                st.caption(r.columns)
with col1:
    example = st.selectbox("Câu mẫu", list(EXAMPLES))
    sql = st.text_area("SQL", EXAMPLES[example], height=260, key=f"sql_{example}")
    go = st.button("Chạy", type="primary")
    first_visit = "sql_seen" not in st.session_state  # lần đầu mở trang: tự chạy câu mẫu
    st.session_state["sql_seen"] = True

if (go or first_visit) and sql.strip():
    try:
        df, truncated, secs = run_sql(sql)
        st.success(f"{len(df):,} dòng{' (đã cắt ở 1.000)' if truncated else ''} · {secs * 1000:.0f} ms")
        st.dataframe(df, hide_index=True, width="stretch")
        st.download_button("Tải CSV", df.to_csv(index=False).encode("utf-8-sig"), "ket_qua.csv", "text/csv")
    except duckdb.InterruptException:
        st.error(f"Truy vấn chạy quá {TIMEOUT_S} giây nên đã bị dừng.")
    except Exception as e:
        st.error(f"{type(e).__name__}: {e}")

if source() != "motherduck":
    st.caption("Đang ở chế độ snapshot: chỉ có các bảng tổng hợp trong schema app.")
