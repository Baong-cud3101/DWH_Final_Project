#! TÀI LIỆU THAM KHẢO

1. Kimball, R., & Ross, M. (2013). *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling* (3rd ed.). Wiley.
2. Inmon, W. H. (2005). *Building the Data Warehouse* (4th ed.). Wiley.
3. Nguyễn Thôn Dã. (2026). *Bài giảng Nhà kho dữ liệu và tích hợp* (Slide 1–9). Khoa Hệ thống thông tin, Trường Đại học Kinh tế - Luật, ĐHQG-HCM.
4. Databricks. *What is a Medallion Architecture?* https://www.databricks.com/glossary/medallion-architecture
5. DuckDB Foundation. *DuckDB Documentation* (v1.5). https://duckdb.org/docs/
6. dbt Labs. *dbt Developer Hub: dbt Core, data tests, macros, docs*. https://docs.getdbt.com/
7. dbt-duckdb. *DuckDB adapter for dbt*. https://github.com/duckdb/dbt-duckdb
8. Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.
9. Seabold, S., & Perktold, J. (2010). Statsmodels: Econometric and statistical modeling with Python. *Proceedings of the 9th Python in Science Conference*.
10. Hyndman, R. J., & Athanasopoulos, G. (2021). *Forecasting: Principles and Practice* (3rd ed.). OTexts. https://otexts.com/fpp3/
11. Rousseeuw, P. J. (1987). Silhouettes: A graphical aid to the interpretation and validation of cluster analysis. *Journal of Computational and Applied Mathematics*, 20, 53–65.
12. Davies, D. L., & Bouldin, D. W. (1979). A cluster separation measure. *IEEE Transactions on Pattern Analysis and Machine Intelligence*, 1(2), 224–227.
13. Agrawal, R., & Srikant, R. (1994). Fast algorithms for mining association rules. *Proceedings of the 20th VLDB Conference*, 487–499.
14. Xóm Data. *Xóm Dataset – Schema E-Commerce*. https://dataset.xomdata.com/datasets/schema/e_commerce
15. Nguyễn, T. (2026). *a-simple-t2s-flow: E-Commerce Data Warehouse Pipeline & Text-to-SQL Engine* [Mã nguồn]. GitHub. https://github.com/tunguyenn99/a-simple-t2s-flow

#! PHỤ LỤC

## Phụ lục A. Hướng dẫn chạy lại hệ thống

Yêu cầu: Python 3.10 trở lên, khoảng 200 MB dung lượng trống. Thực hiện các bước sau trong thư mục gốc dự án `XomEcom_DuckDB`:

1. Đặt bốn file `customer.csv`, `ecom_sales.csv`, `product.csv`, `region.csv` vào `data/raw/`.
2. Tạo môi trường và cài thư viện: `python -m venv .venv`, kích hoạt môi trường, rồi chạy `pip install -r requirements.txt`.
3. Chạy toàn bộ pipeline: `python scripts/run_all.py`. Lệnh này nạp Bronze, chạy dbt build, profiling, ML, phân tích, biểu đồ, xuất CSV, đối chiếu, dbt docs và dựng báo cáo.
4. Xem lineage: `python scripts/run_dbt.py docs serve`, rồi mở trình duyệt tại địa chỉ được in ra.
5. Truy vấn kho: mở `warehouse/xomecom.duckdb` bằng DBeaver hoặc DuckDB CLI.

