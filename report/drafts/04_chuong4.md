# CHƯƠNG 4. THỬ NGHIỆM, PHÂN TÍCH VÀ DIỄN GIẢI KẾT QUẢ

Toàn bộ hệ thống được xây dựng lại từ đầu trên DuckDB. Mọi con số trong chương được truy vấn trực tiếp từ kho sau một lần chạy pipeline đầy đủ (`python scripts/run_all.py`). Các câu SQL đối chiếu được lưu trong `sql/checks/`, và số liệu dùng trong báo cáo được ghi lại tại `results/tables/key_numbers.json`.

## 4.1. Môi trường và trạng thái triển khai

Hệ thống chạy trên máy tính cá nhân Windows 11 với Python 3.11, DuckDB 1.5, dbt Core 1.12 và dbt-duckdb 1.11. Toàn bộ pipeline, từ nạp CSV đến xuất CSV cho Power BI, mất khoảng 50 giây. Riêng bước `dbt build` (21 model, 1 seed, 101 kiểm thử dữ liệu) mất khoảng 10 giây.

::table B4.1 | Trạng thái triển khai từng hạng mục | Nhóm thực hiện
| Hạng mục | Trạng thái | Sản phẩm / minh chứng |
|---|---|---|
| Nạp Bronze | Hoàn thành | 4 bảng trong schema bronze; số dòng khớp 100% với CSV |
| Khảo sát chất lượng | Hoàn thành | 16 quy tắc profiling ({B2.4}), {H2.2} |
| Silver bằng dbt | Hoàn thành | 4 model, toàn bộ kiểm thử đạt |
| Gold (Kimball) | Hoàn thành | fact_sales, fact_monthly_snapshot, 6 dimension, kiểm thử đối chiếu |
| KPI và data mart | Hoàn thành | Metric catalog 9 KPI; 5 data mart và mart_kpi_overview |
| Khai phá dữ liệu và học máy (Python) | Hoàn thành | Phân cụm, phân lớp, luật kết hợp, hồi quy, chuỗi thời gian; 10 phiên bản trong ml.model_registry |
| Xuất dữ liệu cho dashboard | Hoàn thành | 14 file CSV trong exports/powerbi |
| Dashboard Power BI | Có đặc tả, nhóm dựng | 4 trang theo Phụ lục C |

::screenshot H4.1 | Kết quả dbt build: các model được tạo và toàn bộ kiểm thử đạt | Chạy: python scripts/run_dbt.py build, chụp phần cuối terminal có dòng "Done. PASS=124 WARN=0 ERROR=0"

::screenshot H4.2 | Kho DuckDB với các schema bronze, silver, gold, mart, ml và danh sách bảng | Mở warehouse/xomecom.duckdb bằng DBeaver (hoặc DuckDB CLI: SHOW ALL TABLES), chụp cây schema

::csvtable B4.2b | Số bảng và số dòng theo từng schema của kho | Truy vấn duckdb_tables() | B4.1_tables_per_schema.csv | table_schema:Schema:str;table_name:Bảng:str;rows:Số dòng:int | table_schema in ['bronze','silver','gold','mart']

## 4.2. Kết quả tầng Bronze và Silver

Số dòng giao dịch, số `row_id` phân biệt, tổng doanh thu và tổng lợi nhuận được bảo toàn 100% từ Bronze sang Silver ({B4.2}). Các ngoại lệ được xử lý đúng quy tắc của {B3.2}: 124 khách thiếu giới tính được gán `Unknown`, 3 dòng có mã không khớp được gắn cờ, và 11.041 dòng lỗ được giữ nguyên.

::table B4.2 | Đối chiếu trước và sau xử lý Silver | Nhóm thực hiện, script 01_profiling.py
| Chỉ tiêu | Trước xử lý (Bronze) | Sau xử lý (Silver) |
|---|---|---|
| Dòng giao dịch | 51.290 | 51.290 |
| row_id phân biệt | 51.290 | 51.290 |
| Tổng sales (USD) | 6.517.674,00 | 6.517.674,00 |
| Tổng profit (USD) | 1.065.413,58 | 1.065.413,58 |
| Khách thiếu gender | 124 | 0 (gán Unknown, ảnh hưởng 362 dòng) |
| Dòng không khớp customer | 0 | 0 |
| Dòng không khớp product / region | 2 / 2 | 2 / 2 (gắn cờ, không xóa) |
| Dòng lợi nhuận âm | 11.041 | 11.041 (giữ nguyên) |

## 4.3. Kiểm tra tầng Gold

**Đối chiếu số liệu.** {B4.3} cho thấy số dòng, tổng doanh thu, tổng lợi nhuận, số đơn và số khách khớp tuyệt đối giữa ba tầng. Không có dòng nào bị nhân bản khi nối dimension (fan-out), vì số dòng `fact_sales` bằng số `row_id` phân biệt. Không có khóa ngoại NULL: 2 dòng rơi vào product Unknown và 2 dòng rơi vào region Unknown, đúng bằng số dòng gắn cờ ở Silver. Các điều kiện này cũng được viết thành kiểm thử dbt (`tests/assert_*.sql`), nên pipeline sẽ dừng nếu chúng bị vi phạm trong tương lai.

::table B4.3 | Đối chiếu Gold với Bronze và Silver | Script 09_checks.py, SQL lưu tại sql/checks/reconcile_layers.sql
| Chỉ tiêu | Bronze | Silver | Gold | Khớp |
|---|---|---|---|---|
| Số dòng giao dịch | 51.290 | 51.290 | 51.290 | Có |
| Tổng sales (USD) | 6.517.674,00 | 6.517.674,00 | 6.517.674,00 | Có |
| Tổng profit (USD) | 1.065.413,58 | 1.065.413,58 | 1.065.413,58 | Có |
| Số đơn hàng | 25.728 | 25.728 | 25.728 | Có |
| Số khách hàng | 17.415 | 17.415 | 17.415 (+1 Unknown) | Có |
| Dòng rơi vào product / region Unknown (-1) | – | 2 / 2 (cờ) | 2 / 2 | Có |
| Dòng có khóa ngoại NULL | – | – | 0 | Có |

