"""Đưa mô hình dùng cho dự đoán trực tiếp vào kho: bảng ml.model_artifacts (BLOB joblib).

Ứng dụng Streamlit đọc mô hình từ bảng này nên không cần file .joblib trên GitHub.
Phiên bản scikit-learn được ghi kèm; ứng dụng phải dùng đúng phiên bản đó (xem app/requirements.txt).
"""

import sklearn

from common import MODEL_DIR, connect

PUBLISH = {
    "margin_hgb_full_v1": "Biên lợi nhuận từng dòng (HistGradientBoosting, học 2020-2023, có đặc trưng year)",
    "repeat_tree_bundle_v1": "Khách quay lại trong 365 ngày (cây quyết định + OrdinalEncoder)",
}

con = connect()
con.execute("CREATE SCHEMA IF NOT EXISTS ml")
con.execute("""CREATE OR REPLACE TABLE ml.model_artifacts (
                   model_version VARCHAR, description VARCHAR, sklearn_version VARCHAR,
                   size_bytes BIGINT, published_at TIMESTAMP, artifact BLOB)""")
for ver, desc in PUBLISH.items():
    blob = (MODEL_DIR / f"{ver}.joblib").read_bytes()
    con.execute("INSERT INTO ml.model_artifacts VALUES (?, ?, ?, ?, current_timestamp, ?)",
                [ver, desc, sklearn.__version__, len(blob), blob])
    print(f"[models] {ver:<24} {len(blob) / 1024:>8.1f} KB  sklearn {sklearn.__version__}")
con.close()