::table BA.1 | Cấu trúc thư mục dự án | Nhóm thực hiện
| Thư mục / tệp | Nội dung |
|---|---|
| data/raw/ | 4 file CSV nguồn (không đưa lên Git) |
| warehouse/xomecom.duckdb | Kho dữ liệu (5 schema) |
| dbt/models/silver, gold/dims, gold/facts, marts, ml | Các model dbt theo tầng |
| dbt/macros/ | metrics.sql (metric catalog), discount_band.sql, safe_divide.sql, log_run_results.sql, generate_schema_name.sql |
| dbt/tests/ | 4 kiểm thử đối chiếu và kiểm thử generic unique_combination |
| dbt/seeds/metric_catalog.csv | Danh mục KPI |
| scripts/ | 00_load_bronze → 10_build_report và run_all.py |
| sql/analysis, sql/checks | SQL phân tích giỏ hàng, benchmark sắp xếp, đối chiếu tầng |
| results/tables, results/figures | Bảng (CSV) và hình (PNG) dùng trong báo cáo; key_numbers.json |
| exports/powerbi/ | 14 file CSV cho Power BI |
| models/ | File mô hình joblib có phiên bản |
| report/ | Bản nháp, mã mermaid các sơ đồ, báo cáo Word |

## Phụ lục B. Một số câu SQL tiêu biểu

**B.1. Fact giao dịch với surrogate key và thành viên Unknown** (trích `fact_sales.sql`):

::code

```
select
    s.row_id,
    s.order_id,                                         -- degenerate dimension
    cast(strftime(s.order_date, '%Y%m%d') as integer)   as date_key,
    coalesce(c.customer_key, -1)                        as customer_key,
    coalesce(p.product_key, -1)                         as product_key,
    coalesce(r.region_key, -1)                          as region_key,
    coalesce(sg.segment_key, -1)                        as segment_key,
    f.flag_key,
    s.quantity, s.sales, s.discount, s.profit, s.implied_cost
from silver_sales_integrated as s
left join dim_customer c on s.customer_id = c.customer_id
left join dim_product  p on s.product_code = p.product_code
left join dim_region   r on s.region_code = r.region_code
left join dim_segment sg on s.segment = sg.segment_name
left join dim_flags    f on f.is_valid_product = s.is_valid_product
                        and f.is_valid_region = s.is_valid_region
                        and f.discount_band_order = s.discount_band_order
                        and f.is_loss = s.is_loss
order by s.order_date, s.row_id
```

**B.2. Metric catalog bằng macro dbt** (trích `metrics.sql`):

::code

```
{% macro kpi_profit_margin() -%}
    {{ safe_divide('sum(profit)', 'sum(sales)') }}
{%- endmacro %}

{% macro kpi_deep_discount_share() -%}
    {{ safe_divide('count(*) filter (where discount > '
                   ~ var('deep_discount_threshold') ~ ')', 'count(*)') }}
{%- endmacro %}
```

**B.3. Kiểm thử đối chiếu tổng tiền giữa các tầng** (`assert_totals_reconcile_across_layers.sql`):

::code

```
with t as (
    select 'bronze' as layer, sum(cast(sales as decimal(14,2))) as sales,
           sum(cast(profit as decimal(14,2))) as profit from bronze.ecom_sales
    union all select 'silver', sum(sales), sum(profit) from silver_sales_integrated
    union all select 'fact_sales', sum(sales), sum(profit) from fact_sales
    union all select 'snapshot', sum(revenue), sum(profit) from fact_monthly_snapshot
)
select * from t
where sales  <> (select sales  from t where layer = 'bronze')
   or profit <> (select profit from t where layer = 'bronze')   -- trả về 0 dòng = đạt
```

**B.4. Phân tích giỏ hàng theo subcategory** (trích):

::code

```
select a.subcategory as antecedent, b.subcategory as consequent,
       count(*) as orders_both,
       count(*) / n.n                                         as support,
       count(*) / sa.orders_with                              as confidence,
       (count(*) / sa.orders_with) / (sb.orders_with / n.n)   as lift
from order_sub a
join order_sub b on a.order_id = b.order_id and a.subcategory <> b.subcategory
...
```

## Phụ lục C. Đặc tả dashboard Power BI