**Kiểm thử dbt.** Lần chạy `dbt build` cuối cùng có 124 nút đều đạt: 21 model, 1 seed, 101 kiểm thử dữ liệu và 1 hook ghi log. Các kiểm thử chia thành năm nhóm:

1. Tính duy nhất và không rỗng của khóa.
2. Miền giá trị (`accepted_values`).
3. Toàn vẹn tham chiếu từ fact tới sáu dimension (`relationships`).
4. Tính duy nhất theo grain của snapshot và các data mart (kiểm thử tự viết `unique_combination`).
5. Bốn kiểm thử đối chiếu nghiệp vụ tự viết: bảo toàn số dòng qua các tầng, khớp tổng tiền, thành viên Unknown khớp cờ, và lưới snapshot đủ 720 ô.

Trong quá trình phát triển, kiểm thử grain đã phát hiện một lỗi thiết kế. Data mart địa lý ban đầu dùng grain năm × quốc gia, nhưng Mỹ được chia thành 4 region và Sudan thành 2 region, nên grain đúng phải là năm × quốc gia × region. Ví dụ này cho thấy giá trị của việc kiểm thử theo grain.

**Sắp xếp theo order_date.** Cùng một truy vấn (doanh thu quý 4/2023 theo thị trường) được chạy 15 lần trên bảng đã sắp xếp và bảng xáo trộn ngẫu nhiên, ở hai quy mô: dữ liệu thật và dữ liệu nhân bản 20 lần (khoảng 1 triệu dòng). Kết quả ở {B4.4}. Ở quy mô thật, 51 nghìn dòng chỉ nằm trong một row group (DuckDB dùng row group 122.880 dòng), nên sắp xếp gần như không tạo khác biệt. Ở quy mô khoảng 1 triệu dòng, bảng đã sắp xếp nhanh hơn rõ rệt (khoảng 3–5 lần tùy lần chạy), vì DuckDB dùng thống kê min/max của từng row group để bỏ qua các khối ngoài quý 4/2023. Kết quả EXPLAIN ANALYZE được lưu tại `results/tables/B4.4b_explain_*.txt`. Như vậy việc sắp xếp chưa cần thiết với dữ liệu hiện tại, nhưng sẽ có lợi khi kho lớn lên.

::csvtable B4.4 | Thời gian chạy truy vấn mẫu trên bảng có và không sắp xếp theo order_date (trung vị 15 lần, 1 luồng) | Script 06_analysis_sql.py | B4.4_sort_benchmark.csv | scale:Quy mô:str;table_rows:Số dòng bảng:int;layout:Bố cục:str;rows_matching_filter:Dòng thỏa điều kiện:int;median_ms:Trung vị (ms):f2;speedup_vs_unsorted:Nhanh hơn (lần):f2

## 4.4. Phân tích kinh doanh

### 4.4.1. Q1 – Chiết khấu và ngưỡng lỗ

Trong toàn kỳ, dòng không giảm giá không có dòng nào lỗ và đạt biên 31,3%. Biên giảm dần theo mức chiết khấu ({H4.3}): còn 20,1% ở nhóm đến 10%, 11,8% ở nhóm 10–20%, 5,8% ở nhóm 20–30%, rồi âm từ nhóm trên 30%. Mọi dòng giảm trên 50% đều lỗ; riêng 318 dòng giảm từ 80% trở lên lỗ trung bình 46 USD mỗi dòng. Các dòng giảm giá sâu (trên 30%) chiếm 20,2% số dòng và 20,6% doanh thu, nhưng tạo ra khoản lỗ ròng 295.701 USD, tương đương 27,8% tổng lợi nhuận của toàn sàn.

::figure H4.3 H4.3_margin_by_discount_level.png | Biên lợi nhuận (cột) và tỷ lệ dòng lỗ (đường) theo từng mức chiết khấu, có đường 0 để thấy ngưỡng lỗ | Data mart mart_discount_analysis

Mô hình what-if (mục 4.5.3) ước lượng ngưỡng hòa vốn khoảng 27,5% ở cả năm ngành hàng. Kết quả này khớp với quan sát thực tế: biên còn dương ở nhóm 20–30% và chuyển âm ngay sau 30%.

### 4.4.2. Q2 – P&L theo phân khúc

::csvtable B4.5 | P&L theo phân khúc: doanh thu, chi phí ngầm, lợi nhuận và biên (toàn kỳ) | Data mart mart_segment_profitability | B4.5_segment_pnl.csv | segment:Phân khúc:str;revenue:Doanh thu (USD):usd;implied_cost:Chi phí ngầm (USD):usd;profit:Lợi nhuận (USD):usd;margin:Biên:pct1;share_revenue:Tỷ trọng DT:pct1;share_profit:Tỷ trọng LN:pct1;loss_amount:Lỗ từ dòng lỗ (USD):usd | year == 0

::csvtable B4.5y | Biên lợi nhuận theo phân khúc và theo năm | Data mart mart_segment_profitability | B4.5_segment_pnl.csv | segment:Phân khúc:str;year:Năm:str;revenue:Doanh thu (USD):usd;profit:Lợi nhuận (USD):usd;margin:Biên:pct1;orders:Số đơn:int | year > 0

Corporate đúng là nguồn lợi nhuận lớn nhất: 608.523 USD, chiếm 57,1% lợi nhuận toàn sàn ({B4.5}). Tuy vậy, Corporate không phải phân khúc hiệu quả nhất:

