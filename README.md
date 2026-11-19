# Xóm E-Com Data Warehouse trên DuckDB

Đồ án học phần Nhà kho dữ liệu và tích hợp (BIM5021, UEL). Kho dữ liệu Medallion (Bronze, Silver, Gold) trên **DuckDB**, biến đổi bằng **dbt-duckdb**, học máy bằng **Python** trên dữ liệu Gold, dashboard **Power BI** đọc CSV xuất từ data mart. Đề cương: `../DeCuong_Final_DuckDB.docx`.

## Chạy lại toàn bộ (một lệnh)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
# đặt 4 file CSV vào data/raw/
python scripts/run_all.py         # khoảng 1 phút
```

Các bước của `run_all.py` (dừng ngay nếu một bước lỗi):

| Bước | Script | Kết quả |
| --- | --- | --- |
| 1 | `00_load_bronze.py` | 4 bảng `bronze.*` (VARCHAR + `_ingested_at`, `_source_file`), đối chiếu số dòng với CSV |
| 2 | `run_dbt.py build` | Silver, Gold (star schema), mart, ml_features, ml_first_order_features + 124 nút (101 kiểm thử) |
| 3 | `01_profiling.py` | Profiling chất lượng, bảng B2.4, B4.2 |
| 4–7 | `03_ml_kmeans.py`, `04_ml_margin_whatif.py`, `04b_ml_classification.py` (cây quyết định, Naive Bayes), `05_ml_timeseries.py` | Schema `ml`, model_registry, file `models/*.joblib` |
| 8 | `06_analysis_sql.py` | Giỏ hàng (SQL + Apriori), cohort, benchmark sắp xếp theo order_date |
| 9 | `07_charts.py` | Hình và bảng cho Chương 2, 4 |
| 10 | `08_export_marts.py` | 14 file CSV trong `exports/powerbi/` (chỉ cột không nhạy cảm) |
| 11 | `11_build_powerbi.py` | Dashboard `powerbi/XomEcom_Dashboard.pbip` (mô hình TMDL + báo cáo PBIR, 5 trang) |
| 12 | `09_checks.py` | Đối chiếu Bronze = Silver = Gold (dừng nếu lệch) |
| 13 | `run_dbt.py docs generate` | Tài liệu và lineage dbt |
| 14 | `10_build_report.py` | `report/final/BaoCao_XomEcom_DuckDB.docx` |

Lệnh lẻ: `python scripts/run_dbt.py build`, `python scripts/run_dbt.py docs serve` (xem lineage), `python scripts/run_all.py --no-report`.

## Chạy trực tuyến: MotherDuck + GitHub Actions + Streamlit

| Thành phần | Dịch vụ | Cấu hình |
| --- | --- | --- |
| Kho dữ liệu | MotherDuck (`md:xomecom`) | `DUCKDB_PATH=md:xomecom` + `MOTHERDUCK_TOKEN`; mọi script và dbt dùng chung qua `scripts/common.py` |
| Pipeline | GitHub Actions `.github/workflows/pipeline.yml` | secrets `MOTHERDUCK_TOKEN`, `DATA_REPO_TOKEN`; variable `DATA_REPO` (repo riêng tư chứa 4 CSV) |
| Ứng dụng | Streamlit Community Cloud, `app/streamlit_app.py` | secret `MOTHERDUCK_TOKEN` (nên dùng token chỉ-đọc) |

Workflow chạy khi bấm *Run workflow*, khi có commit sửa `dbt/`, `scripts/`, `sql/`, và 8 giờ sáng thứ Hai.
Các bước: Bronze → dbt build → profiling → ML → đối chiếu → `14_publish_models.py` (mô hình vào `ml.model_artifacts`)
→ `12_build_app_data.py` (schema `app`: view phục vụ ứng dụng).

Ứng dụng có 8 trang: 6 trang phân tích, **Dự đoán trực tiếp** (nạp mô hình từ kho) và **SQL Playground**
(DuckDB trong bộ nhớ, chỉ bảng được phép, một câu SELECT, không truy cập file/mạng, 1.000 dòng, 15 giây).
Không có token thì ứng dụng đọc snapshot `app/data/xomecom_app.duckdb` (chỉ bảng tổng hợp).

```bash
python scripts/12_build_app_data.py --snapshot   # cập nhật schema app + snapshot trong repo
streamlit run app/streamlit_app.py
```

## Cấu trúc kho (`warehouse/xomecom.duckdb`)

| Schema | Bảng |
| --- | --- |
| bronze | customer, ecom_sales, product, region |
| silver | silver_customer, silver_product, silver_region, silver_sales_integrated |
| gold | fact_sales, fact_monthly_snapshot, dim_date, dim_customer, dim_product, dim_region, dim_segment, dim_flags |
| mart | mart_segment_profitability, mart_product_profitability, mart_geographic_performance, mart_discount_analysis, mart_customer_value, mart_customer_cohort, mart_kpi_overview |
| ml | ml_features, customer_clusters, cluster_profile, whatif_discount, whatif_discount_cap, margin_*, forecast_monthly, monthly_anomalies, model_registry, ... |
| main | metric_catalog (seed), audit_run_log (log mỗi lần dbt chạy) |

## Thư mục

| Thư mục | Nội dung |
| --- | --- |
| `dbt/` | dự án dbt: `models/{silver,gold/dims,gold/facts,marts,ml}`, `macros/` (metric catalog, discount_band, safe_divide, audit log), `tests/` (đối chiếu), `seeds/metric_catalog.csv` |
| `scripts/` | toàn bộ Python của pipeline |
| `sql/analysis`, `sql/checks` | SQL phân tích và đối chiếu |
| `results/tables`, `results/figures` | bảng CSV và hình PNG dùng trong báo cáo; `key_numbers.json` chứa mọi con số của báo cáo |
| `exports/powerbi/` | CSV cho Power BI |
| `powerbi/` | Dự án Power BI sinh từ `scripts/11_build_powerbi.py` (không chứa dữ liệu; cache `.pbi/` bị bỏ qua) |
| `report/drafts/` | nội dung báo cáo (Markdown) – sửa ở đây rồi chạy lại `10_build_report.py` |
| `report/mermaid/` | mã mermaid 6 sơ đồ để vẽ lại |
| `report/final/` | báo cáo Word |

## Việc nhóm cần làm thủ công

1. Vẽ 6 sơ đồ từ `report/mermaid/*.mmd` (mermaid.live hoặc draw.io), thay vào các khung vàng trong Word.
2. Chụp 4 ảnh: `dbt build` (dòng `Done. PASS=124`), cây schema trong DBeaver, lineage `dbt docs serve`, 4 trang dashboard.
3. Dashboard Power BI: chạy `python scripts/11_build_powerbi.py` (đã có trong `run_all.py`), mở `powerbi/XomEcom_Dashboard.pbip` bằng Power BI Desktop và bấm Refresh. Đặc tả ở Phụ lục C; đổi thư mục CSV bằng tham số `DataFolder`. Bản đồ trang Địa lý là scatter kinh độ × vĩ độ nên hiển thị được mà không cần đăng nhập.
4. Điền tên nhóm, MSSV, logo UEL, link Google Drive, bảng phân công; trong Word nhấn Ctrl+A rồi F9 để cập nhật Mục lục và Danh mục hình/bảng.

## Bảo mật dữ liệu

`data/raw/*.csv`, `warehouse/*.duckdb` và `exports/` chứa hoặc dẫn xuất từ dữ liệu cá nhân, nên đã nằm trong `.gitignore`. Gold chỉ giữ email đã băm và nhóm tuổi.