**Cách dựng:** dashboard được sinh bằng mã (`scripts/11_build_powerbi.py`) dưới dạng dự án Power BI (PBIP), gồm mô hình ngữ nghĩa viết bằng TMDL và báo cáo viết bằng PBIR, lưu ở `powerbi/XomEcom_Dashboard.pbip`. Mở file bằng Power BI Desktop rồi bấm Refresh để nạp CSV. Thư mục CSV là tham số `DataFolder` (Transform data → Edit parameters). Bố cục theo mẫu báo cáo Hotel của nhóm: trang 1280 × 720, thanh tiêu đề có nút điều hướng và nút xóa bộ lọc, thẻ trắng bo góc, màu xanh navy và vàng. Ngoài bốn trang phân tích có thêm một trang chủ tóm tắt bốn khuyến nghị.

**Mô hình dữ liệu:** nạp 14 file CSV trong `exports/powerbi/`. Bốn bảng chiều dùng chung cho slicer: `DimYear` (2020–2023), `DimMarket`, `DimSegment`, `DimCategory`, nối 1–nhiều với các bảng mart có cột tương ứng. Ngoài ra `mart_customer_value[cluster]` nối với `ml_cluster_profile[cluster]`, và `ml_monthly_anomalies[month_start]` nối với `ml_forecast_monthly[month_start]`. Dòng `year = 0` (tổng toàn kỳ) của `mart_kpi_overview` bị lọc trong Power Query để slicer năm không có giá trị trống. Các bảng kết quả mô hình (`ml_forecast_monthly`, `ml_whatif_discount_cap`, `mart_customer_cohort`) không chịu tác động của slicer. Mọi measure nằm trong bảng `_Measures`.

**Measure DAX chính** (danh sách đầy đủ ở `powerbi/XomEcom_Dashboard.SemanticModel/definition/tables/_Measures.tmdl`):

::code

```
Revenue        = SUM ( mart_segment_profitability[revenue] )
Profit         = SUM ( mart_segment_profitability[profit] )
Profit Margin  = DIVIDE ( [Profit], [Revenue] )
Implied Cost   = [Revenue] - [Profit]
Orders         = IF ( ISFILTERED ( DimMarket[market] ) || ISFILTERED ( DimSegment[segment] ),
                      SUM ( mart_segment_profitability[total_orders] ),
                      SUM ( mart_kpi_overview[total_orders] ) )
AOV            = DIVIDE ( [Revenue], [Orders] )
Repeat Rate    = IF ( ISFILTERED ( DimYear[year] ),
                      IF ( HASONEVALUE ( DimYear[year] ), MAX ( mart_kpi_overview[repeat_customer_rate] ) ),
                      [Customer Repeat Rate] )
Margin LY      = VAR y = MAX ( DimYear[year] )
                 RETURN CALCULATE ( [Profit Margin], DimYear[year] = y - 1 )
Margin Change  = [Profit Margin] - [Margin LY]
Disc Margin    = DIVIDE ( SUM ( mart_discount_analysis[profit] ), SUM ( mart_discount_analysis[revenue] ) )
WhatIf Margin  = DIVIDE ( SUM ( ml_whatif_discount[pred_profit] ), SUM ( ml_whatif_discount[sales] ) )
Geo Margin     = DIVIDE ( SUM ( mart_geographic_performance[profit] ), SUM ( mart_geographic_performance[revenue] ) )
Geo Growth     = VAR y = MAX ( DimYear[year] )
                 RETURN DIVIDE ( CALCULATE ( [Geo Revenue], DimYear[year] = y ),
                                 CALCULATE ( [Geo Revenue], DimYear[year] = y - 1 ) ) - 1
Customer Repeat Rate = DIVIDE ( CALCULATE ( COUNTROWS ( mart_customer_value ),
                                mart_customer_value[is_repeat_customer] = TRUE () ),
                                COUNTROWS ( mart_customer_value ) )
Profit Share   = DIVIDE ( SUM ( mart_customer_value[profit] ),
                          CALCULATE ( SUM ( mart_customer_value[profit] ),
                                      ALLSELECTED ( mart_customer_value[cluster_name] ) ) )
Retention      = AVERAGE ( mart_customer_cohort[retention_rate] )
```

