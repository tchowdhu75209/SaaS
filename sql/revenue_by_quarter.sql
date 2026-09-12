-- Raw quarterly revenue per company (no growth math), for the Streamlit Home page's
-- overview chart and raw-data browser. is_recast/has_data_caveat are carried through
-- so the chart/table can flag which points fall in EchoStar's pre-2024 recast era
-- rather than presenting them as clean, directly comparable numbers.
SELECT ticker, period_end, revenue, is_recast, has_data_caveat
FROM v_quarterly_financials
WHERE revenue IS NOT NULL
ORDER BY ticker, period_end;
