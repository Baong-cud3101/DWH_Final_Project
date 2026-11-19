"""Chạy toàn bộ pipeline từ CSV đến báo cáo bằng một lệnh.

    python scripts/run_all.py            # toàn bộ
    python scripts/run_all.py --no-report

Thứ tự: nạp Bronze -> dbt build (Silver, Gold, mart, ml_features + toàn bộ test)
        -> profiling -> ML (K-Means, hồi quy + what-if, chuỗi thời gian) -> phân tích SQL
        -> biểu đồ -> xuất CSV cho Power BI -> đối chiếu -> dbt docs -> báo cáo Word.
Dừng ngay khi một bước lỗi (tương tự orchestrator.py của repo tham khảo).
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable

STEPS = [
    ("Nạp Bronze", ["00_load_bronze.py"]),
    ("dbt build (Silver, Gold, mart, ml + test)", ["run_dbt.py", "build"]),
    ("Profiling chất lượng", ["01_profiling.py"]),
    ("ML: K-Means RFM", ["03_ml_kmeans.py"]),
    ("ML: hồi quy biên + what-if", ["04_ml_margin_whatif.py"]),
    ("ML: phân lớp khách quay lại", ["04b_ml_classification.py"]),
    ("ML: chuỗi thời gian + bất thường", ["05_ml_timeseries.py"]),
    ("Phân tích SQL (giỏ hàng, cohort, sắp xếp)", ["06_analysis_sql.py"]),
    ("Biểu đồ và bảng mô tả", ["07_charts.py"]),
    ("Xuất CSV cho Power BI", ["08_export_marts.py"]),
    ("Sinh dashboard Power BI (PBIP)", ["11_build_powerbi.py"]),
    ("Đối chiếu số liệu", ["09_checks.py"]),
    ("Xuất bản mô hình vào kho (ml.model_artifacts)", ["14_publish_models.py"]),
    ("Schema app + snapshot cho Streamlit", ["12_build_app_data.py", "--snapshot"]),
    ("dbt docs generate (lineage)", ["run_dbt.py", "docs", "generate"]),
    ("Dựng báo cáo Word", ["10_build_report.py"]),
]


def main() -> None:
    skip_report = "--no-report" in sys.argv
    run_id = datetime.now().strftime("run_%Y%m%dT%H%M%S")
    print(f"[run_all] {run_id}")
    t_all = time.time()
    for i, (name, args) in enumerate(STEPS, 1):
        if skip_report and args[0] == "10_build_report.py":
            continue
        print(f"\n[run_all] Bước {i}/{len(STEPS)}: {name}")
        t0 = time.time()
        res = subprocess.run([PY, str(HERE / args[0]), *args[1:]], cwd=HERE.parent)
        if res.returncode != 0:
            print(f"[run_all] LỖI ở bước '{name}' (mã {res.returncode}). Dừng pipeline.")
            sys.exit(res.returncode)
        print(f"[run_all] Xong '{name}' trong {time.time() - t0:.1f}s")
    print(f"\n[run_all] Hoàn tất {run_id} trong {time.time() - t_all:.1f}s")


if __name__ == "__main__":
    main()
