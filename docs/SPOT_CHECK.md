# Spot checks against SEC EDGAR (2026-10-27, Asia/Taipei)

Values ingested by the pipeline were compared to independent EDGAR sources (SEC frames API, companyconcept API, and the filed 10-Q HTML).

| Check | Pipeline value | EDGAR reference | Result |
|---|---|---|---|
| AMZN capex, CY2026 Q2 | $54,208M (reported) | frames API `PaymentsToAcquireProductiveAssets/USD/CY2026Q2` = 54,208M | ✅ |
| AMZN OCF, CY2026 Q2 | $45,387M | frames API `NetCashProvidedByUsedInOperatingActivities/USD/CY2026Q2` = 45,387M | ✅ |
| MSFT capex FY2026 Q4 (Apr–Jun 2026) | $35,802M (derived) | companyconcept: FY26 12M 115,948M − 9M 80,146M = 35,802M | ✅ |
| META capex 2026 Q3 | $33,942M (derived) | 10-Q `meta-20260930.htm`: 9M 2026 = 83,055M. Prior-year 9M 2025 = 48,308M = our derived 12,941 + 16,538 + 18,829 | ✅ |
| GOOGL capex 2026 Q2 | $44,924M (derived) | 10-Q `goog-20260630.htm`: 6M 2026 = 80,598M = 35,674 + 44,924; 6M 2025 = 39,643M = 17,197 + 22,446 | ✅ |
| Known 2025 figures | MSFT 16,745 / 17,079M; AMZN Q1-25 25,019M; ORCL FY26 Q1 8,502M | Match published filings | ✅ |

Re-run: start the API, then compare `/api/observations?metric_id=capex_total&entity_id=AMZN` with
`https://data.sec.gov/api/xbrl/frames/us-gaap/PaymentsToAcquireProductiveAssets/USD/CY2026Q2.json` (send a User-Agent).