Số đơn khi không lọc thị trường và phân khúc lấy từ `mart_kpi_overview` (đếm order_id phân biệt toàn bảng), vì cộng số đơn theo từng phân khúc × thị trường có thể đếm trùng một đơn. Biên và tăng trưởng 2022–2023 trên trang Địa lý là các measure cố định năm (`CALCULATE(..., DimYear[year] = 2023)`).

::table BC.1 | Đặc tả bốn trang dashboard | Nhóm thực hiện
| Trang | Visual | Nguồn (CSV) | Khuyến nghị cuối trang |
|---|---|---|---|
| 1. Tổng quan | 6 thẻ KPI; cột doanh thu và đường biên theo năm; đường biên theo năm × thị trường; đường lợi nhuận theo tháng kèm dự báo 2024 (nét đứt) và điểm bất thường (chấm đỏ) | mart_segment_profitability, mart_kpi_overview, ml_forecast_monthly, ml_monthly_anomalies | Biên 2023 giảm ở mọi nơi: rà soát chi phí vận hành |
| 2. Phân khúc & Chiết khấu | Ma trận lợi nhuận và biên theo phân khúc × năm; cột biên theo nhóm chiết khấu có đường hòa vốn; cột kịch bản trần chiết khấu kèm đường mức tăng; đường biên dự đoán theo mức chiết khấu và ngành hàng | mart_segment_profitability, mart_discount_analysis, ml_whatif_discount_cap, ml_whatif_discount | Đặt trần chiết khấu 30%; đánh giá Corporate theo biên |
| 3. Địa lý | Bản đồ điểm (scatter kinh độ × vĩ độ theo country_longitude, country_latitude; kích thước = doanh thu, màu = biên; không cần đăng nhập hay bật visual Map); bảng chi tiết quốc gia; cột biên 2022 so với 2023 và cột tăng trưởng doanh thu 2023 theo thị trường | mart_geographic_performance | Ưu tiên Europe; siết giảm giá ở Asia Pacific |
| 4. Khách hàng | Thẻ số khách mỗi cụm; scatter recency × monetary tô màu theo cụm; bảng hồ sơ cụm; ma trận cohort; cột số khách theo nhóm RFM | mart_customer_value, ml_cluster_profile, mart_customer_cohort | Giữ chân cụm trung thành; kích hoạt lại cụm mua một lần giá trị cao |

## Phụ lục D. Công thức và mô hình sử dụng

Phụ lục tập hợp mọi công thức và mô hình được dùng để tính số liệu trong báo cáo, kèm nơi cài đặt trong mã nguồn. Ký hiệu: i là dòng giao dịch, s là sales (doanh thu dòng), p là profit (lợi nhuận dòng), d là discount (tỷ lệ chiết khấu), q là quantity, o là order_id, c là khách hàng, ∣A∣ là số phần tử của tập A.

**D.1. KPI và chỉ số kinh doanh** (macro dbt trong `dbt/macros/metrics.sql`, data mart trong `dbt/models/marts/`)

