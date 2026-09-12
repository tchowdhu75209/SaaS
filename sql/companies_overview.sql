-- The three companies tracked by this project -- used by the Streamlit app's Home
-- page. Trivial on its own, but kept as a saved query (not inlined in Python) so
-- every query the app runs stays in one place, same as the rest of sql/.
SELECT ticker, name, cik
FROM companies
ORDER BY ticker;
