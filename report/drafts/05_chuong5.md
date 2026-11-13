# CHƯƠNG 5. KẾT LUẬN

Đề tài đã xây dựng một kho dữ liệu có kiểm thử, đi từ bốn file CSV đến dashboard. Kho dữ liệu này trả lời năm câu hỏi kinh doanh của Xóm E-Com bằng số liệu có thể đối chiếu.

## 5.1. Kết quả đạt được so với mục tiêu

::table B5.1 | Đối chiếu mục tiêu với kết quả đạt được | Nhóm thực hiện
| Mục tiêu ({B1.3}) | Kết quả đạt được | Mức đạt |
|---|---|---|
| Kho dữ liệu Medallion trên DuckDB | 5 schema (bronze, silver, gold, mart, ml) trong một file; chạy lại toàn bộ trong khoảng 50 giây | Đạt |
| Chất lượng dữ liệu | 124/124 nút dbt build đạt (101 kiểm thử dữ liệu); số dòng, doanh thu, lợi nhuận, số đơn, số khách khớp tuyệt đối giữa 3 tầng | Đạt |
| Mô hình hóa Kimball | Grain row_id; 2 fact (transaction, periodic snapshot); 6 dimension có surrogate key và Unknown; degenerate và junk dimension | Đạt |
| KPI và data mart | 9 KPI trong metric catalog (macro dbt); 5 data mart + KPI overview | Đạt |
| Khai phá dữ liệu và học máy trên kho | Đủ phân lớp (cây quyết định, Naive Bayes), phân cụm (K-Means), luật kết hợp (Apriori) theo CLO5, cùng hồi quy và chuỗi thời gian; chia theo thời gian; 10 phiên bản trong ml.model_registry | Đạt |
| Trả lời Q1–Q5 | Mỗi câu có bằng chứng số liệu và khuyến nghị ({B5.2}) | Đạt |
| Dashboard | 14 file CSV và đặc tả 4 trang; nhóm dựng trên Power BI | Một phần (phụ thuộc bước dựng thủ công) |
| Tái lập | `python scripts/run_all.py`; tham số cố định (ngày tham chiếu, random_state) | Đạt |

::table B5.2 | Tổng hợp trả lời năm câu hỏi nghiên cứu | Nhóm thực hiện, tổng hợp từ Chương 4
| Câu hỏi | Kết luận | Bằng chứng chính | Khuyến nghị |
|---|---|---|---|
| Q1 Chiết khấu | Lợi nhuận bắt đầu âm khi chiết khấu vượt khoảng 27,5–30% | Biên 31,3% khi không giảm giá, −15,6% ở nhóm 30–50%, −32,3% trên 50%; giảm sâu lỗ 295.701 USD | Trần chiết khấu 30% (ước tính +85 nghìn USD/năm) |
| Q2 Phân khúc | Corporate lớn nhất nhưng kém hiệu quả nhất | 57,1% lợi nhuận nhưng biên 15,8% (thấp nhất), lỗ 213.475 USD | Đánh giá hợp đồng Corporate theo biên |
| Q3 Thị trường | Europe tăng trưởng lành mạnh; Asia Pacific tăng nhờ giảm giá; LATAM chững lại | Europe +45,6%, biên 18,5%; APAC biên 13,4% → 7,2%, 29% dòng giảm sâu | Ưu tiên Europe; siết giảm giá ở APAC, LATAM |
| Q4 Khách hàng | Giá trị và khả năng quay lại do hành vi và thị trường quyết định, không do nhân khẩu học | 68,8% khách mua 1 lần; cụm trung thành tạo 56% lợi nhuận; cụm săn giảm giá −257 nghìn USD; giảm nhẹ ở đơn đầu: 30,6% quay lại so với 11,7% khi giảm 30–50%; USCA 27,9% so với Africa 5,7% | Giữ chân, kích hoạt lại; ưu đãi nhẹ thay vì giảm sâu cho khách mới; ngừng giảm giá cho khách gây lỗ |
| Q5 Biên 2023 | Biên giảm do chi phí, không do giá hay chiết khấu | Giảm ở mọi chiều; dòng không giảm giá 33,0% → 27,7%; chi phí ngầm/đơn vị +7,7%; model drift +5,5 điểm % | Rà soát chi phí logistics; bổ sung dữ liệu chi phí |

## 5.2. Đóng góp của đề tài

