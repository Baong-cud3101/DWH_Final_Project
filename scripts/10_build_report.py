"""Dựng báo cáo Word theo chuẩn UEL từ các bản nháp Markdown trong report/drafts/.

Định dạng: A4, lề trái 3 cm / phải 2 cm / trên 2 cm / dưới 2 cm, Times New Roman 13,
giãn dòng 1,3, căn đều; bìa không đánh số; phần đầu đánh số La Mã; nội dung đánh số Ả Rập.

Cú pháp Markdown được hỗ trợ (mỗi khối cách nhau một dòng trống):
  # / ## / ###         heading cấp 1-3 (cấp 1 sang trang mới)
  #! Tiêu đề           heading cấp 1 không đánh số chương (Tóm tắt, Phụ lục...)
  - mục / 1. mục       danh sách
  **đậm**, *nghiêng*, `mã`
  {H2.4} {B4.5}        tham chiếu chéo -> "Hình 2.3", "Bảng 4.5"
  ::figure KEY file.png | chú thích | nguồn
  ::mermaid KEY tên_file | chú thích           (khối ```mermaid ngay sau)
  ::table KEY | chú thích | nguồn               (bảng Markdown ngay sau)
  ::csvtable KEY | chú thích | nguồn | file.csv | cột:Nhãn:định_dạng;... | bộ_lọc(tùy chọn)
  ::screenshot KEY | chú thích | hướng dẫn chụp
  ::code                                         (khối ``` ngay sau, in đơn cách)
  ::pagebreak
"""

import re
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from common import FIG_DIR, ROOT, TABLES_DIR

DRAFTS = ROOT / "report" / "drafts"
MERMAID_DIR = ROOT / "report" / "mermaid"
OUT = ROOT / "report" / "final" / "BaoCao_XomEcom_DuckDB.docx"
FONT = "Times New Roman"
MERMAID_DIR.mkdir(parents=True, exist_ok=True)
OUT.parent.mkdir(parents=True, exist_ok=True)

TITLE = ("XÂY DỰNG KHO DỮ LIỆU THEO KIẾN TRÚC MEDALLION VÀ ỨNG DỤNG HỌC MÁY TRÊN KHO DỮ LIỆU "
         "PHÂN TÍCH HIỆU QUẢ LỢI NHUẬN ĐA PHÂN KHÚC CHO SÀN THƯƠNG MẠI ĐIỆN TỬ XÓM E-COM")
MEMBERS = ["[MSSV 1] – [Họ và tên] (Nhóm trưởng)", "[MSSV 2] – [Họ và tên]",
           "[MSSV 3] – [Họ và tên]", "[MSSV 4] – [Họ và tên]", "[MSSV 5] – [Họ và tên]"]


# ----------------------------------------------------------------- tiện ích XML
def set_cell_shading(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def add_field(paragraph, instr, placeholder=""):
    """Chèn field Word (TOC, PAGE...). Người dùng nhấn F9 để cập nhật."""
    run = paragraph.add_run()
    b = OxmlElement("w:fldChar")
    b.set(qn("w:fldCharType"), "begin")
    b.set(qn("w:dirty"), "true")
    run._r.append(b)
    run2 = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = f" {instr} "
    run2._r.append(it)
    run3 = paragraph.add_run()
    s = OxmlElement("w:fldChar")
    s.set(qn("w:fldCharType"), "separate")
    run3._r.append(s)
    paragraph.add_run(placeholder)
    run4 = paragraph.add_run()
    e = OxmlElement("w:fldChar")
    e.set(qn("w:fldCharType"), "end")
    run4._r.append(e)


def set_page_number_format(section, fmt, start=1):
    sectPr = section._sectPr
    pg = sectPr.find(qn("w:pgNumType"))
    if pg is None:
        pg = OxmlElement("w:pgNumType")
        sectPr.append(pg)
    pg.set(qn("w:fmt"), fmt)
    pg.set(qn("w:start"), str(start))


def page_border(section):
    sectPr = section._sectPr
    borders = OxmlElement("w:pgBorders")
    borders.set(qn("w:offsetFrom"), "page")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "thinThickSmallGap")
        el.set(qn("w:sz"), "24")
        el.set(qn("w:space"), "24")
        el.set(qn("w:color"), "1F4E79")
        borders.append(el)
    sectPr.append(borders)


