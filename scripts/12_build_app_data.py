"""Tạo kho rút gọn cho ứng dụng Streamlit: app/data/xomecom_app.duckdb.

Chỉ chép bảng tổng hợp từ mart, gold.fact_monthly_snapshot và schema ml. Không chép
bảng có một dòng cho mỗi khách hàng (dim_customer, mart_customer_value, customer_clusters,
repeat_scores, ml_features...). Thông tin khách hàng chỉ được đưa sang dưới dạng số đếm
theo nhóm, nên file này có thể đưa lên GitHub để triển khai trên Streamlit Community Cloud.
"""

import sys

import duckdb
import pandas as pd

from common import DB_PATH, ROOT, TABLES_DIR

APP_DB = ROOT / "app" / "data" / "xomecom_app.duckdb"
MIN_GROUP = 10  # nhóm khách có ít hơn 10 người thì không xuất

COPY = {
    # tên bảng trong app : câu SELECT trên kho gốc (alias src)
    "kpi_overview": "SELECT * FROM src.mart.mart_kpi_overview",
    "monthly": "SELECT * FROM src.gold.fact_monthly_snapshot",
    "segment": "SELECT * FROM src.mart.mart_segment_profitability",
    "discount": "SELECT * FROM src.mart.mart_discount_analysis",
    "product": "SELECT * EXCLUDE (product_key) FROM src.mart.mart_product_profitability",
    "geo": "SELECT * FROM src.mart.mart_geographic_performance",
    "cohort": "SELECT * FROM src.mart.mart_customer_cohort",
    "metric_catalog": "SELECT * FROM src.main.metric_catalog",
    "cluster_profile": "SELECT * FROM src.ml.cluster_profile",
    "k_selection": "SELECT * FROM src.ml.kmeans_k_selection",
    "forecast": "SELECT * FROM src.ml.forecast_monthly",
    "anomalies": "SELECT * FROM src.ml.monthly_anomalies",
    "ts_metrics": "SELECT * FROM src.ml.ts_model_metrics",
    "whatif": "SELECT * FROM src.ml.whatif_discount",
    "whatif_cap": "SELECT * FROM src.ml.whatif_discount_cap",
    "margin_metrics": "SELECT * FROM src.ml.margin_model_metrics",
    "margin_importance": "SELECT * FROM src.ml.margin_feature_importance",
    "margin_drift": "SELECT * FROM src.ml.margin_drift_by_month",
    "repeat_metrics": "SELECT * FROM src.ml.repeat_classifier_metrics",
    "repeat_by_discount": "SELECT * FROM src.ml.repeat_by_first_discount",
    "repeat_rules": "SELECT * FROM src.ml.repeat_tree_rules",
    "apriori_rules": "SELECT * FROM src.ml.apriori_rules",
    "model_registry": """SELECT model_name, model_version, algorithm, trained_at,
                                CAST(params AS VARCHAR) AS params, CAST(metrics AS VARCHAR) AS metrics
                         FROM src.ml.model_registry""",
    # Tổng hợp theo nhóm, không có khóa khách hàng
    "rfm_summary": f"""
        SELECT rfm_segment, count(*) AS customers, avg(recency_days) AS recency_days,
               avg(frequency) AS frequency, avg(monetary) AS monetary,
               sum(monetary) AS revenue, sum(profit) AS profit
        FROM src.mart.mart_customer_value GROUP BY 1 HAVING count(*) >= {MIN_GROUP}""",
    "customer_demo": f"""
        WITH c AS (SELECT * FROM src.mart.mart_customer_value)
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
        FROM src.ml.repeat_scores GROUP BY 1""",
    # Chất lượng dữ liệu
    "quality_flags": """
        SELECT f.is_valid_product, f.is_valid_region, f.discount_band, f.discount_band_order,
               f.is_deep_discount, f.is_loss, count(*) AS lines,
               sum(s.sales) AS sales, sum(s.profit) AS profit
        FROM src.gold.fact_sales s JOIN src.gold.dim_flags f USING (flag_key)
        GROUP BY ALL""",
    "audit_log": """
        SELECT invocation_id, min(run_at) AS run_at, any_value(command) AS command,
               count(*) AS nodes, count(*) FILTER (WHERE status IN ('success', 'pass')) AS ok,
               count(*) FILTER (WHERE status NOT IN ('success', 'pass')) AS not_ok,
               sum(execution_time) AS seconds
        FROM src.main.audit_run_log GROUP BY 1""",
}

CSV_TABLES = {
    "quality_profiling": "B2.4_profiling.csv",
    "quality_bronze_silver": "B4.2_bronze_vs_silver.csv",
    "quality_gold_recon": "B4.3_gold_reconciliation.csv",
}


def main() -> None:
    if not DB_PATH.exists():
        sys.exit(f"Không thấy kho {DB_PATH}. Chạy scripts/run_all.py trước.")
    APP_DB.parent.mkdir(parents=True, exist_ok=True)
    if APP_DB.exists():
        APP_DB.unlink()

    con = duckdb.connect()  # dựng trong bộ nhớ rồi mới ghi ra file cho gọn
    con.execute(f"ATTACH '{DB_PATH.as_posix()}' AS src (READ_ONLY)")
    for name, sql in COPY.items():
        con.execute(f"CREATE TABLE {name} AS {sql}")
    for name, file in CSV_TABLES.items():
        df = pd.read_csv(TABLES_DIR / file, encoding="utf-8-sig", dtype=str)
        con.register("tmp_df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
    # Số dòng thật của từng bảng trong kho gốc (cho trang Chất lượng dữ liệu)
    tables = con.sql(
        "SELECT schema_name, table_name FROM duckdb_tables() "
        "WHERE database_name = 'src' ORDER BY 1, 2").fetchall()
    con.execute("CREATE TABLE table_counts (table_schema VARCHAR, table_name VARCHAR, row_count BIGINT)")
    for sch, tbl in tables:
        n = con.sql(f'SELECT count(*) FROM src."{sch}"."{tbl}"').fetchone()[0]
        con.execute("INSERT INTO table_counts VALUES (?, ?, ?)", [sch, tbl, n])
    con.execute("DETACH src")

    # DECIMAL/HUGEINT -> DOUBLE để pandas và biểu đồ dùng trực tiếp
    for tbl, col in con.sql(
            "SELECT table_name, column_name FROM duckdb_columns() "
            "WHERE database_name = 'memory' AND (data_type LIKE 'DECIMAL%' OR data_type = 'HUGEINT')"
    ).fetchall():
        con.execute(f'ALTER TABLE "{tbl}" ALTER "{col}" TYPE DOUBLE')

    rows = con.sql(
        "SELECT table_name, estimated_size FROM duckdb_tables() WHERE database_name = 'memory' ORDER BY 1"
    ).fetchall()
    con.execute(f"ATTACH '{APP_DB.as_posix()}' AS app")
    con.execute("COPY FROM DATABASE memory TO app")
    con.execute("DETACH app")
    con.close()
    size_kb = APP_DB.stat().st_size / 1024
    print(f"Đã tạo {APP_DB} ({size_kb:,.0f} KB), {len(rows)} bảng:")
    for name, n in rows:
        print(f"  {name:<22} {n:>7}")


if __name__ == "__main__":
    main()
