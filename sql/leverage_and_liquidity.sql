-- Net debt and leverage per company per quarter. Leverage uses trailing-twelve-month
-- (TTM) revenue as the denominator, not a single quarter's revenue -- dividing an
-- annual-scale balance-sheet figure like total_debt by one quarter's revenue
-- overstates the ratio ~4x versus a standard reading (verified: Charter's naive
-- single-quarter debt/revenue comes out at 6.95x; the real leverage picture is a
-- normal single-digit multiple once TTM revenue is used instead).
--
-- Same date-gap-validation pattern as revenue_yoy_growth.sql: SUM(revenue) over the
-- trailing 4 rows only means "trailing 12 months" if there's no missing quarter-row
-- in that window (confirmed real gaps exist for CMCSA/ECHO in 2007-2009 -- see that
-- file's header). ttm_window_incomplete is true whenever the window doesn't actually
-- span ~365 days, including when there simply aren't 4 prior rows yet.
--
-- NOTE: the span check compares the CURRENT row's period_end against the OLDEST
-- included quarter's period_START (not its period_end) -- verified empirically that
-- period_end(t) - period_end(t-3) is only ~273 days (3 quarter-boundaries between
-- four quarter-END dates), not ~365. period_end(t) - period_start(t-3) is the correct
-- measure of "does this window actually cover 12 months of revenue."
WITH ttm AS (
    SELECT
        ticker,
        period_end,
        total_debt,
        cash,
        is_recast,
        has_data_caveat,
        SUM(revenue) OVER (
            PARTITION BY ticker ORDER BY period_end
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ) AS revenue_ttm,
        COUNT(revenue) OVER (
            PARTITION BY ticker ORDER BY period_end
            ROWS BETWEEN 3 PRECEDING AND CURRENT ROW
        ) AS revenue_ttm_n,
        period_end - LAG(period_start, 3) OVER (PARTITION BY ticker ORDER BY period_end)
            AS ttm_window_days
    FROM v_quarterly_financials
)
SELECT
    ticker,
    period_end,
    total_debt,
    cash,
    (total_debt - cash) AS net_debt,
    ROUND(total_debt / revenue_ttm, 2) AS debt_to_ttm_revenue,
    (
        revenue_ttm_n < 4
        OR ttm_window_days IS NULL
        OR ttm_window_days NOT BETWEEN 350 AND 380
    ) AS ttm_window_incomplete,
    (is_recast OR has_data_caveat) AS leverage_may_be_unreliable
FROM ttm
WHERE total_debt IS NOT NULL
ORDER BY ticker, period_end;
