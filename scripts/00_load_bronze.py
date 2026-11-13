"""Nap 4 file CSV vao schema bronze cua DuckDB, giu nguyen ban (moi cot dang VARCHAR).

Bronze khong bien doi du lieu; chi them 2 cot metadata de truy vet:
_ingested_at (thoi diem nap) va _source_file (ten file nguon).
Ep kieu va lam sach duoc thuc hien o Silver bang dbt.
"""

from pathlib import Path

from common import RAW_DIR, connect

TABLES = ["customer", "ecom_sales", "product", "region"]


def main() -> None:
    con = connect()
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    for table in TABLES:
        path = Path(RAW_DIR) / f"{table}.csv"
        con.execute(
            f"""
            CREATE OR REPLACE TABLE bronze.{table} AS
            SELECT *,
                   current_timestamp AS _ingested_at,
                   '{path.name}'     AS _source_file
            FROM read_csv_auto(?, header = true, all_varchar = true)
            """,
            [str(path)],
        )
        n_csv = sum(1 for _ in open(path, encoding="utf-8")) - 1
        n_db = con.execute(f"SELECT count(*) FROM bronze.{table}").fetchone()[0]
        status = "OK" if n_csv == n_db else "LECH"
        print(f"[bronze] {table:<11} csv={n_csv:>6}  bronze={n_db:>6}  {status}")
        if n_csv != n_db:
            raise SystemExit(f"So dong bronze.{table} khong khop CSV")
    con.close()


if __name__ == "__main__":
    main()
