"""Sinh dashboard Power BI (định dạng PBIP: mô hình TMDL + báo cáo PBIR) từ exports/powerbi.

Bố cục và theme theo mẫu Hotel_Merged.pbix (trang 1280x720, header tiêu đề + thanh điều hướng,
thẻ trắng bo góc, màu navy/vàng). Năm trang: Trang chủ + bốn trang theo Phụ lục C của báo cáo.

Chạy:  python scripts/11_build_powerbi.py
Mở:    powerbi/XomEcom_Dashboard.pbip bằng Power BI Desktop, bấm Refresh để nạp CSV.
Đường dẫn CSV là tham số DataFolder (Transform data > Edit parameters) nếu chuyển máy.
"""

import json
import re
import shutil
import uuid
from pathlib import Path

import pandas as pd

from common import EXPORT_DIR, ROOT

NAME = "XomEcom_Dashboard"
OUT = ROOT / "powerbi"
ASSETS = Path(__file__).resolve().parent / "powerbi_assets"
REPORT = OUT / f"{NAME}.Report"
MODEL = OUT / f"{NAME}.SemanticModel"
DEF = REPORT / "definition"

SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item"
NAVY, GOLD, INK, MUTED, LINE = "#1F3A5F", "#E8A33D", "#1E2A3A", "#5B6B82", "#E3E8F0"
RED, GREEN, SKY = "#C8553D", "#2E7D6B", "#5B8DB8"
M = "_Measures"


