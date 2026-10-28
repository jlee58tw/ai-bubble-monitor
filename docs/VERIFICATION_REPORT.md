# Data verification audit + gap fill — 2026-10-28 (Asia/Taipei, UTC+8)

Independent audit of `ai-bubble-monitor`. Each family was re-fetched **fresh from the original source with separate
code** (`scripts/audit/*.py`, plain `urllib`/`curl` + SQL; no `app.providers` / `app.services` imports). Every check row,
with stored value, source value and source URL, is in `docs/verification/<family>.json`. Re-run with e.g.
`cd scripts/audit && ../../.venv/bin/python edgar_check.py`. The Tiingo key is only loaded from `backend/.env` via
`get_settings()`; `token_check.py` confirms (booleans only) that it appears in no tracked file, doc, log or git history.

Network note: the user's computer was offline during this run; all fetches went over the build box's own network.

## 1. Summary of checks

| # | Family | Source re-fetched | Pass | Fail | N/A | Result |
|---|---|---|---:|---:|---:|---|
| 1 | EDGAR CapEx / OCF / revenue (MSFT, GOOGL, AMZN, META, ORCL; latest quarters incl. YTD→quarter, fiscal labels), NVDA data-center revenue 16 quarters incl. Q4 = FY − 9M, FCF, CapEx/OCF, YoY | `data.sec.gov/api/xbrl/companyconcept/...` + filing HTML | 327 | 0 | 0 | PASS (after fixes §2) |
| 2 | TWSE 2330 / 2382 / 2317: 258 daily closes each, P/E, P/B, yield, shares, market cap, 52w drawdown | `www.twse.com.tw/exchangeReport/STOCK_DAY`, `BWIBBU_d`, OpenAPI `t187ap03_L` | 43 | 0 | 1 | PASS (N/A = BWIBBU_ALL ~1-day lag) |
| 3 | Tiingo / FRED: raw + split-adjusted closes (e.g. NVDA 603/603), 52w drawdown, market cap (price × SEC dei shares), 1y relative return vs NDX/SOX | `api.tiingo.com/tiingo/daily/<t>/prices`, `fred.stlouisfed.org/graph/fredgraph.csv`, SEC dei | 83 | 0 | 2 | PASS (N/A = GOOGL/META multi-class market cap not computed) |
| 4 | API pricing OpenAI / Anthropic / Gemini, per 1M tokens, current vs scheduled vs documented_history | `developers.openai.com/api/docs/pricing.md`, `platform.claude.com/docs/en/about-claude/pricing.md`, `ai.google.dev/gemini-api/docs/pricing.md.txt` | 237 | 0 | 5 | PASS (N/A = per-image / per-minute prices correctly not stored as per-1M) |
| 5 | Benchmarks: SWE-bench 323 entries, METR horizons, Terminal-Bench | `raw.githubusercontent.com/SWE-bench/.../leaderboards.json`, `metr.org/assets/benchmark_results_1_1.yaml`, `tbench.ai/leaderboard` | 16 | 0 | 2 | PASS (N/A = Terminal-Bench version label, see caveats) |
| 6 | Azure GPU list / Spot prices (eastus, Linux), per-GPU-hour | `prices.azure.com/api/retail/prices` | 16 | 0 | 1 | PASS |
| 7 | Risk score: every indicator, weights, coverage, point score, range, alerts recomputed from DB + `risk.yaml` | DB + `GET /api/risk`, `/api/alerts`, latest snapshot | 24 | 0 | 0 | PASS |
| 8 | Integrity: duplicates, units, period labels, look-ahead (publication ≥ period end, as-of), freshness vs `max_age_days` | DB | 44 | 0 | 36 | PASS (N/A = informational freshness rows for metrics with no risk max-age) |
| 9 | Gap-fill sources (new) | MOPS CSV, FRED, Anthropic S-1, 8-K EX-99.1, media pages | 34 | 0 | 4 | PASS (N/A = Investing.com returns HTTP 403 to scripts; quotes were checked manually in a browser) |

Example rows (USD unless noted):
* MSFT FY2026 Q2 (Oct–Dec 2025): CapEx 29,876M, OCF 35,758M, revenue 81,273M = SEC companyconcept; FCF 5,882M; CapEx/OCF 0.8355.
* GOOGL / AMZN CY2025 Q4 derived as FY − 9M YTD: GOOGL CapEx 27,851M, AMZN CapEx 39,522M, AMZN revenue 213,386M.
* ORCL CapEx 18,635M is labelled **FY2026 Q3** (Dec 1 2025 – Feb 28 2026), not CY Q1.
* NVDA data-center revenue Q4 = 10-K FY − 9M: FY2026 Q4 = 193,737 − 131,423 = 62,314M (publication date 2026-02-25 = 10-K filing date).
* TWSE 2330 close 2026-10-22 = NT$2,385; 258/258 trading days match.
* TSMC September 2026 revenue NT$511,857,399k; YoY = 511,857,399 / 330,980,920 − 1 = +54.65% (MOPS CSV).
* FRED BAA10Y 1.45 (2026-10-26), DGS2 4.68 (2026-10-26), T10Y2Y 0.29 (2026-10-27): every date since 2026-07-01 matches.

## 2. Discrepancies found and fixed (all with tests, 98 tests pass)

