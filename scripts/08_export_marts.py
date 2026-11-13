"""Xuất data mart và kết quả ML ra CSV cho Power BI (COPY ... TO).

Quản trị dữ liệu: DuckDB không có phân quyền theo cột, nên chỉ xuất các cột KHÔNG nhạy cảm.
Không xuất: họ tên, email (kể cả bản băm), ngày sinh, tuổi chính xác, customer_id gốc.
"""

from common import EXPORT_DIR, connect

EXPORTS = {
    "mart_kpi_overview": "select * from mart.mart_kpi_overview",
    "mart_segment_profitability": "select * from mart.mart_segment_profitability",
    "mart_product_profitability": "select * from mart.mart_product_profitability",
    "mart_geographic_performance": "select * from mart.mart_geographic_performance",
    "mart_discount_analysis": "select * from mart.mart_discount_analysis",
    "mart_customer_cohort": "select * from mart.mart_customer_cohort",
    # Customer value: bỏ cột định danh gốc, giữ customer_key (surrogate) và thuộc tính đã gom nhóm
    "mart_customer_value": """
        select v.customer_key, v.segment, v.gender, v.age_group, v.income_band, v.occupation,
               v.education_level, v.marital_status, v.is_home_owner, v.cohort_year,
               v.first_order_date, v.last_order_date, v.recency_days, v.frequency, v.monetary,
               v.profit, v.profit_margin, v.avg_discount, v.n_categories, v.n_markets,
               v.r_score, v.f_score, v.m_score, v.rfm_segment, v.is_repeat_customer,
               c.cluster, c.cluster_name
        from mart.mart_customer_value v
        left join ml.customer_clusters c using (customer_key)""",
    "fact_monthly_snapshot": "select * from gold.fact_monthly_snapshot",
    "ml_cluster_profile": "select * from ml.cluster_profile",
    "ml_whatif_discount": "select * from ml.whatif_discount",
    "ml_whatif_discount_cap": "select * from ml.whatif_discount_cap",
    "ml_forecast_monthly": "select * from ml.forecast_monthly",
    "ml_monthly_anomalies": "select * from ml.monthly_anomalies",
    "metric_catalog": "select * from main.metric_catalog",
}


def main() -> None:
    con = connect(read_only=True)
    for name, sql in EXPORTS.items():
        path = EXPORT_DIR / f"{name}.csv"
        con.execute(f"COPY ({sql}) TO '{path.as_posix()}' (HEADER, DELIMITER ',')")
        n = con.execute(f"select count(*) from ({sql})").fetchone()[0]
        print(f"[export] {name:<30} {n:>7} dòng -> {path.name}")
    con.close()


if __name__ == "__main__":
    main()