def guid(*parts) -> str:
    """lineageTag ổn định giữa các lần chạy (để Git không báo thay đổi giả)."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "xomecom/" + "/".join(map(str, parts))))


def vn_pct(x, nd=1):
    """Làm tròn nửa lên như trong báo cáo (0,18450 -> 18,5%)."""
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(repr(float(x) * 100)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP)
    return f"{q}".replace(".", ",") + "%"


def vn_num(x):
    return f"{x:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- dữ liệu nguồn
TABLES = [
    "mart_kpi_overview", "mart_segment_profitability", "mart_product_profitability",
    "mart_geographic_performance", "mart_discount_analysis", "mart_customer_cohort",
    "mart_customer_value", "fact_monthly_snapshot", "metric_catalog", "ml_cluster_profile",
    "ml_whatif_discount", "ml_whatif_discount_cap", "ml_forecast_monthly", "ml_monthly_anomalies",
]
DF = {t: pd.read_csv(EXPORT_DIR / f"{t}.csv") for t in TABLES}

NO_SUM = {"year", "month", "month_key", "cluster", "customer_key", "product_key", "cohort_year",
          "active_year", "years_since_first", "discount_band_order", "r_score", "f_score",
          "m_score", "country_latitude", "country_longitude", "cap", "discount_level", "discount"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}( 00:00:00)?$")

# Cột thêm trong Power Query: (bảng) -> [(tên, kiểu TMDL, biểu thức M, kiểu M)]
EXTRA_COLS = {
    "ml_forecast_monthly": [("year", "int64", "Date.Year([month_start])", "Int64.Type")],
    "ml_whatif_discount_cap": [
        ("cap_label", "string", '"Trần " & Text.From(Number.Round([cap] * 100)) & "%"', "type text")],
}
# Lọc dòng trong Power Query: dòng year = 0 của mart_kpi_overview là tổng toàn kỳ (tránh (Blank) trên slicer năm)
ROW_FILTERS = {"mart_kpi_overview": "each [year] <> 0"}
SORT_BY = {("mart_discount_analysis", "discount_band"): "discount_band_order"}
DATA_CAT = {"country_latitude": "Latitude", "country_longitude": "Longitude", "country": "Country"}
FORMATS = {"month_start": "mmm yyyy", "first_order_date": "dd/mm/yyyy", "last_order_date": "dd/mm/yyyy"}


def col_types(df: pd.DataFrame):
    out = []
    for c in df.columns:
        s = df[c]
        if s.dtype == bool:
            out.append((c, "boolean", "type logical"))
        elif pd.api.types.is_integer_dtype(s):
            out.append((c, "int64", "Int64.Type"))
        elif pd.api.types.is_float_dtype(s):
            whole = s.dropna()
            if c in NO_SUM and len(whole) and (whole == whole.round()).all() and c not in (
                    "country_latitude", "country_longitude", "cap", "discount_level", "discount"):
                out.append((c, "int64", "Int64.Type"))
            else:
                out.append((c, "double", "type number"))
        else:
            vals = s.dropna().astype(str)
            if len(vals) and vals.str.match(DATE_RE).all():
                out.append((c, "dateTime", "type datetime"))
            else:
                out.append((c, "string", "type text"))
    return out


# ---------------------------------------------------------------- TMDL helpers
def tmdl_name(n: str) -> str:
    return n if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n) else "'" + n.replace("'", "''") + "'"


def m_block(lines, indent=4):
    pad = "\t" * indent
    return "\n".join(pad + ln for ln in lines)


def column_tmdl(table, c, dtype, hidden=False):
    lines = [f"\tcolumn {tmdl_name(c)}", f"\t\tdataType: {dtype}"]
    if c in FORMATS:
        lines.append(f"\t\tformatString: {FORMATS[c]}")
    elif dtype == "int64":
        lines.append("\t\tformatString: 0")
    if hidden:
        lines.append("\t\tisHidden")
    lines.append(f"\t\tlineageTag: {guid(table, c)}")
    if c in DATA_CAT:
        lines.append(f"\t\tdataCategory: {DATA_CAT[c]}")
    numeric = dtype in ("int64", "double")
    lines.append(f"\t\tsummarizeBy: {'sum' if numeric and c not in NO_SUM else 'none'}")
    lines.append(f"\t\tsourceColumn: {c}")
    if (table, c) in SORT_BY:
        lines.append(f"\t\tsortByColumn: {SORT_BY[(table, c)]}")
    lines.append("")
    lines.append("\t\tannotation SummarizationSetBy = Automatic")
    return "\n".join(lines)


def table_tmdl(name, columns, m_lines, measures=()):
    parts = [f"table {tmdl_name(name)}", f"\tlineageTag: {guid(name)}", ""]
    for mname, expr, fmt in measures:
        parts += [f"\tmeasure {tmdl_name(mname)} = {expr}",
                  f"\t\tformatString: {fmt}",
                  f"\t\tlineageTag: {guid(name, 'measure', mname)}", ""]
    for c, dtype, hidden in columns:
        parts += [column_tmdl(name, c, dtype, hidden), ""]
    parts += [f"\tpartition {tmdl_name(name)} = m", "\t\tmode: import", "\t\tsource =",
              m_block(m_lines), "", "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(parts)


def csv_table(name):
    df = DF[name]
    types = col_types(df)
    type_list = ", ".join(f'{{"{c}", {mt}}}' for c, _, mt in types)
    m = [
        "let",
        f'    Source = Csv.Document(File.Contents(DataFolder & "{name}.csv"), '
        f'[Delimiter = ",", Columns = {len(df.columns)}, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{type_list}}}, "en-US")',
    ]
    last = "Typed"
    if name in ROW_FILTERS:
        m[-1] += ","
        m.append(f"    Filtered = Table.SelectRows(Typed, {ROW_FILTERS[name]})")
        last = "Filtered"
    cols = [(c, t, False) for c, t, _ in types]
    for i, (c, t, expr, mt) in enumerate(EXTRA_COLS.get(name, [])):
        m[-1] += ","
        m.append(f'    Added{i} = Table.AddColumn({last}, "{c}", each {expr}, {mt})')
        last = f"Added{i}"
        cols.append((c, t, False))
    m += ["in", f"    {last}"]
    return cols, m


def dim_table(name, col, values, dtype):
    if dtype == "int64":
        rows, mt = ", ".join(f"{{{v}}}" for v in values), "Int64.Type"
    else:
        rows, mt = ", ".join(f'{{"{v}"}}' for v in values), "text"
    m = ["let", f"    Source = #table(type table [{col} = {mt}], {{{rows}}})", "in", "    Source"]
    return [(col, dtype, False)], m


# ---------------------------------------------------------------- measures (DAX)
YEARS = sorted(int(y) for y in DF["mart_kpi_overview"]["year"] if y != 0)
LY, PY = YEARS[-1], YEARS[-2]
CL = DF["ml_cluster_profile"].sort_values("cluster")
CLUSTERS = list(zip(CL["cluster"].astype(int), CL["cluster_name"]))

SP, KPI, DA, GEO = "mart_segment_profitability", "mart_kpi_overview", "mart_discount_analysis", "mart_geographic_performance"
CV, FC, AN = "mart_customer_value", "ml_forecast_monthly", "ml_monthly_anomalies"
USD, PCT, INT = "#,0", "0.0%", "#,0"

MEASURES = [
    # Trang 1 (Phụ lục C)
    ("Revenue", f"SUM({SP}[revenue])", USD),
    ("Profit", f"SUM({SP}[profit])", USD),
    ("Profit Margin", "DIVIDE([Profit], [Revenue])", PCT),
    ("Implied Cost", "[Revenue] - [Profit]", USD),
    ("Orders", f"IF(ISFILTERED(DimMarket[market]) || ISFILTERED(DimSegment[segment]), "
               f"SUM({SP}[total_orders]), SUM({KPI}[total_orders]))", INT),
    ("AOV", "DIVIDE([Revenue], [Orders])", "#,0.00"),
    # Có lọc 1 năm: tỷ lệ của năm đó (mart_kpi_overview); không lọc năm: tính trên toàn bộ khách
    ("Repeat Rate", f"IF(ISFILTERED(DimYear[year]), IF(HASONEVALUE(DimYear[year]), "
                    f"MAX({KPI}[repeat_customer_rate])), [Customer Repeat Rate])", PCT),
    ("Margin LY", "VAR y = MAX(DimYear[year]) RETURN CALCULATE([Profit Margin], DimYear[year] = y - 1)", PCT),
    ("Margin Change", "[Profit Margin] - [Margin LY]", "+0.0%;-0.0%;0.0%"),
    ("Actual Profit", f'CALCULATE(SUM({FC}[profit]), {FC}[kind] = "actual")', USD),
    ("Forecast Profit", f'CALCULATE(SUM({FC}[profit]), {FC}[kind] = "forecast")', USD),
    ("Anomaly Profit", f"CALCULATE(SUM({AN}[profit]), {AN}[is_anomaly] = TRUE())", USD),
    # Trang 2
    ("Disc Revenue", f"SUM({DA}[revenue])", USD),
    ("Disc Margin", f"DIVIDE(SUM({DA}[profit]), SUM({DA}[revenue]))", PCT),
    ("Disc Loss Line Rate", f"DIVIDE(SUM({DA}[loss_lines]), SUM({DA}[total_lines]))", PCT),
    ("Cap Profit Baseline", "SUM(ml_whatif_discount_cap[pred_profit_baseline])", USD),
    ("Cap Profit Capped", "SUM(ml_whatif_discount_cap[pred_profit_capped])", USD),
    ("Cap Uplift %", "AVERAGE(ml_whatif_discount_cap[uplift_pct])", PCT),
    ("WhatIf Margin", "DIVIDE(SUM(ml_whatif_discount[pred_profit]), SUM(ml_whatif_discount[sales]))", PCT),
    # Trang 3
    ("Geo Revenue", f"SUM({GEO}[revenue])", USD),
    ("Geo Profit", f"SUM({GEO}[profit])", USD),
    ("Geo Margin", "DIVIDE([Geo Profit], [Geo Revenue])", PCT),
    (f"Geo Margin {PY}", f"CALCULATE([Geo Margin], DimYear[year] = {PY})", PCT),
    (f"Geo Margin {LY}", f"CALCULATE([Geo Margin], DimYear[year] = {LY})", PCT),
    ("Geo Growth", "VAR y = MAX(DimYear[year]) RETURN DIVIDE(CALCULATE([Geo Revenue], DimYear[year] = y), "
                   "CALCULATE([Geo Revenue], DimYear[year] = y - 1)) - 1", "+0.0%;-0.0%;0.0%"),
    (f"Geo Growth {LY}", f"CALCULATE([Geo Growth], DimYear[year] = {LY})", "+0.0%;-0.0%;0.0%"),
    # Trang 4
    ("Customers", f"COUNTROWS({CV})", INT),
    ("Avg Recency", f"AVERAGE({CV}[recency_days])", "#,0"),
    ("Avg Frequency", f"AVERAGE({CV}[frequency])", "0.00"),
    ("Avg Monetary", f"AVERAGE({CV}[monetary])", "#,0"),
    ("Customer Margin", f"DIVIDE(SUM({CV}[profit]), SUM({CV}[monetary]))", PCT),
    ("Customer Repeat Rate", f"DIVIDE(CALCULATE(COUNTROWS({CV}), {CV}[is_repeat_customer] = TRUE()), COUNTROWS({CV}))", PCT),
    ("Profit Share", f"DIVIDE(SUM({CV}[profit]), CALCULATE(SUM({CV}[profit]), ALLSELECTED({CV}[cluster_name])))", PCT),
    ("Retention", "AVERAGE(mart_customer_cohort[retention_rate])", PCT),
] + [(f"Customers C{k}", f"CALCULATE(COUNTROWS({CV}), KEEPFILTERS({CV}[cluster] = {k}))", INT)
     for k, _ in CLUSTERS]

RELATIONSHIPS = (
    [(t, "year", "DimYear", "year") for t in
     (KPI, SP, DA, GEO, "mart_product_profitability", "fact_monthly_snapshot")]
    + [(t, "market", "DimMarket", "market") for t in
       (SP, DA, GEO, "fact_monthly_snapshot", "ml_whatif_discount")]
    + [(t, "segment", "DimSegment", "segment") for t in (SP, DA, "fact_monthly_snapshot", CV)]
    + [(t, "category", "DimCategory", "category") for t in
       (DA, "mart_product_profitability", "ml_whatif_discount")]
    + [(CV, "cluster", "ml_cluster_profile", "cluster"), (AN, "month_start", FC, "month_start")]
)


def build_model():
    if MODEL.exists():
        shutil.rmtree(MODEL)
    tdir = MODEL / "definition" / "tables"
    tdir.mkdir(parents=True)
    (MODEL / "definition.pbism").write_text(json.dumps({
        "$schema": f"{SCHEMA}/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2", "settings": {}}, indent=2), encoding="utf-8")

    markets = sorted(set(DF[SP]["market"]) | set(DF[GEO]["market"]))
    segments = sorted(set(DF[SP]["segment"]) | set(DF[CV]["segment"]))
    categories = sorted(set(DF[DA]["category"]) | set(DF["mart_product_profitability"]["category"]))
    dims = {
        "DimYear": dim_table("DimYear", "year", YEARS, "int64"),
        "DimMarket": dim_table("DimMarket", "market", markets, "string"),
        "DimSegment": dim_table("DimSegment", "segment", segments, "string"),
        "DimCategory": dim_table("DimCategory", "category", categories, "string"),
    }
    order = [M] + list(dims) + TABLES
    for name in order:
        if name == M:
            text = table_tmdl(M, [("Dummy", "string", True)],
                              ["let", "    Source = #table(type table [Dummy = text], {})", "in", "    Source"],
                              MEASURES)
        elif name in dims:
            cols, m = dims[name]
            text = table_tmdl(name, cols, m)
        else:
            cols, m = csv_table(name)
            text = table_tmdl(name, cols, m)
        (tdir / f"{name}.tmdl").write_text(text, encoding="utf-8")

    folder = str(EXPORT_DIR.resolve()) + "\\"
    (MODEL / "definition" / "expressions.tmdl").write_text(
        f'expression DataFolder = "{folder}" meta [IsParameterQuery = true, Type = "Text", '
        f'IsParameterQueryRequired = true]\n\tlineageTag: {guid("DataFolder")}\n\n'
        "\tannotation PBI_ResultType = Text\n", encoding="utf-8")
    (MODEL / "definition" / "database.tmdl").write_text(
        "database\n\tcompatibilityLevel: 1600\n", encoding="utf-8")
    query_order = json.dumps(["DataFolder"] + order, ensure_ascii=False)
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects",
             "\t\treturnErrorValuesAsNull", "", f"annotation PBI_QueryOrder = {query_order}", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", ""]
    model += [f"ref table {tmdl_name(n)}" for n in order] + [""]
    (MODEL / "definition" / "model.tmdl").write_text("\n".join(model), encoding="utf-8")
    rel = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel += [f"relationship {guid('rel', ft, fc, tt)}", f"\tfromColumn: {ft}.{fc}",
                f"\ttoColumn: {tt}.{tc}", ""]
    (MODEL / "definition" / "relationships.tmdl").write_text("\n".join(rel), encoding="utf-8")


# ---------------------------------------------------------------- PBIR helpers
def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def s(text):
    return lit("'" + str(text).replace("'", "''") + "'")


def d(n):
    return lit(f"{n}D")


def b(x):
    return lit("true" if x else "false")


def solid(c):
    return {"solid": {"color": s(c)}}


def C(t, c):
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def MS(name):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": M}}, "Property": name}}


AGG_NAMES = {0: "Sum", 1: "Avg", 3: "Min", 4: "Max"}


def A(t, c, fn):
    return {"Aggregation": {"Expression": C(t, c), "Function": fn}}


def ref_of(field):
    if "Column" in field:
        x = field["Column"]
        return f'{x["Expression"]["SourceRef"]["Entity"]}.{x["Property"]}', x["Property"]
    if "Measure" in field:
        x = field["Measure"]
        return f'{x["Expression"]["SourceRef"]["Entity"]}.{x["Property"]}', x["Property"]
    x = field["Aggregation"]
    inner, prop = ref_of(x["Expression"])
    fn = AGG_NAMES[x["Function"]]
    return f"{fn}({inner})", f"{fn} of {prop}"


def P(field, display, active=False):
    q, native = ref_of(field)
    p = {"field": field, "queryRef": q, "nativeQueryRef": native, "displayName": display}
    if active:
        p["active"] = True
    return p


def query(roles, sort=None):
    qs = {"queryState": {r: {"projections": ps} for r, ps in roles.items()}}
    if sort:
        field, direction = sort
        qs["sortDefinition"] = {"sort": [{"field": field, "direction": direction}], "isDefaultSort": True}
    return qs


def container_objects(title=None, alt="", card=True, pad=8):
    vco = {
        "background": [{"properties": {"show": b(card), "color": solid("#FFFFFF"), "transparency": d(0)}}],
        "border": [{"properties": {"show": b(card), "color": solid(LINE), "radius": d(12), "width": d(1)}}],
        "title": [{"properties": {"show": b(bool(title)), "text": s(title or ""), "fontColor": solid(INK),
                                  "fontSize": d(12), "bold": b(False), "fontFamily": s("Segoe UI Semibold"),
                                  "alignment": s("left")}}],
        "padding": [{"properties": {"top": d(pad), "bottom": d(pad), "left": d(pad + 4), "right": d(pad + 4)}}],
        "general": [{"properties": {"altText": s(alt or title or "")}}],
    }
    return vco


class Page:
    def __init__(self, name, display):
        self.name, self.display, self.visuals, self.z = name, display, [], 1000

    def add(self, vname, vtype, pos, *, query_=None, objects=None, vco=None, filters=None, tab=True):
        x, y, w, h = pos
        self.z += 1000
        v = {"visualType": vtype, "drillFilterOtherVisuals": True}
        if query_:
            v["query"] = query_
        if objects:
            v["objects"] = objects
        v["visualContainerObjects"] = vco or container_objects()
        body = {"$schema": f"{SCHEMA}/report/definition/visualContainer/2.13.0/schema.json",
                "name": vname,
                "position": {"x": x, "y": y, "z": self.z, "width": w, "height": h,
                             "tabOrder": self.z if tab else -9999000},
                "visual": v}
        if filters:
            body["filterConfig"] = {"filters": filters}
        self.visuals.append(body)


AXES = {
    "categoryAxis": [{"properties": {"showAxisTitle": b(False), "fontSize": d(9)}}],
    "valueAxis": [{"properties": {"showAxisTitle": b(False), "fontSize": d(9)}}],
    "legend": [{"properties": {"show": b(True), "position": s("Top"), "showTitle": b(False), "fontSize": d(9)}}],
}


def axes(**over):
    o = json.loads(json.dumps(AXES))
    for k, v in over.items():
        if v is None:
            o.pop(k, None)
        else:
            o[k] = v
    return o


def series_colors(pairs):
    return [{"properties": {"fill": solid(c)}, "selector": {"metadata": f"{M}.{m}"}} for m, c in pairs]


def not_in_filter(name, table, column, values):
    return {
        "name": name, "field": C(table, column), "type": "Categorical",
        "filter": {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}],
                   "Where": [{"Condition": {"Not": {"Expression": {"In": {
                       "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": column}}],
                       "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values]}}}}}]},
    }


def gradient(measure, lo, hi, mid=None, mid_value=None):
    if mid:
        rule = {"linearGradient3": {
            "min": {"color": {"Literal": {"Value": f"'{lo}'"}}},
            "mid": {"color": {"Literal": {"Value": f"'{mid}'"}}, "value": {"Literal": {"Value": f"{mid_value}D"}}},
            "max": {"color": {"Literal": {"Value": f"'{hi}'"}}},
            "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}
    else:
        rule = {"linearGradient2": {
            "min": {"color": {"Literal": {"Value": f"'{lo}'"}}},
            "max": {"color": {"Literal": {"Value": f"'{hi}'"}}},
            "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}
    return {"solid": {"color": {"expr": {"FillRule": {"Input": MS(measure), "FillRule": rule}}}}}


def runs(*items):
    """items: (text, size_pt, color, bold) -> paragraph list; mỗi item là một đoạn."""
    return [{"textRuns": [{"value": t, "textStyle": {
        "fontFamily": "Segoe UI Semibold" if bold else "Segoe UI", "fontSize": f"{size}pt", "color": col}}]}
        for t, size, col, bold in items]


def textbox(page, vname, pos, paragraphs, *, bg=None, border=None, radius=12, alt=None, tab=True):
    vco = {
        "title": [{"properties": {"show": b(False)}}],
        "padding": [{"properties": {"top": d(4), "bottom": d(4), "left": d(6), "right": d(6)}}],
        "background": [{"properties": {"show": b(bool(bg)), **({"color": solid(bg), "transparency": d(0)} if bg else {})}}],
        "border": [{"properties": {"show": b(bool(border)), **(
            {"color": solid(border), "radius": d(radius), "width": d(1)} if border else {})}}],
        "general": [{"properties": {"altText": s(alt if alt is not None else " ".join(
            r["value"] for p in paragraphs for r in p["textRuns"])[:250])}}],
    }
    page.add(vname, "textbox", pos, objects={"general": [{"properties": {"paragraphs": paragraphs}}]},
             vco=vco, tab=tab)


def button(page, vname, pos, text, *, fill, color, link, target=None, size=10, align="center",
           curve=20, transparency=0, show_fill=True, tooltip=""):
    objects = {
        "text": [{"properties": {"show": b(True)}},
                 {"properties": {"text": s(text), "fontSize": d(size), "fontColor": solid(color), "bold": b(False),
                                 "fontFamily": s("Segoe UI Semibold"), "horizontalAlignment": s(align)},
                  "selector": {"id": "default"}}],
        "fill": [{"properties": {"show": b(show_fill)}},
                 {"properties": {"fillColor": solid(fill), "transparency": d(transparency)},
                  "selector": {"id": "default"}}],
        "outline": [{"properties": {"show": b(False), "lineColor": solid("#FFFFFF"), "weight": d(1)},
                     "selector": {"id": "default"}}],
        "shape": [{"properties": {"tileShape": s("roundedRectangle"), "rectangleRoundedCurve": lit(f"{curve}L")}}],
        "icon": [{"properties": {"show": b(False)}}],
    }
    link_props = {"show": b(True), "type": s(link), "tooltip": s(tooltip)}
    if target:
        link_props["navigationSection"] = s(target)
    vco = {
        "background": [{"properties": {"show": b(False)}}],
        "border": [{"properties": {"show": b(False)}}],
        "title": [{"properties": {"show": b(False)}}],
        "visualLink": [{"properties": link_props}],
        "padding": [{"properties": {"top": d(0), "bottom": d(0), "left": d(0), "right": d(0)}}],
        "general": [{"properties": {"altText": s(tooltip or text)}}],
    }
    page.add(vname, "actionButton", pos, objects=objects, vco=vco)


NAV = [("Home", "Trang chủ"), ("Overview", "Tổng quan"), ("SegmentDiscount", "Phân khúc & CK"),
       ("Geography", "Địa lý"), ("Customer", "Khách hàng")]


def header(page):
    textbox(page, "hdr_title", (18, 6, 290, 82),
            runs(("Xóm E-Com", 20, NAVY, True), ("Profit Intelligence", 20, "#B7791F", True)),
            alt="Xóm E-Com Profit Intelligence")
    textbox(page, "hdr_navbg", (318, 8, 808, 50), [{"textRuns": [{"value": " "}]}],
            bg="#FFFFFF", border="#DCE3EC", radius=25, alt="", tab=False)
    for i, (target, label) in enumerate(NAV):
        active = target == page.name
        button(page, f"hdr_nav{i}", (324 + i * 160, 13, 156, 40), label,
               fill=NAVY if active else "#FFFFFF", color="#FFFFFF" if active else NAVY,
               show_fill=active, link="PageNavigation", target=target,
               tooltip=f"Chuyển tới trang {label}")
    button(page, "hdr_reset", (1140, 8, 120, 50), "Xóa bộ lọc", fill="#FFFFFF", color=NAVY,
           link="ClearAllSlicers", curve=25, tooltip="Xóa tất cả bộ lọc trên trang")


def card(page, vname, pos, measure, label, units=0, precision=None):
    """units: 0 = tự động, 1 = không rút gọn, 1e6 = triệu (Power BI labelDisplayUnits)."""
    lbl = {"fontSize": d(22), "fontFamily": s("Segoe UI Semibold"), "color": solid(NAVY),
           "labelDisplayUnits": d(int(units))}
    if precision is not None:
        lbl["labelPrecision"] = lit(f"{precision}L")
    objects = {
        "labels": [{"properties": lbl}],
        "categoryLabels": [{"properties": {"show": b(True), "fontSize": d(9), "color": solid(MUTED),
                                           "fontFamily": s("Segoe UI")}}],
    }
    page.add(vname, "card", pos, query_=query({"Values": [P(MS(measure), label)]}), objects=objects,
             vco=container_objects(None, f"Thẻ KPI: {label}", pad=2))


def slicer(page, vname, pos, field, label):
    objects = {
        "data": [{"properties": {"mode": s("Dropdown")}}],
        "header": [{"properties": {"show": b(True), "text": s(label), "fontColor": solid("#3D4A5C"),
                                   "textSize": d(10), "fontFamily": s("Segoe UI Semibold")}}],
    }
    page.add(vname, "slicer", pos, query_=query({"Values": [P(field, label, True)]}), objects=objects,
             vco=container_objects(None, f"Bộ lọc theo {label}"))


def slicer_column(page, items, y0=98):
    for i, (field, label) in enumerate(items):
        slicer(page, f"slc_{i}", (1092, y0 + i * 85, 164, 80), field, label)


def recommendation(page, text, pos=(24, 640, 1232, 68)):
    textbox(page, "rec_box", pos,
            [{"textRuns": [
                {"value": "KHUYẾN NGHỊ  ", "textStyle": {"fontFamily": "Segoe UI Semibold", "fontSize": "10pt",
                                                         "color": "#B7791F"}},
                {"value": text, "textStyle": {"fontFamily": "Segoe UI", "fontSize": "10pt", "color": INK}}]}],
            bg="#FFF8EC", border=GOLD, alt="Khuyến nghị: " + text)


# ---------------------------------------------------------------- số liệu cho khuyến nghị
def facts():
    k = DF[KPI].set_index("year")
    # Làm tròn đầu vào giống báo cáo (key_numbers.json lưu biên 4 chữ số; tác động tính trên số đã làm tròn)
    m = {y: round(k.loc[y, "profit"] / k.loc[y, "revenue"], 4) for y in (PY, LY)}
    cap = DF["ml_whatif_discount_cap"].set_index("cap")
    sp = DF[SP].groupby("segment")[["revenue", "profit"]].sum()
    seg_m = (sp["profit"] / sp["revenue"]).sort_values()
    g = DF[GEO].groupby(["year", "market"])[["revenue", "profit"]].sum()
    eu_growth = g.loc[(LY, "Europe"), "revenue"] / g.loc[(PY, "Europe"), "revenue"] - 1
    # biên thị trường: làm tròn một lần (0,18449 -> 18,4%), khớp Bảng 4.8 của báo cáo
    eu_m = g.loc[(LY, "Europe"), "profit"] / g.loc[(LY, "Europe"), "revenue"]
    ap_m = g.loc[(LY, "Asia Pacific"), "profit"] / g.loc[(LY, "Asia Pacific"), "revenue"]
    cp = DF["ml_cluster_profile"].set_index("cluster_name")
    loyal = cp.loc["Trung thành, giá trị cao"]
    one_time = (~DF[CV]["is_repeat_customer"]).mean()
    return {
        "m_py": vn_pct(m[PY]), "m_ly": vn_pct(m[LY]),
        "restore": vn_num((round(m[PY], 3) - round(m[LY], 3)) * round(k.loc[LY, "revenue"], -4) / 1000),
        "cap30": vn_num(cap.loc[0.3, "uplift"] / 1000), "cap30_pct": vn_pct(cap.loc[0.3, "uplift_pct"]),
        "low_seg": seg_m.index[0], "low_seg_m": vn_pct(seg_m.iloc[0]),
        "eu_growth": vn_pct(eu_growth), "eu_m": vn_pct(eu_m), "ap_m": vn_pct(ap_m),
        "loyal_share": vn_pct(loyal["share_profit"], 0), "one_time": vn_pct(one_time),
        "hv_n": vn_num(cp.loc["Mua một lần, giá trị cao", "customers"]),
    }


# ---------------------------------------------------------------- các trang
def page_home(F):
    p = Page("Home", "Trang chủ")
    header(p)
    textbox(p, "home_hero", (24, 98, 600, 610), [{"textRuns": [{"value": " "}]}], bg=NAVY, border=NAVY,
            radius=24, alt="", tab=False)
    textbox(p, "home_herotext", (52, 118, 548, 236), runs(
        ("BÁO CÁO PHÂN TÍCH LỢI NHUẬN XÓM E-COM", 10, GOLD, True),
        ("Doanh thu tăng, biên giảm:", 22, "#FFFFFF", True),
        ("vì sao và làm gì?", 22, "#FFFFFF", True),
        (f"Kho dữ liệu Medallion trên DuckDB, giai đoạn {YEARS[0]}–{LY}. Bốn trang dashboard theo bốn pain point: "
         "tổng quan biên lợi nhuận, phân khúc và chiết khấu, địa lý, cụm khách hàng (K-Means). "
         "Mỗi trang kết thúc bằng một khuyến nghị hành động.", 10, "#DCE3EC", False)))
    p.add("home_cover", "image", (64, 370, 520, 320), objects={
        "general": [{"properties": {"imageUrl": {"expr": {"ResourcePackageItem": {
            "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": "cover.svg"}}}}}],
        "imageScaling": [{"properties": {"imageScalingType": s("Fit")}}]},
        vco={"background": [{"properties": {"show": b(False)}}], "border": [{"properties": {"show": b(False)}}],
             "title": [{"properties": {"show": b(False)}}], "general": [{"properties": {"altText": s("")}}]},
        tab=False)
    textbox(p, "home_sec1", (648, 98, 608, 26), runs(("BỐN TRANG PHÂN TÍCH", 10, MUTED, True)))
    for i, (target, label) in enumerate(NAV[1:]):
        x, y = (648 if i % 2 == 0 else 956), 128 + (i // 2) * 74
        button(p, f"home_t{i}", (x, y, 300, 66), f"0{i + 1}   {label}", fill="#FFFFFF", color=INK,
               link="PageNavigation", target=target, size=12, align="left", curve=18, transparency=25,
               tooltip=f"Chuyển tới trang {label}")
    textbox(p, "home_sec2", (648, 286, 608, 26), runs(("KHUYẾN NGHỊ CHÍNH", 10, MUTED, True)))
    recs = [
        ("Rà soát chi phí vận hành 2023",
         f"Biên giảm từ {F['m_py']} ({PY}) xuống {F['m_ly']} ({LY}). Khôi phục biên ≈ {F['restore']} nghìn USD/năm."),
        ("Trần chiết khấu 30%",
         f"Mô hình what-if: +{F['cap30']} nghìn USD lợi nhuận ({F['cap30_pct']}). "
         f"Đánh giá {F['low_seg']} theo biên ({F['low_seg_m']})."),
        ("Ưu tiên Europe, siết giảm giá ở Asia Pacific",
         f"Europe tăng {F['eu_growth']}, biên {F['eu_m']}; Asia Pacific biên {F['ap_m']} ({LY})."),
        ("Giữ chân cụm trung thành",
         f"Cụm trung thành tạo {F['loyal_share']} lợi nhuận; {F['one_time']} khách chỉ mua một lần. "
         f"Kích hoạt lại {F['hv_n']} khách 'Mua một lần, giá trị cao'."),
    ]
    for i, (head, body) in enumerate(recs):
        textbox(p, f"home_rec{i}", (648, 316 + i * 98, 608, 90),
                runs((head, 12, NAVY, True), (body, 10, "#3D4A5C", False)), bg="#FFFFFF", border=LINE)
    return p


def page_overview(F):
    p = Page("Overview", "Tổng quan")
    header(p)
    kpis = [("Revenue", "Doanh thu (USD)", 1e6, 2), ("Profit", "Lợi nhuận (USD)", 1e6, 2),
            ("Profit Margin", "Biên lợi nhuận", 0, None), ("Orders", "Số đơn hàng", 1, None),
            ("AOV", "Giá trị đơn trung bình (USD)", 1, None), ("Repeat Rate", "Tỷ lệ khách quay lại", 0, None)]
    for i, (m, label, units, prec) in enumerate(kpis):
        card(p, f"kpi_{i}", (24 + round(i * 206.8), 98, 198, 92), m, label, units, prec)
    year = C("DimYear", "year")
    p.add("rev_margin_year", "lineClusteredColumnComboChart", (24, 198, 520, 240),
          query_=query({"Category": [P(year, "Năm", True)],
                        "Y": [P(MS("Revenue"), "Doanh thu")],
                        "Y2": [P(MS("Profit Margin"), "Biên lợi nhuận")]}, sort=(year, "Ascending")),
          objects=axes(categoryAxis=[{"properties": {"showAxisTitle": b(False), "fontSize": d(9),
                                                     "axisType": s("Categorical")}}],
                       dataPoint=series_colors([("Revenue", NAVY), ("Profit Margin", GOLD)]),
                       labels=[{"properties": {"show": b(True), "fontSize": d(8)}}]),
          vco=container_objects("Doanh thu (cột) và biên lợi nhuận (đường) theo năm"))
    p.add("margin_market_year", "lineChart", (552, 198, 532, 240),
          query_=query({"Category": [P(year, "Năm", True)], "Series": [P(C("DimMarket", "market"), "Thị trường")],
                        "Y": [P(MS("Profit Margin"), "Biên lợi nhuận")]}, sort=(year, "Ascending")),
          objects=axes(categoryAxis=[{"properties": {"showAxisTitle": b(False), "fontSize": d(9),
                                                     "axisType": s("Categorical")}}]),
          vco=container_objects(f"Biên lợi nhuận theo thị trường: {LY} giảm ở mọi nơi"),
          filters=[not_in_filter("f_unknown", "DimMarket", "market", ["Unknown"])])
    month = C(FC, "month_start")
    p.add("profit_month", "lineChart", (24, 446, 1060, 186),
          query_=query({"Category": [P(month, "Tháng", True)],
                        "Y": [P(MS("Actual Profit"), "Lợi nhuận thực tế"),
                              P(MS("Forecast Profit"), "Dự báo (ETS)"),
                              P(MS("Anomaly Profit"), "Tháng bất thường")]}, sort=(month, "Ascending")),
          objects=axes(dataPoint=series_colors([("Actual Profit", NAVY), ("Forecast Profit", GOLD),
                                                ("Anomaly Profit", RED)]),
                       lineStyles=[
                           {"properties": {"lineStyle": s("dashed")}, "selector": {"metadata": f"{M}.Forecast Profit"}},
                           {"properties": {"showMarker": b(True), "markerSize": d(7), "strokeWidth": d(0)},
                            "selector": {"metadata": f"{M}.Anomaly Profit"}}]),
          vco=container_objects(f"Lợi nhuận theo tháng: thực tế, dự báo {LY + 1} và tháng bất thường"))
    slicer_column(p, [(year, "Năm"), (C("DimMarket", "market"), "Thị trường"),
                      (C("DimSegment", "segment"), "Phân khúc")], y0=198)
    textbox(p, "slc_note", (1092, 453, 164, 179), runs(
        ("Ghi chú", 10, NAVY, True),
        ("Tỷ lệ khách quay lại chỉ lọc theo năm. Biểu đồ theo tháng (mô hình ETS, ml.forecast_monthly) "
         "luôn hiện đủ chuỗi, không lọc theo bộ lọc.",
         9, MUTED, False)), bg="#FFFFFF", border=LINE)
    recommendation(p, f"Biên lợi nhuận {LY} giảm ở mọi thị trường và phân khúc ({F['m_py']} → {F['m_ly']}), "
                      f"kể cả dòng không giảm giá. Rà soát chi phí vận hành, logistics {LY}; "
                      f"khôi phục biên về mức {PY} tương ứng khoảng {F['restore']} nghìn USD/năm.")
    return p


def page_segment(F):
    p = Page("SegmentDiscount", "Phân khúc & Chiết khấu")
    header(p)
    year, seg = C("DimYear", "year"), C("DimSegment", "segment")
    p.add("pl_matrix", "pivotTable", (24, 98, 520, 300),
          query_=query({"Rows": [P(seg, "Phân khúc", True)], "Columns": [P(year, "Năm", True)],
                        "Values": [P(MS("Profit"), "Lợi nhuận"), P(MS("Profit Margin"), "Biên")]}),
          objects={"columnHeaders": [{"properties": {"fontColor": solid("#FFFFFF"), "backColor": solid(NAVY),
                                                     "fontSize": d(9)}}],
                   "rowHeaders": [{"properties": {"fontSize": d(9)}}],
                   "values": [{"properties": {"fontSize": d(9)}},
                              {"properties": {"fontColor": gradient("Profit Margin", RED, GREEN, GOLD, 0.15)},
                               "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                            "metadata": f"{M}.Profit Margin"}}]},
          vco=container_objects("Lợi nhuận (USD) và biên theo phân khúc × năm"))
    band = C(DA, "discount_band")
    p.add("disc_margin", "clusteredColumnChart", (552, 98, 532, 300),
          query_=query({"Category": [P(band, "Mức chiết khấu", True)],
                        "Y": [P(MS("Disc Margin"), "Biên lợi nhuận")]}, sort=(band, "Ascending")),
          objects=axes(legend=[{"properties": {"show": b(False)}}],
                       dataPoint=[{"properties": {"fill": gradient("Disc Margin", RED, NAVY, GOLD, 0)},
                                   "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}],
                       labels=[{"properties": {"show": b(True), "fontSize": d(9)}}],
                       y1AxisReferenceLine=[{"properties": {
                           "show": b(True), "displayName": s("Hòa vốn"), "value": d(0), "lineColor": solid(RED),
                           "transparency": d(0), "style": s("dashed"), "dataLabelShow": b(True),
                           "dataLabelText": s("Name")}, "selector": {"id": "1"}}]),
          vco=container_objects("Biên lợi nhuận theo mức chiết khấu (đường đỏ = hòa vốn)"))
    capl = C("ml_whatif_discount_cap", "cap_label")
    p.add("cap_scenario", "lineClusteredColumnComboChart", (24, 406, 520, 226),
          query_=query({"Category": [P(capl, "Kịch bản", True)],
                        "Y": [P(MS("Cap Profit Baseline"), "Lợi nhuận hiện tại (dự đoán)"),
                              P(MS("Cap Profit Capped"), "Lợi nhuận khi áp trần")],
                        "Y2": [P(MS("Cap Uplift %"), "Mức tăng (%)")]}, sort=(capl, "Ascending")),
          objects=axes(dataPoint=series_colors([("Cap Profit Baseline", "#8FA6BF"), ("Cap Profit Capped", NAVY),
                                                ("Cap Uplift %", GOLD)])),
          vco=container_objects(f"Kịch bản trần chiết khấu (mô hình what-if, dữ liệu {LY})"))
    lvl = C("ml_whatif_discount", "discount_level")
    p.add("whatif_curve", "lineChart", (552, 406, 532, 226),
          query_=query({"Category": [P(lvl, "Mức chiết khấu", True)],
                        "Series": [P(C("DimCategory", "category"), "Ngành hàng")],
                        "Y": [P(MS("WhatIf Margin"), "Biên dự đoán")]}, sort=(lvl, "Ascending")),
          objects=axes(categoryAxis=[{"properties": {"showAxisTitle": b(False), "fontSize": d(9),
                                                     "axisType": s("Categorical")}}],
                       y1AxisReferenceLine=[{"properties": {
                           "show": b(True), "displayName": s("Hòa vốn"), "value": d(0), "lineColor": solid(RED),
                           "style": s("dashed")}, "selector": {"id": "1"}}]),
          vco=container_objects("Biên dự đoán theo mức chiết khấu và ngành hàng (what-if)"),
          filters=[not_in_filter("f_unknown", "DimCategory", "category", ["Unknown"])])
    slicer_column(p, [(year, "Năm"), (C("DimMarket", "market"), "Thị trường"), (seg, "Phân khúc"),
                      (C("DimCategory", "category"), "Ngành hàng")])
    textbox(p, "slc_note", (1092, 438, 164, 194), runs(
        ("Ghi chú", 10, NAVY, True),
        ("Kịch bản trần chiết khấu là kết quả cố định của mô hình (ml.whatif_discount_cap), "
         "không lọc theo bộ lọc bên trên.", 9, MUTED, False)), bg="#FFFFFF", border=LINE)
    recommendation(p, f"Đặt trần chiết khấu 30%; chương trình giảm trên 30% phải được Tài chính duyệt "
                      f"(mô hình ước tính +{F['cap30']} nghìn USD lợi nhuận, +{F['cap30_pct']}). "
                      f"Đánh giá hợp đồng {F['low_seg']} theo biên lợi nhuận (biên thấp nhất: {F['low_seg_m']}).")
    return p


def page_geo(F):
    p = Page("Geography", "Địa lý")
    header(p)
    country = C(GEO, "country")
    # "Bản đồ điểm": scatter kinh độ × vĩ độ, không cần đăng nhập hay bật visual Map/Azure Maps
    def axis(lo, hi):
        return [{"properties": {"showAxisTitle": b(False), "fontSize": d(8), "start": d(lo), "end": d(hi),
                                "gridlineShow": b(True), "labelColor": solid("#A3B4C8")}}]
    p.add("geo_map", "scatterChart", (24, 98, 520, 300),
          query_=query({"Category": [P(country, "Quốc gia", True)],
                        "X": [P(A(GEO, "country_longitude", 1), "Kinh độ")],
                        "Y": [P(A(GEO, "country_latitude", 1), "Vĩ độ")],
                        "Size": [P(MS("Geo Revenue"), "Doanh thu")],
                        "Tooltips": [P(MS("Geo Margin"), "Biên lợi nhuận"), P(MS("Geo Profit"), "Lợi nhuận"),
                                     P(MS("Geo Growth"), "Tăng trưởng doanh thu")]}),
          objects={"categoryAxis": axis(-170, 180), "valueAxis": axis(-60, 80),
                   "legend": [{"properties": {"show": b(False)}}],
                   "categoryLabels": [{"properties": {"show": b(True), "fontSize": d(7), "color": solid(MUTED)}}],
                   "bubbles": [{"properties": {"bubbleSize": d(10)}}],
                   "dataPoint": [{"properties": {"fill": gradient("Geo Margin", RED, GREEN, GOLD, 0.1)},
                                  "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}]}}]},
          vco=container_objects("Bản đồ điểm theo kinh độ × vĩ độ: kích thước = doanh thu, màu = biên (đỏ thấp → xanh cao)"))
    market = C("DimMarket", "market")
    no_unknown = [not_in_filter("f_unknown", "DimMarket", "market", ["Unknown"])]
    p.add("margin_py_ly", "clusteredColumnChart", (24, 406, 520, 226),
          query_=query({"Category": [P(market, "Thị trường", True)],
                        "Y": [P(MS(f"Geo Margin {PY}"), f"Biên {PY}"), P(MS(f"Geo Margin {LY}"), f"Biên {LY}")]}),
          objects=axes(dataPoint=series_colors([(f"Geo Margin {PY}", "#8FA6BF"), (f"Geo Margin {LY}", NAVY)]),
                       labels=[{"properties": {"show": b(True), "fontSize": d(8)}}]),
          vco=container_objects(f"Biên lợi nhuận {PY} so với {LY} theo thị trường"), filters=no_unknown)
    p.add("growth_ly", "clusteredColumnChart", (552, 406, 532, 226),
          query_=query({"Category": [P(market, "Thị trường", True)],
                        "Y": [P(MS(f"Geo Growth {LY}"), f"Tăng trưởng doanh thu {LY}")]},
                       sort=(MS(f"Geo Growth {LY}"), "Descending")),
          objects=axes(legend=[{"properties": {"show": b(False)}}], dataPoint=[{"properties": {"fill": solid(GOLD)}}],
                       labels=[{"properties": {"show": b(True), "fontSize": d(9)}}]),
          vco=container_objects(f"Tăng trưởng doanh thu {LY} so với {PY} theo thị trường"), filters=no_unknown)
    p.add("country_table", "tableEx", (552, 98, 532, 300),
          query_=query({"Values": [P(country, "Quốc gia"), P(C(GEO, "market"), "Thị trường"),
                                   P(MS("Geo Revenue"), "Doanh thu"), P(MS("Geo Profit"), "Lợi nhuận"),
                                   P(MS("Geo Margin"), "Biên"), P(MS("Geo Growth"), "Tăng trưởng DT")]},
                       sort=(MS("Geo Revenue"), "Descending")),
          objects={"columnHeaders": [{"properties": {"fontColor": solid("#FFFFFF"), "backColor": solid(NAVY),
                                                     "fontSize": d(10)}}],
                   "values": [{"properties": {"fontSize": d(10)}}]},
          vco=container_objects("Chi tiết theo quốc gia (sắp theo doanh thu)"))
    slicer_column(p, [(C("DimYear", "year"), "Năm"), (market, "Thị trường"),
                      (C(GEO, "market_group"), "Nhóm thị trường")])
    textbox(p, "slc_note", (1092, 353, 164, 279), runs(
        ("Ghi chú", 10, NAVY, True),
        ("Bản đồ điểm vẽ bằng tọa độ quốc gia (dim_geography), trục ngang là kinh độ, trục dọc là vĩ độ; "
         "rê chuột để xem tên nước. Biên hai năm và tăng trưởng "
         f"luôn so sánh {PY}–{LY}, không đổi theo bộ lọc năm.", 9, MUTED, False)), bg="#FFFFFF", border=LINE)
    recommendation(p, f"Ưu tiên Europe khi mở rộng (doanh thu {LY} tăng {F['eu_growth']}, biên {F['eu_m']}). "
                      f"Siết giảm giá ở Asia Pacific (biên {LY} chỉ {F['ap_m']}) và theo dõi LATAM đang chậm lại.")
    return p


def page_customer(F):
    p = Page("Customer", "Khách hàng")
    header(p)
    for i, (k, name) in enumerate(CLUSTERS):
        card(p, f"cluster_{k}", (24 + i * 267, 98, 259, 92), f"Customers C{k}", f"Cụm {k}: {name}")
    cname = C(CV, "cluster_name")
    p.add("rfm_scatter", "scatterChart", (24, 198, 500, 250),
          query_=query({"Category": [P(C(CV, "customer_key"), "Khách hàng", True)],
                        "Series": [P(cname, "Cụm")],
                        "X": [P(A(CV, "recency_days", 1), "Recency (ngày)")],
                        "Y": [P(A(CV, "monetary", 0), "Monetary (USD)")]}),
          objects=axes(categoryAxis=[{"properties": {"showAxisTitle": b(True), "fontSize": d(9)}}],
                       valueAxis=[{"properties": {"showAxisTitle": b(True), "fontSize": d(9)}}]),
          vco=container_objects("Recency × Monetary của từng khách, tô màu theo cụm K-Means"))
    p.add("cluster_table", "tableEx", (532, 198, 552, 250),
          query_=query({"Values": [P(cname, "Cụm"), P(MS("Customers"), "Số khách"),
                                   P(MS("Avg Recency"), "Recency TB"), P(MS("Avg Frequency"), "Tần suất TB"),
                                   P(MS("Avg Monetary"), "Chi tiêu TB"), P(MS("Customer Margin"), "Biên"),
                                   P(MS("Customer Repeat Rate"), "Quay lại"), P(MS("Profit Share"), "Tỷ trọng LN")]},
                       sort=(MS("Customers"), "Descending")),
          objects={"columnHeaders": [{"properties": {"fontColor": solid("#FFFFFF"), "backColor": solid(NAVY),
                                                     "fontSize": d(9), "wordWrap": b(True)}}],
                   "values": [{"properties": {"fontSize": d(9), "wordWrap": b(True)}}]},
          vco=container_objects("Hồ sơ cụm khách hàng"))
    coh = "mart_customer_cohort"
    p.add("cohort", "pivotTable", (24, 456, 520, 176),
          query_=query({"Rows": [P(C(coh, "cohort_year"), "Năm mua đầu", True)],
                        "Columns": [P(C(coh, "years_since_first"), "Số năm sau lần mua đầu", True)],
                        "Values": [P(MS("Retention"), "Tỷ lệ còn hoạt động")]}),
          objects={"columnHeaders": [{"properties": {"fontColor": solid("#FFFFFF"), "backColor": solid(NAVY),
                                                     "fontSize": d(10)}}],
                   "values": [{"properties": {"fontSize": d(10)}},
                              {"properties": {"backColor": gradient("Retention", "#EEF2F7", "#8FA6BF")},
                               "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}],
                                            "metadata": f"{M}.Retention"}}],
                   "subTotals": [{"properties": {"rowSubtotals": b(False), "columnSubtotals": b(False)}}]},
          vco=container_objects("Cohort: tỷ lệ khách còn mua theo năm mua đầu"))
    rfm = C(CV, "rfm_segment")
    p.add("rfm_bar", "clusteredColumnChart", (552, 456, 532, 176),
          query_=query({"Category": [P(rfm, "Nhóm RFM", True)], "Y": [P(MS("Customers"), "Số khách")]},
                       sort=(MS("Customers"), "Descending")),
          objects=axes(legend=[{"properties": {"show": b(False)}}], dataPoint=[{"properties": {"fill": solid(NAVY)}}],
                       labels=[{"properties": {"show": b(True), "fontSize": d(9)}}]),
          vco=container_objects("Số khách theo nhóm RFM"))
    slicer_column(p, [(C("DimSegment", "segment"), "Phân khúc"), (cname, "Cụm khách hàng"),
                      (C(CV, "age_group"), "Nhóm tuổi"), (C(CV, "income_band"), "Mức thu nhập")])
    textbox(p, "slc_note", (1092, 438, 164, 194), runs(
        ("Ghi chú", 10, NAVY, True),
        ("Cụm từ K-Means (k = 4) trên RFM chuẩn hóa. Ma trận cohort không chịu tác động của bộ lọc.",
         9, MUTED, False)), bg="#FFFFFF", border=LINE)
    recommendation(p, f"Chương trình thân thiết cho cụm 'Trung thành, giá trị cao' (tạo {F['loyal_share']} lợi nhuận). "
                      f"Kích hoạt lại {F['hv_n']} khách 'Mua một lần, giá trị cao'; ngừng mã giảm giá cho "
                      f"cụm 'Săn giảm giá, gây lỗ'.")
    return p


def page_json(p):
    bg = {"image": {"name": s("bg.png"), "url": {"expr": {"ResourcePackageItem": {
        "PackageName": "RegisteredResources", "PackageType": 1, "ItemName": "bg.png"}}},
        "scaling": s("Fill")}}
    return {"$schema": f"{SCHEMA}/report/definition/page/2.1.0/schema.json", "name": p.name,
            "displayName": p.display, "displayOption": "FitToPage", "height": 720, "width": 1280,
            "objects": {"background": [{"properties": {**bg, "transparency": d(0)}}],
                        "outspace": [{"properties": {"color": solid("#EAEAEA")}}]}}


def dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def build_report():
    if REPORT.exists():
        shutil.rmtree(REPORT)
    F = facts()
    pages = [page_home(F), page_overview(F), page_segment(F), page_geo(F), page_customer(F)]
    dump(REPORT / "definition.pbir", {
        "$schema": f"{SCHEMA}/report/definitionProperties/2.0.0/schema.json", "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    dump(DEF / "version.json", {"$schema": f"{SCHEMA}/report/definition/versionMetadata/1.0.0/schema.json",
                                "version": "2.0.0"})
    imported = {"visual": "2.4.0", "report": "3.0.0", "page": "2.3.0"}
    dump(DEF / "report.json", {
        "$schema": f"{SCHEMA}/report/definition/report/3.3.0/schema.json",
        "themeCollection": {
            "baseTheme": {"name": "CY26SU10", "reportVersionAtImport": imported, "type": "SharedResources"},
            "customTheme": {"name": "XomEcomTheme.json", "reportVersionAtImport": imported,
                            "type": "RegisteredResources"}},
        "objects": {"outspacePane": [{"properties": {"expanded": b(False)}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources",
             "items": [{"name": "CY26SU10", "path": "BaseThemes/CY26SU10.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": "bg.png", "path": "bg.png", "type": "Image"},
                       {"name": "cover.svg", "path": "cover.svg", "type": "Image"},
                       {"name": "XomEcomTheme.json", "path": "XomEcomTheme.json", "type": "CustomTheme"}]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                     "defaultDrillFilterOtherVisuals": True, "useEnhancedTooltips": False}})
    dump(DEF / "pages" / "pages.json", {
        "$schema": f"{SCHEMA}/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": "Home"})
    for p in pages:
        dump(DEF / "pages" / p.name / "page.json", page_json(p))
        for v in p.visuals:
            dump(DEF / "pages" / p.name / "visuals" / v["name"] / "visual.json", v)
    reg = REPORT / "StaticResources" / "RegisteredResources"
    base = REPORT / "StaticResources" / "SharedResources" / "BaseThemes"
    reg.mkdir(parents=True)
    base.mkdir(parents=True)
    for f in ("bg.png", "cover.svg", "XomEcomTheme.json"):
        shutil.copy(ASSETS / f, reg / f)
    shutil.copy(ASSETS / "CY26SU10.json", base / "CY26SU10.json")
    return pages


def main():
    OUT.mkdir(exist_ok=True)
    build_model()
    pages = build_report()
    dump(OUT / f"{NAME}.pbip", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    (OUT / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")
    n = sum(len(p.visuals) for p in pages)
    print(f"Done: {OUT / (NAME + '.pbip')} | {len(pages)} trang, {n} visual, "
          f"{len(TABLES) + 5} bảng, {len(MEASURES)} measure, {len(RELATIONSHIPS)} quan hệ")


if __name__ == "__main__":
    main()