- **Biên thấp nhất:** biên của Corporate (15,8%) thấp hơn Consumer (17,0%) và Self-Employed (17,3%).
- **Lỗ nhiều nhất:** các dòng lỗ của Corporate làm mất 213.475 USD, gấp đôi Consumer.
- **Biên giảm sớm nhất:** biên của Corporate đã bắt đầu giảm từ năm 2022 (16,3%), trong khi Consumer khi đó vẫn tăng lên 20,6% ({B4.5y}).

{B4.6} lý giải vì sao Corporate lớn. Phân khúc này có ít khách hơn Consumer (5.221 so với 8.987), số đơn mỗi khách gần như bằng nhau (khoảng 1,48), nhưng giá trị đơn trung bình cao gấp ba (497 USD so với 161 USD). Mức chiết khấu bình quân và tỷ lệ giảm giá sâu giữa ba phân khúc gần như bằng nhau (khoảng 14% và 20%). Vì vậy biên thấp hơn của Corporate không đến từ chiết khấu mà đến từ cơ cấu chi phí của đơn hàng lớn.

::csvtable B4.6 | Đặc điểm khách hàng theo phân khúc | Data mart mart_customer_value | B4.5d_segment_customers.csv | segment:Phân khúc:str;customers:Số khách:int;avg_orders:Đơn/khách:f2;aov:AOV (USD):f1;avg_monetary:Doanh thu/khách (USD):f1;avg_profit_per_customer:Lợi nhuận/khách (USD):f1;avg_discount:Chiết khấu TB:pct1;deep_share:Tỷ lệ giảm sâu:pct1

**Kết luận Q2:** Corporate là "cash cow" về quy mô nhưng không phải về hiệu quả. Hợp đồng Corporate nên được đánh giá theo biên lợi nhuận, không chỉ theo doanh thu.

### 4.4.3. Q3 – Sức khỏe thị trường

::figure H4.4 H4.4_market_growth_margin.png | Tăng trưởng doanh thu và biên lợi nhuận theo thị trường, so sánh 2022 với 2023 | Gold fact_sales, fact_monthly_snapshot

::csvtable B4.7 | Doanh thu, tăng trưởng, biên và tỷ lệ giảm giá sâu theo thị trường, 2022–2023 | Gold, data mart mart_segment_profitability | B4.5b_market_by_year.csv | market:Thị trường:str;year:Năm:str;revenue:Doanh thu (USD):usd;growth:Tăng trưởng:pct1;margin:Biên:pct1;deep_share:Tỷ lệ dòng giảm > 30%:pct1;avg_discount:Chiết khấu TB:pct1 | year >= 2022

Tăng trưởng doanh thu toàn sàn chững lại một chút, từ 26,0% năm 2022 xuống 23,8% năm 2023. Năm thị trường có diễn biến khác nhau ({H4.4}, {B4.7}):

- **Europe – tăng trưởng lành mạnh.** Tăng trưởng nhanh nhất năm 2023 (+45,6%), biên cao nhất (18,5% năm 2023, 22,3% toàn kỳ), tỷ lệ giảm giá sâu thấp (14,0%). Europe là ứng viên số một để đầu tư mở rộng.
- **Asia Pacific – tăng trưởng nhờ giảm giá.** Doanh thu lớn nhất và vẫn tăng 21,9%, nhưng biên rơi từ 13,4% xuống 7,2%. Đây cũng là thị trường giảm giá sâu nhiều nhất (29,0% số dòng năm 2023, chiết khấu bình quân 18,7%). Trong thị trường này, Indonesia gần như hòa vốn và Thổ Nhĩ Kỳ lỗ 29% doanh thu.
- **LATAM – có dấu hiệu bão hòa.** Tăng trưởng chậm nhất (+12,9%, giảm từ +36,1% năm 2022), biên giảm từ 18,6% xuống 12,4%, và tỷ lệ giảm giá sâu cao (26,0%).
- **USCA và Africa – tăng trưởng trung bình.** Tăng khoảng 17–19%; biên giảm ở mức trung bình. Riêng USCA có tỷ lệ giảm giá sâu thấp nhất (11,2%).

**Kết luận Q3:** ưu tiên Europe cho mở rộng; ở Asia Pacific và LATAM cần siết chính sách giảm giá trước khi đầu tư thêm, vì tăng trưởng ở đây đang được mua bằng biên lợi nhuận.

### 4.4.4. Q4 – Giá trị khách hàng và hành vi mua lặp

Trong 17.415 khách, 11.979 khách (68,8%) chỉ mua một lần trong bốn năm; bình quân mỗi khách mua 1,48 đơn. Phân tích cohort theo năm mua đầu tiên ({H4.6}) cho thấy chỉ 18–21% khách quay lại vào năm kế tiếp. Tỷ lệ này cải thiện nhẹ qua các cohort (18,1% với cohort 2020, 19,4% với cohort 2021, 21,3% với cohort 2022). Đáng chú ý, khách cohort 2020 có xu hướng quay lại muộn: 25,4% hoạt động trở lại trong năm 2023. Điều này cho thấy khách không hẳn rời bỏ mà mua thưa, đúng với đặc thù ngành mỹ phẩm.

::figure H4.6 H4.6_cohort_heatmap.png | Tỷ lệ khách hoạt động theo cohort năm mua đầu tiên | Data mart mart_customer_cohort

Phân nhóm RFM theo quy tắc (tính tại 31/12/2023, frequency đếm theo số đơn) cho thấy lợi nhuận tập trung ở ba nhóm Loyal, Big One-time và Champions, chiếm 71,7% lợi nhuận dù chỉ có 38,5% số khách ({B4.8}). Nhóm Hibernating đông nhất (34,0% số khách) nhưng chỉ đóng góp 8,4% lợi nhuận. Kết quả phân cụm K-Means ở mục 4.5.1 bổ sung góc nhìn về chiết khấu.