| Problem | Effect | Fix |
|---|---|---|
| NVDA data-center: later filings repeat older quarters as comparatives, and those quarters were stamped with the later filing date | Wrong publication dates (look-ahead / late vintage) | Comparatives-only quarters dropped; first-published filing date kept (filings limit 18) |
| YTD → quarter subtraction across a segment recast mixed old and new definitions | Wrong quarterly values for some segment/YTD rows | Subtraction only within the same filing vintage; bad derived rows retracted with **correction rows dated 2026-10-28** (append-only history kept) |
| Pricing: metadata-only changes (e.g. notes) created new "price" versions | False price-change events | Only numeric price changes create new versions |
| SEC dei shares: filer scaling errors (AMD 2012, ORCL 2012 > 1000× median) | Huge market-cap outliers | Shares-scaling guard rejects them |
| Gemini pricing: per-image / per-minute prices | Could be stored as per-1M tokens | Non-token units excluded |
| Audit scripts (not app data): TWSE 307 throttling, risk coverage rounding, integrity query bugs | False FAILs | Backoff + cache; 4-dp tolerance; fixed queries |

## 3. Gap fill — before / after

Metric registry: **before 31 connected / 2 unavailable / 2 placeholder (35)** → **after 51 connected / 2 unavailable / 0 placeholder (53)**.

Newly available (rows): `tw_monthly_revenue` (15), `tw_monthly_revenue_yoy` (5), `tw_revenue_ytd_yoy` (5),
`cloud_segment_revenue` (59), `cloud_segment_operating_income` (59), `cloud_segment_operating_margin` (50),
`cloud_segment_revenue_yoy` (39), `aws_segment_capex` (6), `us2y_yield` (2,955), `us_10y2y_spread` (2,956),
`baa_10y_spread` (2,950), `ai_lab_revenue` / `ai_lab_compute_cost` / `ai_lab_operating_income` (Anthropic S-1, 6 each,
**disclosed**), `ai_lab_revenue_media` (3), `ai_lab_operating_income_media` (2), `ai_lab_run_rate_media` (2) (all
**estimated / media-reported**), `azure_growth_yoy` (4), `ai_revenue_disclosed` (AMZN 1, **lower bound**),
`capex_guidance` (META, 4 rows in `guidance_items`).

Anthropic S-1 quarterly (USD M): revenue 376 / 787 / 1,382 / 2,040 / 4,731 / 11,555 (Q1'25–Q2'26); compute & infra
944 / 1,390 / 2,047 / 2,945 / 3,387 / 5,558; operating income −935 / −1,200 / −3,089 / −2,836 / −1,667 / +974.
Cross-checks: FY2025 4,585, H1 2025 1,163, H1 2026 16,286 all equal the S-1 annual/six-month table.

META 2026 capex guidance (verbatim 8-K): 115–135B (2026-01-28) → 125–145B (04-29) → 130–145B (07-29) → 135–145B (10-21).
MSFT Azure growth: 40% / 39% / 40% / 43% (quarters ending 2025-09 … 2026-06).

Risk score:

| | Coverage | Point score | Range (missing = 0 / 100) |
|---|---:|---:|---|
| Before (snapshot #3) | 60.0% | 64.07 | 38.44 – 78.44 |
| After (snapshot #4) | **76.7%** | **64.61** | **49.54 – 72.87** |

Newly scored indicators: `tsmc_monthly_revenue` (+54.6% YoY → 88.1), `credit_spreads` (Baa−10Y 1.45 pp → 100, fully
stretched/tight), `ai_lab_compute_intensity` (new; Anthropic compute / revenue Q2'26 = 0.481 → 25.9; single company,
disclosed, research threshold). Still unscored: `ai_capex_disclosed`, `us_ai_forward_pe`, `ai_revenue_disclosed`
(unavailable) and `model_price_deflation` (insufficient: price history only since 2026-10-26).

Still unavailable (and why): see `docs/DATA_SOURCES.md` → "Still unavailable after gap fill" (AI-only capex, forward
P/E, call-only capex guidance, non-AMZN AI revenue, OpenAI financials, ICE BofA OAS, EIA, GOOGL/META market cap).

UI: placeholder pages replaced by `/ai-monetization` and `/credit` (screenshots `docs/screenshot_ai_monetization.png`,
`docs/screenshot_credit.png`).

## 4. Caveats

* Terminal-Bench: URL path says 2.0 but the page payload title is "Terminal-Bench 4.0"; the payload title is stored.
* Anthropic pricing page lists retired models; those are labelled `documented_history`, not current.
* Azure list prices are sticky (e.g. A100 on-demand effective since 2022-06-01); Spot prices move more often.
* ORCL uses a fiscal year ending May; quarters are labelled fiscal (FY2026 Q3 = Dec–Feb).
* TWSE BWIBBU_ALL (P/E, P/B, yield) is ~1 trading day behind closes.
* Segment recasts: older segment rows reflect the definition at first publication; correction rows are dated 2026-10-28.
* Tiingo HTTP 429 seen earlier was resolved by pacing; no data gap remains.
* Media figures are **estimates**; run-rate definitions differ by outlet/company and are not comparable with quarterly revenue.
* S-1 quarterly data is **unaudited** and company-disclosed by a pre-IPO issuer; it may be amended (S-1/A).
* AMZN "exceeded $25B" AI run-rate is a **lower bound**.
* `ai_lab_compute_intensity` and the new thresholds are research hypotheses, not validated signals.
