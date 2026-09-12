"""
Static config for the SEC EDGAR pipeline: which companies to pull, and the XBRL
tag-fallback order for each financial concept.

The tag lists below were NOT copied from generic XBRL documentation -- they were
verified against the actual `companyfacts` JSON these three companies have filed
(see the plan notes / README for how). Different companies tag the same real-world
concept with different XBRL elements, and the same company can switch tags over time
(most commonly around the 2018 ASC 606 revenue-recognition transition), so every
concept is a priority-ordered list: the extractor tries each tag in order and uses
the first one that has data for a given period.

One assumption from generic XBRL docs turned out to be company-specific rather than
universal: "RevenueFromContractWithCustomer{Excluding,Including}AssessedTax" are
usually alternate presentations of the SAME whole-company total-revenue concept
(gross vs. net of collected taxes). That holds for Comcast and EchoStar, but NOT for
Charter -- Charter's "...IncludingAssessedTax" tag is a small, separate ~$0.9-1.1B/
year line item (confirmed against 12 real facts, 2020-2025), while Charter's actual
total revenue (confirmed against 274 real facts, full 2009-2026 history) has always
lived under the older, generic "Revenues" tag. COMPANY_TAG_OVERRIDES below is how a
verified per-company exception like this overrides the default TAG_MAP priority.
"""

from __future__ import annotations

# SEC requires a 10-digit, zero-padded CIK in the companyfacts URL.
COMPANIES = [
    {"name": "EchoStar Corporation", "ticker": "ECHO", "cik": "0001415404"},
    {"name": "Charter Communications, Inc.", "ticker": "CHTR", "cik": "0001091667"},
    {"name": "Comcast Corporation", "ticker": "CMCSA", "cik": "0001166691"},
]

# Concept -> ordered list of (taxonomy, tag) candidates, most-preferred first.
# All of these live in the 'us-gaap' taxonomy for these three companies.
TAG_MAP: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",  # pre-ASC606 tag, still used by all three into ~2018-2019
        # EchoStar's revenue tag before that transition (2008-2016) -- confirmed 164
        # real facts under this name, zero under "Revenues" for that span.
        "SalesRevenueNet",
    ],
    "operating_income": [
        "OperatingIncomeLoss",  # identical across all three companies
    ],
    "total_debt": [
        "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
        "LongTermDebt",
        # Comcast's real primary total-debt tag for its ENTIRE history (91 facts,
        # 2009-2026, values matching known Comcast debt levels including the real
        # 2018 Sky-acquisition debt jump from $72.9B to $111.7B) -- confirmed by
        # inspecting the raw facts, it matches "IncludingCurrentMaturities" almost
        # exactly in the years both exist. Also the tag EchoStar used specifically for
        # 2024 Q2-Q3 while the DISH merger (closed Dec 2023) was being integrated.
        "DebtAndCapitalLeaseObligations",
        # For the (rare) periods still uncovered: verified against real Comcast data
        # that this bare tag (no "IncludingCurrentMaturities" suffix) is the
        # NONCURRENT-only portion whenever a separate current-maturities tag also
        # exists for that period (bare + current ~= the full total, within a small
        # reconciling item) -- but Comcast doesn't tag a current portion most periods,
        # so used alone here it may understate true total debt by an untagged
        # current-maturities amount. Documented in README.md's data caveats.
        "LongTermDebtAndCapitalLeaseObligations",
        # When none of the above exist for a period, extract.py falls back to summing
        # a current + noncurrent component pair (see TOTAL_DEBT_FALLBACK_COMPONENT_PAIRS)
        # -- verified equal to LongTermDebt exactly on real Charter data.
        #
        # Last resort: Charter's own 2011-2014 filings (post-bankruptcy-reorg era)
        # tag LongTermDebtNoncurrent but never tag a separate current-maturities
        # figure at all for that span -- confirmed by inspecting the raw facts
        # (LongTermDebtCurrent doesn't start until 2014-12-31). Same understatement
        # caveat as the bare Comcast tag above; documented in README.md.
        "LongTermDebtNoncurrent",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        # Includes restricted cash -- only used if the plain balance is missing.
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
}

# Fallback current/noncurrent tag-name pairs, tried in order, used only if no tag in
# TAG_MAP["total_debt"] has data for a period. Different companies name these
# differently (verified: EchoStar and Charter both use the bare "LongTermDebt*"
# names; Comcast's equivalent pair only appears for one period and isn't enough on
# its own, but is included for completeness).
TOTAL_DEBT_FALLBACK_COMPONENT_PAIRS = [
    ("LongTermDebtCurrent", "LongTermDebtNoncurrent"),
    ("LongTermDebtAndCapitalLeaseObligationsCurrent", "LongTermDebtAndCapitalLeaseObligationsNoncurrent"),
]

# Per-company exceptions to TAG_MAP, only added when real inspection proved the
# default priority order picks the wrong tag for that company/concept (see module
# docstring for the Charter revenue case this currently holds).
COMPANY_TAG_OVERRIDES: dict[str, dict[str, list[str]]] = {
    "CHTR": {
        "revenue": ["Revenues", "SalesRevenueNet"],
    },
}


def get_tag_priority(ticker: str, concept: str) -> list[str]:
    """Returns the tag-fallback list to use for this company/concept: a verified
    per-company override if one exists, else the default TAG_MAP order."""
    return COMPANY_TAG_OVERRIDES.get(ticker, {}).get(concept, TAG_MAP[concept])

# Verified by direct inspection of all three companies' real companyfacts JSON
# (searched every taxonomy for tags matching /subscriber|churn/i -- zero hits).
# No XBRL tag exists for this concept for any of the three companies. The column is
# emitted as null on every row rather than silently dropped, per CLAUDE.md's
# "scope down explicitly" rule. Getting real subscriber counts requires a separate,
# later step that reads the prose/tables inside the filings themselves.
SUBSCRIBER_TAGS_EXIST = False

SEC_USER_AGENT = "Lead-FA-SaaS-SubscriberEconomics taif.chow@gmail.com"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# EchoStar's Dec 2023 reverse merger with DISH Network means periods before this date
# can be reported on TWO different accounting bases depending on which filing a fact
# is pulled from (pre-merger EchoStar/Hughes-only, or DISH's history recast in as the
# accounting acquirer) -- verified directly: e.g. FY2021 revenue is $1.99B as
# originally filed, $19.8B as recast in the FY2023 10-K. The [RECAST] tag suffix (see
# extract.py) only catches this where the SAME XBRL tag has two filed values to
# compare; it can't catch every instance (e.g. a tag used only once, post-recast).
# So every ECHO row for a period ending before this cutoff also gets an explicit
# `data_caveat` note in the CSV -- a systematic, row-level flag rather than relying on
# per-value detection alone.
ECHO_MERGER_RECAST_CUTOFF = "2024-01-01"
ECHO_MERGER_RECAST_CAVEAT = (
    "EchoStar figures before 2024 predate the Dec 2023 DISH Network reverse merger; "
    "depending on which filing a figure was pulled from, it may reflect the small "
    "pre-merger Hughes-only entity or DISH's history recast in as accounting "
    "acquirer -- not reliably comparable across this boundary. See README.md."
)