def keep_with_next(p):
    p.paragraph_format.keep_with_next = True


def box_paragraph(p, fill="F2F2F2"):
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    for side in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "4")
        el.set(qn("w:color"), "808080")
        bdr.append(el)
    pPr.append(bdr)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    pPr.append(shd)


# ----------------------------------------------------------------- styles
def setup_styles(doc):
    st = doc.styles
    normal = st["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(13)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    pf = normal.paragraph_format
    pf.line_spacing = 1.3
    pf.space_after = Pt(6)
    pf.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for lvl, size in ((1, 15), (2, 14), (3, 13)):
        h = st[f"Heading {lvl}"]
        h.font.name = FONT
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.italic = lvl == 3
        h.font.color.rgb = RGBColor(0, 0, 0)
        rpr = h.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.append(rf)
        for a in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
            rf.set(qn(a), FONT)
        # bỏ font theo theme (Calibri Light) vốn ghi đè font chỉ định
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rf.get(qn(a)) is not None:
                del rf.attrib[qn(a)]
        h.paragraph_format.space_before = Pt(18 if lvl == 1 else 12)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.keep_with_next = True
        h.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER if lvl == 1 else WD_ALIGN_PARAGRAPH.LEFT

    for name in ("Chú thích hình", "Chú thích bảng"):
        s = st.add_style(name, 1)
        s.base_style = normal
        s.font.size = Pt(12)
        s.font.italic = True
        s.font.bold = False
        s.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
        s.paragraph_format.space_before = Pt(4)
        s.paragraph_format.space_after = Pt(10)

    s = st.add_style("Bảng nội dung", 1)
    s.base_style = normal
    s.font.size = Pt(11)
    s.paragraph_format.line_spacing = 1.0
    s.paragraph_format.space_after = Pt(0)
    s.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    s = st.add_style("Mã nguồn", 1)
    s.base_style = normal
    s.font.name = "Consolas"
    s.font.size = Pt(9)
    s.paragraph_format.line_spacing = 1.0
    s.paragraph_format.space_after = Pt(0)
    s.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    s = st.add_style("Nguồn", 1)
    s.base_style = normal
    s.font.size = Pt(11)
    s.font.italic = True
    s.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s.paragraph_format.space_after = Pt(10)


# ----------------------------------------------------------------- inline
INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")


def add_inline(p, text, size=None, bold=None):
    for part in INLINE.split(text):
        if not part:
            continue
        if part.startswith("**"):
            r = p.add_run(part[2:-2])
            r.bold = True
        elif part.startswith("`"):
            r = p.add_run(part[1:-1])
            r.font.name = "Consolas"
            r.font.size = Pt(11 if size is None else max(size - 1, 8))
        elif part.startswith("*"):
            r = p.add_run(part[1:-1])
            r.italic = True
        else:
            r = p.add_run(part)
        if size and not part.startswith("`"):
            r.font.size = Pt(size)
        if bold:
            r.bold = True
    return p


# ----------------------------------------------------------------- bìa và phần đầu
def cover(doc):
    sec = doc.sections[0]
    page_border(sec)

    def line(text, size=14, bold=True, before=0, after=4, color=None, caps=False):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(text.upper() if caps else text)
        r.bold = bold
        r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(color)
        return p

    line("ĐẠI HỌC QUỐC GIA THÀNH PHỐ HỒ CHÍ MINH", 14, False, 0, 0, "1F4E79")
    line("TRƯỜNG ĐẠI HỌC KINH TẾ - LUẬT", 16, True, 0, 0, "1F4E79")
    line("KHOA HỆ THỐNG THÔNG TIN", 16, True, 24, 12)
    p = line("[Chèn logo UEL tại đây]", 11, False, 24, 24, "808080")
    box_paragraph(p, "FFFFFF")
    line("BÀI TẬP LỚN", 16, True, 18, 0)
    line("NHÀ KHO DỮ LIỆU VÀ TÍCH HỢP", 16, True, 0, 24)
    line(TITLE, 15, True, 6, 30, "1F4E79")
    for t in ["GVHD: TS. Nguyễn Thôn Dã", "Mã nhóm: [điền]"] + MEMBERS:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(2.5)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.15
        r = p.add_run(t)
        r.bold = True
        r.font.size = Pt(14)
    line("TP. Hồ Chí Minh, tháng 11 năm 2026", 13, False, 30, 0)


def new_section(doc, fmt, start=1):
    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.footer.is_linked_to_previous = False
    p = sec.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_field(p, "PAGE", "1")
    set_page_number_format(sec, fmt, start)
    # tắt viền trang thừa hưởng từ bìa
    b = sec._sectPr.find(qn("w:pgBorders"))
    if b is not None:
        sec._sectPr.remove(b)
    return sec


def front_heading(doc, text):
    p = doc.add_paragraph(style="Heading 1")
    p.add_run(text)
    return p


def front_matter(doc):
    new_section(doc, "lowerRoman", 1)
    front_heading(doc, "LỜI CẢM ƠN")
    for t in [
        "Nhóm xin chân thành cảm ơn TS. Nguyễn Thôn Dã, giảng viên học phần Nhà kho dữ liệu và tích hợp, "
        "đã truyền đạt kiến thức nền tảng về kho dữ liệu, mô hình hóa đa chiều, tích hợp dữ liệu và khai thác "
        "dữ liệu, đồng thời định hướng nhóm trong quá trình thực hiện bài tập lớn.",
        "Nhóm cũng cảm ơn Khoa Hệ thống thông tin, Trường Đại học Kinh tế - Luật đã tạo điều kiện học tập, "
        "và cộng đồng Xóm Data đã chia sẻ bộ dữ liệu Xóm E-Com cùng dự án mã nguồn mở tham khảo.",
        "Do thời gian và kinh nghiệm còn hạn chế, báo cáo khó tránh khỏi thiếu sót. Nhóm mong nhận được "
        "góp ý của Thầy để hoàn thiện hơn.",
    ]:
        doc.add_paragraph(t)
    p = doc.add_paragraph("Nhóm thực hiện")
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.runs[0].italic = True

    doc.add_page_break()
    front_heading(doc, "MỤC LỤC")
    add_field(doc.add_paragraph(), 'TOC \\o "1-3" \\h \\z \\u',
              "Nhấn chuột phải, chọn Update Field (hoặc Ctrl+A rồi F9) để tạo mục lục.")
    doc.add_page_break()
    front_heading(doc, "DANH MỤC HÌNH")
    add_field(doc.add_paragraph(), 'TOC \\h \\z \\t "Chú thích hình,1"',
              "Nhấn F9 để cập nhật danh mục hình.")
    doc.add_page_break()
    front_heading(doc, "DANH MỤC BẢNG")
    add_field(doc.add_paragraph(), 'TOC \\h \\z \\t "Chú thích bảng,1"',
              "Nhấn F9 để cập nhật danh mục bảng.")
    doc.add_page_break()
    front_heading(doc, "DANH MỤC TỪ VIẾT TẮT")
    abbr = [
        ("AOV", "Average Order Value – giá trị trung bình một đơn hàng"),
        ("APAC", "Asia Pacific – thị trường châu Á - Thái Bình Dương"),
        ("ARIMA / SARIMA", "(Seasonal) AutoRegressive Integrated Moving Average"),
        ("B2B / B2C", "Business-to-Business / Business-to-Consumer"),
        ("CDC", "Change Data Capture – thu thập dữ liệu thay đổi"),
        ("CSV", "Comma-Separated Values"),
        ("dbt", "data build tool – công cụ biến đổi dữ liệu bằng SQL"),
        ("DDS", "Deep-Discount Share – tỷ lệ dòng giảm giá trên 30%"),
        ("EDA", "Exploratory Data Analysis – khám phá dữ liệu"),
        ("ELT", "Extract – Load – Transform"),
        ("EMEA", "Europe, Middle East and Africa"),
        ("ETS", "Error – Trend – Seasonality (Holt-Winters)"),
        ("HGB", "HistGradientBoostingRegressor"),
        ("KPI", "Key Performance Indicator – chỉ số đo lường hiệu quả chính"),
        ("LTV", "Lifetime Value – giá trị vòng đời khách hàng"),
        ("MAE / MAPE", "Mean Absolute Error / Mean Absolute Percentage Error"),
        ("OLAP", "Online Analytical Processing"),
        ("P&L", "Profit and Loss – báo cáo lãi lỗ"),
        ("R²", "Hệ số xác định"),
        ("RFM", "Recency – Frequency – Monetary"),
        ("SCD", "Slowly Changing Dimension"),
        ("SK", "Surrogate Key – khóa thay thế"),
        ("USCA", "United States & Canada – thị trường Mỹ và Canada"),
    ]
    t = doc.add_table(rows=1, cols=2)
    t.style = "Table Grid"
    for c, h in zip(t.rows[0].cells, ("Từ viết tắt", "Diễn giải")):
        c.text = ""
        add_inline(c.paragraphs[0], h, 12, True)
        set_cell_shading(c, "D9E2F3")
    for a, b in abbr:
        r = t.add_row().cells
        for c, v in zip(r, (a, b)):
            c.text = ""
            c.paragraphs[0].style = doc.styles["Bảng nội dung"]
            add_inline(c.paragraphs[0], v, 12)
    t.columns[0].width = Cm(3.5)
    for row in t.rows:
        row.cells[0].width = Cm(3.5)
        row.cells[1].width = Cm(12.5)


# ----------------------------------------------------------------- bảng
def fmt_value(v, f):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "–"
    try:
        if f == "int":
            return f"{int(round(float(v))):,}".replace(",", ".")
        if f == "usd":
            return f"{float(v):,.0f}".replace(",", ".")
        if f == "usd2":
            return f"{float(v):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
        if f == "pct1":
            return f"{float(v) * 100:.1f}%".replace(".", ",")
        if f == "pct0":
            return f"{float(v) * 100:.0f}%"
        if f == "pp":
            return f"{float(v) * 100:+.1f} điểm %".replace(".", ",")
        if f == "f2":
            return f"{float(v):.2f}".replace(".", ",")
        if f == "f3":
            return f"{float(v):.3f}".replace(".", ",")
        if f == "f4":
            return f"{float(v):.4f}".replace(".", ",")
        if f == "f1":
            return f"{float(v):.1f}".replace(".", ",")
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def add_table(doc, header, rows, numeric_cols=None):
    numeric_cols = numeric_cols or set()
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    size = 11 if len(header) <= 5 else 10
    for i, (c, h) in enumerate(zip(t.rows[0].cells, header)):
        c.text = ""
        p = c.paragraphs[0]
        p.style = doc.styles["Bảng nội dung"]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_inline(p, h, size, True)
        set_cell_shading(c, "D9E2F3")
    set_repeat_header(t.rows[0])
    for row in rows:
        cells = t.add_row().cells
        for i, (c, v) in enumerate(zip(cells, row)):
            c.text = ""
            p = c.paragraphs[0]
            p.style = doc.styles["Bảng nội dung"]
            if i in numeric_cols:
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            add_inline(p, str(v), size)
    return t


def is_numeric_text(s):
    return bool(re.fullmatch(r"[-+–]?[\d.,]+\s?(%|USD|điểm %)?", s.strip())) and any(ch.isdigit() for ch in s)


# ----------------------------------------------------------------- phân tích nháp
def load_blocks():
    files = sorted(DRAFTS.glob("*.md"))
    text = "\n\n".join(f.read_text(encoding="utf-8") for f in files)
    lines = text.splitlines()
    blocks, buf, i = [], [], 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            fence = [line]
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                fence.append(lines[i])
                i += 1
            fence.append("```")
            if buf:
                blocks.append(buf)
                buf = []
            blocks.append(fence)
            i += 1
            continue
        if not line.strip():
            if buf:
                blocks.append(buf)
                buf = []
        else:
            buf.append(line)
        i += 1
    if buf:
        blocks.append(buf)
    return blocks


def assign_numbers(blocks):
    """Lượt 1: đánh số hình/bảng theo chương."""
    chapter, nums, counters = 0, {}, {}
    for b in blocks:
        first = b[0]
        m = re.match(r"^# (CHƯƠNG|Chương) (\d+)", first)
        if m:
            chapter = int(m.group(2))
        if first.startswith("#! PHỤ LỤC") or first.startswith("#! Phụ lục"):
            chapter = "PL"
        m = re.match(r"^::(figure|mermaid|screenshot|table|csvtable)\s+(\S+)", first)
        if m:
            kind = "Bảng" if m.group(1) in ("table", "csvtable") else "Hình"
            key = (kind, chapter)
            counters[key] = counters.get(key, 0) + 1
            nums[m.group(2).rstrip("|").strip()] = f"{kind} {chapter}.{counters[key]}"
    return nums


def resolve_refs(text, nums):
    def rep(m):
        k = m.group(1)
        if k not in nums:
            raise KeyError(f"Tham chiếu {k} chưa được định nghĩa")
        return nums[k]
    return re.sub(r"\{([HB]\d[\w.]*)\}", rep, text)


def caption(doc, kind, label, text):
    style = "Chú thích hình" if kind == "Hình" else "Chú thích bảng"
    p = doc.add_paragraph(style=style)
    r = p.add_run(f"{label}. ")
    r.bold = True
    r.italic = False
    add_inline(p, text)
    if kind == "Bảng":
        keep_with_next(p)
    return p


def source_line(doc, src):
    if src:
        doc.add_paragraph(f"Nguồn: {src}", style="Nguồn")


def build():
    blocks = load_blocks()
    nums = assign_numbers(blocks)
    doc = Document()
    sec = doc.sections[0]
    sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
    sec.left_margin, sec.right_margin = Cm(3), Cm(2)
    sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
    setup_styles(doc)
    cover(doc)
    front_matter(doc)
    main_started = False
    pending_kind = None   # (kind, label, caption, src) cho mermaid/table/code chờ khối sau
    index = []            # bảng tra: số Hình/Bảng trong Word -> mục, tệp nguồn
    section = ""

    def reg(label, cap, kind, source):
        index.append({"label": label, "caption": re.sub(r"[*`]", "", cap), "section": section,
                      "kind": kind, "source": source})

    for b in blocks:
        first = b[0]
        txt = "\n".join(b)

        # khối rào ``` (mermaid, bảng mã)
        if first.strip().startswith("```"):
            body = b[1:-1]
            if pending_kind and pending_kind[0] == "mermaid":
                _, label, cap, fname = pending_kind
                (MERMAID_DIR / f"{fname}.mmd").write_text("\n".join(body) + "\n", encoding="utf-8")
                note = doc.add_paragraph(style="Mã nguồn")
                r = note.add_run(f"[SƠ ĐỒ – nhóm tự vẽ từ mã mermaid dưới đây; tệp report/mermaid/{fname}.mmd]")
                r.bold = True
                box_paragraph(note, "FFF2CC")
                for ln in body:
                    p = doc.add_paragraph(style="Mã nguồn")
                    p.add_run(ln if ln else " ")
                    box_paragraph(p, "FFF2CC")
                caption(doc, "Hình", label, cap)
                reg(label, cap, "Sơ đồ (mermaid, tự vẽ)", f"report/mermaid/{fname}.mmd")
            else:
                for ln in body:
                    p = doc.add_paragraph(style="Mã nguồn")
                    p.add_run(ln if ln else " ")
                    box_paragraph(p)
                doc.add_paragraph()
            pending_kind = None
            continue

        if first.startswith("#"):
            m = re.match(r"^(#+)(!?)\s+(.*)$", first)
            level, unnumbered, title = len(m.group(1)), m.group(2), m.group(3)
            if level == 1:
                if not main_started:
                    new_section(doc, "decimal", 1)
                    main_started = True
                else:
                    doc.add_page_break()
            doc.add_paragraph(resolve_refs(title, nums), style=f"Heading {level}")
            section = title  # mục gần nhất chứa hình/bảng
            continue

        if first.startswith("::pagebreak"):
            doc.add_page_break()
            continue

        if first.startswith("::figure"):
            parts = [x.strip() for x in first[len("::figure"):].split("|")]
            key, fname = parts[0].split()[:2]
            cap = parts[1]
            src = parts[2] if len(parts) > 2 else "Nhóm thực hiện, truy vấn từ kho DuckDB"
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            keep_with_next(p)
            p.add_run().add_picture(str(FIG_DIR / fname), width=Cm(15.5))
            caption(doc, "Hình", nums[key], resolve_refs(cap, nums))
            source_line(doc, src)
            reg(nums[key], resolve_refs(cap, nums), "Biểu đồ (PNG)", f"results/figures/{fname}")
            continue

        if first.startswith("::mermaid"):
            parts = [x.strip() for x in first[len("::mermaid"):].split("|")]
            key, fname = parts[0].split()[:2]
            pending_kind = ("mermaid", nums[key], resolve_refs(parts[1], nums), fname)
            continue

        if first.startswith("::screenshot"):
            parts = [x.strip() for x in first[len("::screenshot"):].split("|")]
            key = parts[0].split()[0]
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(6)
            r = p.add_run(f"\n[CHÈN ẢNH CHỤP MÀN HÌNH]\n{parts[2] if len(parts) > 2 else ''}\n")
            r.italic = True
            r.font.size = Pt(11)
            r.font.color.rgb = RGBColor(0x80, 0x80, 0x80)
            box_paragraph(p, "FFFFFF")
            keep_with_next(p)
            caption(doc, "Hình", nums[key], resolve_refs(parts[1], nums))
            reg(nums[key], resolve_refs(parts[1], nums), "Ảnh chụp (nhóm tự chụp)", parts[2] if len(parts) > 2 else "")
            continue

        if first.startswith("::code"):
            pending_kind = ("code",)
            continue

        if first.startswith("::table"):
            parts = [x.strip() for x in first[len("::table"):].split("|")]
            key = parts[0].split()[0]
            cap, src = parts[1], (parts[2] if len(parts) > 2 else "")
            caption(doc, "Bảng", nums[key], resolve_refs(cap, nums))
            md = [ln for ln in b[1:] if ln.strip().startswith("|")]
            rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in md]
            header, body = [resolve_refs(c, nums) for c in rows[0]], [r for r in rows[2:]]
            body = [[resolve_refs(c, nums) for c in r] for r in body]
            numeric = {i for i in range(len(header))
                       if body and all(is_numeric_text(r[i]) or r[i] in ("–", "") for r in body if i < len(r))}
            add_table(doc, header, body, numeric)
            source_line(doc, src)
            reg(nums[key], resolve_refs(cap, nums), "Bảng viết trong bản nháp", f"report/drafts (nguồn: {src})")
            continue

        if first.startswith("::csvtable"):
            parts = [x.strip() for x in first[len("::csvtable"):].split("|")]
            key, cap, src, csv, spec = parts[0].split()[0], parts[1], parts[2], parts[3], parts[4]
            flt = parts[5] if len(parts) > 5 else ""
            df = pd.read_csv(TABLES_DIR / csv, encoding="utf-8-sig")
            if flt:
                df = df.query(flt)
            cols = [c.split(":") for c in spec.split(";")]
            header = [c[1] for c in cols]
            body, numeric = [], set()
            for _, r in df.iterrows():
                body.append([fmt_value(r[c[0]], c[2] if len(c) > 2 else "str") for c in cols])
            for i, c in enumerate(cols):
                if len(c) > 2 and c[2] != "str":
                    numeric.add(i)
            caption(doc, "Bảng", nums[key], resolve_refs(cap, nums))
            add_table(doc, header, body, numeric)
            source_line(doc, src)
            csv_rel = (TABLES_DIR / csv).resolve().relative_to(ROOT.resolve()).as_posix()
            reg(nums[key], resolve_refs(cap, nums), "Bảng số liệu (CSV)",
                csv_rel + (f" (lọc: {flt})" if flt else ""))
            continue

        # danh sách
        if all(re.match(r"^\s*(-|\d+\.)\s+", ln) for ln in b):
            for ln in b:
                m = re.match(r"^(\s*)(-|\d+\.)\s+(.*)$", ln)
                indent = 1 if len(m.group(1)) >= 2 else 0
                if m.group(2) == "-":
                    p = doc.add_paragraph(style="List Bullet 2" if indent else "List Bullet")
                    add_inline(p, resolve_refs(m.group(3), nums))
                else:
                    # đánh số bằng chữ để mỗi danh sách bắt đầu lại từ 1
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Cm(1.0 + indent * 0.8)
                    p.paragraph_format.first_line_indent = Cm(-0.7)
                    add_inline(p, m.group(2) + "	" + resolve_refs(m.group(3), nums))
                    p.paragraph_format.tab_stops.add_tab_stop(Cm(1.0 + indent * 0.8))
                p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.3
            continue

        # đoạn văn thường (nối các dòng)
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Cm(1)
        add_inline(p, resolve_refs(" ".join(ln.strip() for ln in b), nums))

    # danh sách kiểu bullet dùng Times New Roman
    for sname in ("List Bullet", "List Number", "List Bullet 2", "List Number 2"):
        s = doc.styles[sname]
        s.font.name = FONT
        s.font.size = Pt(13)
    doc.settings.element.append(OxmlElement("w:updateFields"))
    doc.settings.element[-1].set(qn("w:val"), "true")
    doc.save(OUT)
    print(f"Đã ghi {OUT}")
    write_index(index)
    print(f"Số hình: {sum(1 for v in nums.values() if v.startswith('Hình'))}, "
          f"số bảng: {sum(1 for v in nums.values() if v.startswith('Bảng'))}")


