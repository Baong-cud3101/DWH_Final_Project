"""Tầng phục vụ ứng dụng Streamlit: schema `app` trong kho (cục bộ hoặc MotherDuck).

    python scripts/12_build_app_data.py              # tạo/cập nhật schema app trong kho
    python scripts/12_build_app_data.py --snapshot   # thêm: xuất app/data/xomecom_app.duckdb

Schema app gồm các VIEW tính trực tiếp trên mart, gold và ml, nên khi chạy trên MotherDuck
ứng dụng luôn thấy số liệu của lần pipeline gần nhất. Thông tin khách hàng chỉ đi ra dưới
dạng số đếm theo nhóm (nhóm < 10 khách bị loại). Vài bảng nhỏ (kết quả kiểm tra chất lượng,
số dòng từng bảng, nhật ký chạy pipeline) được ghi lại mỗi lần chạy.

Bản snapshot (--snapshot) chỉ chứa schema app, dùng khi ứng dụng không kết nối được MotherDuck.
"""

import os
import sys
from datetime import datetime, timezone

import duckdb
import pandas as pd

from common import DB_URI, IS_MOTHERDUCK, ROOT, TABLES_DIR, connect

APP_DB = ROOT / "app" / "data" / "xomecom_app.duckdb"
MIN_GROUP = 10

MARGIN_CAT = ["category", "subcategory", "market", "segment", "gender", "age_group",
              "occupation", "education_level", "marital_status", "is_home_owner"]
MARGIN_NUM = ["discount", "quantity", "prior_orders", "lines_in_order", "annual_income", "month"]
REPEAT_CAT = ["first_main_category", "market", "segment", "gender", "age_group", "income_band",
              "occupation", "education_level", "is_home_owner"]
REPEAT_NUM = ["first_sales", "first_quantity", "first_lines", "first_discount", "first_n_categories"]


def _options_sql(table: str, cols: list[str]) -> str:
    parts = []
    for c in cols:
        v = f"CASE WHEN {c} THEN 'True' ELSE 'False' END" if c == "is_home_owner" else f"CAST({c} AS VARCHAR)"
        parts.append(f"SELECT '{c}' AS feature, {v} AS value, count(*) AS n FROM {table} GROUP BY ALL")
    return " UNION ALL ".join(parts)


def _defaults_sql(table: str, cols: list[str]) -> str:
    return " UNION ALL ".join(
        f"SELECT '{c}' AS feature, median({c})::DOUBLE AS median, min({c})::DOUBLE AS min, "
        f"max({c})::DOUBLE AS max FROM {table}" for c in cols)


