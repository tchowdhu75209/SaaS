"""
Downloads raw XBRL company-facts JSON from data.sec.gov and saves it untouched,
before any parsing happens. Nothing in this module interprets the data -- that's
extract.py's job. This module's only responsibility is: get the bytes, save the bytes.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

import requests

from .config import COMPANYFACTS_URL, SEC_USER_AGENT

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 2  # doubles each retry: 2, 4, 8, 16


def fetch_company_facts(cik: str) -> dict:
    """
    GET the companyfacts JSON for one CIK, with the SEC-required identifying
    User-Agent header. Retries with exponential backoff on rate-limiting (429) or
    server errors (5xx); raises immediately on anything else (e.g. a bad CIK -> 404).
    """
    url = COMPANYFACTS_URL.format(cik=cik)
    headers = {"User-Agent": SEC_USER_AGENT}

    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()
            if response.status_code in (429, 500, 502, 503, 504):
                wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "CIK %s: HTTP %s on attempt %d/%d, retrying in %ds",
                    cik, response.status_code, attempt, MAX_RETRIES, wait,
                )
                time.sleep(wait)
                continue
            response.raise_for_status()
        except requests.RequestException as exc:
            last_exc = exc
            wait = RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "CIK %s: request error on attempt %d/%d (%s), retrying in %ds",
                cik, attempt, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Failed to fetch companyfacts for CIK {cik} after {MAX_RETRIES} attempts"
    ) from last_exc


def save_raw(ticker: str, payload: dict, pull_date: date | None = None) -> Path:
    """
    Writes the payload untouched (no re-serialization choices that would change the
    bytes meaningfully -- just pretty-printed for human readability) to a snapshot
    file named for today's pull date. Re-running on the same day overwrites that
    day's snapshot (idempotent), but never touches a previous day's snapshot --
    that's the point-in-time archive.
    """
    pull_date = pull_date or date.today()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / f"{ticker}_companyfacts_{pull_date.isoformat()}.json"
    out_path.write_text(json.dumps(payload, indent=2))
    logger.info("Saved raw companyfacts for %s -> %s", ticker, out_path)
    return out_path


def latest_raw_snapshot(ticker: str) -> Path:
    """Returns the most recent saved raw snapshot for a ticker, or raises if none exist."""
    candidates = sorted(RAW_DIR.glob(f"{ticker}_companyfacts_*.json"))
    if not candidates:
        raise FileNotFoundError(
            f"No raw snapshot found for {ticker} in {RAW_DIR}. Run `fetch` first."
        )
    return candidates[-1]


def fetch_all(companies: list[dict]) -> dict[str, Path]:
    """Fetches and saves raw JSON for every company; returns ticker -> saved path."""
    saved = {}
    for company in companies:
        logger.info("Fetching %s (CIK %s)...", company["name"], company["cik"])
        payload = fetch_company_facts(company["cik"])
        saved[company["ticker"]] = save_raw(company["ticker"], payload)
    return saved
