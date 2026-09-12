"""
Shared data-access helpers for the Streamlit app. Every page imports from here rather
than touching DuckDB or sql/*.sql directly -- keeps the app a thin, read-only
presentation layer over the pipeline already built in steps 1-2.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.edgar_pipeline.load_db import DEFAULT_CSV_PATH, DEFAULT_DB_PATH, load_database
from src.edgar_pipeline.queries import run_saved_query


def ensure_database() -> None:
    """
    Builds data/warehouse.duckdb from the tracked CSV if it isn't already there.

    Needed because the .duckdb file is gitignored (step 2's deliberate choice: it's
    100% reproducible from the tracked CSV, so no binary belongs in git) -- which
    means a fresh Streamlit Community Cloud checkout of this repo won't have one.
    load_database() is already idempotent (drops/recreates tables each call), so this
    is safe to call on every rerun; the file-existence check keeps it a no-op after
    the first run.
    """
    if not DEFAULT_DB_PATH.exists():
        load_database(DEFAULT_CSV_PATH, DEFAULT_DB_PATH)


@st.cache_data
def cached_query(name: str) -> pd.DataFrame:
    """Runs a saved query from sql/ and caches the result for the session -- avoids
    re-hitting DuckDB on every widget interaction (Streamlit reruns the whole script
    on each one). run_saved_query() itself opens the warehouse read_only=True."""
    ensure_database()
    return run_saved_query(name)