VIEWS = {
    "kpi_overview": "SELECT * FROM mart.mart_kpi_overview",
    "monthly": "SELECT * FROM gold.fact_monthly_snapshot",
    "segment": "SELECT * FROM mart.mart_segment_profitability",
    "discount": "SELECT * FROM mart.mart_discount_analysis",
    "product": "SELECT * EXCLUDE (product_key) FROM mart.mart_product_profitability",
    "geo": "SELECT * FROM mart.mart_geographic_performance",
    "cohort": "SELECT * FROM mart.mart_customer_cohort",
    "metric_catalog": "SELECT * FROM main.metric_catalog",
    "cluster_profile": "SELECT * FROM ml.cluster_profile",
    "k_selection": "SELECT * FROM ml.kmeans_k_selection",
    "forecast": "SELECT * FROM ml.forecast_monthly",
    "anomalies": "SELECT * FROM ml.monthly_anomalies",
    "ts_metrics": "SELECT * FROM ml.ts_model_metrics",
    "whatif": "SELECT * FROM ml.whatif_discount",
    "whatif_cap": "SELECT * FROM ml.whatif_discount_cap",
    "margin_metrics": "SELECT * FROM ml.margin_model_metrics",
    "margin_importance": "SELECT * FROM ml.margin_feature_importance",
    "margin_drift": "SELECT * FROM ml.margin_drift_by_month",
    "repeat_metrics": "SELECT * FROM ml.repeat_classifier_metrics",
    "repeat_by_discount": "SELECT * FROM ml.repeat_by_first_discount",
    "repeat_rules": "SELECT * FROM ml.repeat_tree_rules",
    "apriori_rules": "SELECT * FROM ml.apriori_rules",
    "model_registry": """SELECT model_name, model_version, algorithm, trained_at,
                                CAST(params AS VARCHAR) AS params, CAST(metrics AS VARCHAR) AS metrics
                         FROM ml.model_registry""",
    "rfm_summary": f"""
        SELECT rfm_segment, count(*) AS customers, avg(recency_days) AS recency_days,
               avg(frequency) AS frequency, avg(monetary) AS monetary,
               sum(monetary) AS revenue, sum(profit) AS profit
        FROM mart.mart_customer_value GROUP BY 1 HAVING count(*) >= {MIN_GROUP}""",
    "customer_demo": f"""
        WITH c AS (SELECT * FROM mart.mart_customer_value)
        SELECT dimension, value, count(*) AS customers, sum(monetary) AS revenue,
               sum(profit) AS profit, avg(is_repeat_customer::INT) AS repeat_rate
        FROM (
            SELECT 'Giới tính' AS dimension, gender AS value, * FROM c UNION ALL
            SELECT 'Nhóm tuổi', age_group, * FROM c UNION ALL
            SELECT 'Nhóm thu nhập', income_band, * FROM c UNION ALL
            SELECT 'Nghề nghiệp', occupation, * FROM c UNION ALL
            SELECT 'Học vấn', education_level, * FROM c UNION ALL
            SELECT 'Phân khúc', segment, * FROM c
        ) GROUP BY 1, 2 HAVING count(*) >= {MIN_GROUP}""",
    "repeat_deciles": """
        SELECT decile, count(*) AS customers, avg(y) AS return_rate,
               avg(score_tree) AS avg_score_tree, avg(score_nb) AS avg_score_nb
        FROM ml.repeat_scores GROUP BY 1""",
    "quality_flags": """
        SELECT f.is_valid_product, f.is_valid_region, f.discount_band, f.discount_band_order,
               f.is_deep_discount, f.is_loss, count(*) AS lines,
               sum(s.sales) AS sales, sum(s.profit) AS profit
        FROM gold.fact_sales s JOIN gold.dim_flags f USING (flag_key)
        GROUP BY ALL""",
    "audit_log": """
        SELECT invocation_id, min(run_at) AS run_at, any_value(command) AS command,
               count(*) AS nodes, count(*) FILTER (WHERE status IN ('success', 'pass')) AS ok,
               count(*) FILTER (WHERE status NOT IN ('success', 'pass')) AS not_ok,
               sum(execution_time) AS seconds
        FROM main.audit_run_log GROUP BY 1""",
    # Lựa chọn và giá trị mặc định cho trang Dự đoán trực tiếp
    "margin_options": _options_sql("ml.ml_features", MARGIN_CAT),
    "margin_defaults": _defaults_sql("ml.ml_features", MARGIN_NUM),
    "product_options": "SELECT DISTINCT category, subcategory FROM ml.ml_features",
    "repeat_options": _options_sql("ml.ml_first_order_features", REPEAT_CAT),
    "repeat_defaults": _defaults_sql("ml.ml_first_order_features", REPEAT_NUM),
}

CSV_TABLES = {
    "quality_profiling": "B2.4_profiling.csv",
    "quality_bronze_silver": "B4.2_bronze_vs_silver.csv",
    "quality_gold_recon": "B4.3_gold_reconciliation.csv",
}


