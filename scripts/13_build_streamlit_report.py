"""Báo cáo ngắn về ứng dụng Streamlit: report/final/Streamlit.docx.

Ảnh chụp màn hình (nếu có) đặt trong report/streamlit/<số trang>_*.png.
Số liệu về kho rút gọn đọc trực tiếp từ app/data/xomecom_app.duckdb.
"""

import sys

import duckdb
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from common import ROOT

APP_DB = ROOT / "app" / "data" / "xomecom_app.duckdb"
SHOTS = ROOT / "report" / "streamlit"
OUT = ROOT / "report" / "final" / "Streamlit.docx"
FONT = "Times New Roman"
PAGE_NAMES = {"1": "Tổng quan KPI", "2": "Sản phẩm & Chiết khấu", "3": "Địa lý", "4": "Khách hàng",
              "5": "Học máy", "6": "Chất lượng dữ liệu", "7": "Dự đoán trực tiếp",
              "8": "SQL Playground"}
APP_URL = sys.argv[1] if len(sys.argv) > 1 else None  # link sau khi triển khai


def set_font(style, size, bold=False, italic=False):
    style.font.name = FONT
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.italic = italic
    style.font.color.rgb = RGBColor(0, 0, 0)
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rpr.append(rf)
    for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(a), FONT)
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rf.attrib.pop(qn(a), None)


def shade(cell, color):
    tcpr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tcpr.append(shd)


def table(doc, header, rows, widths):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(h)
        r.bold = True
        r.font.size = Pt(11)
        shade(c, "D9E2F3")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            cells[i].paragraphs[0].add_run(str(v)).font.size = Pt(11)
    for row in t.rows:
        for i, w in enumerate(widths):
            row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return t


