# Data sources — Phases 1–3

Connectivity was tested from the build host on **2026-10-27 (Asia/Taipei, UTC+8)**. Re-test before relying on this list.
Phase 2 sources are listed first; the Phase 1 sections below are kept and updated.

## Phase 3 — added (verified live 2026-10-28, UTC+8)

| Source | Endpoint | What | Terms / access notes |
|---|---|---|---|
| SEC EDGAR submissions API | `https://data.sec.gov/submissions/CIK##########.json` | `filing_events`: 10-Q/10-K/20-F/40-F (+/A) and 8-K with Item 2.02 for MSFT, AMZN, GOOGL, META, ORCL, NVDA, AMD, TSM. `reportDate` = observation date, `filingDate` = publication date, `acceptanceDateTime` (UTC). 360 events stored on 2026-10-28. | SEC fair-access policy: `SEC_USER_AGENT` with contact e-mail, 2 req/s (limit 10). **Only the `filings.recent` block** (latest ~1,000 filings of any form) is read, so the earliest stored event differs per company (e.g. GOOGL 2023-07, META 2024-07, ORCL 2016); older `filings.files` pages are not fetched. |
| Guidance | — | **Placeholder.** No guidance source is connected; 8-K earnings releases are listed but not parsed. Rows can only be stored with a source URL and verbatim quote. | — |
| TWSE / MOPS filing calendar | — | **Not connected** (2330, 2382, 2317 show UNAVAILABLE on /events). | — |
| Backtest outcomes | stored `tw_price_close` (TWSE STOCK_DAY) | ~13 months of daily closes for 2330/2382/2317; US prices unavailable without `TIINGO_API_KEY` / `ALPHAVANTAGE_API_KEY`. | No new fetches; uses stored data only. |

## US price options (researched and tested 2026-10-28, Asia/Taipei)

| Option | Works without key? | Free tier | Terms for this use | History | Result from build host |
|---|---|---|---|---|---|
| **FRED fredgraph CSV** (`NASDAQ100`, `NASDAQCOM`, `NASDAQSOX`) | **Yes** | robots.txt `Crawl-delay: 1` (respected: 1 req/s) | Allowed; series © Nasdaq, Inc. — personal research with attribution | NDX from 1986, SOX from 2004 (stored from 2015) | **Connected.** NDX 29,651.44 / COMP 26,477.81 / SOX 11,482.51 on 2026-10-27 |
| **Tiingo** EOD (`/tiingo/daily/<t>/prices`) | No — free key | 50 req/h, 1,000 req/day, 500 symbols/month | Free plan = personal / internal use | 30+ years; raw close + adjClose + splitFactor | **Implemented (optional, `TIINGO_API_KEY`)**; verified with synthetic payloads only ("Please supply a token" without key) |
| Alpha Vantage | No — free key | 25 req/day | Free key | Compact ≈100 sessions (full history premium) | Already implemented as alternative |
| Twelve Data | No (demo key = AAPL only) | 800 credits/day, 8/min | Free = internal, **non-display** use | — | NVDA with demo key → 401 |
| Finnhub | No | 60 calls/min | Personal | Daily candles are premium → no history | Not usable |
| Polygon.io / Massive | No | 5 calls/min | Individual non-professional | 2 years | Too short for 10y; not used |
| Financial Modeling Prep | No | 250 calls/day | Display/redistribution needs a separate licence | 5 years (free) | Not used |
| EODHD | No | 20 calls/day | — | 1 year (free) | Not used |
| marketstack | No | 100 requests/month | Non-commercial | 1 year (free) | Not used |
| Stooq CSV | — | — | **robots.txt `Disallow: /`** for all agents + JS proof-of-work challenge | — | **Rejected** |
| api.nasdaq.com | Returns data | — | **nasdaq.com legal terms prohibit automated/manual data capture** | — | **Rejected** |
| Nasdaq Data Link | — | — | No free current US equity EOD dataset | — | Blocked / HTML |
| Yahoo Finance chart API | Returns data | — | Unofficial endpoint, ToS | — | **Rejected** (Phase 1) |

Implementation notes: Tiingo raw `close` is stored (`reported`), `splitFactor` stored on split days only; `us_price_split_adj`
divides by later splits (not dividend-adjusted → price return, consistent with the FRED price-return indices and free of mass
revisions after every dividend). Market cap = raw close × latest SEC `dei:EntityCommonStockSharesOutstanding` dated ≤ price date
(≤120 days old; TSM ≤400 days from the annual 20-F, ÷5 per ADR), times splits between the share date and the price date. SOXX tracks
the NYSE Semiconductor Index (not SOX), so relative performance is measured against the actual SOX index from FRED.