::table BD.1 | Công thức KPI và chỉ số kinh doanh | Nhóm thực hiện
| Chỉ số | Công thức | Ghi chú | Dùng ở |
|---|---|---|---|
| Doanh thu (Revenue) | R = Σᵢ sᵢ | | Mọi chương |
| Lợi nhuận (Profit) | P = Σᵢ pᵢ | Có thể âm | Mọi chương |
| Biên lợi nhuận (Profit Margin) | M = P / R | Biên có trọng số doanh thu, không phải trung bình biên từng dòng | Mọi chương |
| Chi phí ngầm (Implied Cost) | C = R − P = Σᵢ (sᵢ − pᵢ) | Thay cho cột chi phí không có trong dữ liệu | Q2, Q5 |
| Số đơn (Total Orders) | O = số order_id phân biệt | | Q2, Q3 |
| Giá trị đơn trung bình (AOV) | AOV = R / O | | Q2 |
| Tỷ lệ dòng lỗ (Loss-Making Line Rate) | LLR = #{i : pᵢ < 0} / N | N là tổng số dòng | Q1, Q2 |
| Tỷ lệ giảm giá sâu (Deep-Discount Share) | DDS = #{i : dᵢ > 0,30} / N | Ngưỡng 30% là biến dbt `deep_discount_threshold` | Q1, Q3 |
| Tỷ lệ khách quay lại (Repeat Customer Rate) | RCR = #{c : số đơn của c ≥ 2} / số khách | | Q4 |
| Tăng trưởng so với cùng kỳ | g = (Rₜ − Rₜ₋₁) / Rₜ₋₁; với tháng dùng Rₜ₋₁₂ | `lag(…, 12)` trên lưới đầy đủ của fact_monthly_snapshot | Q3 |
| Tỷ trọng | share(k) = Rₖ / Σₖ Rₖ | Áp dụng cho doanh thu, lợi nhuận, số khách | Q2, Q4 |
| Giá bán và chi phí ngầm mỗi đơn vị | price = Σ s / Σ q; cost = Σ (s − p) / Σ q | Tính riêng cho dòng không giảm giá ở Q5 | Q5 |
| Tỷ lệ giữ chân theo cohort | ret(c, y) = số khách cohort c hoạt động năm y / số khách cohort c | Cohort = năm mua đầu tiên | Q4 |
| Tuổi | age = năm(2023-12-31) − năm(birth_date), trừ 1 nếu chưa tới sinh nhật | Ngày tham chiếu cố định để tái lập | Dimension khách |
| Nhóm chiết khấu | 0%; (0, 10%]; (10, 20%]; (20, 30%]; (30, 50%]; > 50% | Macro `discount_band` | Q1, Q5 |

**D.2. RFM** (`dbt/models/marts/mart_customer_value.sql`)

::table BD.2 | Công thức RFM và quy tắc phân nhóm | Nhóm thực hiện
| Thành phần | Công thức | Ghi chú |
|---|---|---|
| Recency | Rec(c) = 2023-12-31 − ngày đơn cuối của c (ngày) | Ngày tham chiếu cố định |
| Frequency | Freq(c) = số order_id phân biệt của c | Đếm theo đơn, không theo dòng |
| Monetary | Mon(c) = Σ sᵢ của c | |
| Điểm R | r = 6 − NTILE₅(Rec), sắp tăng dần | Mua càng gần, điểm càng cao |
| Điểm F | f = min(Freq, 5) | Theo ngưỡng vì 68,8% khách chỉ có 1 đơn |
| Điểm M | m = NTILE₅(Mon), sắp tăng dần | |
| Phân nhóm | Champions: r ≥ 4, f ≥ 3, m ≥ 4; Loyal: f ≥ 2, r ≥ 3; At Risk: f ≥ 2, r ≤ 2; New: f = 1, r ≥ 4; Big One-time: f = 1, m ≥ 4; còn lại: Hibernating | Xét theo thứ tự từ trên xuống |

**D.3. Luật kết hợp và thuật toán Apriori** (`sql/analysis/market_basket_subcategory.sql`, `scripts/06_analysis_sql.py`)