::csvtable B4.8 | Phân nhóm khách hàng theo RFM | Data mart mart_customer_value | B4.6c_rfm_segments.csv | rfm_segment:Nhóm RFM:str;customers:Số khách:int;share_customers:Tỷ trọng khách:pct1;recency_days:Recency TB (ngày):f1;frequency:Số đơn TB:f2;monetary:Doanh thu TB (USD):f1;profit:Lợi nhuận (USD):usd;share_profit:Tỷ trọng LN:pct1

**Luật kết hợp (Apriori).** Mỗi đơn hàng được xem là một giao dịch, mỗi subcategory là một item (17 item, 25.728 giao dịch); 47,9% số đơn có từ hai subcategory trở lên. Thuật toán Apriori được cài theo đúng các bước của bài giảng: tìm tập phổ biến kích thước 1 (L1), sinh ứng viên kích thước 2 (C2) từ L1, tỉa các ứng viên có tập con không phổ biến, đếm support để được L2, lặp lại cho L3, rồi sinh luật X ⇒ Y và lọc theo minconf. Kết quả ở {B4.9a} cho thấy dù hạ minsup từ 1% xuống 0,2% (52 đơn) để có thêm tập phổ biến, **không có luật nào đạt minconf 80% (ngưỡng thường dùng trong bài giảng), thậm chí không có luật nào đạt 50%**; độ tin cậy cao nhất chỉ 33%. Phép tính cặp bằng SQL cho kết quả tương tự: lift cao nhất ở mức cặp chỉ khoảng 1,30 (fragrances và candles, sprays, diffusers), các cặp còn lại đều dưới 1,15 ({B4.9}). Kết luận: khách không có thói quen mua theo "bộ sản phẩm" rõ ràng, nên chiến lược bán chéo theo cặp ngành hàng khó tạo tác động lớn; gợi ý sản phẩm theo lịch sử mua của từng khách là hướng hợp lý hơn. Đây là một kết quả âm nhưng có giá trị, vì giúp doanh nghiệp tránh đầu tư vào chương trình combo kém hiệu quả.

::csvtable B4.9a | Kết quả Apriori trên giỏ hàng subcategory theo các ngưỡng minsup và minconf | Script 06_analysis_sql.py, bảng ml.apriori_rules | B4.6e_apriori_thresholds.csv | minsup:minsup:pct1;min_orders:Số đơn tối thiểu:int;L1:Số tập L1:int;L2:Số tập L2:int;L3:Số tập L3:int;rules_conf80:Luật conf ≥ 80%:int;rules_conf50:Luật conf ≥ 50%:int;rules_conf20:Luật conf ≥ 20%:int;max_conf:Confidence cao nhất:pct1;max_lift:Lift cao nhất:f2

::csvtable B4.9 | Mười cặp subcategory có lift cao nhất (ít nhất 30 đơn chung) | SQL sql/analysis/market_basket_subcategory.sql | B4.6_market_basket.csv | antecedent:Tiền đề:str;consequent:Hệ quả:str;orders_both:Số đơn chung:int;support:Support:f4;confidence:Confidence:f3;lift:Lift:f3 | index < 10

### 4.4.5. Q5 – Vì sao biên lợi nhuận 2023 giảm

**Giảm ở mọi nơi.** Biên năm 2023 giảm so với năm 2022 ở cả 5 thị trường, 5 ngành hàng và 3 phân khúc, với mức giảm từ 2,7 đến 8,3 điểm phần trăm ({B4.10}). Một nguyên nhân cục bộ (một thị trường hay một ngành hàng) không thể giải thích sự sụt giảm đồng loạt như vậy.

::csvtable B4.10 | Biên lợi nhuận theo năm ở mọi thị trường, ngành hàng và phân khúc | Gold fact_sales | B4.5e_margin_by_year_all_dims.csv | dimension:Chiều:str;k:Giá trị:str;2020:2020:pct1;2021:2021:pct1;2022:2022:pct1;2023:2023:pct1;change_2023_vs_2022:Thay đổi 2023:pp

**Không do chiết khấu.** Biên giảm cả ở dòng không giảm giá, từ 33,0% (2022) xuống 27,7% (2023), song song với dòng có giảm giá ({H4.5}). Mức chiết khấu bình quân (14,0% so với 14,3%) và tỷ lệ dòng giảm giá sâu (20,1% so với 20,5%) gần như không đổi ({B4.11}).

::figure H4.5 H4.5_margin_nodiscount_vs_discount.png | Biên lợi nhuận theo năm của dòng không giảm giá và dòng có giảm giá | Data mart mart_discount_analysis

**Do chi phí.** Ở các dòng không giảm giá, giá bán bình quân mỗi đơn vị gần như không đổi (22,93 USD so với 22,87 USD). Trong khi đó, chi phí ngầm mỗi đơn vị tăng từ 15,35 USD lên 16,54 USD (+7,7%), sau ba năm ổn định quanh 15,4–15,6 USD ({B4.11}). Giá giữ nguyên trong khi chi phí trên mỗi đơn vị tăng, nên biên bị thu hẹp. Kết hợp với bối cảnh doanh nghiệp (logistics là chi phí lớn của thương mại điện tử), nhóm đưa ra giả thuyết rằng chi phí vận hành, nhiều khả năng là phí logistics, đã tăng trong năm 2023. Dữ liệu không có cột chi phí chi tiết nên chưa phân rã được thành phần (xem hạn chế ở Chương 5).

