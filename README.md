# SEC EDGAR XBRL Pipeline + SQL Layer + Streamlit App

**🔗 Live app: [4eg3mmnwcr6sm3wyqbnluo.streamlit.app](https://4eg3mmnwcr6sm3wyqbnluo.streamlit.app/)**

Steps 1-3 of the Subscriber Economics Analytics Platform (see [CLAUDE.md](CLAUDE.md)):
step 1 pulls quarterly revenue, operating income, total debt, and cash for EchoStar
(ECHO), Charter Communications (CHTR), and Comcast (CMCSA) directly from SEC EDGAR's
XBRL `companyfacts` API and combines them into one tidy CSV; step 2 loads that CSV
into a queryable DuckDB warehouse with a handful of saved analysis queries; step 3 is
a Streamlit app shell with a real Home page and placeholder pages for what's still to
come.

## Running it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python -m src.edgar_pipeline.main fetch          # pull + save raw JSON for all 3 companies
.venv/bin/python -m src.edgar_pipeline.main build-csv       # extract from latest raw snapshots -> CSV
.venv/bin/python -m src.edgar_pipeline.main load-db         # load the combined CSV into DuckDB
.venv/bin/python -m src.edgar_pipeline.main query <name>    # run one saved query from sql/ (e.g. revenue_yoy_growth)
.venv/bin/python -m src.edgar_pipeline.main run             # fetch -> build-csv -> load-db, in sequence
```

Output: `data/processed/combined_quarterly.csv` -- one row per company per fiscal
quarter. Raw, untouched API responses are saved to `data/raw/{TICKER}_companyfacts_
{date}.json` before any processing, one snapshot per pull date, kept forever.
`data/warehouse.duckdb` is the queryable database built from that CSV -- it's
git-ignored (100% reproducible from the tracked CSV via `load-db`, so there's no
reason to track a binary file).

## SQL layer

`load-db` builds two tables plus a view in `data/warehouse.duckdb`:

- **`companies`** (3 rows): `ticker` (PK), `name`, `cik` (explicitly typed VARCHAR --
  otherwise DuckDB's CSV auto-detection infers `cik` as an integer and silently drops
  the leading zero, e.g. `0001091667` -> `1091667`).
- **`quarterly_financials`** (213 rows): everything from the CSV except `company`/
  `cik` (normalized out into `companies`), with `period_start`/`period_end`/
  `filed_date` cast to DATE. Every `*_tag` column and `data_caveat` carry over
  completely unchanged -- nothing about step 1's provenance/flagging work is
  summarized away.
- **View `v_quarterly_financials`**: everything above plus three computed booleans --
  `is_recast`, `is_derived_q4`, `has_data_caveat` -- so queries don't have to repeat
  the same string-matching logic. Every saved query selects from this view.

Saved queries live as plain, portable `.sql` files in `sql/` (runnable standalone in
any DuckDB client, not just through this CLI):

| Query | What it does |
|---|---|
| `revenue_yoy_growth` | Year-over-year revenue growth % per company per quarter. |
| `revenue_qoq_growth` | Quarter-over-quarter revenue growth %. |
| `operating_margin_trend` | `operating_income / revenue` per company per quarter. |
| `data_quality_summary` | Per-company counts of recast/derived-Q4/caveated/missing quarters. |
| `companies_overview` | The three companies (ticker, name, CIK) -- used by the Streamlit Home page. |
| `revenue_by_quarter` | Raw quarterly revenue (no growth math) -- used by the Home page's chart. |
| `leverage_and_liquidity` | Net debt and debt/TTM-revenue leverage per company per quarter -- used by the Metrics & Judgment Calls page. |

Each growth/margin query includes a `growth_may_be_unreliable` /
`margin_may_be_unreliable` column: true if either endpoint of the calculation is
`[RECAST]`-flagged or carries a `data_caveat` (e.g. any EchoStar comparison spanning
its Dec 2023 DISH merger, below) -- the row is still shown, never hidden, just marked.

`leverage_and_liquidity` divides `total_debt` by **trailing-twelve-month (TTM)
revenue**, not a single quarter's revenue -- dividing an annual-scale balance-sheet
figure by one quarter's revenue overstates the ratio ~4x (verified: Charter's naive
single-quarter debt/revenue is 6.95x vs. a real 1.73x on a TTM basis). Its
`ttm_window_incomplete` flag needed a real fix during review: an initial version
compared `period_end(t)` to `period_end(t-3)`, which is only a ~9-month gap (3
quarter-boundaries between four quarter-end dates), not the ~12-month span the window
actually covers -- fixed by comparing against `period_start(t-3)` instead.
`revenue_yoy_growth`/`revenue_qoq_growth` also flag `date_gap_mismatch`: a handful of
quarters are entirely absent from the row sequence (CMCSA/ECHO, 2007-2009, before
SEC's XBRL mandate fully phased in), so `LAG(revenue, N)` alone can't be trusted to
mean "N quarters back" -- both queries verify the actual `period_end` gap is ~365 days
(YoY) or ~90 days (QoQ) before treating a comparison as reliable.

**A real bug caught and fixed while building step 3**: `is_recast`/`is_derived_q4` in
`v_quarterly_financials` used plain `OR` across several `... LIKE '...'` checks. SQL's
three-valued logic means `NULL LIKE '...'` is `NULL`, and `NULL OR FALSE` is `NULL`
(not `FALSE`) -- so any quarter where one of the `*_tag` columns was simply null (that
metric wasn't tagged that period, unrelated to any recast) made `is_recast` come out
`NULL` instead of `FALSE`, unless another tag column happened to force it `TRUE`. Fixed
by wrapping every check in `COALESCE(..., FALSE)` in `load_db.py`.

## Streamlit app

```bash
.venv/bin/streamlit run app.py
```

- **`app.py`** -- Home/Overview page: the three companies, a revenue-over-time chart
  across all three, the real `data_quality_summary` results, and the two caveats above
  surfaced directly in the UI (not just here in README prose). Everything on this page
  is pulled from the saved queries in `sql/` -- nothing fabricated or placeholder.
- **`pages/1_Metrics_and_Judgment_Calls.py`** -- real content (step 4's metrics half):
  revenue growth, operating margin, and leverage/liquidity for all three companies,
  each with a written verdict that names all three, a latest-quarter side-by-side
  snapshot, and an explicit "what this page can't show" section (subscriber/ARPU/
  churn data doesn't exist in XBRL at all; EBITDA/FCF/capex data wasn't extracted in
  step 1 but could be; NPV is on the Monte Carlo page instead).
- **`pages/2-4`** -- still honest placeholders for CLAUDE.md steps 4 (NPV + Monte
  Carlo)-6 (Predictive Models, LLM Assistant): a title and an explicit "not built
  yet," no invented charts or numbers.
- **`app_common.py`** -- shared helpers every page uses: `ensure_database()` and a
  cached `cached_query(name)` wrapper around `run_saved_query()`.

**Why the app can build its own warehouse on startup**: `data/warehouse.duckdb` is
git-ignored (see above), so a fresh clone -- including a Streamlit Community Cloud
deploy -- won't have one. `ensure_database()` calls step 2's `load_database()` to build
it from the tracked CSV if it's missing, so the app works identically locally and on a
fresh Cloud checkout with no extra setup. Verified by deleting `data/warehouse.duckdb`
and confirming the app rebuilds it automatically on the next run.

### Deploying to Streamlit Community Cloud
1. Push to GitHub (already done -- `tchowdhu75209/SaaS`, branch `main`).
2. On [share.streamlit.io](https://share.streamlit.io): New app -> pick that repo and
   branch, set **main file path to `app.py`** (Cloud defaults to looking for
   `streamlit_app.py` if this isn't set explicitly).
3. Cloud installs from the root `requirements.txt` automatically -- already includes
   `streamlit`. No other config is needed; `ensure_database()` handles the warehouse.
4. The deployed app only reflects what's committed to `main`. Pulling fresh SEC data
   means re-running `fetch` -> `build-csv` locally and pushing the updated CSV -- the
   Cloud app doesn't refresh live data on its own.

## CSV columns

| Column | Meaning |
|---|---|
| `revenue`, `operating_income`, `total_debt`, `cash` | The four financial figures, in USD. |
| `{concept}_tag` | The exact XBRL element that value came from (see below) -- always present alongside the value so every number traces back to a specific filing. |
| `subscribers` | Always null (see "No subscriber data" below). |
| `source_accn`, `source_form`, `filed_date` | The SEC accession number, form type, and filing date behind the row (representative, from whichever concept anchors it -- look up the exact per-metric filing via the `_tag` column + EDGAR full-text search if needed). |
| `data_caveat` | Set on EchoStar rows before 2024 -- see "EchoStar's 2023 merger" below. |

## Tag mapping (verified against real filings, not generic XBRL docs)

Different companies tag the same concept with different XBRL elements, and a company
can switch tags over time. Each concept in `config.py`'s `TAG_MAP` is a
priority-ordered list; `extract.py` tries each tag in order and uses whichever has
data for a given period (a later filing under the same tag is preferred, unless
flagged `[RECAST]` -- see below).

- **Revenue**: `RevenueFromContractWithCustomerExcludingAssessedTax` →
  `RevenueFromContractWithCustomerIncludingAssessedTax` → `Revenues` (pre-ASC606) →
  `SalesRevenueNet` (EchoStar's own pre-2016 tag).
  **Exception**: Charter's `...IncludingAssessedTax` tag is NOT their total revenue --
  it's a small, separate ~$0.9-1.1B/year line item. Charter's real revenue has always
  lived under the plain `Revenues` tag (274 facts, full history). This is a verified
  per-company override in `config.py`'s `COMPANY_TAG_OVERRIDES`, not a guess.
- **Operating income**: `OperatingIncomeLoss` -- identical across all three, no
  fallback needed.
- **Total debt**: `LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities` →
  `LongTermDebt` → `DebtAndCapitalLeaseObligations` (Comcast's real primary tag for
  its entire history, and EchoStar's tag for 2024 Q2-Q3) →
  `LongTermDebtAndCapitalLeaseObligations` (a noncurrent-only figure when no separate
  current-maturities tag exists that period -- may understate true total debt) →
  computed `current + noncurrent` component sum → `LongTermDebtNoncurrent` alone as a
  last resort (Charter's 2011-2014 filings never tagged a current-maturities figure at
  all).
- **Cash**: `CashAndCashEquivalentsAtCarryingValue` →
  `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents` (includes restricted
  cash; only used if the plain balance is missing).

## Known data caveats (real limitations, documented rather than hidden or faked)

**No subscriber or churn data.** Searched every taxonomy in all three companies' real
`companyfacts` JSON for anything matching `subscriber|churn` -- zero hits. None of
these three companies tag subscriber counts in XBRL; that data only exists as
prose/tables inside the filing text. The `subscribers` column is emitted and always
null rather than silently dropped. Getting real subscriber figures requires a
separate, later step that parses the filing text itself.

**EchoStar's 2023 DISH merger is a structural break, not a data-quality bug.**
EchoStar's Dec 2023 merger with DISH Network was accounted for as a reverse merger, so
EchoStar's FY2023 10-K retroactively recast 2021-2023 comparatives to DISH's much
larger history (verified: FY2021 revenue was $1.99B as originally filed, $19.8B as
recast). Pre-merger EchoStar was a Hughes-broadband-and-satellite-technology company
only, nowhere near the Pay-TV/Wireless/Broadband company described in CLAUDE.md --
that description only applies from the merger close (Dec 2023) onward. Two mechanisms
flag this in the data:
1. Any single XBRL tag whose value swung >=2x between its earliest and latest filed
   value gets `[RECAST]` appended to its `_tag` column (a real, generic detector --
   not EchoStar-specific -- for "this looks like an accounting-entity change, not a
   routine restatement").
2. Every EchoStar row for a period ending before 2024-01-01 also carries an explicit
   `data_caveat` note, since the recast doesn't always leave two versions of the same
   tag to compare (sometimes a tag is only ever reported once, already recast).

**Practical implication for analysis**: don't treat EchoStar's quarterly series as one
continuous company across the 2023/2024 boundary. Real multi-company comparison
(Pay-TV + Broadband + Wireless, per CLAUDE.md) is only meaningful from FY2024 Q1
onward.

**Sparse pre-2010 coverage across all three companies.** The SEC's XBRL mandate only
phased in for large accelerated filers around fiscal periods ending after June 15,
2009. A handful of quarters in 2006-2010 (and a few derived-Q4 gaps where an
underlying Q1-Q3 discrete value is missing) are genuinely absent from XBRL, not a
pipeline bug -- each is logged when `build-csv` runs.

## Two real XBRL mechanics this pipeline had to handle

1. **Duration facts appear twice per 10-Q**: once as a year-to-date cumulative figure,
   once as the discrete 3-month figure, both under the same `fp` label. The only
   reliable signal is the actual `end - start` span (~80-100 days = discrete quarter).
   No company ever files a discrete Q4 (10-Ks only report the full year), so Q4 is
   derived as `FY total - (Q1 + Q2 + Q3)`, and skipped (left null, logged) if any of
   Q1-Q3 is missing.
2. **Restatements**: the same historical period can appear more than once across
   filings. The latest-filed value is kept as the current, most-authoritative figure
   -- except when flagged `[RECAST]` (see above), which signals the swing is too large
   to be a routine correction.
