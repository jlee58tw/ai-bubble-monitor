"""Risk engine, methodology and alerts endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import RiskSnapshot
from ..services import risk as risk_svc

router = APIRouter(prefix="/api")


@router.get("/risk")
def risk_now(session: Session = Depends(get_session)):
    """Evaluated live from stored data (no fetch). Use POST /api/risk/snapshot to persist."""
    return risk_svc.evaluate(session)


@router.post("/risk/snapshot")
def risk_snapshot(session: Session = Depends(get_session)):
    s = risk_svc.snapshot_risk(session)
    return {"id": s.id, "computed_at": s.computed_at, "coverage": s.coverage, "score": s.score,
            "score_low": s.score_low, "score_high": s.score_high, "config_hash": s.config_hash}


@router.get("/risk/history")
def risk_history(limit: int = 200, session: Session = Depends(get_session)):
    rows = session.scalars(select(RiskSnapshot).order_by(RiskSnapshot.computed_at.desc()).limit(limit))
    return [{"id": r.id, "computed_at": r.computed_at, "config_hash": r.config_hash, "coverage": r.coverage,
             "score": r.score, "score_low": r.score_low, "score_high": r.score_high} for r in rows]


@router.get("/methodology")
def methodology():
    return risk_svc.methodology()


@router.get("/alerts")
def alerts(session: Session = Depends(get_session)):
    from ..services.alerts import compute_alerts
    return compute_alerts(session)