::csvtable B4.11 | Giá bán, chiết khấu và chi phí ngầm mỗi đơn vị theo năm | Gold fact_sales | B4.5f_price_discount_cost_by_year.csv | year:Năm:str;avg_unit_price:Giá/đơn vị (USD):f2;avg_discount:Chiết khấu TB:pct1;deep_share:Tỷ lệ giảm sâu:pct1;price_per_unit_nodisc:Giá/đơn vị, không giảm giá:f2;cost_per_unit_nodisc:Chi phí ngầm/đơn vị, không giảm giá:f2

**Bằng chứng từ mô hình.** Ba kết quả học máy ở mục 4.5 xác nhận rằng năm 2023 là một điểm gãy:

1. Mô hình hồi quy học trên 2020–2022 dự báo biên 2023 cao hơn thực tế khoảng 5,5 điểm phần trăm, một hiện tượng model drift.
2. Mô hình chuỗi thời gian dự báo lợi nhuận 2023 cao hơn thực tế khoảng 25%.
3. 7 trên 12 tháng của năm 2023 nằm dưới khoảng dự báo 95%.

Trong khi đó, doanh thu 2023 vẫn được dự báo khá chính xác (MAPE 6,5–8,4%). Điều này cho thấy điểm gãy nằm ở phía chi phí, không nằm ở phía cầu.

## 4.5. Kết quả học máy

### 4.5.1. Phân cụm khách hàng bằng K-Means

Bốn đặc trưng cấp khách hàng (recency, frequency, monetary, profit) được biến đổi log có dấu, để nén đuôi dài mà vẫn giữ thứ tự cho lợi nhuận âm, rồi chuẩn hóa bằng StandardScaler. K-Means được chạy với k từ 2 đến 6 ({H4.7}, {B4.12}). Silhouette cao nhất ở k = 3 (0,327), còn Davies-Bouldin thấp nhất ở k = 5 (1,010). Các giá trị silhouette chỉ ở mức 0,29–0,33, tức là cụm tách ở mức trung bình. Nguyên nhân là đa số khách chỉ có 1 đơn, nên đặc trưng frequency ít phân tán. Nhóm chọn **k = 4** vì đây là điểm cân bằng: silhouette 0,291 chỉ thấp hơn mức tốt nhất 0,036, Davies-Bouldin 1,127 tốt hơn k = 2 và k = 3, và bốn cụm có ý nghĩa kinh doanh rõ ràng, tách riêng được nhóm khách gây lỗ.

::figure H4.7 H4.7_kmeans_k_selection.png | Chọn số cụm K-Means theo Silhouette và Davies-Bouldin | Bảng ml.kmeans_k_selection

::csvtable B4.12 | Chỉ số đánh giá K-Means theo số cụm k | Bảng ml.kmeans_k_selection | B4.7a_k_selection.csv | k:k:str;silhouette:Silhouette:f3;davies_bouldin:Davies-Bouldin:f3;inertia:Inertia:usd

::csvtable B4.13 | Đặc điểm bốn cụm khách hàng (k = 4) | Bảng ml.cluster_profile, gán nhãn bằng predict() rồi tổng hợp bằng SQL | B4.7_cluster_profile.csv | cluster_name:Cụm:str;customers:Số khách:int;recency_days:Recency (ngày):f1;frequency:Số đơn TB:f2;monetary:Doanh thu TB (USD):f1;margin:Biên:pct1;avg_discount:Chiết khấu TB:pct1;repeat_rate:Tỷ lệ mua lặp:pct1;share_profit:Tỷ trọng LN:pct1

::figure H4.7b H4.7b_cluster_scatter.png | Phân bố bốn cụm khách hàng theo recency và monetary | Bảng ml.customer_clusters

Bốn cụm khách hàng ({B4.13}):

- **Trung thành, giá trị cao** (3.423 khách, 19,7%): bình quân 2,74 đơn, mua gần nhất cách đây khoảng 6 tháng, 96% có mua lặp. Nhóm này tạo 56,4% lợi nhuận. Đây là nhóm cần giữ chân bằng chương trình khách hàng thân thiết, không cần giảm giá sâu.
- **Mua một lần, giá trị cao** (5.900 khách, 33,9%): đơn lớn (410 USD), biên rất tốt (28,2%), ít dùng chiết khấu (5%), nhưng đã khoảng 22 tháng không quay lại. Nhóm này tạo 64,0% lợi nhuận, là nhóm có tiềm năng kích hoạt lại lớn nhất.
- **Mua một lần, giá trị thấp** (5.335 khách, 30,6%): đơn nhỏ (42 USD), đóng góp 3,8% lợi nhuận.
- **Săn giảm giá, gây lỗ** (2.757 khách, 15,8%): chiết khấu trung bình 45%, biên −20%, làm mất 256.630 USD (tương đương −24,1% lợi nhuận). Nhóm này không nên nhận thêm mã giảm giá.

Thu nhập trung vị và nghề nghiệp phổ biến nhất (Professional) giống nhau ở cả bốn cụm. Như vậy giá trị khách hàng được quyết định bởi **hành vi** (mức chiết khấu, tần suất), không bởi nhân khẩu học. Đây là lý do 68,8% khách chỉ mua một lần: không có nhóm nhân khẩu học nào "trung thành tự nhiên". Mua lặp phải được tạo ra bằng chính sách giữ chân, không thể dựa vào việc nhắm đúng phân khúc dân số.

### 4.5.2. Hồi quy biên lợi nhuận

::csvtable B4.14 | Kết quả hồi quy biên lợi nhuận trên tập huấn luyện 2020–2022 và tập kiểm tra 2023 | Bảng ml.margin_model_metrics | B4.8_margin_model_metrics.csv | model:Mô hình:str;split:Tập dữ liệu:str;R2:R²:f3;MAE:MAE:f3;mean_actual_margin:Biên thực tế TB:pct1;mean_predicted_margin:Biên dự báo TB:pct1;weighted_margin_bias:Sai lệch biên (theo DT):pp

