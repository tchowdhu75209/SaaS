"""
CLI entry point.

Usage (run from the project root):
    python -m src.edgar_pipeline.main fetch          # pull + save raw JSON for all 3 companies
    python -m src.edgar_pipeline.main build-csv       # extract from latest raw snapshots -> CSV
    python -m src.edgar_pipeline.main load-db         # load the combined CSV into DuckDB
    python -m src.edgar_pipeline.main query <name>    # run one saved query from sql/
    python -m src.edgar_pipeline.main run             # fetch -> build-csv -> load-db, in sequence
"""

from __future__ import annotations

import argparse
import logging

from .build_csv import build_combined_csv
from .config import COMPANIES
from .fetch import fetch_all
from .load_db import load_database
from .queries import list_saved_queries, run_saved_query


def main() -> None:
    parser = argparse.ArgumentParser(description="SEC EDGAR XBRL pipeline")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("fetch", help="Pull + save raw JSON for all 3 companies")
    subparsers.add_parser("build-csv", help="Extract from latest raw snapshots -> CSV")
    subparsers.add_parser("load-db", help="Load the combined CSV into DuckDB")
    subparsers.add_parser("run", help="fetch -> build-csv -> load-db, in sequence")

    query_parser = subparsers.add_parser("query", help="Run one saved query from sql/")
    query_parser.add_argument(
        "name", help=f"Saved query name (available: {', '.join(list_saved_queries())})"
    )
    query_parser.add_argument("--out", help="Optional path to also save the result as CSV")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command in ("fetch", "run"):
        fetch_all(COMPANIES)
    if args.command in ("build-csv", "run"):
        build_combined_csv(COMPANIES)
    if args.command in ("load-db", "run"):
        load_database()
    if args.command == "query":
        df = run_saved_query(args.name)
        print(df.to_string(index=False))
        if args.out:
            df.to_csv(args.out, index=False)
            print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
