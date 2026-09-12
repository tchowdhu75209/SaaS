"""Metrics & Judgment Calls -- CLAUDE.md build-order step 4 (the metrics half; NPV
and Monte Carlo live on their own page). Built entirely from data/warehouse.duckdb via
app_common.cached_query() -- every number here traces back to the same saved queries
and tag-level provenance the rest of the app already uses."""

from __future__ import annotations

import streamlit as st

from app_common import cached_query

st.set_page_config(page_title="Metrics & Judgment Calls", page_icon="📐", layout="wide")

st.title("Metrics & Judgment Calls")
st.caption("CLAUDE.md build-order step 4 (metrics half). Monte Carlo/NPV is a separate page.")

st.info(
    "**Scope note**: every section below covers all three companies from their full "
    "available history, with EchoStar's pre-2024 data flagged (not hidden) wherever "
    "it appears. But any statement here that treats EchoStar as *comparable* to "
    "Charter/Comcast — not just shown alongside them — is restricted to FY2024 Q1 "
    "onward, since that's when EchoStar's business actually became the combined "
    "Pay-TV/Broadband/Wireless company described in CLAUDE.md. Before that it was "
    "Hughes-broadband-only. See the Home page for the full merger caveat."
)

# --- 1. Revenue growth ----------------------------------------------------------
st.header("1. Revenue growth")
yoy = cached_query("revenue_yoy_growth")
yoy_wide = yoy.pivot(index="period_end", columns="ticker", values="yoy_growth_pct")
st.line_chart(yoy_wide)
st.caption("Year-over-year revenue growth %, all history. See the expander below for quarter-over-quarter.")

with st.expander("Quarter-over-quarter growth instead"):
    qoq = cached_query("revenue_qoq_growth")
    qoq_wide = qoq.pivot(index="period_end", columns="ticker", values="qoq_growth_pct")
    st.line_chart(qoq_wide)

recent_yoy = yoy.groupby("ticker").tail(4)
unreliable_recent = int(recent_yoy["growth_may_be_unreliable"].sum())
st.markdown(
    f"""
**Verdict**: All three companies are shrinking on a year-over-year basis right now —
this isn't one company's problem. Over the last four reported quarters, **EchoStar**
is declining fastest (roughly -4% to -7% YoY, consistent with continued Pay-TV
subscriber losses at DISH/Sling), **Charter** is down a more moderate ~1-2%, and
**Comcast** is the most mixed of the three (from -2.7% to +5.3% quarter to quarter,
roughly flat over the year). None of the last four quarters for any of the three
companies are flagged `growth_may_be_unreliable` — this particular comparison window
sits entirely past EchoStar's 2024 merger recast, so it's a clean read. ({unreliable_recent}
of the last 4 quarters across all three companies are flagged, for reference — flagged
quarters do exist earlier in the series, mostly around EchoStar's 2021-2023
recast years and a couple of early-history date-gap quarters; see the raw query output
for exactly which.)
"""
)

# --- 2. Operating margin --------------------------------------------------------
st.header("2. Operating margin")
margin = cached_query("operating_margin_trend")
margin_wide = margin.pivot(index="period_end", columns="ticker", values="operating_margin_pct")
st.line_chart(margin_wide)
st.caption("operating_income / revenue, all history.")

st.markdown(
    """
**Verdict**: **Charter** runs the highest and steadiest operating margin of the three,
consistently in the low-to-mid 20s% over the last year. **Comcast** runs a lower but
still solidly positive margin, roughly 11-18% over the same period. **EchoStar** is the
outlier and it's a real, disclosed event, not a data error: EchoStar posted an
operating margin of **-460%** in Q3 2025 (operating income of -$16.6B on $3.6B of
revenue) — verified this flows consistently through `NetIncomeLoss`, `ProfitLoss`, and
`ComprehensiveIncomeNetOfTax` too, not an isolated tag, so it's a genuine one-time
charge (almost certainly a large impairment), not an extraction artifact. EchoStar's
margin recovered to positive territory by Q1-Q2 2026 (+10.7%, +14.3%). Reading
EchoStar's margin trend without knowing about that one quarter would be actively
misleading — flagging it here rather than smoothing it out of the chart.
"""
)

# --- 3. Leverage & liquidity -----------------------------------------------------
st.header("3. Leverage & liquidity")
st.caption(
    "Leverage is total_debt divided by **trailing-twelve-month (TTM) revenue** — not "
    "a single quarter's revenue. Dividing an annual-scale balance-sheet figure by one "
    "quarter's revenue overstates the ratio ~4x (verified: Charter's naive "
    "single-quarter debt/revenue comes out at 6.95x, vs. a real 1.73x on a TTM basis)."
)
leverage = cached_query("leverage_and_liquidity")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Net debt (total_debt − cash)")
    net_debt_wide = leverage.pivot(index="period_end", columns="ticker", values="net_debt")
    st.line_chart(net_debt_wide)
