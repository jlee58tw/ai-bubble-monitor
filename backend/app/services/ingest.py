"""Ingestion orchestration: provider -> append-only observations, then derived metrics."""
from __future__ import annotations

import datetime as dt
import math
import threading
from collections import defaultdict

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..logging_setup import get_logger
from ..models import IngestionError, IngestionRun, Observation, utcnow
from ..providers import get_provider
from ..providers.base import ObservationRecord, Provider
from ..registry.registry import Registry, get_registry, sync_registry
from . import derive as D
from .queries import observations_frame

log = get_logger(__name__)
_RUN_LOCK = threading.Lock()


class RefreshInProgress(RuntimeError):
    pass


def _same(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def store_records(session: Session, run: IngestionRun, records: list[ObservationRecord]) -> dict[str, int]:
    """Append records. Never updates or deletes existing observations.

    For each (metric, entity, period_start, period_end):
      * vintage already stored (same publication_date & value) -> unchanged
      * value equal to current row                              -> unchanged
      * older than current row's publication_date               -> skipped (logged)
      * otherwise insert new version superseding the current row (a revision, or first value)
    """
    counts = {"inserted": 0, "revised": 0, "unchanged": 0, "out_of_order": 0}
    if not records:
        return counts
    pairs = {(r.metric_id, r.entity_id) for r in records}
    chains: dict[tuple, list[Observation]] = defaultdict(list)
    for mid, eid in pairs:
        for o in session.scalars(select(Observation).where(Observation.metric_id == mid,
                                                           Observation.entity_id == eid)):
            chains[(o.metric_id, o.entity_id, o.period_start, o.period_end)].append(o)
    for ch in chains.values():
        ch.sort(key=lambda o: o.version)

    for r in sorted(records, key=lambda r: (r.metric_id, r.entity_id, r.period_end,
                                             str(r.period_start), r.publication_date)):
        chain = chains[r.key]
        if any(o.publication_date == r.publication_date and _same(o.value, r.value) for o in chain):
            counts["unchanged"] += 1
            continue
        cur = chain[-1] if chain else None
        if cur is not None and _same(cur.value, r.value):
            counts["unchanged"] += 1
            continue
        if cur is not None and r.publication_date < cur.publication_date:
            counts["out_of_order"] += 1
            continue
        o = Observation(
            metric_id=r.metric_id, entity_id=r.entity_id, value=float(r.value), unit=r.unit,
            fiscal_period=r.fiscal_period, period_start=r.period_start, period_end=r.period_end,
            publication_date=r.publication_date, ingestion_ts=utcnow(), source_url=r.source_url,
            source_type=r.source_type, classification=r.classification, confidence=r.confidence,
            methodology=r.methodology, source_ref=r.source_ref,
            version=(cur.version + 1) if cur else 1, supersedes_id=cur.id if cur else None,
            ingestion_run_id=run.id,
        )
        session.add(o)
        session.flush()  # assign id so a later vintage in this batch can supersede it
        chain.append(o)
        counts["revised" if cur else "inserted"] += 1
    return counts


def _log_error(session: Session, run: IngestionRun, message: str, level: str = "error",
               entity_id: str | None = None, metric_id: str | None = None, context: dict | None = None):
    session.add(IngestionError(run_id=run.id, level=level, entity_id=entity_id, metric_id=metric_id,
                               message=message, context=context))
    run.error_count += 1


def compute_derived(session: Session, run: IngestionRun, reg: Registry) -> dict[str, int]:
    """Compute derived metrics in dependency order from CURRENT input observations."""
    totals = {"inserted": 0, "revised": 0, "unchanged": 0, "out_of_order": 0}
    derived = [m for m in reg.metrics.values() if m.derive and m.status == "connected"]
    done: set[str] = set()
    pending = list(derived)
    while pending:
        progressed = False
        for m in list(pending):
            ins = m.derive["inputs"]
            if any(i in {d.id for d in pending} for i in ins):
                continue  # input not computed yet
            frames = [observations_frame(session, i) for i in ins]
            op = m.derive["op"]
            if any(f.empty for f in frames):
                out = pd.DataFrame()
            elif op == "subtract":
                out = D.subtract(*frames)
            elif op == "ratio":
                out = D.ratio(*frames, positive_denominator=m.derive.get("positive_denominator", False))
            elif op == "yoy":
                out = D.yoy(frames[0])
            elif op == "sum_entities":
                out = D.sum_entities(frames[0], m.derive["members"], m.entities[0])
            else:
                raise ValueError(f"unknown derive op {op}")
            recs = []
            for row in out.to_dict("records"):
                if row["entity_id"] not in m.entities:
                    continue
                recs.append(ObservationRecord(
                    metric_id=m.id, entity_id=row["entity_id"], value=float(row["value"]), unit=m.unit,
                    period_start=row["period_start"], period_end=row["period_end"],
                    fiscal_period=row["fiscal_period"], publication_date=row["publication_date"],
                    source_type="derived", classification="derived", confidence=row["confidence"],
                    source_url=row["source_url"],
                    methodology=f"{(m.methodology or '').strip()} [{row['inputs']}]",
                    source_ref=f"derived:{op}({','.join(ins)})"))
            c = store_records(session, run, recs)
            for k in totals:
                totals[k] += c[k]
            session.flush()
            pending.remove(m); done.add(m.id); progressed = True
        if not progressed:
            raise ValueError(f"cyclic derive dependencies: {[m.id for m in pending]}")
    return totals


def run_ingestion(session: Session, provider_names: list[str], trigger: str = "manual",
                  entity_ids: list[str] | None = None, providers: dict[str, Provider] | None = None,
                  run_derivations: bool = True) -> list[IngestionRun]:
    """Run providers sequentially (one run row each), then derivations (run row 'derived')."""
    if not _RUN_LOCK.acquire(blocking=False):
        raise RefreshInProgress("an ingestion run is already in progress")
    try:
        reg = get_registry()
        sync_registry(session, reg)
        runs = []
        for name in provider_names:
            prov = (providers or {}).get(name) or get_provider(name)
            run = IngestionRun(provider=name, trigger=trigger, status="running", started_at=utcnow())
            session.add(run); session.commit()
            log.info("ingestion_start", provider=name, run_id=run.id, trigger=trigger)
            try:
                result = prov.fetch(reg, entity_ids)
                for e in result.errors:
                    _log_error(session, run, e.message, e.level, e.entity_id, e.metric_id, e.context)
                c = store_records(session, run, result.records)
                run.records_fetched = result.fetched
                run.records_inserted, run.records_revised = c["inserted"], c["revised"]
                run.records_unchanged = c["unchanged"] + c["out_of_order"]
                hard = [e for e in result.errors if e.level == "error"]
                run.status = "failed" if (hard and not result.records) else ("partial" if hard else "success")
                run.message = (f"{len(result.records)} vintages parsed; {c['out_of_order']} out-of-order skipped"
                               + (f"; {len(hard)} errors" if hard else ""))
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                run = session.merge(run)
                run.status = "failed"; run.message = f"{type(exc).__name__}: {exc}"
                _log_error(session, run, run.message)
                log.exception("ingestion_failed", provider=name, run_id=run.id)
            run.finished_at = utcnow()
            session.commit()
            log.info("ingestion_done", provider=name, run_id=run.id, status=run.status,
                     inserted=run.records_inserted, revised=run.records_revised, errors=run.error_count)
            runs.append(run)

        if run_derivations:
            run = IngestionRun(provider="derived", trigger=trigger, status="running", started_at=utcnow())
            session.add(run); session.commit()
            try:
                c = compute_derived(session, run, reg)
                run.records_inserted, run.records_revised = c["inserted"], c["revised"]
                run.records_unchanged = c["unchanged"] + c["out_of_order"]
                run.status = "success"
            except Exception as exc:  # noqa: BLE001
                session.rollback(); run = session.merge(run)
                run.status = "failed"; run.message = f"{type(exc).__name__}: {exc}"
                _log_error(session, run, run.message)
                log.exception("derivation_failed", run_id=run.id)
            run.finished_at = utcnow(); session.commit()
            runs.append(run)
        return runs
    finally:
        _RUN_LOCK.release()


def is_running() -> bool:
    return _RUN_LOCK.locked()
