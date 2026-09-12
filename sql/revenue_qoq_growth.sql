-- Quarter-over-quarter revenue growth % per company (current quarter vs. the
-- immediately preceding quarter). Same LAG-based approach and same date-gap check as
-- revenue_yoy_growth.sql, just with a 1-quarter offset and an 80-100 day tolerance
-- (matching the discrete-quarter window extract.py already uses in step 1) instead of
-- 350-380 -- see that file's header for why the row-contiguity assumption can't be
-- taken for granted and what date_gap_mismatch catches.
WITH ordered AS (
    SELECT
        ticker,
        fiscal_year,
        fiscal_period,
        period_end,
        revenue,
        is_recast,
        has_data_caveat,
        LAG(revenue, 1) OVER (PARTITION BY ticker ORDER BY period_end) AS revenue_prior_quarter,
        LAG(period_end, 1) OVER (PARTITION BY ticker ORDER BY period_end) AS prior_quarter_period_end,
        LAG(is_recast, 1) OVER (PARTITION BY ticker ORDER BY period_end) AS prior_quarter_is_recast,
        LAG(has_data_caveat, 1) OVER (PARTITION BY ticker ORDER BY period_end) AS prior_quarter_has_caveat
    FROM v_quarterly_financials
)
SELECT
    ticker,
    fiscal_year,
    fiscal_period,
    period_end,
    revenue,
    revenue_prior_quarter,
    prior_quarter_period_end,
    (period_end - prior_quarter_period_end) AS days_since_prior_quarter_period,
    ROUND(100.0 * (revenue - revenue_prior_quarter) / revenue_prior_quarter, 1) AS qoq_growth_pct,
    ((period_end - prior_quarter_period_end) NOT BETWEEN 80 AND 100) AS date_gap_mismatch,
    (
        is_recast OR has_data_caveat
        OR prior_quarter_is_recast OR prior_quarter_has_caveat
        OR (period_end - prior_quarter_period_end) NOT BETWEEN 80 AND 100
    ) AS growth_may_be_unreliable
FROM ordered
WHERE revenue IS NOT NULL AND revenue_prior_quarter IS NOT NULL
ORDER BY ticker, period_end;
