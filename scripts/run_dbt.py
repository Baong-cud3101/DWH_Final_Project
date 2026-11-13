"""Chạy dbt với đúng project-dir và profiles-dir.

Ví dụ: python scripts/run_dbt.py build    |    python scripts/run_dbt.py docs generate
"""

import os
import sys

from dbt.cli.main import dbtRunner

from common import DB_PATH, ROOT

DBT_DIR = ROOT / "dbt"


def run(*args: str) -> bool:
    os.environ.setdefault("DUCKDB_PATH", str(DB_PATH))
    res = dbtRunner().invoke(
        [*args, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    )
    return bool(res.success)


if __name__ == "__main__":
    sys.exit(0 if run(*sys.argv[1:]) else 1)
