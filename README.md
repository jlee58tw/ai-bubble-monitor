# AI Bubble Monitor — Phase 1 + Phase 2

A research dashboard asking one question: **is AI monetization keeping up with AI capex?**
Phase 1 is a vertical slice: hyperscaler capex, revenue, operating cash flow and FCF from **SEC EDGAR**, plus the
US 10Y yield from **FRED**. Everything else is shown as explicitly *unavailable* or *placeholder*.

**Phase 2** adds: Taiwan AI supply-chain valuation from TWSE open data (price, trailing P/E, P/B, yield, derived market cap and
52-week drawdown), NVIDIA Data Center revenue from SEC filing XBRL, optional US prices via Alpha Vantage (free key), model API
list prices (OpenAI, Anthropic, Gemini, OpenRouter open-weight), agent benchmarks (SWE-bench, METR time horizon, Terminal-Bench,
never merged across benchmarks), Azure GPU list prices, a six-dimension **risk score** with coverage and ranges, a methodology
page, a reliability **ROI simulator**, and in-app **alerts**. Full source list and unavailable metrics: [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

> Research only, not a trading tool and not investment advice.

## Data rules (enforced in code and UI)

- **No fabricated data.** If a source is unavailable, the metric is registered with `status: unavailable` and the UI says so.
- Every observation carries a **classification**: `reported | guidance | estimated | derived | qualitative`, plus `confidence`, `source_url`, `publication_date` (point-in-time) and `methodology`.
- **Missing ≠ zero risk.** Gaps are never zero-filled; charts break, and cards show MISSING / UNAVAILABLE.
- **Total company capex is not AI capex.** `capex_total` has `is_ai_specific: false` and a warning everywhere it's shown.
- **Append-only history.** A changed value is a new row (`version + 1`, `supersedes_id` → previous row). Rows are never updated or deleted. `as_of=` queries reconstruct what was known on a date.

See [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) for connected vs unavailable sources and limitations, and [`docs/SPOT_CHECK.md`](docs/SPOT_CHECK.md) for verification against EDGAR.

## Quick start (local)

```bash
cp .env.example backend/.env          # then edit: SEC_USER_AGENT="YourApp you@yourdomain.com" (required by SEC)
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt

cd backend
alembic upgrade head                   # creates ./data/aibm.db (SQLite)
python -m app.cli refresh              # ingest SEC EDGAR + FRED, then compute derived metrics (~10 s)
uvicorn app.main:app --port 8000       # API at http://localhost:8000/docs

cd ../frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run build && npm start   # or: npm run dev
# open http://localhost:3000
```

CLI options: `python -m app.cli refresh --provider sec_edgar --entity MSFT`.

Phase 2 CLI:
```bash
python -m app.cli refresh --provider twse        # TWSE prices/valuation (spaced 3 s per request; ~2 min)
python -m app.cli refresh --provider sec_filing_xbrl   # NVDA Data Center revenue
python -m app.cli datasets                       # model pricing + benchmarks + Azure GPU prices (or --source pricing_google ...)
python -m app.cli risk                           # compute and store a risk snapshot
```

Tests: `cd backend && pytest -q`. They are offline and use recorded companyfacts fixtures plus a mocked HTTP transport.

### Docker Compose

```bash
cp .env.example .env    # set SEC_USER_AGENT
docker compose up --build
docker compose exec api python -m app.cli refresh
```

SQLite lives on the `aibm-data` volume. For Postgres, set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/aibm` (psycopg is included).
*Note: the compose files were written but **not run**: Docker is not available on the build host (Phase 1 and Phase 2).*

## Configuration (env)

| Var | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/aibm.db` | Any SQLAlchemy URL |
| `SEC_USER_AGENT` | — (**required**) | SEC fair-access UA, must include a contact email; SEC ingestion refuses to run without it |
| `SEC_MAX_RPS` | 5 | SEC request rate, hard-capped at 10 |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated |
| `SCHEDULER_ENABLED` / `SCHEDULER_CRON` | false / `30 22 * * *` (UTC) | APScheduler daily refresh |
| `LOG_LEVEL`, `LOG_JSON` | INFO, true | structlog JSON logs |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | API URL as seen by the browser (inlined at build time) |
| `TWSE_HISTORY_MONTHS` / `TWSE_MIN_INTERVAL_S` | 13 / 3 | TWSE daily history depth and request spacing |
| `ALPHAVANTAGE_API_KEY` | — | Optional free key for US prices; unset = UNAVAILABLE |
| `SEC_FILINGS_LIMIT` | 12 | Recent 10-Q/10-K instances parsed for dimensional facts |
| `RISK_MIN_COVERAGE` | — (uses `risk.yaml`, 0.5) | Below this weighted coverage the overall score is withheld |
| `DATASETS_CRON` | `0 23 * * 0` (UTC) | Weekly datasets refresh + risk snapshot (needs `SCHEDULER_ENABLED=true`) |

## API

| Method | Path | |
|---|---|---|
| GET | `/api/health` | liveness + whether a refresh is running |
| GET | `/api/metrics`, `/api/entities` | registry with status (connected/unavailable/placeholder), warnings, row counts |
| GET | `/api/observations` | filters: `metric_id`, `entity_id` (comma lists), `start`, `end`, `classification`, `as_of`, `include_history`, `limit` |
| GET | `/api/observations.csv` | same filters, CSV download |
| POST | `/api/refresh?provider=` | manual refresh (202, runs in background; 409 if one is already running) |
| GET | `/api/ingestion/status` | provider status + per-series freshness (fresh/stale/missing/unavailable/placeholder) |
| GET | `/api/ingestion/runs`, `/api/ingestion/errors` | run log and error log |
| GET | `/api/overview` | dashboard cards (current, previous, abs/% change, source, confidence) |
| GET | `/api/model-prices`, `/api/model-prices/changes`, `/api/model-prices/history` | model API prices (`vendor`, `open_weight`, `q`), observed/scheduled/documented changes |
| GET | `/api/benchmarks` | benchmark groups keyed by (benchmark, version, split, metric) — never merged |
| GET | `/api/gpu-prices` | Azure GPU list prices + explicit placeholders |
| GET / POST | `/api/datasets/status`, `/api/datasets/counts`, `/api/datasets/refresh` | dataset sources and manual refresh |
| GET / POST | `/api/risk`, `/api/risk/history`, `/api/risk/snapshot` | live risk evaluation, stored snapshots |
| GET | `/api/methodology` | risk config (weights, thresholds, rationale), rules, config hash |
| GET | `/api/alerts` | alerts computed from stored real data |
| GET | `/api/roi` | ROI scenario calculator (spec formulas; see below) |

## Frontend pages

- **Overview** (`/`): metric cards.
- **Hyperscaler CapEx** (`/capex`): company + date range, YoY growth chart (capex vs revenue vs OCF vs FCF), levels chart, cross-company capex, observation table with EDGAR links, CSV, manual refresh.
- **Data Sources / Pipeline** (`/pipeline`): providers, registry, freshness, runs, errors.
- **Risk score** (`/risk`): overall score (withheld below min coverage), possible range given missing data, coverage, six dimensions with indicator values/thresholds, snapshot history.
- **Alerts** (`/alerts`): capex vs revenue growth gap, negative FCF, risk rise (same config only), low coverage, price cuts/increases, scheduled price changes, drawdowns, failing sources.
- **Valuation** (`/valuation`): TWSE table + price/drawdown charts; US tickers shown UNAVAILABLE without a key; forward P/E UNAVAILABLE.
- **Supply chain / GPU** (`/supply-chain`): NVDA Data Center revenue, Azure GPU list prices, marketplace placeholder.
- **Model pricing** (`/pricing`), **Benchmarks** (`/benchmarks`), **ROI simulator** (`/roi`), **Methodology** (`/methodology`).
- `[PH]` pages are labeled placeholders with no data: AI Monetization, Credit/Funding.

Screenshots: `docs/screenshot_*.png`.

## Risk score (research prototype)

Six dimensions, weights in `backend/app/registry/risk.yaml`: capex vs cash 25, valuation 20, monetization 20, supply chain 15,
macro/funding 10, technology/reliability 10. Each indicator maps linearly from a `benign` (0) to a `stretched` (100) threshold;
**all thresholds are research hypotheses**. Unavailable, stale or insufficient indicators are excluded from the point score and
widen the range (0 for the low bound, 100 for the high bound) — missing data never counts as zero risk. If weighted coverage is
below `min_coverage` (0.5) the overall score is withheld and only the range is shown. Every snapshot stores the config hash.

## ROI simulator (`/roi`, `GET /api/roi`)

Definitions from the project spec, implemented exactly in `backend/app/services/roi.py`:
```
Effective Task Cost = AI Inference Cost + Tool Cost + Human Review Cost + Expected Rework Cost + Expected Failure Loss
Effective ROI       = (Baseline Human Cost - Effective Task Cost) / Baseline Human Cost
```
Inputs (query params of `/api/roi`): `success_probability` p, `review_minutes`, `reviewer_hourly_rate`, `inference_cost`,
`tool_cost`, `rework_cost`, `rework_share` s, `failure_recovery_cost`, `baseline_human_cost`, `task_volume`.

**Modeling assumptions** (how the terms are computed; not part of the spec definitions):
```
Human Review Cost     = review_minutes / 60 x reviewer_hourly_rate        (every task is reviewed)
Expected Rework Cost  = (1 - p) x s       x rework_cost                   (failed task fixed by rework)
Expected Failure Loss = (1 - p) x (1 - s) x failure_recovery_cost         (failure not fixable by rework)
```
A failed task is either reworked or a loss, never both. Totals = per-task values x task volume. Break-even success
probability = p where Effective Task Cost = Baseline Human Cost (ROI = 0): `p* = 1 - (B - inference - tool - review) / (s x rework + (1 - s) x recovery)`;
the API reports "always profitable" / "never breaks even" when p* falls outside [0, 1]. Benchmark scores on the page are references only.

## How to add a new metric

Everything is driven by `backend/app/registry/metrics.yaml`, which is synced into the `metrics` table on startup and on each refresh.

1. **From an existing provider** (e.g. another SEC concept):
   ```yaml
   - id: rnd_expense
     name: R&D expense
     description: ResearchAndDevelopmentExpense, quarterly.
     unit: USD
     frequency: quarterly
     category: hyperscaler_capex
     default_classification: reported
     provider: sec_edgar
     status: connected
     is_ai_specific: false
     entities: [MSFT, GOOGL, AMZN, META, ORCL]
     concepts: [ResearchAndDevelopmentExpense]       # ordered preference; concept_overrides: {TICKER: [...]} per entity
   ```
   Cash-flow (YTD) and income-statement (discrete) facts are both handled by `services/periods.py`.
2. **Derived:** set `provider: derived` and `derive: {op: subtract|ratio|yoy|sum_entities, inputs: [...]}`. Ops live in `services/derive.py`. Dependencies are resolved automatically.
3. **No source yet:** add it with `status: unavailable` (or `placeholder`) and no provider. It will appear in the UI as UNAVAILABLE, never as zero.
4. Run `python -m app.cli refresh` and add a test in `backend/tests/`.

New entities go in `backend/app/registry/entities.yaml` (SEC needs a 10-digit `cik`).

## How to add a new provider

1. Create `backend/app/providers/my_source.py`:
   ```python
   class MySourceProvider(Provider):
       name = "my_source"
       def status(self) -> ProviderStatus:          # report missing keys/config honestly
           ...
       def fetch(self, registry, entity_ids=None) -> ProviderResult:
           # return ProviderResult(records=[ObservationRecord(...)], errors=[ProviderError(...)])
           ...
   ```
   Use `RateLimiter` and `get_with_retry` from `providers/base.py`. Keep parsing in a pure function so it can be tested against a recorded fixture.
2. Register it in `PROVIDERS` in `backend/app/providers/__init__.py`.
3. Point metrics at it with `provider: my_source` in `metrics.yaml`.
4. Add any secrets as env vars in `app/config.py` and `.env.example`. Never commit them.
5. Add a fixture-based parser test plus an entry in `docs/DATA_SOURCES.md`.

The ingestion service handles storage (dedupe, append-only revisions), run/error logging and recomputing derived metrics.

## Layout

```
backend/
  app/
    api/routes.py          FastAPI endpoints
    providers/             base.py (interface, rate limiter), sec_edgar.py, fred.py, twse.py, alphavantage.py, sec_filing_xbrl.py
    datasets/              pricing.py, benchmarks.py, gpu.py, runner.py (append-only dataset tables)
    registry/risk.yaml     risk weights, thresholds (hypotheses), alert rules
    registry/              metrics.yaml, entities.yaml, loader/sync
    services/              periods.py (YTD→quarter, vintages), derive.py, ingest.py, queries.py, risk.py, alerts.py, roi.py
    models.py db.py config.py scheduler.py cli.py main.py
  alembic/                 migrations
  tests/                   pytest + recorded EDGAR fixtures
frontend/
  app/                     page.tsx (Overview), capex/, pipeline/, risk/, alerts/, valuation/, supply-chain/, pricing/,
                           benchmarks/, roi/, methodology/, [placeholder]/
  components/ lib/
docs/                      DATA_SOURCES.md, SPOT_CHECK.md, screenshots
docker-compose.yml
```