Hai mô hình đạt R² khoảng 0,55–0,65 ({B4.14}). HistGradientBoosting tốt hơn hồi quy tuyến tính một chút (R² 0,651 so với 0,635 trên tập kiểm tra 2023; MAE 0,128 so với 0,132). R² trên tập kiểm tra cao hơn trên tập huấn luyện vì năm 2023 có phương sai biên lớn hơn, nên phần chiết khấu giải thích được chiếm tỷ trọng lớn hơn. Tuy nhiên, **sai lệch có hệ thống** trên tập 2023 lại lớn: mô hình dự báo biên cao hơn thực tế 5,5 điểm phần trăm, trong khi sai lệch này gần như bằng 0 trên tập huấn luyện. Đây là biểu hiện của **model drift** ({H4.8b}): quan hệ giữa đặc trưng và biên đã thay đổi trong năm 2023. Biên thực tế nằm dưới đường dự báo ở hầu hết các tháng, khớp với kết luận ở mục 4.4.5.

::figure H4.8b H4.8b_margin_drift.png | Model drift: biên lợi nhuận thực tế và biên dự báo bởi mô hình học trên 2020–2022 | Bảng ml.margin_drift_by_month

Permutation importance ({H4.8}) cho thấy chiết khấu chi phối gần như hoàn toàn: khi xáo trộn cột chiết khấu, R² giảm khoảng 1,43. Các đặc trưng khác như subcategory (0,008), thị trường (0,006) và các thuộc tính khách hàng có ảnh hưởng không đáng kể. Nói cách khác, trong cùng một năm, biên của một giao dịch được quyết định bởi mức giảm giá.

::figure H4.8 H4.8_feature_importance.png | Mức quan trọng của đặc trưng theo permutation importance trên tập kiểm tra 2023 | Bảng ml.margin_feature_importance

### 4.5.3. What-if chiết khấu

Mô hình triển khai là HistGradientBoosting huấn luyện trên toàn bộ 2020–2023, có thêm đặc trưng năm để nắm mức biên riêng của 2023, và có ràng buộc đơn điệu (chiết khấu tăng thì biên không tăng). Mô hình được áp lên toàn bộ dòng giao dịch năm 2023 với chiết khấu được gán lại ở từng mức, các yếu tố khác giữ nguyên. Lợi nhuận dự báo ở kịch bản gốc (281.224 USD) khớp với thực tế (279.929 USD), cho thấy mô hình đã được hiệu chỉnh tốt.

::figure H4.9 H4.9_whatif_discount.png | What-if: biên lợi nhuận dự báo theo mức chiết khấu, mỗi ngành hàng một đường | Bảng ml.whatif_discount

::csvtable B4.15 | Biên lợi nhuận dự báo năm 2023 theo mức chiết khấu và ngành hàng | Bảng ml.whatif_discount | B4.9a_whatif_margin_by_category.csv | category:Ngành hàng:str;0.0:0%:pct1;0.1:10%:pct1;0.2:20%:pct1;0.3:30%:pct1;0.4:40%:pct1;0.5:50%:pct1

Biên dự báo dương đến mức chiết khấu 27,5% và âm từ 30% ở cả năm ngành hàng ({H4.9}, {B4.15}). Ngưỡng này giống nhau giữa các ngành hàng vì mô hình gần như chỉ dùng chiết khấu để dự báo biên. Kịch bản đặt trần chiết khấu ({B4.16}, {H4.9b}) ước lượng như sau: nếu mọi dòng giảm vượt 30% được đưa về 30%, lợi nhuận 2023 tăng khoảng 85 nghìn USD (+30%) và biên tăng từ 12,8% lên khoảng 16,7%; trần 20% cho mức tăng cao hơn (khoảng 152 nghìn USD). Các ước lượng này giả định doanh thu giữ nguyên. Thực tế một phần khách săn giảm giá sẽ không mua nữa, nên con số cần được hiểu là **cận trên** và cần kiểm chứng bằng thử nghiệm A/B.

::csvtable B4.16 | Kịch bản trần chiết khấu năm 2023 (giữ nguyên doanh thu) | Bảng ml.whatif_discount_cap | B4.9c_discount_cap_scenarios.csv | cap:Trần chiết khấu:pct0;rows_affected:Số dòng bị ảnh hưởng:int;pred_profit_baseline:LN dự báo hiện tại (USD):usd;pred_profit_capped:LN dự báo khi có trần (USD):usd;uplift:Tăng thêm (USD):usd;uplift_pct:Tăng thêm:pct1;pred_margin_capped:Biên dự báo:pct1

::figure H4.9b H4.9b_discount_cap.png | Lợi nhuận tăng thêm dự báo theo từng mức trần chiết khấu năm 2023 | Bảng ml.whatif_discount_cap

### 4.5.4. Chuỗi thời gian và phát hiện bất thường

::csvtable B4.17 | Đánh giá mô hình chuỗi thời gian trên năm 2023 (học trên 2020–2022) | Bảng ml.ts_model_metrics | B4.10_ts_metrics.csv | target:Chuỗi:str;model:Mô hình:str;MAPE_2023:MAPE 2023:pct1;forecast_total_2023:Tổng dự báo 2023 (USD):usd;actual_total_2023:Tổng thực tế 2023 (USD):usd;gap_pct:Thực tế so với dự báo:pct1

