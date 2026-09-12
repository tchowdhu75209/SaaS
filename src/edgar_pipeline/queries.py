"""Runs one of the saved .sql files in sql/ against the DuckDB warehouse."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from .load_db import DEFAULT_DB_PATH

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"


def list_saved_queries() -> list[str]:
    """Names (without .sql) of every saved query in sql/, sorted."""
    return sorted(p.stem for p in SQL_DIR.glob("*.sql"))


def run_saved_query(name: str, db_path: Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Reads sql/{name}.sql and executes it against the warehouse, returning a DataFrame."""
    sql_path = SQL_DIR / f"{name}.sql"
    if not sql_path.exists():
        available = ", ".join(list_saved_queries())
        raise FileNotFoundError(f"No saved query '{name}' -- available: {available}")
    if not Path(db_path).exists():
        raise FileNotFoundError(f"{db_path} doesn't exist -- run `load-db` first.")

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        return con.execute(sql_path.read_text()).fetchdf()
    finally:
        con.close()
