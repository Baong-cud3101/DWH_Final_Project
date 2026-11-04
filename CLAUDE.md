# Đồ án Nhà kho dữ liệu và tích hợp: Xóm E-Com

Học phần BIM5021, UEL, GV TS. Nguyễn Thôn Dã. Tài liệu gốc: `docs/outline/DeCuong_Final.docx`
(đề cương cuối, thay thế `Report_ba_de_cuong_cu.docx`). Hãy đọc đề cương trước khi làm.

## Mục tiêu
Kho dữ liệu Medallion trên BigQuery + dbt + BigQuery ML, phân tích lợi nhuận đa phân khúc.
Trả lời 5 câu hỏi Q1 đến Q5 trong đề cương (chiết khấu, P&L phân khúc, thị trường, khách hàng, biên 2023).

## Hạ tầng
- GCP project: `formidable-app-510501-p3`
- Dataset: `Dataset1_Bronze`, `Dataset2_Silver`, `Dataset3_Gold` (Gold chưa tạo)
- dbt project nằm ở `dbt/` (tên profile `ecommerce_dbt`); cấu hình kết nối xem `.env.example` và `dbt/profiles.yml.example`
- Khóa truy cập để NGOÀI repo; không bao giờ đọc, in hay commit nội dung khóa

## Dữ liệu (4 CSV trong `data/raw/`)
`ecom_sales` 51.290 dòng (khóa `row_id`), `customer` 17.415, `product` 28.356, `region` 3.828. Thời gian 2020 đến 2023.
Tổng sales 6.517.674 USD, profit 1.065.414 USD. Dữ liệu có thông tin cá nhân: không đưa lên Git.

## Quy tắc đã chốt (không tự đổi)
- Không xóa dòng lợi nhuận âm (11.041 dòng, là giao dịch lỗ thật).
- `order_id` lặp là hợp lệ, không khử trùng.
- 124 khách thiếu `gender`: gán `Unknown`, giữ bản ghi.
- 2 mã product và 2 mã region không khớp: giữ mã gốc, gắn cờ `is_valid_*`, không xóa.
- Trục thời gian duy nhất là `order_date` (năm trong `order_id` bị lệch, bỏ qua).
- `age` tính theo ngày tham chiếu cố định 2023-12-31.
- Chi phí ngầm = `sales - profit`. Chưa rõ `sales` là trước hay sau chiết khấu.
- ML: chia train/test theo thời gian (train 2020 đến 2022, test 2023); biến mục tiêu là biên lợi nhuận; không dùng `sales` hay `profit` làm đặc trưng.

## Cấu trúc thư mục
`dbt/models/{staging,silver,gold/dimensions,gold/facts,marts,ml}`, `sql/ml` (BigQuery ML), `sql/checks` (đối chiếu),
`scripts/` (Python), `results/{tables,figures,screenshots}`, `report/{drafts,final}`, `docs/`.

## Quy tắc làm việc
- Hỏi trước khi chạy `CREATE MODEL`, ghi đè bảng, hoặc bất kỳ thao tác ghi vào BigQuery lần đầu.
- Mỗi lần xong một tầng: chạy `dbt test` và đối chiếu số dòng, tổng sales, tổng profit với tầng trước.
- Không sửa file gốc trong `docs/`. Báo cáo và slide đặt trong `report/`.
- Số liệu nêu trong báo cáo phải lấy từ truy vấn trên Gold, ghi lại câu SQL trong `sql/checks`.
