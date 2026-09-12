"""
CLI entry point.

Usage (run from the project root):
    python -m src.edgar_pipeline.main fetch       # pull + save raw JSON for all 3 companies
    python -m src.edgar_pipeline.main build-csv    # extract from latest raw snapshots -> CSV
    python -m src.edgar_pipeline.main run          # both, in sequence
"""

from __future__ import annotations

import argparse
import logging

from .build_csv import build_combined_csv
from .config import COMPANIES
from .fetch import fetch_all


def main() -> None:
    parser = argparse.ArgumentParser(description="SEC EDGAR XBRL pipeline")
    parser.add_argument("command", choices=["fetch", "build-csv", "run"])
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command in ("fetch", "run"):
        fetch_all(COMPANIES)
    if args.command in ("build-csv", "run"):
        build_combined_csv(COMPANIES)


if __name__ == "__main__":
    main()
