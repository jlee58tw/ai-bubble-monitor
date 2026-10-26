# AI Bubble Monitor — Phase 1

A research dashboard asking one question: **is AI monetization keeping up with AI capex?**
Phase 1 is a vertical slice: hyperscaler capex, revenue, operating cash flow and FCF from **SEC EDGAR**, plus the
US 10Y yield from **FRED**. Everything else is shown as explicitly *unavailable* or *placeholder*.

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

Tests: `cd backend && pytest -q`. They are offline and use recorded companyfacts fixtures plus a mocked HTTP transport.

### Docker Compose

```bash
cp .env.example .env    # set SEC_USER_AGENT
docker compose up --build
docker compose exec api python -m app.cli refresh
```

SQLite lives on the `aibm-data` volume. For Postgres, set `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/aibm` (psycopg is included).
*Note: the compose files were written but not run on the build host (Docker was not installed there).*

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

## Frontend pages

- **Overview** (`/`): metric cards.
- **Hyperscaler CapEx** (`/capex`): company + date range, YoY growth chart (capex vs revenue vs OCF vs FCF), levels chart, cross-company capex, observation table with EDGAR links, CSV, manual refresh.
- **Data Sources / Pipeline** (`/pipeline`): providers, registry, freshness, runs, errors.
- `[PH]` pages are labeled placeholders with no data: AI Monetization, Valuation, Semis/Supply Chain, Credit/Funding.

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
    providers/             base.py (interface, rate limiter), sec_edgar.py, fred.py
    registry/              metrics.yaml, entities.yaml, loader/sync
    services/              periods.py (YTD→quarter, vintages), derive.py, ingest.py, queries.py
    models.py db.py config.py scheduler.py cli.py main.py
  alembic/                 migrations
  tests/                   pytest + recorded EDGAR fixtures
frontend/
  app/                     page.tsx (Overview), capex/, pipeline/, [placeholder]/
  components/ lib/
docs/                      DATA_SOURCES.md, SPOT_CHECK.md, screenshots
docker-compose.yml
```
