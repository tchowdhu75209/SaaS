-- Year-over-year revenue growth % per company per quarter (current quarter vs. the
-- same quarter one year earlier). Uses LAG(revenue, 4) partitioned by ticker and
-- ordered by period_end, meaning "4 rows back" -- which is only actually "4 quarters
-- back" if there's no missing quarter-ROW in between.
--
-- That assumption does NOT hold everywhere: CMCSA and ECHO both have real gaps in
-- 2007-2009 (a quarter with zero data under any tag, so no row was ever produced for
-- it in step 1 -- confirmed via
--   SELECT period_end - LAG(period_end) OVER (...) FROM quarterly_financials
-- which turns up >100-day jumps for both). After a gap, "4 rows back" can land on a
-- quarter that isn't actually a year prior, which would silently compute a nonsense
-- growth number if left unchecked. So this query also computes the actual calendar
-- gap (prior_period_end, days_since_prior_year_period) and sets date_gap_mismatch
-- whenever that gap isn't ~365 days (tolerance 350-380, matching the annual-duration
-- tolerance extract.py already uses in step 1) -- the number is still shown, never
-- hidden, but flagged so it's never mistaken for a clean same-quarter comparison.
--
-- growth_may_be_unreliable is true if EITHER endpoint is [RECAST]-flagged or carries
-- a data_caveat, OR the date-gap check above fails.
WITH ordered AS (
    SELECT
        ticker,
        fiscal_year,
        fiscal_period,
        period_end,
        revenue,
        is_recast,
        has_data_caveat,
        LAG(revenue, 4) OVER (PARTITION BY ticker ORDER BY period_end) AS revenue_prior_year,
        LAG(period_end, 4) OVER (PARTITION BY ticker ORDER BY period_end) AS prior_year_period_end,
        LAG(is_recast, 4) OVER (PARTITION BY ticker ORDER BY period_end) AS prior_year_is_recast,
        LAG(has_data_caveat, 4) OVER (PARTITION BY ticker ORDER BY period_end) AS prior_year_has_caveat
    FROM v_quarterly_financials
)
SELECT
    ticker,
    fiscal_year,
    fiscal_period,
    period_end,
    revenue,
    revenue_prior_year,
    prior_year_period_end,
    (period_end - prior_year_period_end) AS days_since_prior_year_period,
    ROUND(100.0 * (revenue - revenue_prior_year) / revenue_prior_year, 1) AS yoy_growth_pct,
    ((period_end - prior_year_period_end) NOT BETWEEN 350 AND 380) AS date_gap_mismatch,
    (
        is_recast OR has_data_caveat
        OR prior_year_is_recast OR prior_year_has_caveat
        OR (period_end - prior_year_period_end) NOT BETWEEN 350 AND 380
    ) AS growth_may_be_unreliable
FROM ordered
WHERE revenue IS NOT NULL AND revenue_prior_year IS NOT NULL
ORDER BY ticker, period_end;
