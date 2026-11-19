"""Duong dan va ket noi dung chung cho moi script."""

import json
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
# DUCKDB_PATH là đường dẫn file .duckdb, hoặc "md:<tên_db>" để chạy trên MotherDuck
# (token lấy từ biến môi trường MOTHERDUCK_TOKEN)
DB_URI = str(os.getenv("DUCKDB_PATH", ROOT / "warehouse" / "xomecom.duckdb"))
IS_MOTHERDUCK = DB_URI.startswith("md:")
DB_PATH = Path(DB_URI) if not IS_MOTHERDUCK else ROOT / "warehouse" / "_motherduck"
TABLES_DIR = ROOT / "results" / "tables"
FIG_DIR = ROOT / "results" / "figures"
EXPORT_DIR = ROOT / "exports" / "powerbi"
MODEL_DIR = ROOT / "models"
KEY_NUMBERS = TABLES_DIR / "key_numbers.json"

for d in (TABLES_DIR, FIG_DIR, EXPORT_DIR, MODEL_DIR, DB_PATH.parent):
    d.mkdir(parents=True, exist_ok=True)


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    if IS_MOTHERDUCK:
        db = DB_URI[3:]
        con = duckdb.connect("md:")
        con.execute(f"CREATE DATABASE IF NOT EXISTS {db}")
        con.execute(f"USE {db}")
        return con
    return duckdb.connect(DB_URI, read_only=read_only)


def register_model(con, name: str, version: str, algorithm: str, params: dict,
                   metrics: dict, artifact: str) -> None:
    """Lưu thông tin mô hình (phiên bản, tham số, chỉ số) vào ml.model_registry."""
    con.execute("CREATE SCHEMA IF NOT EXISTS ml")
    con.execute(
        """CREATE TABLE IF NOT EXISTS ml.model_registry (
               model_name VARCHAR, model_version VARCHAR, algorithm VARCHAR,
               trained_at TIMESTAMP, params JSON, metrics JSON, artifact_path VARCHAR)"""
    )
    con.execute(
        "DELETE FROM ml.model_registry WHERE model_name = ? AND model_version = ?",
        [name, version],
    )
    con.execute(
        "INSERT INTO ml.model_registry VALUES (?, ?, ?, current_timestamp, ?, ?, ?)",
        [name, version, algorithm, json.dumps(params, default=str),
         json.dumps(metrics, default=float), artifact],
    )


def update_key_numbers(section: str, values: dict) -> None:
    """Ghi so lieu dung trong bao cao vao mot file JSON duy nhat."""
    data = {}
    if KEY_NUMBERS.exists():
        data = json.loads(KEY_NUMBERS.read_text(encoding="utf-8"))
    data[section] = values
    KEY_NUMBERS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=float), encoding="utf-8"
    )