Doanh thu theo tháng có xu hướng tăng và mùa vụ rõ (thấp vào đầu năm, đỉnh vào tháng 6 và các tháng cuối năm). Cả hai mô hình dự báo doanh thu 2023 tốt: MAPE 8,4% với ETS và 6,5% với SARIMA ({B4.17}). Ngược lại, lợi nhuận thực tế 2023 thấp hơn dự báo 25–30%. Bảy tháng (01, 02, 05, 09, 10, 11 và 12/2023) nằm dưới khoảng dự báo 95% của SARIMA và được đánh dấu bất thường ({H4.10}). Ngoài ra, phần dư chuẩn hóa của mô hình ETS toàn kỳ đánh dấu thêm ba tháng có biến động lớn trước đó: 11/2021 (cao bất thường), 08/2022 và 11/2022 (thấp bất thường). Dự báo sáu tháng đầu năm 2024 bằng ETS học trên toàn kỳ cho doanh thu khoảng 1,01 triệu USD và lợi nhuận khoảng 122 nghìn USD (biên khoảng 12%), tức là biên thấp của năm 2023 sẽ tiếp diễn nếu không có thay đổi về chi phí hoặc chính sách giá.

::figure H4.10 H4.10_timeseries_forecast.png | Chuỗi doanh thu và lợi nhuận theo tháng: thực tế, dự báo 2023 từ mô hình 2020–2022, dự báo 6 tháng 2024 và các tháng bất thường | Bảng ml.forecast_monthly, ml.monthly_anomalies

### 4.5.5. Phân lớp khách hàng quay lại

Bài toán: ngay sau đơn hàng đầu tiên, dự đoán khách có mua đơn thứ hai trong vòng 365 ngày hay không. Nếu dự đoán được, bộ phận CRM có thể dồn ngân sách giữ chân vào đúng nhóm khách. Dữ liệu gồm 12.780 khách có đơn đầu từ 2020 đến hết 2022 (để ai cũng có đủ 365 ngày quan sát); 17,8% trong số đó quay lại. Dữ liệu được chia theo cohort: huấn luyện trên khách có đơn đầu năm 2020–2021 (8.361 khách), kiểm tra trên khách năm 2022 (4.419 khách). Hai thuật toán phân lớp của bài giảng được dùng: cây quyết định với tiêu chí entropy (cùng nguyên lý information gain của ID3/C4.5), giới hạn độ sâu 4 để đọc được luật, và Naive Bayes trên các đặc trưng đã rời rạc hóa.

::csvtable B4.19 | Kết quả phân lớp khách quay lại trên tập kiểm tra (cohort 2022) | Bảng ml.repeat_classifier_metrics | B4.19_repeat_classifier_metrics.csv | model:Mô hình:str;AUC:AUC:f3;F1:F1:f3;precision:Precision:f3;recall:Recall:f3;return_rate_top20:Tỷ lệ quay lại ở top 20%:pct1;lift_top20:Lift top 20%:f2;base_rate:Tỷ lệ chung:pct1

Hai mô hình cho kết quả gần như nhau: AUC 0,65 và F1 khoảng 0,37 ({B4.19}). Đây là mức dự báo **yếu đến trung bình**, dễ hiểu vì đơn đầu chứa ít thông tin về ý định quay lại (không có dữ liệu lượt xem, giỏ hàng bỏ dở hay đánh giá). Tuy vậy mô hình vẫn có giá trị xếp hạng: 20% khách có điểm cao nhất quay lại 32,0%, gấp 1,7 lần tỷ lệ chung 19,1%, còn 10% khách điểm thấp nhất chỉ quay lại 6,1% ({H4.13}). Nếu ngân sách giữ chân chỉ đủ cho một phần năm số khách mới, chọn theo điểm mô hình sẽ hiệu quả gần gấp đôi chọn ngẫu nhiên.

::figure H4.13 H4.13_classifier_confusion_lift.png | Ma trận nhầm lẫn của cây quyết định và tỷ lệ quay lại thực tế theo decile điểm dự đoán (cohort 2022) | Bảng ml.repeat_scores

Cây quyết định dùng hai đặc trưng chính: **thị trường** (57,7% mức giảm entropy) và **chiết khấu của đơn đầu** (31,1%); các thuộc tính nhân khẩu học gần như không có vai trò, khớp với kết luận từ K-Means. {B4.20} liệt kê các luật if-then của cây. Hai luật có ý nghĩa kinh doanh nhất:

- Khách ở USCA quay lại nhiều nhất (20–31% tùy nhánh), còn khách ở Africa gần như không quay lại (dưới 12% ở mọi nhánh). Theo toàn bộ dữ liệu, tỷ lệ quay lại theo thị trường là USCA 27,9%, Europe 19,2%, Asia Pacific 16,5%, LATAM 15,7% và Africa 5,7%. Đây là một chiều mới cho đánh giá sức khỏe thị trường ở Q3: Africa không chỉ có biên thấp mà còn không giữ được khách.
- Ở Asia Pacific, Europe và LATAM, khách có đơn đầu được giảm nhẹ (từ 1,5% đến 23,4%) quay lại 24,4%, cao hơn khách không được giảm (15,8%) và cao gấp đôi khách được giảm trên 23,4% (7,7–12,4%).

::csvtable B4.20 | Luật if-then của cây quyết định (tỷ lệ quay lại tính trên tập huấn luyện) | Bảng ml.repeat_tree_rules | B4.19b_tree_rules.csv | rule:Điều kiện (IF):str;customers_train:Số khách:int;return_rate_train:Tỷ lệ quay lại:pct1;prediction:Dự đoán (THEN):str

{H4.12} kiểm tra lại phát hiện về chiết khấu trên toàn bộ 12.780 khách: tỷ lệ quay lại cao nhất ở nhóm giảm đến 10% (30,6%), giảm dần ở 10–20% (23,5%) và 20–30% (18,0%), thấp nhất ở 30–50% (11,7%), trong khi khách không được giảm chỉ quay lại 16,0%. Như vậy **giảm giá nhẹ ở đơn đầu đi cùng khả năng giữ chân cao hơn, còn giảm sâu thì không**, tức là giảm sâu vừa làm mất lợi nhuận (Q1) vừa không mua được lòng trung thành (Q4). Lưu ý đây là quan hệ tương quan trên dữ liệu quan sát, chưa phải quan hệ nhân quả; cần thử nghiệm A/B để xác nhận trước khi đưa thành chính sách.