::table BD.3 | Công thức luật kết hợp và các bước Apriori | Nhóm thực hiện
| Khái niệm | Công thức | Ghi chú |
|---|---|---|
| Giao dịch, item | T = tập subcategory trong một đơn; D = mọi đơn (25.728) | 17 item |
| Support | sup(X) = #{T ∈ D : X ⊆ T} / ∣D∣ | |
| Confidence | conf(X ⇒ Y) = sup(X ∪ Y) / sup(X) | |
| Lift | lift(X ⇒ Y) = conf(X ⇒ Y) / sup(Y) | > 1: liên kết dương; = 1: độc lập |
| Tính chất Apriori | Nếu X ⊆ Y thì sup(Y) ≤ sup(X); tập có tập con không phổ biến thì không phổ biến | Dùng để tỉa ứng viên |
| Các bước | L₁ = {item : sup ≥ minsup}; Cₖ = hợp hai tập thuộc Lₖ₋₁ có kích thước k; bỏ ứng viên có tập con (k−1) ∉ Lₖ₋₁; Lₖ = {X ∈ Cₖ : sup ≥ minsup}; luật giữ khi conf ≥ minconf | minsup ∈ {1%; 0,5%; 0,2%}, minconf ∈ {80%; 50%; 20%}, k ≤ 3 |

**D.4. Phân cụm K-Means** (`scripts/03_ml_kmeans.py`)

::table BD.4 | Mô hình K-Means và các độ đo chọn số cụm | Nhóm thực hiện
| Thành phần | Công thức | Ghi chú |
|---|---|---|
| Biến đổi log có dấu | x′ = sign(x) · ln(1 + ∣x∣) | Nén đuôi dài, giữ thứ tự cho lợi nhuận âm |
| Chuẩn hóa Z-score | z = (x′ − μ) / σ | StandardScaler |
| Hàm mục tiêu | min Σₖ Σ_{x ∈ Cₖ} ‖x − μₖ‖² | 4 đặc trưng: recency, frequency, monetary, profit; n_init = 10, random_state = 42 |
| Silhouette | s(i) = (b(i) − a(i)) / max(a(i), b(i)); S = trung bình s(i) | a: khoảng cách TB tới điểm cùng cụm; b: tới cụm gần nhất khác; S ∈ [−1, 1], cao tốt |
| Davies-Bouldin | DB = (1/k) Σᵢ maxⱼ≠ᵢ (σᵢ + σⱼ) / d(μᵢ, μⱼ) | σ: độ phân tán trong cụm; thấp tốt |
| Đặt tên cụm | biên thấp nhất → "Săn giảm giá, gây lỗ"; số đơn cao nhất → "Trung thành"; hai cụm còn lại theo Monetary | Quy tắc tất định |

**D.5. Hồi quy biên lợi nhuận và what-if** (`dbt/models/ml/ml_features.sql`, `scripts/04_ml_margin_whatif.py`)

::table BD.5 | Mô hình hồi quy biên lợi nhuận, độ đo đánh giá và kịch bản what-if | Nhóm thực hiện
| Thành phần | Công thức | Ghi chú |
|---|---|---|
| Biến mục tiêu | yᵢ = pᵢ / sᵢ | Không dùng s, p làm đặc trưng |
| Hồi quy tuyến tính | ŷ = β₀ + Σⱼ βⱼ xⱼ, ước lượng bằng bình phương nhỏ nhất | Biến phân loại mã hóa one-hot |
| Gradient boosting (HGB) | ŷ = Σₘ η · hₘ(x), mỗi cây hₘ khớp phần dư của tổng các cây trước | 400 vòng, η = 0,06, 31 lá; ràng buộc đơn điệu: ŷ không tăng theo discount |
| R² | R² = 1 − Σ(yᵢ − ŷᵢ)² / Σ(yᵢ − ȳ)² | |
| MAE | MAE = (1/n) Σ ∣yᵢ − ŷᵢ∣ | |
| Sai lệch biên theo doanh thu | bias = (Σ ŷᵢ sᵢ − Σ pᵢ) / Σ sᵢ | Dương: mô hình dự báo biên cao hơn thực tế (model drift) |
| Permutation importance | I(j) = R²(gốc) − trung bình R²(cột j bị xáo trộn), 5 lần | Trên 6.000 dòng test 2023 |
| What-if mức chiết khấu | P̂(δ) = Σᵢ ŷ(xᵢ với discount = δ) · sᵢ | Áp cho mọi dòng 2023; doanh thu giữ nguyên |
| Ngưỡng hòa vốn | d̂ = max{δ : P̂(δ) > 0}, lưới bước 2,5% | |
| Kịch bản trần chiết khấu | d′ᵢ = min(dᵢ, trần); uplift = P̂(d′) − P̂(d) | Cận trên vì không mô hình hóa độ co giãn của cầu |

