from __future__ import annotations

import csv
import datetime as dt
import io
import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_session, session_factory
from ..models import Entity, IngestionError, IngestionRun, Metric, Observation
from ..providers import PROVIDERS, get_provider
from ..registry.registry import get_registry
from ..services.ingest import is_running, run_ingestion
from ..services.queries import query_observations

router = APIRouter(prefix="/api")

OBS_FIELDS = ["id", "metric_id", "entity_id", "value", "unit", "fiscal_period", "period_start", "period_end",
              "publication_date", "ingestion_ts", "source_url", "source_type", "classification", "confidence",
              "methodology", "source_ref", "version", "supersedes_id", "ingestion_run_id"]


def obs_dict(o: Observation) -> dict:
    d = {f: getattr(o, f) for f in OBS_FIELDS}
    d["observation_date"] = o.period_end
    return d


def provider_states() -> dict[str, tuple[bool, str | None]]:
    """Cheap (no network) configuration check for every provider."""
    out = {}
    for name in PROVIDERS:
        st = get_provider(name).status()
        out[name] = (st.available, st.reason)
    return out


def metric_providers(provider: str | None, params: dict | None) -> list[str]:
    """Providers that can feed a metric: params.upstream (derived metrics) or primary + params.alt_providers."""
    params = params or {}
    if params.get("upstream"):
        return list(params["upstream"])
    return [p for p in [provider, *params.get("alt_providers", [])] if p]


def effective_status(status: str, provider: str | None, states: dict,
                     params: dict | None = None) -> tuple[str, str | None]:
    """A 'connected' metric is UNAVAILABLE when none of the providers that can feed it is configured
    (e.g. no API key). One configured alternative is enough."""
    provs = [p for p in metric_providers(provider, params) if p in states]
    if status == "connected" and provs and not any(states[p][0] for p in provs):
        return "unavailable", " / ".join(states[p][1] or p for p in provs)
    return status, None


def _csv(param: str | None) -> list[str] | None:
    return [x.strip() for x in param.split(",") if x.strip()] if param else None


@router.get("/health")
def health():
    return {"status": "ok", "refresh_in_progress": is_running()}


@router.get("/metrics")
def list_metrics(session: Session = Depends(get_session)):
    rows = session.scalars(select(Metric).order_by(Metric.category, Metric.id)).all()
    counts = dict(session.execute(select(Observation.metric_id, func.count()).group_by(Observation.metric_id)).all())
    states = provider_states()
    out = []
    for m in rows:
        eff, reason = effective_status(m.status, m.provider, states, (m.config or {}).get("params"))
        out.append({
        "id": m.id, "name": m.name, "description": m.description, "unit": m.unit, "frequency": m.frequency,
        "category": m.category, "default_classification": m.default_classification, "provider": m.provider,
        "status": m.status, "is_ai_specific": m.is_ai_specific, "warning": m.warning,
        "methodology": m.methodology, "entities": (m.config or {}).get("entities", []),
        "observation_rows": counts.get(m.id, 0), "effective_status": eff, "unavailable_reason": reason,
        "params": (m.config or {}).get("params") or {},
    })
    return out


@router.get("/entities")
def list_entities(session: Session = Depends(get_session)):
    return [{"id": e.id, "name": e.name, "entity_type": e.entity_type, "group": e.group, "cik": e.cik,
             "notes": e.notes} for e in session.scalars(select(Entity).order_by(Entity.id))]


def _filters(metric_id: str | None = Query(None, description="comma-separated"),
             entity_id: str | None = Query(None, description="comma-separated"),
             start: dt.date | None = None, end: dt.date | None = None,
             classification: str | None = None,
             as_of: dt.date | None = Query(None, description="point-in-time: only data published <= as_of"),
             include_history: bool = Query(False, description="include superseded vintages")):
    return dict(metric_ids=_csv(metric_id), entity_ids=_csv(entity_id), start=start, end=end,
                classification=classification, as_of=as_of, include_history=include_history)


@router.get("/observations")
def observations(f: dict = Depends(_filters), limit: int = Query(5000, le=50000),
                 session: Session = Depends(get_session)):
    return [obs_dict(o) for o in query_observations(session, limit=limit, **f)]


@router.get("/observations.csv")
def observations_csv(f: dict = Depends(_filters), session: Session = Depends(get_session)):
    rows = query_observations(session, **f)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(OBS_FIELDS)
    for o in rows:
        w.writerow([getattr(o, k) if getattr(o, k) is not None else "" for k in OBS_FIELDS])
    buf.seek(0)
    name = f"aibm_observations_{dt.date.today().isoformat()}.csv"
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/refresh", status_code=202)
def refresh(provider: str | None = Query(None, description="provider name; default = all")):
    names = [provider] if provider else list(PROVIDERS)
    for n in names:
        if n not in PROVIDERS:
            raise HTTPException(404, f"unknown provider {n}")
    if is_running():
        raise HTTPException(409, "refresh already in progress")

    def _job():
        s = session_factory()()
        try:
            run_ingestion(s, names, trigger="manual")
        except Exception:  # noqa: BLE001 - already recorded in ingestion_runs
            pass
        finally:
            s.close()

    threading.Thread(target=_job, daemon=True).start()
    return {"accepted": True, "providers": names}


