# Subscriber Economics Analytics Platform

## Project Purpose
A real-data comparative analysis of EchoStar, Charter Communications, and Comcast —
three genuine competitors in Pay-TV, Broadband, and Wireless (via Charter's Spectrum
Mobile and Comcast's Xfinity Mobile MVNOs). Built as a portfolio piece for analytics/
data science roles at subscriber-based companies.

## Hard Rule
Real data only. No synthetic, fabricated, or third-party pre-collected datasets.
Every number must trace back to a real SEC filing or company disclosure. Where public
data doesn't support subscriber-level detail (none of these three companies publish
it), scope down explicitly and say so — never fake it.

## The Three Companies
- EchoStar (NASDAQ: ECHO, CIK 0001415404) — Pay-TV (DISH/Sling), Wireless (Boost/Gen
  Mobile), Broadband (Hughes)
- Charter Communications (NASDAQ: CHTR) — Spectrum cable TV, broadband, Spectrum
  Mobile
- Comcast (NASDAQ: CMCSA) — Xfinity cable TV, broadband, Xfinity Mobile

## Tech Stack
Python, SQL (SQLite or DuckDB), Streamlit (deployed to Streamlit Community Cloud).
Tableau Public is a separate, manually-built deliverable, not part of this codebase.

## Planned Build Order
1. SEC EDGAR data pipeline (all three companies) — done
2. SQL layer on the cleaned data — done
3. Streamlit app shell, deployed early — CURRENT STEP
4. Metrics/judgment content, NPV + Monte Carlo engine
5. Real-data aggregate model + labeled-synthetic classifier
6. Multi-agent LLM assistant (Simulation Agent + Data Analyst Agent + Orchestrator)
