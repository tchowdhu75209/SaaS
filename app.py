"""Home/Overview page -- the Streamlit app's entry point."""

from __future__ import annotations

import streamlit as st

from app_common import cached_query

st.set_page_config(page_title="Subscriber Economics Analytics", page_icon="📡", layout="wide")

st.title("Subscriber Economics Analytics Platform")
st.caption(
    "A real-data comparative analysis of EchoStar, Charter Communications, and "
    "Comcast — three genuine competitors in Pay-TV, Broadband, and Wireless (via "
    "Charter's Spectrum Mobile and Comcast's Xfinity Mobile MVNOs). Built as a "
    "portfolio piece for analytics/data science roles at subscriber-based companies."
)

st.info(
    "**Hard rule**: real data only. No synthetic, fabricated, or third-party "
    "pre-collected datasets. Every number on this page traces back to a real SEC "
    "filing via SEC EDGAR's XBRL API — see the callouts below for where that data "
    "runs into real limitations."
)

# --- The three companies ------------------------------------------------------
st.subheader("The three companies")
companies = cached_query("companies_overview")
st.dataframe(companies, hide_index=True, width="stretch")

# --- Revenue over time ---------------------------------------------------------
st.subheader("Quarterly revenue, all three companies")
revenue = cached_query("revenue_by_quarter")
revenue_wide = revenue.pivot(index="period_end", columns="ticker", values="revenue")
st.line_chart(revenue_wide)
st.caption(
    "Revenue in USD, one line per ticker. EchoStar's series before 2024 sits on a "
    "different accounting basis than its 2024-onward figures — see the caveat below "
    "before reading trend across that boundary."
)

# --- Data quality summary ------------------------------------------------------
st.subheader("Data quality summary")
st.caption(
    "Turns the tag-fallback, Q4-derivation, and recast-detection work from steps 1-2 "
    "into a queryable summary instead of something only visible in build logs."
)
quality = cached_query("data_quality_summary")
st.dataframe(quality, hide_index=True, width="stretch")

echo_row = quality.loc[quality.ticker == "ECHO"].iloc[0]
chtr_row = quality.loc[quality.ticker == "CHTR"].iloc[0]
recast_total = int(quality["recast_quarters"].sum())

col1, col2 = st.columns(2)
with col1:
    st.warning(
        f"**No subscriber or churn data.** None of the three companies tag "
        f"subscriber counts or churn in XBRL — confirmed by searching every "
        f"taxonomy in all three companies' real SEC filings for anything matching "
        f"`subscriber|churn` (zero hits). The `subscribers` column exists in this "
        f"data and is always null, rather than silently dropped."
    )
with col2:
    st.warning(
        f"**EchoStar's Dec 2023 DISH merger is a structural break, not a "
        f"data-quality bug.** {int(echo_row['caveated_quarters'])} of "
        f"{int(echo_row['total_quarters'])} EchoStar quarters (everything before "
        f"2024) predate the merger and may sit on a different accounting basis than "
        f"the current combined entity. {recast_total} quarters across all three "
        f"companies ({int(chtr_row['recast_quarters'])} Charter, "
        f"{int(echo_row['recast_quarters'])} EchoStar) are flagged `[RECAST]` where "
        f"a value swung ≥2x between filings. Real multi-company comparison is only "
        f"meaningful from FY2024 Q1 onward."
    )

# --- Raw data browser -----------------------------------------------------------
with st.expander("Browse the raw quarterly revenue data"):
    st.dataframe(revenue, hide_index=True, width="stretch")

st.divider()
st.caption(
    "Built from SEC EDGAR's XBRL companyfacts API — see README.md for the full "
    "tag-mapping table and data caveats. Steps 4-6 (Metrics & Judgment Calls, Monte "
    "Carlo Simulation, Predictive Models, LLM Assistant) are placeholders for now — "
    "see the sidebar."
)