@router.get("/ingestion/runs")
def ingestion_runs(limit: int = 50, session: Session = Depends(get_session)):
    rows = session.scalars(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(limit))
    return [{c: getattr(r, c) for c in ("id", "provider", "trigger", "status", "started_at", "finished_at",
                                         "records_fetched", "records_inserted", "records_revised",
                                         "records_unchanged", "error_count", "message")} for r in rows]


@router.get("/ingestion/errors")
def ingestion_errors(limit: int = 100, session: Session = Depends(get_session)):
    rows = session.scalars(select(IngestionError).order_by(IngestionError.id.desc()).limit(limit))
    return [{c: getattr(r, c) for c in ("id", "run_id", "created_at", "level", "entity_id", "metric_id",
                                         "message", "context")} for r in rows]


STALE_DAYS = {"quarterly": 120, "daily": 7, "irregular": 400}


@router.get("/ingestion/status")
def ingestion_status(session: Session = Depends(get_session)):
    """Freshness per provider and per (metric, entity) series."""
    providers = []
    for name in PROVIDERS:
        st = get_provider(name).status()
        last = session.scalars(select(IngestionRun).where(IngestionRun.provider == name)
                               .order_by(IngestionRun.id.desc()).limit(1)).first()
        last_ok = session.scalars(select(IngestionRun).where(IngestionRun.provider == name,
                                                             IngestionRun.status.in_(["success", "partial"]))
                                  .order_by(IngestionRun.id.desc()).limit(1)).first()
        providers.append({"provider": name, "configured": st.available, "reason": st.reason,
                          "last_run_status": last.status if last else None,
                          "last_run_at": last.started_at if last else None,
                          "last_success_at": last_ok.finished_at if last_ok else None})
    reg = get_registry()
    states = provider_states()
    agg = session.execute(select(Observation.metric_id, Observation.entity_id, func.max(Observation.period_end),
                                 func.max(Observation.publication_date), func.max(Observation.ingestion_ts),
                                 func.count()).group_by(Observation.metric_id, Observation.entity_id)).all()
    have = {(a[0], a[1]): a for a in agg}
    today = dt.date.today()
    series = []
    for m in reg.metrics.values():
        for e in m.entities:
            a = have.get((m.id, e))
            eff, reason = effective_status(m.status, m.provider, states, m.params)
            if eff != "connected":
                state = eff
            elif a is None:
                state = "missing"
            else:
                lag = (today - a[2]).days
                state = "stale" if lag > STALE_DAYS.get(m.frequency, 120) else "fresh"
            series.append({"metric_id": m.id, "entity_id": e, "metric_status": eff, "state": state,
                           "reason": reason,
                           "latest_period_end": a[2] if a else None,
                           "latest_publication_date": a[3] if a else None,
                           "last_ingested_at": a[4] if a else None, "rows": a[5] if a else 0})
    return {"refresh_in_progress": is_running(), "providers": providers, "series": series}


@router.get("/overview")
def overview(session: Session = Depends(get_session)):
    """Cards: latest vs previous period for every (metric, entity) in the overview set."""
    reg = get_registry()
    want = ["capex_total_big4_cal", "capex_total_big4_cal_yoy", "capex_total", "capex_yoy", "capex_to_ocf",
            "capex_to_revenue", "fcf", "revenue", "us10y_yield", "nvda_datacenter_revenue", "ai_capex_disclosed",
            "market_cap"]
    cards = []
    for mid in want:
        m = reg.metrics[mid]
        for e in m.entities:
            card = {"metric_id": mid, "metric_name": m.name, "entity_id": e, "unit": m.unit,
                    "status": m.status, "warning": m.warning, "is_ai_specific": m.is_ai_specific,
                    "current": None, "previous": None, "abs_change": None, "pct_change": None}
            if m.status == "connected":
                obs = query_observations(session, [mid], [e])
                if m.frequency == "daily":
                    obs = obs[-2:]
                if obs:
                    cur = obs[-1]
                    card["current"] = obs_dict(cur)
                    if len(obs) > 1:
                        prev = obs[-2]
                        card["previous"] = obs_dict(prev)
                        card["abs_change"] = cur.value - prev.value
                        # % change of a ratio/percentage is misleading: only abs change (pp) for those
                        if m.unit == "USD" and prev.value > 0:
                            card["pct_change"] = cur.value / prev.value - 1
                else:
                    card["status"] = "missing"
            cards.append(card)
    return {"generated_at": dt.datetime.now(dt.timezone.utc), "cards": cards}
