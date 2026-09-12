-- Turns the step-1 data-integrity work (tag fallbacks, Q4 derivation, [RECAST]
-- flagging, the EchoStar merger caveat) into a queryable per-company summary, instead
-- of something only visible in the build-csv log output.
SELECT
    ticker,
    COUNT(*) AS total_quarters,
    SUM(CASE WHEN is_recast THEN 1 ELSE 0 END) AS recast_quarters,
    SUM(CASE WHEN is_derived_q4 THEN 1 ELSE 0 END) AS derived_q4_quarters,
    SUM(CASE WHEN has_data_caveat THEN 1 ELSE 0 END) AS caveated_quarters,
    SUM(CASE WHEN revenue IS NULL THEN 1 ELSE 0 END) AS missing_revenue,
    SUM(CASE WHEN total_debt IS NULL THEN 1 ELSE 0 END) AS missing_total_debt,
    MIN(period_end) AS earliest_quarter,
    MAX(period_end) AS latest_quarter
FROM v_quarterly_financials
GROUP BY ticker
ORDER BY ticker;
