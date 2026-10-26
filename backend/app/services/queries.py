"""Read helpers: current (non-superseded) observations, optionally point-in-time (as_of)."""
from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session, aliased

from ..models import Observation


def current_observations_stmt(as_of: dt.date | None = None):
    """Rows not superseded by any newer row (visible as of `as_of` if given)."""
    newer = aliased(Observation)
    cond = [newer.supersedes_id == Observation.id]
    if as_of is not None:
        cond.append(newer.publication_date <= as_of)
    stmt = select(Observation).where(~exists().where(and_(*cond)))
    if as_of is not None:
        stmt = stmt.where(Observation.publication_date <= as_of)
    return stmt


def query_observations(session: Session, metric_ids: list[str] | None = None, entity_ids: list[str] | None = None,
                       start: dt.date | None = None, end: dt.date | None = None,
                       classification: str | None = None, as_of: dt.date | None = None,
                       include_history: bool = False, limit: int | None = None) -> list[Observation]:
    stmt = select(Observation) if include_history else current_observations_stmt(as_of)
    if include_history and as_of is not None:
        stmt = stmt.where(Observation.publication_date <= as_of)
    if metric_ids:
        stmt = stmt.where(Observation.metric_id.in_(metric_ids))
    if entity_ids:
        stmt = stmt.where(Observation.entity_id.in_(entity_ids))
    if start:
        stmt = stmt.where(Observation.period_end >= start)
    if end:
        stmt = stmt.where(Observation.period_end <= end)
    if classification:
        stmt = stmt.where(Observation.classification == classification)
    stmt = stmt.order_by(Observation.metric_id, Observation.entity_id, Observation.period_end, Observation.version)
    if limit:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def observations_frame(session: Session, metric_id: str) -> pd.DataFrame:
    rows = query_observations(session, [metric_id])
    cols = ["id", "entity_id", "period_start", "period_end", "value", "publication_date", "confidence",
            "source_url", "fiscal_period"]
    return pd.DataFrame([{c: getattr(r, c) for c in cols} for r in rows], columns=cols)