def caption(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.italic = True
    r.font.size = Pt(11)


def bullets(doc, items):
    for it in items:
        p = doc.add_paragraph(style="List Bullet")
        if isinstance(it, tuple):
            p.add_run(it[0]).bold = True
            p.add_run(it[1])
        else:
            p.add_run(it)


def main():
    con = duckdb.connect(str(APP_DB), read_only=True)
    n_tables = con.sql("SELECT count(*) FROM duckdb_tables()").fetchone()[0]
    n_rows = sum(con.sql(f'SELECT count(*) FROM "{t}"').fetchone()[0]
                 for (t,) in con.sql("SELECT table_name FROM duckdb_tables()").fetchall())
    src_rows = con.sql("SELECT sum(row_count) FROM table_counts").fetchone()[0]
    src_tables = con.sql("SELECT count(*) FROM table_counts").fetchone()[0]
    con.close()
    size_mb = APP_DB.stat().st_size / 1024 / 1024

    doc = Document()
    for s in doc.sections:
        s.top_margin, s.bottom_margin = Cm(2), Cm(2)
        s.left_margin, s.right_margin = Cm(3), Cm(2)
    normal = doc.styles["Normal"]
    set_font(normal, 13)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.3
    set_font(doc.styles["Title"], 20, bold=True)
    set_font(doc.styles["Heading 1"], 15, bold=True)
    set_font(doc.styles["Heading 2"], 13, bold=True)
    set_font(doc.styles["List Bullet"], 13)
    for name in ("Heading 1", "Heading 2"):
        pf = doc.styles[name].paragraph_format
        pf.space_before, pf.space_after, pf.keep_with_next = Pt(12), Pt(6), True

    t = doc.add_paragraph(style="Title")
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run("Triển khai trực tuyến kho dữ liệu Xóm E-Com")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("MotherDuck · GitHub Actions · Streamlit Community Cloud").bold = True
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("Nhóm 6 · BIM5021 Nhà kho dữ liệu và tích hợp · UEL. Bổ sung cho mục 4.7 của báo cáo chính.").italic = True

    # 1
    doc.add_heading("1. Streamlit là gì và vì sao chọn", level=1)
    doc.add_paragraph(
        "Streamlit là thư viện Python mã nguồn mở để dựng ứng dụng web phân tích dữ liệu chỉ bằng mã Python, "
        "không cần HTML hay JavaScript. Mỗi lần người dùng đổi bộ lọc, Streamlit chạy lại script và vẽ lại trang. "
        "Ứng dụng có thể đưa lên Streamlit Community Cloud miễn phí: dịch vụ lấy mã từ GitHub, tự cài thư viện "
        "và cấp một đường link công khai."
    )
    doc.add_paragraph("Với đồ án này, Streamlit bổ sung cho dashboard Power BI ở ba điểm:")
    bullets(doc, [
        ("Truy cập trực tuyến: ", "giảng viên mở bằng trình duyệt, không cần Power BI Desktop hay tài khoản Power BI Service."),
        ("Cùng ngôn ngữ với pipeline: ", "ứng dụng gửi SQL thẳng vào kho DuckDB trên MotherDuck, dùng lại các bảng mart và schema ml do dbt và Python tạo ra."),
        ("Tương tác với mô hình: ", "người xem nhập thông tin và nhận dự đoán ngay từ mô hình thật, hoặc tự viết SQL trên dữ liệu kho."),
    ])

    # 2
    doc.add_heading("2. Kiến trúc trực tuyến", level=1)
    doc.add_paragraph(
        "Toàn bộ kho dữ liệu và pipeline chạy trên cloud, không phụ thuộc máy của nhóm. Ba dịch vụ miễn phí "
        "ghép với nhau như sau:"
    )
    arch = [
        ("Kho dữ liệu", "MotherDuck (DuckDB trên cloud)",
         f"Database xomecom: {src_tables} bảng ở các schema bronze, silver, gold, mart, ml ({src_rows:,} dòng); "
         "thêm schema app gồm các view phục vụ ứng dụng."),
        ("Pipeline (ETL + ML)", "GitHub Actions",
         "Workflow .github/workflows/pipeline.yml: nạp Bronze, dbt build (kèm kiểm thử), profiling, 4 nhóm mô hình ML, "
         "đối chiếu Bronze = Silver = Gold, xuất bản mô hình, dựng schema app. Chạy khi bấm Run workflow, "
         "khi có commit sửa dbt/scripts, và tự động 8 giờ sáng thứ Hai."),
        ("Ứng dụng", "Streamlit Community Cloud",
         "Mỗi thao tác lọc gửi câu SQL tới MotherDuck; trang Dự đoán nạp mô hình từ kho và tính ngay; "
         "trang SQL Playground cho chạy SQL trên dữ liệu kho."),
    ]
    table(doc, ["Thành phần", "Dịch vụ", "Vai trò"], arch, [3.2, 3.8, 9])
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("Repo riêng tư (CSV)  →  GitHub Actions: Bronze → dbt (Silver, Gold, Mart) → ML → kiểm tra  →  "
                  "MotherDuck  →  Streamlit Cloud  →  trình duyệt")
    r.font.size = Pt(11)
    r.bold = True

    doc.add_heading("2.1. Bảo mật dữ liệu", level=2)
    bullets(doc, [
        "4 file CSV gốc nằm trong một repo GitHub riêng tư; workflow đọc bằng token chỉ-đọc và xóa khỏi máy chạy sau khi xong. "
        "Repo mã nguồn công khai không chứa dữ liệu khách hàng.",
        "Token MotherDuck lưu trong GitHub Secrets và Streamlit Secrets, không nằm trong mã.",
        "Các trang phân tích chỉ đọc view tổng hợp trong schema app; thông tin khách hàng chỉ ở dạng số đếm theo nhóm (nhóm dưới 10 khách bị loại).",
        "SQL Playground chạy trong một DuckDB riêng trong bộ nhớ, chỉ chứa bảng được phép (bảng khách hàng bỏ customer_id, "
        "email đã băm, tuổi và thu nhập chính xác). Chỉ chấp nhận đúng một câu SELECT, tắt truy cập file và mạng "
        "(enable_external_access = false, khóa cấu hình), tối đa 1.000 dòng và 15 giây.",
        f"Bản snapshot app/data/xomecom_app.duckdb ({n_tables} bảng tổng hợp, {size_mb:.0f} MB) giữ trong repo để ứng dụng "
        "vẫn chạy khi không kết nối được MotherDuck.",
    ])

    # 3
    doc.add_heading("3. Các trang của ứng dụng", level=1)
    pages = [
        ("1. Tổng quan KPI", "Thẻ KPI theo năm (so với năm trước), xu hướng doanh thu, lợi nhuận, biên theo tháng; "
         "biên theo phân khúc × thị trường; danh mục KPI", "mart_kpi_overview, fact_monthly_snapshot, mart_segment_profitability"),
        ("2. Sản phẩm & Chiết khấu", "Biên theo mức chiết khấu; ma trận ngành hàng × chiết khấu; treemap; top sản phẩm lãi/lỗ",
         "mart_discount_analysis, mart_product_profitability"),
        ("3. Địa lý", "Bản đồ quốc gia, thị trường qua các năm, xếp hạng quốc gia", "mart_geographic_performance"),
        ("4. Khách hàng", "Nhóm RFM, 4 cụm K-Means, cohort giữ chân, chân dung khách theo nhóm",
         "mart_customer_value (tổng hợp), mart_customer_cohort, ml.cluster_profile"),
        ("5. Học máy", "What-if và trần chiết khấu; dự báo ETS, tháng bất thường; khách quay lại; Apriori; sổ mô hình", "schema ml"),
        ("6. Chất lượng dữ liệu", "Đối chiếu 3 tầng, profiling, cờ chất lượng, số dòng theo schema, nhật ký dbt",
         "B2.4, B4.2, B4.3, dim_flags, audit_run_log"),
        ("7. Dự đoán trực tiếp", "Nhập thông tin một dòng hàng → biên lợi nhuận dự đoán và đường biên theo chiết khấu; "
         "nhập đơn đầu của khách → khả năng quay lại kèm đường đi trong cây quyết định",
         "ml.model_artifacts (HistGradientBoosting, Decision Tree)"),
        ("8. SQL Playground", "Gõ SQL DuckDB, chạy trên gold, mart, ml; có câu mẫu, tải kết quả CSV", "gold, mart, ml (bản cách ly)"),
    ]
    table(doc, ["Trang", "Nội dung", "Nguồn trong kho"], pages, [3.5, 8, 4.5])
    doc.add_paragraph("Thanh bên trái hiện nguồn dữ liệu đang dùng và thời điểm pipeline chạy gần nhất. "
                      "Kết quả truy vấn được cache 10 phút.")

    shots = sorted(SHOTS.glob("*.png")) if SHOTS.exists() else []
    for i, img in enumerate(shots, 1):
        doc.add_picture(str(img), width=Cm(10))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        name = PAGE_NAMES.get(img.stem.split("_", 1)[0], img.stem)
        caption(doc, f"Hình {i}. Trang {name}")

    # 4
    doc.add_heading("4. Triển khai", level=1)
    for s in [
        "MotherDuck: tạo tài khoản, tạo access token (đọc-ghi cho pipeline, chỉ-đọc cho ứng dụng).",
        "GitHub: tạo repo riêng tư chứa 4 CSV và một fine-grained token chỉ-đọc repo đó; khai báo secrets MOTHERDUCK_TOKEN, "
        "DATA_REPO_TOKEN và variable DATA_REPO trong repo mã nguồn.",
        "Chạy workflow \"Pipeline kho dữ liệu (MotherDuck)\" ở tab Actions; khoảng 5 phút là kho trên MotherDuck đầy đủ.",
        "Streamlit Community Cloud: tạo app từ repo, Main file path app/streamlit_app.py, Python 3.11; "
        "trong Settings > Secrets thêm MOTHERDUCK_TOKEN.",
        "Từ đó, mọi commit sửa dbt hoặc scripts đều tự chạy lại pipeline; ứng dụng thấy số mới sau tối đa 10 phút. "
        "Lần chạy ngày 19/11/2026 mất 3 phút 17 giây (dbt build 28 giây), đạt 123/123 nút và đối chiếu ba tầng đều khớp.",
    ]:
        doc.add_paragraph(s, style="List Number")
    p = doc.add_paragraph()
    p.add_run("Link ứng dụng: ").bold = True
    p.add_run(APP_URL or "(điền sau khi triển khai)")

    # 5
    doc.add_heading("5. Hạn chế", level=1)
    bullets(doc, [
        "Dữ liệu nguồn là 4 file CSV tĩnh nên pipeline chạy lại cho cùng kết quả; khi có dữ liệu mới chỉ cần thay CSV trong repo riêng tư.",
        "Gói miễn phí của Streamlit Community Cloud cho ứng dụng ngủ khi lâu không có người truy cập; lần mở đầu mất khoảng 30 giây.",
        "Benchmark sắp xếp theo order_date (mục 4.1 báo cáo chính) đo bố cục file DuckDB cục bộ nên không chạy trên MotherDuck.",
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Đã tạo {OUT} ({len(shots)} ảnh chụp)")


if __name__ == "__main__":
    main()
