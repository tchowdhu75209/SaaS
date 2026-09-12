"""Runs extract_company for all configured companies and writes the combined CSV."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from .config import COMPANIES
from .extract import extract_company
from .fetch import latest_raw_snapshot

logger = logging.getLogger(__name__)

PROCESSED_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
OUTPUT_CSV = PROCESSED_DIR / "combined_quarterly.csv"


def build_combined_csv(companies: list[dict] = COMPANIES) -> pd.DataFrame:
    frames = []
    for company in companies:
        snapshot_path = latest_raw_snapshot(company["ticker"])
        raw_json = json.loads(snapshot_path.read_text())
        df = extract_company(raw_json, company)
        frames.append(df)
        logger.info(
            "%s: extracted %d quarterly rows from %s",
            company["ticker"], len(df), snapshot_path.name,
        )

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["ticker", "fiscal_year", "fiscal_period"])

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT_CSV, index=False)
    logger.info("Wrote %d total rows -> %s", len(combined), OUTPUT_CSV)

    _print_coverage_summary(combined)
    return combined


def _print_coverage_summary(df: pd.DataFrame) -> None:
    print("\n=== Coverage summary ===")
    for ticker, group in df.groupby("ticker"):
        derived_q4 = group["revenue_tag"].astype(str).str.startswith("derived:").sum()
        n_quarters = len(group)
        earliest = f"{group['fiscal_year'].min()} {group.loc[group['fiscal_year'].idxmin(), 'fiscal_period']}"
        latest_row = group.sort_values(["fiscal_year", "fiscal_period"]).iloc[-1]
        print(
            f"  {ticker}: {n_quarters} quarters "
            f"({group['fiscal_year'].min()}-{latest_row['fiscal_year']}), "
            f"{derived_q4} derived Q4s, "
            f"{group['revenue'].isna().sum()} quarters missing revenue, "
            f"{group['total_debt'].isna().sum()} quarters missing total_debt"
        )
    print("========================\n")