## Phase 2 — connected (verified live 2026-10-27, UTC+8)

| Source | Endpoint | What | Terms / access notes |
|---|---|---|---|
| TWSE OpenAPI | `https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL`, `/v1/opendata/t187ap03_L` | `tw_pe_trailing`, `tw_pb_ratio`, `tw_dividend_yield` (exchange-computed, **trailing**), `tw_shares_outstanding` for 2330, 2382, 2317 | Government open data licence (政府資料開放授權條款). |
| TWSE STOCK_DAY | `https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=YYYYMM01&stockNo=XXXX` | `tw_price_close` (13 months daily) | Same licence; TWSE blocks bursts, so requests are spaced `TWSE_MIN_INTERVAL_S` (default 3 s). |
| Derived | — | `tw_market_cap` = close × listed shares (nearest shares date ≤45 d); `tw_drawdown_52w` = close / max(close, trailing 52 w) − 1 (needs ≥358 days of history) | classification `derived`. |
| SEC filing XBRL instances | `https://www.sec.gov/Archives/edgar/data/<cik>/<acc>/<doc>_htm.xml` (via `data.sec.gov/submissions`) | `nvda_datacenter_revenue` — dimensional fact `us-gaap:Revenues` × `srt:ProductOrServiceAxis=nvda:DataCenterMember`, last `SEC_FILINGS_LIMIT` (12) 10-Q/10-K | SEC fair-access UA + rate limit. Q4 = FY − Q1..Q3 (`derived`). |
| Alpha Vantage | `TIME_SERIES_DAILY` (compact) | `us_price_close`, `us_drawdown_52w` for NVDA, AMD, MSFT, GOOGL, AMZN, META, ORCL, TSM | **Optional free key** `ALPHAVANTAGE_API_KEY`. Not set on the build host → shown as **UNAVAILABLE**, nothing estimated. Compact = ~100 sessions, so 52-week drawdown stays insufficient unless more history accumulates. |
| OpenAI pricing (markdown docs) | `https://developers.openai.com/api/docs/pricing.md` | model list prices (input / cached input / output, USD per 1M tokens) | Public docs page, robots-allowed. |
| Anthropic pricing (markdown docs) | `https://platform.claude.com/docs/en/about-claude/pricing.md` | same; plus one `documented_history` row where the docs state a past price | Public docs page. |
| Google Gemini pricing | `https://ai.google.dev/gemini-api/docs/pricing.md.txt` | same, including `scheduled` future prices stated on the page | robots.txt allows `/`. (`.md` returns HTML; `.md.txt` is the markdown.) |
| OpenRouter models API | `https://openrouter.ai/api/v1/models` | representative **open-weight hosted** prices (models with a Hugging Face id) | Public, documented API, no key. |
| SWE-bench leaderboard | `https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/master/data/leaderboards.json` | resolved % per leaderboard split (lite/verified/test/multimodal/multilingual…) | Public GitHub data behind swebench.com. |
| METR time horizons | `https://metr.org/assets/benchmark_results_1_1.yaml` | p50 / p80 horizon minutes + CI, METR-Horizon-v1.1; doubling time | Public file linked from metr.org/time-horizons. Values >16 h flagged with METR's reliability note. |
| Terminal-Bench leaderboard | `https://www.tbench.ai/leaderboard/terminal-bench/2.0` | accuracy + CI, version read from page payload (currently "Terminal-Bench 4.0") | Public page; parser raises if the layout changes (never guesses). |
| Azure Retail Prices API | `https://prices.azure.com/api/retail/prices` | GPU VM list prices (pay-as-you-go + Spot, Linux, eastus): H100 (ND96isr_H100_v5, NC40ads_H100_v5), A100 (ND96amsr_A100_v4, NC24ads_A100_v4) | Public, unauthenticated, documented by Microsoft for programmatic use. |

Refresh: `python -m app.cli datasets` (pricing, benchmarks, GPU; one IngestionRun per source) and `python -m app.cli refresh` (TWSE, SEC, FRED, AV). Weekly scheduler job `DATASETS_CRON` (default Sun 23:00 UTC = Mon 07:00 Asia/Taipei) also stores a risk snapshot.
Datasets are append-only: unchanged values only bump `last_seen_at`; a changed price/score is a new row with `supersedes_id`.

## Unavailable metrics (complete list, Phase 2)

