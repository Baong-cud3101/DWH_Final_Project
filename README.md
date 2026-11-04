# Xóm E-Com Data Warehouse

Đồ án môn Nhà kho dữ liệu và tích hợp. Medallion (Bronze, Silver, Gold) trên BigQuery, dbt, BigQuery ML.

## Cấu trúc

| Thư mục | Nội dung |
| --- | --- |
| `data/raw/` | 4 file CSV nguồn (không đưa lên Git) |
| `data/exports/` | Kết quả xuất tạm (không đưa lên Git) |
| `notebooks/` | Notebook khảo sát và notebook Colab cũ (tham khảo) |
| `dbt/` | Dự án dbt: staging, silver, gold, marts, ml |
| `sql/ml/` | Các câu lệnh BigQuery ML |
| `sql/checks/` | Truy vấn đối chiếu số liệu giữa các tầng |
| `scripts/` | Script Python (nạp Bronze, xuất kết quả) |
| `results/` | Bảng, biểu đồ, ảnh chụp dùng cho báo cáo |
| `report/drafts/` | Bản nháp báo cáo |
| `report/final/` | Báo cáo và slide nộp |
| `docs/` | Yêu cầu môn học, đề cương, slide bài giảng, báo cáo mẫu |

## Cài đặt
1. `pip install -r requirements.txt`
2. Sao chép `.env.example` thành `.env` và điền giá trị.
3. Sao chép `dbt/profiles.yml.example` thành `dbt/profiles.yml` và điền giá trị.
4. `cd dbt && dbt debug`
