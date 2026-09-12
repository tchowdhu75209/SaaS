"""
Turns one company's raw companyfacts JSON into a tidy DataFrame: one row per fiscal
quarter, with revenue / operating income / total debt / cash (each tagged with the
exact XBRL element it came from), plus a subscribers column that is always null (see
config.py -- no XBRL tag for that concept exists for any of these three companies).

Three real-data quirks drive the logic here (verified against live SEC data, not
assumed from docs):

1. Duration facts (revenue, operating income) show up TWICE per quarter in a 10-Q:
   once as a year-to-date cumulative figure and once as the discrete 3-month figure.
   Both carry the same `fp` label, so the only reliable way to tell them apart is the
   actual (end - start) span. We keep only ~80-100 day spans as "discrete quarters".
2. No company ever files a discrete Q4 -- 10-Ks only report the full fiscal year. Q4
   is derived as FY total minus (Q1 + Q2 + Q3).
3. The same historical period can be reported more than once across different filings.
   Usually that's a routine restatement (a minor reclassification correcting a prior
   figure by a few percent) and we keep whichever value was FILED most recently, as
   the current, most-authoritative figure. But occasionally the swing between the
   original and the latest value is enormous (verified real case: EchoStar's Dec 2023
   merger with DISH Network was accounted for as a reverse merger, so EchoStar's
   FY2023 10-K retroactively recast 2021-2023 comparatives to DISH's much larger
   historical financials -- e.g. FY2021 revenue as originally filed was $1.99B;
   restated in the FY2023 10-K it's $19.8B). That isn't a correction, it's a change of
   which underlying business the numbers describe. We still keep the latest-filed
   (current, audited) value -- that's what the company itself now stands behind -- but
   any period whose value moved by more than RECAST_RATIO_THRESHOLD between its
   earliest and latest filing gets its tag suffixed "[RECAST]" so it's never mistaken
   for an ordinary same-entity data point. See README.md's data caveats.
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from .config import (
    ECHO_MERGER_RECAST_CAVEAT,
    ECHO_MERGER_RECAST_CUTOFF,
    SUBSCRIBER_TAGS_EXIST,
    TOTAL_DEBT_FALLBACK_COMPONENT_PAIRS,
    get_tag_priority,
)

logger = logging.getLogger(__name__)

DURATION_CONCEPTS = ("revenue", "operating_income")
INSTANT_CONCEPTS = ("total_debt", "cash")
ALL_CONCEPTS = DURATION_CONCEPTS + INSTANT_CONCEPTS

STANDARD_QUARTER_ENDS = {(3, 31), (6, 30), (9, 30), (12, 31)}

# A >=2x (or <=0.5x) swing between a period's earliest- and latest-filed value is far
# outside normal restatement territory and signals a probable accounting-entity change
# (e.g. a reverse merger recast) rather than a routine correction.
RECAST_RATIO_THRESHOLD = 2.0


def _is_standard_quarter_end(d: date) -> bool:
    return (d.month, d.day) in STANDARD_QUARTER_ENDS


def _pick_authoritative(facts: list[dict], ticker: str, concept: str) -> dict:
    """
    Given every fact reported for the same period (possibly across several filings),
    returns the latest-filed one -- flagging its '_tag' with "[RECAST]" if it differs
    wildly from the earliest-filed value for that same period (see module docstring).
    """
    if len(facts) == 1:
        return facts[0]
    facts_sorted = sorted(facts, key=lambda f: f["filed"])
    earliest, latest = facts_sorted[0], facts_sorted[-1]
    chosen = dict(latest)
    if earliest["val"] != 0:
        ratio = abs(latest["val"]) / abs(earliest["val"])
        if ratio >= RECAST_RATIO_THRESHOLD or ratio <= 1 / RECAST_RATIO_THRESHOLD:
            logger.warning(
                "%s %s %s: value is %.1fx the original (as first filed %s in %s; now "
                "%s per %s filed %s) -- looks like an accounting-entity recast, not a "
                "routine restatement. Flagging tag with [RECAST].",
                ticker, concept, latest["end"], ratio, earliest["val"], earliest["filed"],
                latest["val"], latest["form"], latest["filed"],
            )
            chosen["_tag"] = f"{chosen['_tag']} [RECAST]"
    return chosen


def _group_by(facts: list[dict], key_fn) -> dict:
    groups: dict = {}
    for f in facts:
        groups.setdefault(key_fn(f), []).append(f)
    return groups


def merged_facts_with_tag(taxonomy_facts: dict, tag_priority: list[str]) -> list[dict]:
    """
    Combines facts from multiple candidate XBRL tags for one concept, in priority
    order: a period claimed by a higher-priority tag is never overridden by a
    lower-priority one, but a lower-priority tag can fill periods the higher-priority
    tag never reported. Each returned fact is tagged with '_tag' so downstream code
    (and the final CSV) always knows exactly which XBRL element produced it.
    """
    claimed_periods: set[tuple[str | None, str]] = set()
    combined: list[dict] = []
    for tag in tag_priority:
        tag_data = taxonomy_facts.get(tag)
        if not tag_data:
            continue
        facts = tag_data.get("units", {}).get("USD", [])
        for f in facts:
            key = (f.get("start"), f["end"])
            if key in claimed_periods:
                continue
            combined.append({**f, "_tag": tag})
        claimed_periods.update((f.get("start"), f["end"]) for f in facts)
    return combined


def discrete_quarters(combined_facts: list[dict], ticker: str, concept: str) -> dict[date, dict]:
    """Filters to ~3-month duration facts, deduped by latest-filed per period-end."""
    candidates = []
    for f in combined_facts:
        if not f.get("start"):
            continue
        start = date.fromisoformat(f["start"])
        end = date.fromisoformat(f["end"])
        if not _is_standard_quarter_end(end):
            continue
        days = (end - start).days
        if not (80 <= days <= 100):
            continue
        candidates.append(f)
    groups = _group_by(candidates, lambda f: date.fromisoformat(f["end"]))
    return {end: _pick_authoritative(facts, ticker, concept) for end, facts in groups.items()}


def full_year_facts(combined_facts: list[dict], ticker: str, concept: str) -> dict[date, dict]:
    """Filters to ~12-month duration facts (10-K annual totals), same dedup rule."""
    candidates = []
    for f in combined_facts:
        if not f.get("start"):
            continue
        start = date.fromisoformat(f["start"])
        end = date.fromisoformat(f["end"])
        if not _is_standard_quarter_end(end):
            continue
        days = (end - start).days
        if not (350 <= days <= 380):
            continue
        candidates.append(f)
    groups = _group_by(candidates, lambda f: date.fromisoformat(f["end"]))
    return {end: _pick_authoritative(facts, ticker, concept) for end, facts in groups.items()}


def instant_values(combined_facts: list[dict], ticker: str, concept: str) -> dict[date, dict]:
    """Balance-sheet (point-in-time) facts, deduped by latest-filed per date."""
    candidates = []
    for f in combined_facts:
        if f.get("start"):
            continue  # skip any duration fact that slipped through
        end = date.fromisoformat(f["end"])
        if not _is_standard_quarter_end(end):
            continue
        candidates.append(f)
    groups = _group_by(candidates, lambda f: date.fromisoformat(f["end"]))
    return {end: _pick_authoritative(facts, ticker, concept) for end, facts in groups.items()}


def derive_q4(
    annual: dict[date, dict], quarters: dict[date, dict], ticker: str, concept: str
) -> dict[date, dict]:
    """Q4 = FY total - (Q1 + Q2 + Q3), only when all three discrete quarters exist."""
    derived: dict[date, dict] = {}
    for end, annual_fact in annual.items():
        if end.month != 12:
            continue
        fy = end.year
        q_ends = [date(fy, 3, 31), date(fy, 6, 30), date(fy, 9, 30)]
        q_facts = [quarters.get(d) for d in q_ends]
        if any(f is None for f in q_facts):
            logger.info(
                "%s %s FY%d: cannot derive Q4 (missing a discrete Q1-Q3 value) -- left null",
                ticker, concept, fy,
            )
            continue
        q4_val = annual_fact["val"] - sum(f["val"] for f in q_facts)
        derived[end] = {
            "start": date(fy, 10, 1).isoformat(),
            "end": end.isoformat(),
            "val": q4_val,
            "accn": annual_fact["accn"],
            "filed": annual_fact["filed"],
            "form": annual_fact["form"],
            "_tag": f"derived:FY({annual_fact['_tag']})-Q1-Q3",
        }
    return derived


def compute_debt_fallback(
    taxonomy_facts: dict, missing_ends: set[date], ticker: str
) -> dict[date, dict]:
    """
    Fills total_debt for periods no direct tag covers, by summing a current +
    noncurrent long-term-debt component pair. Verified on real Charter data that
    LongTermDebtCurrent + LongTermDebtNoncurrent == LongTermDebt exactly, so this is
    a safe reconstruction, not an estimate. Tries each candidate pair in order since
    companies name these components differently.
    """
    fallback: dict[date, dict] = {}
    remaining = set(missing_ends)
    for current_tag, noncurrent_tag in TOTAL_DEBT_FALLBACK_COMPONENT_PAIRS:
        if not remaining:
            break
        current_by_end = instant_values(
            merged_facts_with_tag(taxonomy_facts, [current_tag]), ticker, current_tag
        )
        noncurrent_by_end = instant_values(
            merged_facts_with_tag(taxonomy_facts, [noncurrent_tag]), ticker, noncurrent_tag
        )
        resolved = set()
        for end in remaining:
            cur = current_by_end.get(end)
            non = noncurrent_by_end.get(end)
            if cur is None or non is None:
                continue
            fallback[end] = {
                "end": end.isoformat(),
                "val": cur["val"] + non["val"],
                "accn": max(cur["accn"], non["accn"]),
                "filed": max(cur["filed"], non["filed"]),
                "form": cur["form"],
                "_tag": f"computed:{current_tag}+{noncurrent_tag}",
            }
            resolved.add(end)
        remaining -= resolved
    return fallback


def _quarter_label(end: date) -> tuple[int, str, date]:
    month_to_quarter = {
        3: ("Q1", date(end.year, 1, 1)),
        6: ("Q2", date(end.year, 4, 1)),
        9: ("Q3", date(end.year, 7, 1)),
        12: ("Q4", date(end.year, 10, 1)),
    }
    fp, start = month_to_quarter[end.month]
    return end.year, fp, start


def extract_company(raw_json: dict, company_meta: dict) -> pd.DataFrame:
    """Orchestrates tag selection, quarter/annual filtering, Q4 derivation, and the
    total-debt fallback for one company; returns one tidy row per fiscal quarter."""
    ticker = company_meta["ticker"]
    us_gaap = raw_json.get("facts", {}).get("us-gaap", {})

    quarters_by_concept: dict[str, dict[date, dict]] = {}
    for concept in DURATION_CONCEPTS:
        combined = merged_facts_with_tag(us_gaap, get_tag_priority(ticker, concept))
        quarters = discrete_quarters(combined, ticker, concept)
        annual = full_year_facts(combined, ticker, concept)
        quarters.update(derive_q4(annual, quarters, ticker, concept))
        quarters_by_concept[concept] = quarters

    instants_by_concept: dict[str, dict[date, dict]] = {}
    for concept in INSTANT_CONCEPTS:
        combined = merged_facts_with_tag(us_gaap, get_tag_priority(ticker, concept))
        instants_by_concept[concept] = instant_values(combined, ticker, concept)

    all_ends: set[date] = set()
    for d in quarters_by_concept.values():
        all_ends.update(d.keys())
    for d in instants_by_concept.values():
        all_ends.update(d.keys())

    missing_debt_ends = all_ends - instants_by_concept["total_debt"].keys()
    if missing_debt_ends:
        instants_by_concept["total_debt"].update(
            compute_debt_fallback(us_gaap, missing_debt_ends, ticker)
        )

    rows = []
    for end in sorted(all_ends):
        fy, fp, period_start = _quarter_label(end)
        row = {
            "company": company_meta["name"],
            "ticker": ticker,
            "cik": company_meta["cik"],
            "fiscal_year": fy,
            "fiscal_period": fp,
            "period_start": period_start.isoformat(),
            "period_end": end.isoformat(),
        }
        provenance = None
        for concept in ALL_CONCEPTS:
            source = quarters_by_concept.get(concept) or instants_by_concept.get(concept)
            fact = source.get(end) if source else None
            row[concept] = fact["val"] if fact else None
            row[f"{concept}_tag"] = fact["_tag"] if fact else None
            if fact and provenance is None:
                provenance = fact
        row["subscribers"] = None
        row["source_accn"] = provenance.get("accn") if provenance else None
        row["source_form"] = provenance.get("form") if provenance else None
        row["filed_date"] = provenance.get("filed") if provenance else None
        row["data_caveat"] = (
            ECHO_MERGER_RECAST_CAVEAT
            if ticker == "ECHO" and end.isoformat() < ECHO_MERGER_RECAST_CUTOFF
            else None
        )
        rows.append(row)

    if not SUBSCRIBER_TAGS_EXIST:
        logger.info(
            "%s: no subscriber/churn XBRL tags exist for this company -- "
            "'subscribers' column left null for all %d rows.",
            ticker, len(rows),
        )

    columns = (
        ["company", "ticker", "cik", "fiscal_year", "fiscal_period", "period_start", "period_end"]
        + [c for concept in ALL_CONCEPTS for c in (concept, f"{concept}_tag")]
        + ["subscribers", "source_accn", "source_form", "filed_date", "data_caveat"]
    )
    return pd.DataFrame(rows, columns=columns)
