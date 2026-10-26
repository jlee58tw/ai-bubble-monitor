# Data sources — Phase 1

Connectivity was tested from the build host on **2026-10-27 (Asia/Taipei, UTC+8)**. Re-test before relying on this list.

## Connected (real, working, ingested)

| Source | Endpoint | Metrics | Notes |
|---|---|---|---|
| SEC EDGAR XBRL companyfacts | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | `capex_total`, `operating_cash_flow`, `revenue` for MSFT, GOOGL, AMZN, META, ORCL, NVDA | Free, official. Requires `SEC_USER_AGENT` env var ("App name contact@email"). Throttled to `SEC_MAX_RPS` (default 5, hard cap 10 req/s) with retry/backoff on 429/5xx. |
| FRED (St. Louis Fed) | `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10` | `us10y_yield` | No key needed for the CSV endpoint. Slow at times (>20 s), 60 s timeout used. |
| Derived (in-house) | — | `fcf`, `capex_to_revenue`, `capex_to_ocf`, `*_yoy`, `capex_total_big4_cal(_yoy)` | Computed only from the connected series above; classification `derived`. |

## Reachable but deliberately NOT used

| Source | Result | Why not used |
|---|---|---|
| Yahoo Finance chart API (`query1.finance.yahoo.com`) | HTTP 200 | Unofficial, undocumented endpoint; Terms of Service do not permit this kind of use. Market cap / valuation therefore stays **unavailable**. |
| SEC `frames` / `companyconcept` / `submissions` / `www.sec.gov/Archives` | HTTP 200 (with UA) | Used only for manual spot checks (see `SPOT_CHECK.md`), not for ingestion. |

## Unavailable / placeholder

| Item | Status | Reason |
|---|---|---|
| NVIDIA Data Center segment revenue (`nvda_datacenter_revenue`) | **unavailable** | Disclosed only as a dimensional XBRL fact (segment axis). companyfacts returns non-dimensional facts only. Needs a filing-level XBRL instance parser (Phase 2). |
| AI-specific capex (`ai_capex_disclosed`) | **unavailable** | No company tags AI-only capex in XBRL. Total capex is never relabeled as AI capex. |
| Market cap / prices (`market_cap`) | **unavailable** | Stooq returned a JavaScript challenge page; Alpha Vantage requires an API key (only `demo` works); Yahoo is unofficial (see above). |
| EIA (power/electricity) | **unavailable** | `api.eia.gov` returned HTTP 403 from the host (also needs an API key). |
| Capex guidance (`capex_guidance`) | **placeholder** | Guidance is given on earnings calls / press releases, not in XBRL. Would be `guidance` classification, manual/LLM-assisted entry. |
| AI revenue disclosures (`ai_revenue_disclosed`) | **placeholder** | Qualitative, from earnings calls. |
| UI pages: AI Monetization, Valuation, Semis/Supply Chain, Credit/Funding | **placeholder** | Labeled `[PH]`; show no numbers. |

## Known limitations

1. **Total ≠ AI capex.** `capex_total` = cash purchases of PP&E (`PaymentsToAcquirePropertyPlantAndEquipment`, or `PaymentsToAcquireProductiveAssets` for AMZN/NVDA). It is the whole company's spend.
2. **Finance leases are excluded.** MSFT, ORCL and META add large data-center capacity via finance leases that do not appear in cash capex. True infrastructure commitment is therefore *understated*.
3. **Quarterly values are partly derived.** 10-Q cash-flow statements are year-to-date. Q2/Q3/Q4 are computed as YTD(n) − YTD(n−3m) and labeled `derived` (confidence `medium`) unless the filer reports a discrete 3-month value. Amazon's trailing-twelve-month figures are ignored.
4. **Point-in-time.** `publication_date` = SEC filed date. A derived quarter's publication date is the later of its two inputs. Revisions (e.g. a later 10-K restating a value) are stored as new versions with `supersedes_id`; old rows are never modified.
5. **FRED has no vintage history here.** `publication_date` for DGS10 ≈ observation date (ALFRED not used).
6. **Fiscal calendars differ.** MSFT FY ends June, ORCL May, NVDA late January; the others are calendar years. Cross-company sums (`capex_total_big4_cal`) use only MSFT/GOOGL/AMZN/META with identical calendar quarter-ends.
7. **Missing data is never zero risk.** Unavailable or missing series are shown explicitly as UNAVAILABLE / MISSING / NO DATA and are never zero-filled.
