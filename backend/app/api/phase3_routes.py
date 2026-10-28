"""Phase 3 endpoints: point-in-time backtest, filing/earnings events, guidance (placeholder), watchlist."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import Entity, FilingEvent, GuidanceItem, IngestionRun, Metric, Observation, WatchlistItem
from ..services import backtest as bt
from ..services.queries import query_observations
from .routes import effective_status, obs_dict, provider_states

router = APIRouter(prefix="/api")


# ------------------------------------------------------------------------------------------- backtest
def _bt_params(horizon: int = Query(20, ge=5, le=120, description="forward window, trading days"),
               drawdown: float = Query(0.10, gt=0, lt=1, description="decline that counts as a hit, e.g. 0.10"),
               composite_threshold: float = Query(60, ge=0, le=100),
               indicator_threshold: float = Query(70, ge=0, le=100),
               lookback_days: int = Query(120, ge=1, le=730)) -> dict:
    return dict(horizon=horizon, drawdown=drawdown, composite_threshold=composite_threshold,
                indicator_threshold=indicator_threshold, lookback_days=lookback_days)


@router.get("/backtest")
def backtest(p: dict = Depends(_bt_params), include_daily: bool = True, session: Session = Depends(get_session)):
    r = bt.run_backtest(session, **p)
    return r if include_daily else {k: v for k, v in r.items() if k != "daily"}


@router.get("/backtest.csv", response_class=PlainTextResponse)
def backtest_csv(p: dict = Depends(_bt_params), session: Session = Depends(get_session)):
    return PlainTextResponse(bt.to_csv(bt.run_backtest(session, **p)), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=aibm_backtest.csv"})


# --------------------------------------------------------------------------------------------- events
def _current(model):
    sup = select(model.supersedes_id).where(model.supersedes_id.is_not(None))
    return select(model).where(model.id.not_in(sup))


@router.get("/events")
def events(entity_id: str | None = None, event_type: str | None = Query(None, pattern="^(periodic_report|earnings_release_8k)$"),
           since: dt.date | None = None, limit: int = Query(500, le=5000), session: Session = Depends(get_session)):
    stmt = _current(FilingEvent)
    if entity_id:
        stmt = stmt.where(FilingEvent.entity_id.in_(entity_id.split(",")))
    if event_type:
        stmt = stmt.where(FilingEvent.event_type == event_type)
    if since:
        stmt = stmt.where(FilingEvent.filing_date >= since)
    rows = list(session.scalars(stmt.order_by(FilingEvent.filing_date.desc(), FilingEvent.entity_id).limit(limit)))
    linked = dict(session.execute(select(Observation.source_url, func.count(Observation.id))
                                  .where(Observation.source_url.in_([r.source_url for r in rows]))
                                  .group_by(Observation.source_url)).all()) if rows else {}
    out = [{"id": r.id, "entity_id": r.entity_id, "form": r.form, "event_type": r.event_type,
            "accession_number": r.accession_number, "observation_date": r.report_date, "publication_date": r.filing_date,
            "lag_days": (r.filing_date - r.report_date).days if r.report_date else None,
            "acceptance_datetime_utc": r.acceptance_datetime, "items": r.items,
            "primary_doc_description": r.primary_doc_description, "source_url": r.source_url,
            "observations_from_filing": linked.get(r.source_url, 0), "first_seen_at": r.first_seen_at} for r in rows]
    cov = session.execute(select(FilingEvent.entity_id, func.min(FilingEvent.filing_date), func.max(FilingEvent.filing_date),
                                 func.count(FilingEvent.id)).group_by(FilingEvent.entity_id)).all()
    run = session.scalars(select(IngestionRun).where(IngestionRun.provider == "sec_filing_events")
                          .order_by(IngestionRun.id.desc()).limit(1)).first()
    ents = {e.id: e for e in session.scalars(select(Entity))}
    coverage = [{"entity_id": e, "earliest_filing": a, "latest_filing": b, "events": n,
                 "note": "EDGAR 'recent' block only (latest ~1,000 filings of any type); older events not loaded"}
                for e, a, b, n in cov]
    not_connected = [{"entity_id": e.id, "name": e.name, "status": "unavailable",
                      "reason": "No EDGAR CIK. TWSE/MOPS filing calendars are not connected."}
                     for e in ents.values() if not e.cik and e.entity_type == "company"]
    return {"events": out, "coverage": coverage, "not_connected": not_connected,
            "last_run": {"status": run.status, "started_at": run.started_at, "message": run.message} if run else None,
            "source": "https://data.sec.gov/submissions/ (SEC EDGAR submissions API)",
            "definitions": {"observation_date": "EDGAR reportDate = fiscal period end (10-Q/10-K/20-F) or event date (8-K)",
                            "publication_date": "EDGAR filingDate = date the filing became public",
                            "earnings_release_8k": "8-K containing Item 2.02 (Results of Operations and Financial Condition)"}}


@router.get("/guidance")
def guidance(session: Session = Depends(get_session)):
    rows = list(session.scalars(select(GuidanceItem).order_by(GuidanceItem.publication_date.desc())))
    return {"status": "placeholder" if not rows else "partial",
            "reason": None if rows else "No guidance source is connected. Guidance is only stored with a source URL and "
                                         "verbatim quote; nothing is inferred from filings or estimated.",
            "items": [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]}


# ------------------------------------------------------------------------------------------- watchlist
class WatchIn(BaseModel):
    entity_id: str | None = None
    metric_id: str | None = None
    note: str | None = Field(None, max_length=500)


def _watch_view(session: Session, w: WatchlistItem) -> dict:
    ent = session.get(Entity, w.entity_id) if w.entity_id else None
    met = session.get(Metric, w.metric_id) if w.metric_id else None
    rows = query_observations(session, [w.metric_id] if w.metric_id else None, [w.entity_id] if w.entity_id else None)
    latest: dict[tuple, Observation] = {}
    for o in rows:
        k = (o.metric_id, o.entity_id)
        if k not in latest or o.period_end > latest[k].period_end:
            latest[k] = o
    obs = sorted(latest.values(), key=lambda o: (o.metric_id, o.entity_id))[:50]
    ev = None
    if w.entity_id:
        e = session.scalars(_current(FilingEvent).where(FilingEvent.entity_id == w.entity_id)
                            .order_by(FilingEvent.filing_date.desc()).limit(1)).first()
        ev = {"form": e.form, "publication_date": e.filing_date, "observation_date": e.report_date,
              "source_url": e.source_url} if e else None
    mstat, why = effective_status(met.status, met.provider, provider_states(), (met.config or {}).get("params")) if met else ("connected", None)
    status = mstat if mstat != "connected" else ("ok" if obs else "missing")
    return {"id": w.id, "entity_id": w.entity_id, "entity_name": ent.name if ent else None,
            "metric_id": w.metric_id, "metric_name": met.name if met else None, "metric_status": mstat if met else None, "status_reason": why,
            "note": w.note, "created_at": w.created_at, "status": status, "latest": [obs_dict(o) for o in obs],
            "latest_filing": ev}


@router.get("/watchlist")
def watchlist(session: Session = Depends(get_session)):
    return [_watch_view(session, w) for w in session.scalars(select(WatchlistItem).order_by(WatchlistItem.id))]


@router.post("/watchlist", status_code=201)
def watchlist_add(body: WatchIn, session: Session = Depends(get_session)):
    if not body.entity_id and not body.metric_id:
        raise HTTPException(422, "entity_id and/or metric_id required")
    if body.entity_id and not session.get(Entity, body.entity_id):
        raise HTTPException(404, f"unknown entity {body.entity_id}")
    if body.metric_id and not session.get(Metric, body.metric_id):
        raise HTTPException(404, f"unknown metric {body.metric_id}")
    ec = WatchlistItem.entity_id.is_(None) if body.entity_id is None else WatchlistItem.entity_id == body.entity_id
    mc = WatchlistItem.metric_id.is_(None) if body.metric_id is None else WatchlistItem.metric_id == body.metric_id
    dup = session.scalars(select(WatchlistItem).where(ec, mc)).first()
    if dup:
        raise HTTPException(409, "already on the watchlist")
    w = WatchlistItem(entity_id=body.entity_id, metric_id=body.metric_id, note=body.note)
    session.add(w)
    try:
        session.commit()
    except IntegrityError:
        session.rollback(); raise HTTPException(409, "already on the watchlist")
    return _watch_view(session, w)


@router.delete("/watchlist/{item_id}")
def watchlist_delete(item_id: int, session: Session = Depends(get_session)):
    w = session.get(WatchlistItem, item_id)
    if not w:
        raise HTTPException(404, "not found")
    session.delete(w); session.commit()
    return {"deleted": item_id}