- **Kỹ thuật dữ liệu:** pipeline Medallion trên DuckDB với dbt theo hướng ELT. Mỗi tầng có kiểm thử, có đối chiếu số liệu giữa các tầng, có bảng log giám sát chất lượng, và chạy lại được bằng một lệnh.
- **Kho dữ liệu:** star schema Kimball đầy đủ, gồm grain rõ ràng, surrogate key, thành viên Unknown, degenerate dimension, junk dimension, periodic snapshot fact với lưới đầy đủ và bảng fact sắp xếp theo `order_date`. Lợi ích của việc sắp xếp được đo bằng EXPLAIN ANALYZE.
- **Quản trị dữ liệu:** metric catalog định nghĩa KPI một lần; lineage tự động sinh từ dbt docs; dữ liệu cá nhân được che bằng thiết kế (băm email, đổi ngày sinh thành nhóm tuổi, CSV chỉ chứa cột không nhạy cảm).
- **Khai phá dữ liệu và học máy trên kho:** đủ ba nhóm thuật toán khai phá cốt lõi (phân lớp, phân cụm, luật kết hợp) cùng hồi quy và chuỗi thời gian, huấn luyện bằng Python trên dữ liệu Gold và ghi kết quả ngược vào kho, kèm registry. Mô hình được đánh giá theo thời gian, phát hiện model drift, chạy what-if chiết khấu và phát hiện tháng bất thường.
- **Kinh doanh:** xác định ngưỡng chiết khấu hòa vốn, lập P&L theo phân khúc, lập bản đồ tăng trưởng và biên theo thị trường, phân nhóm khách hàng có giá trị, và chẩn đoán nguyên nhân giảm biên năm 2023 kèm ước lượng tác động bằng tiền.

## 5.3. Hạn chế

::table B5.3 | Hạn chế, nguyên nhân và hướng khắc phục | Nhóm thực hiện
| Hạn chế | Nguyên nhân | Hướng khắc phục |
|---|---|---|
| Chưa phân rã được nguyên nhân giảm biên 2023 | Dữ liệu không có cột chi phí; chi phí ngầm chỉ là sales − profit | Bổ sung dữ liệu chi phí logistics, giá vốn vào kho |
| Chưa rõ `sales` là doanh thu trước hay sau chiết khấu | Nhà cung cấp không mô tả | Xác nhận với nhà cung cấp; nếu là trước chiết khấu thì điều chỉnh công thức |
| Ước lượng what-if là cận trên | Giả định doanh thu không đổi khi giảm chiết khấu (không mô hình hóa độ co giãn của cầu) | Thử nghiệm A/B trần chiết khấu; mô hình độ co giãn giá |
| Phân lớp khách quay lại chỉ đạt AUC 0,65; quan hệ giữa chiết khấu đơn đầu và việc quay lại mới là tương quan | Đơn đầu chứa ít thông tin về ý định quay lại; dữ liệu quan sát, không có nhóm đối chứng | Bổ sung dữ liệu hành vi (lượt xem, giỏ bỏ dở, đánh giá); thử nghiệm A/B mức ưu đãi cho khách mới |
| Mô hình chưa được huấn luyện bằng SQL ngay trong kho (In-Database ML như BigQuery ML) | DuckDB không hỗ trợ `CREATE MODEL`; nhóm dùng Python chạy cùng tiến trình, đọc và ghi trực tiếp vào kho, không xuất dữ liệu ra hệ thống khác | Đóng gói mô hình thành hàm Python (UDF) của DuckDB, hoặc chuyển lên kho có In-Database ML |
| Cụm K-Means tách ở mức trung bình (silhouette khoảng 0,3) | Mỗi khách trung bình chỉ 1,48 đơn, frequency ít phân tán | Bổ sung đặc trưng hành vi (danh mục ưa thích, kênh, thời gian giữa hai đơn) |
| Dữ liệu tĩnh, mô phỏng | Năm trong order_id lệch 8 năm; 11 order_id gắn nhiều ngày hoặc nhiều khách | Khi có dữ liệu thật, nạp gia tăng và kiểm tra lại quy tắc |
| Chưa có nạp gia tăng, SCD Type 2, CI/CD | Thời gian thực hiện ngắn, dữ liệu tĩnh | Mô hình incremental của dbt, snapshot dbt, GitHub Actions |
| DuckDB là kho một người dùng, không phân quyền theo cột | Đặc thù cơ sở dữ liệu nhúng | Chuyển lên MotherDuck hoặc kho đám mây khi cần nhiều người dùng |
| Dashboard phải dựng thủ công | Power BI không dựng được bằng mã trong phạm vi đề tài | Dùng Power BI Project (PBIP) để quản lý dashboard như mã nguồn |

## 5.4. Hướng phát triển

1. **Nạp gia tăng và CDC:** dùng mô hình `incremental` của dbt và điều phối bằng GitHub Actions hoặc Airflow. Dự án tham khảo `a-simple-t2s-flow` đã có mẫu DAG Astronomer Cosmos.
2. **Bổ sung dữ liệu chi phí logistics** để phân rã biên lợi nhuận theo thành phần chi phí và trả lời trọn vẹn Q5.
3. **Generative BI:** hỏi đáp dữ liệu bằng ngôn ngữ tự nhiên trên semantic layer xây từ metric catalog, theo hướng Text-to-SQL có kiểm soát (chỉ đọc, chặn câu lệnh ghi) như dự án tham khảo.
4. **Knowledge graph khách hàng – sản phẩm** và hệ gợi ý sản phẩm cá nhân hóa, thay cho bán chéo theo cặp ngành hàng vốn có lift thấp.
5. **Đưa kho lên MotherDuck hoặc một kho đám mây** để nhiều người cùng truy cập và có phân quyền.
6. **Mô hình độ co giãn giá** và thử nghiệm A/B để chuyển kết quả what-if từ cận trên thành ước lượng nhân quả.