with col2:
    st.subheader("Debt / TTM revenue")
    leverage_clean = leverage[~leverage["ttm_window_incomplete"]]
    debt_ratio_wide = leverage_clean.pivot(index="period_end", columns="ticker", values="debt_to_ttm_revenue")
    st.line_chart(debt_ratio_wide)

latest_leverage = leverage.sort_values("period_end").groupby("ticker").tail(1).set_index("ticker")
st.markdown(
    f"""
**Verdict**: **Charter** carries the most leverage of the three at
**{latest_leverage.loc['CHTR', 'debt_to_ttm_revenue']:.2f}x** TTM revenue (net debt
~${latest_leverage.loc['CHTR', 'net_debt'] / 1e9:.1f}B), consistent with its
cable-industry-standard reliance on debt-financed infrastructure buildout.
**Comcast** is the most conservatively levered at
**{latest_leverage.loc['CMCSA', 'debt_to_ttm_revenue']:.2f}x** (net debt
~${latest_leverage.loc['CMCSA', 'net_debt'] / 1e9:.1f}B) — its larger, more diversified
revenue base (theme parks, NBCUniversal content, broadband) supports more debt in
absolute dollars while keeping the ratio lower. **EchoStar** sits in between at
**{latest_leverage.loc['ECHO', 'debt_to_ttm_revenue']:.2f}x**, but that figure reflects
the post-merger combined entity — its balance sheet inherited DISH's debt load in the
Dec 2023 merger, so this isn't directly comparable to any pre-2024 EchoStar figure.
"""
)

# --- 4. Latest-quarter snapshot ---------------------------------------------------
st.header("4. Latest-quarter snapshot")

common_quarters = set(yoy["period_end"]) & set(margin["period_end"]) & set(leverage["period_end"])
latest_common_quarter = max(common_quarters) if common_quarters else None

if latest_common_quarter:
    st.caption(f"Most recent quarter with data for all three companies: **{latest_common_quarter}**.")
    snap_growth = yoy[yoy.period_end == latest_common_quarter].set_index("ticker")["yoy_growth_pct"]
    snap_margin = margin[margin.period_end == latest_common_quarter].set_index("ticker")["operating_margin_pct"]
    snap_leverage = leverage[leverage.period_end == latest_common_quarter].set_index("ticker")
    snapshot = snap_leverage[["net_debt", "debt_to_ttm_revenue"]].copy()
    snapshot.insert(0, "yoy_revenue_growth_pct", snap_growth)
    snapshot.insert(1, "operating_margin_pct", snap_margin)
    st.dataframe(snapshot, width="stretch")
else:
    st.warning("No quarter has data for all three companies across every metric above.")

# --- 5. What this page can't show ------------------------------------------------
st.header("5. What this page can't show")

st.warning(
    "**Subscriber counts, ARPU, churn, CAC, LTV** — not computable from this data at "
    "all, for any period. Confirmed in step 1: zero XBRL tags exist for any of the "
    "three companies matching `subscriber|churn`. That data only exists as prose/"
    "tables inside the filing text, not as structured facts."
)
st.warning(
    "**EBITDA margin, free cash flow, capex intensity, Debt/EBITDA** — not computable "
    "from the *current* warehouse, but unlike the subscriber gap, this one is fixable: "
    "step 1's `extract.py` never pulled the underlying depreciation/amortization, "
    "capex, or operating-cash-flow XBRL tags. Extending the pipeline to pull them is "
    "future work, not a limitation of the data itself."
)
st.warning(
    "**NPV** — deliberately out of scope for this page. See **🎲 Monte Carlo "
    "Simulation** in the sidebar."
)

# --- 6. Overall judgment-call summary ---------------------------------------------
st.header("6. Overall judgment-call summary")
st.markdown(
    """
All three companies are managing a shrinking legacy Pay-TV business, but from
different financial positions. Charter is running the tightest, highest-margin
operation of the three but with the most balance-sheet leverage. Comcast has the
weakest margin of the three yet the most conservative leverage, backed by a larger,
more diversified revenue base outside cable. EchoStar is furthest along in revenue
decline and — following its Dec 2023 merger with DISH — now carries a debt load and
margin profile that only became comparable to the other two starting FY2024; one
quarter of that post-merger data (Q3 2025) includes a real, large one-time charge that
should not be read as an ongoing trend.
"""
)
