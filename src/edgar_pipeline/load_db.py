"""
Loads data/processed/combined_quarterly.csv into a DuckDB warehouse: a `companies`
dimension table, a `quarterly_financials` fact table, and a `v_quarterly_financials`
view that adds convenience flags on top of it.

This is Python rather than a plain .sql file because it needs the CSV's file path
substituted in at load time -- a one-time build step, not something meant to be
hand-run. The actual analysis queries (sql/*.sql) need no such substitution and stay
as portable, standalone SQL.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV_PATH = PROJECT_ROOT / "data" / "processed" / "combined_quarterly.csv"
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "warehouse.duckdb"

# CSV columns whose values must NOT be auto-inferred as numbers: `cik` is a
# zero-padded 10-digit identifier ("0001091667") -- inferring it as an integer would
# silently drop the leading zero.
CSV_COLUMN_TYPES = {"cik": "VARCHAR"}


def load_database(csv_path: Path = DEFAULT_CSV_PATH, db_path: Path = DEFAULT_DB_PATH) -> None:
    """(Re)builds the DuckDB warehouse from the combined CSV. Idempotent: drops and
    recreates the tables/view each time, so re-running after a fresh build-csv just
    reflects the latest data."""
    csv_path = Path(csv_path)
    db_path = Path(db_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} doesn't exist -- run `build-csv` first.")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        con.execute("DROP VIEW IF EXISTS v_quarterly_financials")
        con.execute("DROP TABLE IF EXISTS quarterly_financials")
        con.execute("DROP TABLE IF EXISTS companies")

        con.execute(
            """
            CREATE TABLE companies AS
            SELECT DISTINCT
                ticker,
                company AS name,
                cik
            FROM read_csv(?, types = ?)
            ORDER BY ticker
            """,
            [str(csv_path), CSV_COLUMN_TYPES],
        )

        con.execute(
            """
            CREATE TABLE quarterly_financials AS
            SELECT
                ticker,
                fiscal_year,
                fiscal_period,
                CAST(period_start AS DATE) AS period_start,
                CAST(period_end AS DATE) AS period_end,
                revenue,
                revenue_tag,
                operating_income,
                operating_income_tag,
                total_debt,
                total_debt_tag,
                cash,
                cash_tag,
                CAST(subscribers AS BIGINT) AS subscribers,
                source_accn,
                source_form,
                CAST(filed_date AS DATE) AS filed_date,
                data_caveat
            FROM read_csv(?, types = ?)
            ORDER BY ticker, period_end
            """,
            [str(csv_path), CSV_COLUMN_TYPES],
        )

        # Convenience booleans so every saved query can filter/flag on these without
        # repeating the same string-matching logic -- built from the raw *_tag and
        # data_caveat columns, which stay untouched in quarterly_financials itself.
        con.execute(
            """
            CREATE VIEW v_quarterly_financials AS
            SELECT
                *,
                (
                    revenue_tag LIKE '%[RECAST]%'
                    OR operating_income_tag LIKE '%[RECAST]%'
                    OR total_debt_tag LIKE '%[RECAST]%'
                    OR cash_tag LIKE '%[RECAST]%'
                ) AS is_recast,
                (
                    revenue_tag LIKE 'derived:%'
                    OR operating_income_tag LIKE 'derived:%'
                ) AS is_derived_q4,
                (data_caveat IS NOT NULL) AS has_data_caveat
            FROM quarterly_financials
            """
        )

        n_companies = con.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
        n_rows = con.execute("SELECT COUNT(*) FROM quarterly_financials").fetchone()[0]
        logger.info(
            "Loaded %d companies and %d quarterly rows into %s", n_companies, n_rows, db_path
        )
    finally:
        con.close()