::figure H4.12 H4.12_repeat_by_first_discount.png | Tỷ lệ khách quay lại trong 365 ngày theo mức chiết khấu của đơn hàng đầu tiên | Bảng ml.repeat_by_first_discount

## 4.6. Dashboard

Dashboard được dựng bằng Power BI, nguồn dữ liệu là 14 file CSV xuất từ data mart và schema `ml` (thư mục `exports/powerbi`). File dashboard được sinh bằng mã (`scripts/11_build_powerbi.py`, định dạng PBIP) nên có thể dựng lại sau mỗi lần chạy pipeline. Dashboard có bốn trang kể chuyện theo bốn pain point, mỗi trang kết thúc bằng một khuyến nghị hành động. Bộ lọc dùng chung gồm năm, thị trường, phân khúc và ngành hàng. Đặc tả chi tiết (visual, measure DAX, quan hệ bảng) nằm ở Phụ lục C.

- **Trang 1 – Overview:** thẻ KPI (doanh thu, lợi nhuận, biên, số đơn, AOV, tỷ lệ khách quay lại), biểu đồ doanh thu và biên theo năm, biểu đồ đường lợi nhuận theo tháng kèm dự báo và điểm bất thường. Khuyến nghị: rà soát chi phí vận hành 2023.
- **Trang 2 – Segment và Discount:** P&L theo phân khúc, biên theo mức chiết khấu có đường 0, kịch bản trần chiết khấu. Khuyến nghị: trần chiết khấu 30%.
- **Trang 3 – Geography:** bản đồ doanh thu và biên theo quốc gia, so sánh tăng trưởng và biên 2022–2023 theo thị trường. Khuyến nghị: ưu tiên Europe, siết giảm giá ở Asia Pacific.
- **Trang 4 – Customer Clusters:** bốn cụm K-Means, nhóm RFM, cohort quay lại. Khuyến nghị: giữ chân nhóm trung thành, kích hoạt lại nhóm "Mua một lần, giá trị cao".

::screenshot H4.11 | Bốn trang dashboard Power BI | Chụp 4 trang dashboard sau khi dựng theo Phụ lục C (có thể ghép 4 ảnh thành lưới 2 x 2)

## 4.7. Khuyến nghị cho ban lãnh đạo

::table B4.18 | Khuyến nghị hành động, bằng chứng, tác động ước tính và độ chắc chắn | Nhóm thực hiện, tổng hợp từ mục 4.4 và 4.5
| Hành động | Bằng chứng (số liệu) | Tác động ước tính | Độ chắc chắn |
|---|---|---|---|
| Đặt trần chiết khấu 30%; mọi chương trình giảm trên 30% phải được Tài chính phê duyệt | Biên âm từ mức trên 30%; ngưỡng hòa vốn mô hình khoảng 27,5%; dòng giảm sâu lỗ 295.701 USD toàn kỳ | +85 nghìn USD lợi nhuận/năm (cận trên, theo số liệu 2023) | Cao về chiều hướng; trung bình về độ lớn (cần A/B test) |
| Đánh giá hợp đồng Corporate theo biên lợi nhuận, đặt biên tối thiểu cho đơn lớn | Corporate có biên thấp nhất (15,8%), lỗ 213.475 USD; chiết khấu giống các phân khúc khác | Thu hẹp phần lỗ 213 nghìn USD | Trung bình |
| Ưu tiên Europe khi mở rộng; siết giảm giá ở Asia Pacific và LATAM | Europe +45,6%, biên 18,5%; APAC biên 7,2%, 29% dòng giảm sâu; LATAM tăng trưởng chậm lại còn +12,9% | Mỗi điểm biên ở APAC tương ứng khoảng 6 nghìn USD/năm | Cao |
| Chương trình thân thiết cho cụm "Trung thành"; chiến dịch kích hoạt lại cụm "Mua một lần, giá trị cao"; ngừng mã giảm giá cho cụm "Săn giảm giá"; với khách mới, thay mã giảm sâu bằng ưu đãi nhẹ (đến 10%) và dùng điểm cây quyết định để ưu tiên chăm sóc 20% khách có điểm cao nhất | 68,8% khách mua 1 lần; cụm trung thành tạo 56% lợi nhuận; cụm săn giảm giá làm mất 257 nghìn USD; giảm nhẹ ở đơn đầu: 30,6% quay lại so với 11,7% khi giảm 30–50%; top 20% điểm mô hình quay lại gấp 1,7 lần | Mỗi 1% khách "Mua một lần, giá trị cao" quay lại tạo thêm khoảng 6,8 nghìn USD lợi nhuận | Trung bình |
| Rà soát chi phí vận hành, logistics năm 2023; bổ sung dữ liệu chi phí vào kho | Biên giảm ở mọi chiều, kể cả dòng không giảm giá; chi phí ngầm/đơn vị +7,7%, giá không đổi; model drift +5,5 điểm % | Khôi phục biên về khoảng 18% tương ứng khoảng 114 nghìn USD/năm | Cao về hiện tượng; chưa xác định được nguyên nhân cụ thể |

Ghi chú cách tính tác động:

- **Asia Pacific:** doanh thu 2023 là 606 nghìn USD, nên mỗi điểm phần trăm biên tương ứng khoảng 6 nghìn USD.
- **Cụm "Mua một lần, giá trị cao":** 1% của 5.900 khách là 59 khách. Mỗi khách đóng góp bình quân 115 USD lợi nhuận, nên tổng là khoảng 6,8 nghìn USD.
- **Khôi phục biên:** (18,0% − 12,8%) × 2,19 triệu USD doanh thu 2023, khoảng 114 nghìn USD.
