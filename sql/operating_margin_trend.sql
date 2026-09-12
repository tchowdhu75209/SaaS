-- Operating margin (operating_income / revenue) per company per quarter, so margin
-- trends can be compared across EchoStar, Charter, and Comcast on one timeline.
-- margin_may_be_unreliable flags any quarter where revenue or operating_income is
-- [RECAST]-flagged or carries a data_caveat (see v_quarterly_financials) -- both
-- inputs to the ratio need to be trustworthy for the margin itself to be.
SELECT
    ticker,
    fiscal_year,
    fiscal_period,
    period_end,
    operating_income,
    revenue,
    ROUND(100.0 * operating_income / revenue, 1) AS operating_margin_pct,
    (is_recast OR has_data_caveat) AS margin_may_be_unreliable
FROM v_quarterly_financials
WHERE revenue IS NOT NULL AND revenue != 0 AND operating_income IS NOT NULL
ORDER BY ticker, period_end;
