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
              "5": "Học máy", "6": "Chất lượng dữ liệu"}
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
    t.add_run("Triển khai trực tuyến kho dữ liệu Xóm E-Com bằng Streamlit")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run("Nhóm 6 · BIM5021 Nhà kho dữ liệu và tích hợp · UEL").italic = True

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
        ("Cùng ngôn ngữ với pipeline: ", "ứng dụng đọc trực tiếp file DuckDB bằng SQL, dùng lại các bảng mart và schema ml do dbt và Python tạo ra."),
        ("Tương tác với kết quả học máy: ", "người xem kéo thanh trượt chiết khấu để xem biên lợi nhuận dự đoán, xem dự báo, luật cây quyết định."),
    ])

    # 2
    doc.add_heading("2. Kiến trúc và bảo mật dữ liệu", level=1)
    doc.add_paragraph(
        f"Kho đầy đủ warehouse/xomecom.duckdb ({src_tables} bảng, {src_rows:,} dòng) chứa dữ liệu khách hàng nên "
        "không được đưa lên GitHub. Script scripts/12_build_app_data.py tạo một kho rút gọn riêng cho ứng dụng, "
        f"app/data/xomecom_app.duckdb ({n_tables} bảng, {n_rows:,} dòng, khoảng {size_mb:.0f} MB), theo ba nguyên tắc:"
    )
    bullets(doc, [
        "Chỉ chép bảng tổng hợp: các data mart, gold.fact_monthly_snapshot và kết quả mô hình trong schema ml.",
        "Không chép bảng có một dòng cho mỗi khách (dim_customer, mart_customer_value, customer_clusters, repeat_scores, ml_features). "
        "Thông tin khách hàng chỉ còn ở dạng số đếm theo nhóm; nhóm dưới 10 khách bị loại.",
        "Ứng dụng mở kho ở chế độ chỉ đọc và không huấn luyện lại mô hình, nên số liệu trùng với báo cáo chính.",
    ])
    doc.add_paragraph("Luồng dữ liệu:")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("CSV → Bronze → Silver → Gold → Mart / ML (dbt, Python)  →  12_build_app_data.py  →  "
                  "xomecom_app.duckdb  →  GitHub  →  Streamlit Community Cloud  →  trình duyệt")
    r.font.size = Pt(11)
    r.bold = True

    # 3
    doc.add_heading("3. Sáu trang của ứng dụng", level=1)
    pages = [
        ("1. Tổng quan KPI", "Thẻ KPI theo năm (so với năm trước), xu hướng doanh thu, lợi nhuận, biên theo tháng; "
         "biên theo phân khúc × thị trường; danh mục KPI", "mart_kpi_overview, fact_monthly_snapshot, mart_segment_profitability, metric_catalog"),
        ("2. Sản phẩm & Chiết khấu", "Doanh thu, lợi nhuận, biên theo mức chiết khấu; ma trận ngành hàng × chiết khấu; "
         "treemap ngành hàng; top sản phẩm lãi/lỗ", "mart_discount_analysis, mart_product_profitability"),
        ("3. Địa lý", "Bản đồ quốc gia (kích thước = doanh thu, màu = biên); thị trường qua các năm; xếp hạng quốc gia",
         "mart_geographic_performance"),
        ("4. Khách hàng", "Nhóm RFM, 4 cụm K-Means, cohort giữ chân, chân dung theo giới tính, tuổi, thu nhập, nghề nghiệp",
         "mart_customer_value (tổng hợp), mart_customer_cohort, ml.cluster_profile"),
        ("5. Học máy", "What-if chiết khấu và trần chiết khấu; dự báo ETS 6 tháng và tháng bất thường; "
         "dự đoán khách quay lại; luật Apriori; sổ đăng ký mô hình", "schema ml"),
        ("6. Chất lượng dữ liệu", "Đối chiếu Bronze = Silver = Gold, profiling, cờ chất lượng, số bảng và số dòng theo schema, nhật ký dbt",
         "B2.4, B4.2, B4.3, dim_flags, audit_run_log"),
    ]
    table(doc, ["Trang", "Nội dung", "Nguồn trong kho"], pages, [3.5, 8, 4.5])
    doc.add_paragraph("Bộ lọc năm, thị trường, phân khúc, ngành hàng nằm ở thanh bên trái; mọi truy vấn có cache nên trang phản hồi ngay.")

    shots = sorted(SHOTS.glob("*.png")) if SHOTS.exists() else []
    for i, img in enumerate(shots, 1):
        doc.add_picture(str(img), width=Cm(10))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        name = PAGE_NAMES.get(img.stem.split("_", 1)[0], img.stem)
        caption(doc, f"Hình {i}. Trang {name}")

    # 4
    doc.add_heading("4. Cách chạy và triển khai", level=1)
    doc.add_heading("4.1. Chạy trên máy", level=2)
    for line in ["pip install -r app/requirements.txt",
                 "python scripts/12_build_app_data.py      # tạo lại kho rút gọn sau khi chạy run_all.py",
                 "streamlit run app/streamlit_app.py       # mở http://localhost:8501"]:
        p = doc.add_paragraph()
        r = p.add_run(line)
        r.font.name = "Consolas"
        r.font.size = Pt(10)
        p.paragraph_format.space_after = Pt(0)
    doc.add_paragraph()
    doc.add_heading("4.2. Triển khai trên Streamlit Community Cloud", level=2)
    for s in [
        "Đẩy mã nguồn cùng thư mục app/ (gồm app/data/xomecom_app.duckdb) lên GitHub.",
        "Đăng nhập share.streamlit.io bằng tài khoản GitHub, chọn Create app.",
        "Chọn repository, nhánh main, Main file path là đường dẫn tới app/streamlit_app.py; Python 3.11.",
        "Bấm Deploy. Streamlit cài thư viện trong app/requirements.txt (streamlit, duckdb, pandas, plotly) và cấp link dạng https://<tên>.streamlit.app.",
        "Mỗi lần đẩy commit mới lên GitHub, ứng dụng tự cập nhật.",
    ]:
        doc.add_paragraph(s, style="List Number")
    p = doc.add_paragraph()
    p.add_run("Link ứng dụng: ").bold = True
    p.add_run(APP_URL or "(điền sau khi triển khai)")

    # 5
    doc.add_heading("5. Hạn chế", level=1)
    bullets(doc, [
        "Ứng dụng hiển thị kết quả mô hình đã tính sẵn; muốn cập nhật phải chạy lại pipeline và 12_build_app_data.py rồi đẩy lên GitHub.",
        "Không xem được dữ liệu ở mức từng khách hàng hay từng dòng giao dịch trên bản trực tuyến (chủ ý, để bảo vệ dữ liệu cá nhân).",
        "Gói miễn phí của Streamlit Community Cloud cho ứng dụng ngủ khi lâu không có người truy cập; lần mở đầu tiên mất khoảng 30 giây để khởi động lại.",
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"Đã tạo {OUT} ({len(shots)} ảnh chụp)")


if __name__ == "__main__":
    main()