**D.6. Chuỗi thời gian và phát hiện bất thường** (`scripts/05_ml_timeseries.py`)

::table BD.6 | Mô hình chuỗi thời gian, độ đo và quy tắc bất thường | Nhóm thực hiện
| Thành phần | Công thức | Ghi chú |
|---|---|---|
| ETS Holt-Winters (xu hướng cộng, mùa vụ nhân, chu kỳ 12) | ℓₜ = α yₜ / sₜ₋₁₂ + (1 − α)(ℓₜ₋₁ + bₜ₋₁); bₜ = β(ℓₜ − ℓₜ₋₁) + (1 − β) bₜ₋₁; sₜ = γ yₜ / ℓₜ + (1 − γ) sₜ₋₁₂; ŷₜ₊ₕ = (ℓₜ + h bₜ) sₜ₊ₕ₋₁₂ | α, β, γ ước lượng tự động |
| SARIMA(1,1,1)(0,1,1)₁₂ trên ln yₜ | (1 − φB)(1 − B)(1 − B¹²) ln yₜ = (1 + θB)(1 + ΘB¹²) εₜ | B là toán tử trễ; dự báo đổi về thang gốc bằng exp |
| MAPE | MAPE = (1/n) Σ ∣yₜ − ŷₜ∣ / yₜ | Học 2020–2022, đo trên 12 tháng 2023 |
| Bất thường theo phần dư | eₜ = yₜ − ŷₜ; zₜ = (eₜ − ē) / sₑ; bất thường nếu ∣zₜ∣ > 2 | ETS học trên toàn kỳ |
| Bất thường theo khoảng dự báo | bất thường nếu yₜ < cận dưới khoảng dự báo 95% của SARIMA | Cho 12 tháng 2023 |

**D.7. Phân lớp khách quay lại** (`dbt/models/ml/ml_first_order_features.sql`, `scripts/04b_ml_classification.py`)

::table BD.7 | Mô hình phân lớp và độ đo đánh giá | Nhóm thực hiện
| Thành phần | Công thức | Ghi chú |
|---|---|---|
| Nhãn | y(c) = 1 nếu c có đơn thứ hai trong 365 ngày sau đơn đầu, ngược lại 0 | Chỉ khách có đơn đầu đến hết 2022 |
| Entropy | H(S) = − Σₖ pₖ log₂ pₖ | pₖ: tỷ lệ lớp k trong tập S |
| Information gain | IG(S, A) = H(S) − Σᵥ (∣Sᵥ∣ / ∣S∣) · H(Sᵥ) | Cây chọn thuộc tính và ngưỡng có IG lớn nhất (nguyên lý ID3/C4.5); sâu tối đa 4, lá tối thiểu 150; class_weight = balanced |
| Naive Bayes | P(y ∣ x) ∝ P(y) · Πⱼ P(xⱼ ∣ y) | Giả định các thuộc tính độc lập có điều kiện theo lớp |
| Làm trơn Laplace | P(xⱼ = v ∣ y) = (n(v, y) + α) / (n(y) + α · Kⱼ), α = 1 | Kⱼ: số giá trị của thuộc tính j; thuộc tính số được rời rạc hóa trước |
| Ngưỡng phân lớp | Cây: 0,5; Naive Bayes: tỷ lệ quay lại của tập huấn luyện (17,1%) | |
| Precision, Recall, F1 | Prec = TP / (TP + FP); Rec = TP / (TP + FN); F1 = 2 · Prec · Rec / (Prec + Rec) | |
| AUC | Xác suất một khách quay lại được chấm điểm cao hơn một khách không quay lại | 0,5 là ngẫu nhiên, 1 là hoàn hảo |
| Lift top 20% | lift = tỷ lệ quay lại trong 20% điểm cao nhất / tỷ lệ quay lại chung | |