| Metric | Status | Why |
|---|---|---|
| US prices / drawdown / relative return (`us_price_close`, `us_drawdown_52w`, `us_rel_return_1y_vs_*`) | **unavailable unless `TIINGO_API_KEY` (or `ALPHAVANTAGE_API_KEY`) is set** | No keyless, terms-compliant per-stock source (see US price options below). Index level/drawdown from FRED is connected. |
| US market cap (`market_cap`) | **unavailable without a price key**; GOOGL/META always unavailable | Derived from price × SEC cover-page shares; GOOGL/META share counts are only dimensional (per-class) facts. |
| Forward P/E (`forward_pe`) — all 11 tickers | **unavailable** | Consensus EPS estimates are licensed (FactSet/LSEG/S&P/Bloomberg). Trailing P/E is NOT substituted. |
| AI-specific capex (`ai_capex_disclosed`) | **unavailable** | Not tagged by any company. |
| AI revenue (`ai_revenue_disclosed`), capex guidance (`capex_guidance`) | **placeholder** | Qualitative, from calls/press releases. |
| TSMC monthly revenue | **unavailable** (risk indicator) | Not ingested in Phase 2. |
| Credit spreads (HY / data-center debt) | **unavailable** | ICE BofA series on FRED carry licence restrictions. |
| GPU marketplace / neocloud rental prices | **placeholder** | No marketplace with terms that clearly permit automated collection. Only hyperscaler list prices (Azure) are shown — they are sticky (H100 list price unchanged since 2023-12) and not market-clearing. |
| Azure H200 (ND96isr_H200_v5) and MI300X (ND96isr_MI300X_v5) | **not offered in eastus** | API returns no rows; not imputed. |
| Model price deflation (risk indicator) | **insufficient** | Needs ≥90 days of own observations and ≥3 changes; undocumented historical prices are never back-filled. |
| EIA power data | **unavailable** | HTTP 403 + key. |

## Phase 1 — connected (real, working, ingested)

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

## Phase 1 — unavailable / placeholder (updated)

| Item | Status | Reason |
|---|---|---|
| AI-specific capex (`ai_capex_disclosed`) | **unavailable** | No company tags AI-only capex in XBRL. Total capex is never relabeled as AI capex. |
| US market cap (`market_cap`) | **unavailable** | See Phase 2 table above. |
| EIA (power/electricity) | **unavailable** | `api.eia.gov` returned HTTP 403 from the host (also needs an API key). |
| Capex guidance (`capex_guidance`) | **placeholder** | Guidance is given on earnings calls / press releases, not in XBRL. Would be `guidance` classification, manual/LLM-assisted entry. |
| AI revenue disclosures (`ai_revenue_disclosed`) | **placeholder** | Qualitative, from earnings calls. |
| UI pages: AI Monetization, Credit/Funding | **placeholder** | Labeled `[PH]`; show no numbers. (Valuation and Supply Chain became real pages in Phase 2.) |

## Known limitations

1. **Total ≠ AI capex.** `capex_total` = cash purchases of PP&E (`PaymentsToAcquirePropertyPlantAndEquipment`, or `PaymentsToAcquireProductiveAssets` for AMZN/NVDA). It is the whole company's spend.
2. **Finance leases are excluded.** MSFT, ORCL and META add large data-center capacity via finance leases that do not appear in cash capex. True infrastructure commitment is therefore *understated*.
3. **Quarterly values are partly derived.** 10-Q cash-flow statements are year-to-date. Q2/Q3/Q4 are computed as YTD(n) − YTD(n−3m) and labeled `derived` (confidence `medium`) unless the filer reports a discrete 3-month value. Amazon's trailing-twelve-month figures are ignored.
4. **Point-in-time.** `publication_date` = SEC filed date. A derived quarter's publication date is the later of its two inputs. Revisions (e.g. a later 10-K restating a value) are stored as new versions with `supersedes_id`; old rows are never modified.
5. **FRED has no vintage history here.** `publication_date` for DGS10 ≈ observation date (ALFRED not used).
6. **Fiscal calendars differ.** MSFT FY ends June, ORCL May, NVDA late January; the others are calendar years. Cross-company sums (`capex_total_big4_cal`) use only MSFT/GOOGL/AMZN/META with identical calendar quarter-ends.
7. **Missing data is never zero risk.** Unavailable or missing series are shown explicitly as UNAVAILABLE / MISSING / NO DATA and are never zero-filled.
8. **Backtest limits.** Point-in-time reconstruction is only as good as stored publication dates: FRED DGS10 publication ≈ observation date (no ALFRED vintages); TWSE P/E is a single recent snapshot (no history), and 52-week drawdown exists only from 2026-09; dataset-based indicators have no pre-collection history. Outcome history is ~13 months for 3 TWSE stocks (~12 independent 20-day windows) — results are descriptive only.

## ROI simulator

`/roi` and `GET /api/roi` use **no external data**: every input is a user scenario value. Formulas and the modeling assumptions for Expected Rework Cost / Expected Failure Loss are in the README ("ROI simulator"). Benchmark top scores appear on the page only as labeled references.