def build_app_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS app")
    for name, sql in VIEWS.items():
        con.execute(f"CREATE OR REPLACE VIEW app.{name} AS {sql}")
    has_artifacts = con.execute(
        "SELECT count(*) FROM duckdb_tables() WHERE database_name = current_database() "
        "AND schema_name = 'ml' AND table_name = 'model_artifacts'").fetchone()[0]
    if has_artifacts:
        con.execute("CREATE OR REPLACE VIEW app.model_artifacts AS SELECT * FROM ml.model_artifacts")

    for name, file in CSV_TABLES.items():
        df = pd.read_csv(TABLES_DIR / file, encoding="utf-8-sig", dtype=str)
        con.register("tmp_df", df)
        con.execute(f"CREATE OR REPLACE TABLE app.{name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")

    tables = con.execute(
        "SELECT schema_name, table_name FROM duckdb_tables() WHERE database_name = current_database() "
        "AND schema_name NOT IN ('app') ORDER BY 1, 2").fetchall()
    counts = [(s, t, con.execute(f'SELECT count(*) FROM "{s}"."{t}"').fetchone()[0]) for s, t in tables]
    con.execute("CREATE OR REPLACE TABLE app.table_counts "
                "(table_schema VARCHAR, table_name VARCHAR, row_count BIGINT)")
    con.executemany("INSERT INTO app.table_counts VALUES (?, ?, ?)", counts)

    con.execute("""CREATE TABLE IF NOT EXISTS app.pipeline_runs (
                       run_at TIMESTAMP, source VARCHAR, run_id VARCHAR, commit_sha VARCHAR)""")
    con.execute("INSERT INTO app.pipeline_runs VALUES (?, ?, ?, ?)", [
        datetime.now(timezone.utc).replace(tzinfo=None),
        "GitHub Actions" if os.getenv("GITHUB_ACTIONS") else "Máy cục bộ",
        os.getenv("GITHUB_RUN_ID", ""), os.getenv("GITHUB_SHA", "")[:7],
    ])
    n = con.execute("SELECT count(*) FROM duckdb_views() WHERE database_name = current_database() "
                    "AND schema_name = 'app'").fetchone()[0]
    print(f"[app] schema app: {n} view, {len(CSV_TABLES) + 2} bảng; đếm {len(counts)} bảng của kho")


def write_snapshot() -> None:
    """Chép schema app (đã tính) ra file DuckDB nhỏ để ứng dụng chạy không cần MotherDuck."""
    if IS_MOTHERDUCK:
        sys.exit("--snapshot chỉ dùng với kho cục bộ")
    APP_DB.parent.mkdir(parents=True, exist_ok=True)
    if APP_DB.exists():
        APP_DB.unlink()
    con = duckdb.connect()
    con.execute(f"ATTACH '{DB_URI}' AS src (READ_ONLY)")
    objs = con.execute("SELECT table_name FROM duckdb_tables() WHERE database_name='src' AND schema_name='app' "
                       "UNION ALL SELECT view_name FROM duckdb_views() WHERE database_name='src' "
                       "AND schema_name='app'").fetchall()
    con.execute("USE src")  # view tham chiếu mart./gold./ml. tương đối theo kho gốc
    con.execute("ATTACH ':memory:' AS snap")
    for (name,) in objs:
        if name == "model_artifacts":
            continue  # mô hình chỉ phục vụ qua MotherDuck
        con.execute(f"CREATE TABLE snap.main.{name} AS SELECT * FROM src.app.{name}")
    for tbl, col in con.execute(
            "SELECT table_name, column_name FROM duckdb_columns() WHERE database_name = 'snap' "
            "AND (data_type LIKE 'DECIMAL%' OR data_type = 'HUGEINT')").fetchall():
        con.execute(f'ALTER TABLE snap.main."{tbl}" ALTER "{col}" TYPE DOUBLE')
    con.execute(f"ATTACH '{APP_DB.as_posix()}' AS out")
    con.execute("COPY FROM DATABASE snap TO out")
    con.close()
    print(f"[app] snapshot {APP_DB} ({APP_DB.stat().st_size / 1024 / 1024:.1f} MB, {len(objs)} đối tượng)")


if __name__ == "__main__":
    c = connect()
    build_app_schema(c)
    c.close()
    if "--snapshot" in sys.argv:
        write_snapshot()