def write_index(index):
    """Bảng tra Hình/Bảng trong Word -> tệp số liệu, sinh lại mỗi lần dựng báo cáo."""
    lines = [
        "# Bảng tra hình và bảng của báo cáo",
        "",
        "Sinh tự động bởi `scripts/10_build_report.py` mỗi lần dựng báo cáo, nên số Hình/Bảng luôn khớp file Word.",
        "Tên file trong `results/tables` dùng mã của đề cương (ví dụ `B4.19_...`), khác số Bảng trong Word; hãy tra theo cột đầu.",
        "Các con số lẻ trong phần chữ nằm ở `results/tables/B_extra_numbers.csv` (kèm câu SQL), "
        "toàn bộ số liệu chính ở `results/tables/key_numbers.json`.",
        "",
    ]
    for kind in ("Hình", "Bảng"):
        lines += [f"## {kind}", "", "| Số trong Word | Tiêu đề | Mục | Loại | Tệp nguồn |", "|---|---|---|---|---|"]
        for e in index:
            if e["label"].startswith(kind):
                cells = [e["label"], e["caption"], e["section"], e["kind"], f"`{e['source']}`" if e["source"] else ""]
                lines.append("| " + " | ".join(c.replace("|", "/") for c in cells) + " |")
        lines.append("")
    text = "\n".join(lines)
    for p in (ROOT / "report" / "INDEX_bang_hinh.md", ROOT / "results" / "INDEX.md"):
        p.write_text(text, encoding="utf-8")
    print(f"Bảng tra: {len(index)} mục -> results/INDEX.md")


if __name__ == "__main__":
    build()