**D.8. Kiểm tra chất lượng và đối chiếu** (`scripts/01_profiling.py`, `scripts/09_checks.py`, `dbt/tests/`)

::table BD.8 | Quy tắc đối chiếu số liệu giữa các tầng | Nhóm thực hiện
| Kiểm tra | Điều kiện đạt | Ghi chú |
|---|---|---|
| Bảo toàn số dòng | N(Bronze) = N(Silver) = N(fact_sales) = số row_id phân biệt | Phát hiện mất dòng hoặc nhân bản khi nối dimension |
| Khớp tổng tiền | Σ s và Σ p bằng nhau ở Bronze, Silver, fact_sales, fact_monthly_snapshot | So sánh kiểu DECIMAL, khớp tuyệt đối |
| Thành viên Unknown | #(product_key = −1) = #(is_valid_product = false); tương tự cho region | Không có khóa ngoại NULL |
| Grain | Không có tổ hợp khóa grain nào xuất hiện quá 1 lần | Kiểm thử `unique_combination` |
| Lưới snapshot | Số ô = 48 tháng × 5 market × 3 segment = 720 | Bảo đảm so sánh cùng kỳ đúng |

## Phụ lục E. Số liệu bổ sung dẫn trong phần chữ

Các con số dưới đây được dẫn trong phần chữ của báo cáo nhưng không thuộc bảng nào ở Chương 2 và Chương 4. Câu SQL tính từng con số được lưu tại `sql/checks/extra_numbers.sql` (và cột SQL của `results/tables/B_extra_numbers.csv`), có thể chạy lại trực tiếp trên kho. Bảng tra giữa số Hình/Bảng trong báo cáo với tệp số liệu nằm ở `results/INDEX.md`.

::csvtable BE.1 | Các con số bổ sung và đơn vị (giá trị tính từ kho DuckDB) | Script 09_checks.py, SQL tại sql/checks/extra_numbers.sql | B_extra_numbers.csv | Chỉ tiêu:Chỉ tiêu:str;Hiển thị:Giá trị:str;Đơn vị:Đơn vị:str

#! PHẦN 2. MÔ TẢ PHÂN CÔNG CÔNG VIỆC TRONG NHÓM

Link Google Drive thư mục chứa toàn bộ file của bài tập lớn: [dán link Google Drive].

Mô tả công việc của các thành viên và mức độ đóng góp (Mức 1 là cao nhất, Mức 2 là cao thứ hai, …), do nhóm trưởng đánh giá và cả nhóm thống nhất:

::table BP.1 | Phân công công việc và mức độ đóng góp | Nhóm thực hiện
| Mã số sinh viên | Họ và tên | Công việc phụ trách | Mức độ đóng góp |
|---|---|---|---|
| [điền] | [điền] (Nhóm trưởng) | [ví dụ: kiến trúc, tầng Gold, tổng hợp báo cáo] | [điền] |
| [điền] | [điền] | [ví dụ: Bronze, Silver, kiểm thử dbt, Chương 2] | [điền] |
| [điền] | [điền] | [ví dụ: data mart, KPI, dashboard Power BI] | [điền] |
| [điền] | [điền] | [ví dụ: học máy, Chương 4] | [điền] |
| [điền] | [điền] | [ví dụ: sơ đồ, Chương 1, 3, 5, thuyết trình] | [điền] |
