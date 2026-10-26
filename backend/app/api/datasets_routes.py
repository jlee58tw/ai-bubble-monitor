"""Phase 2 dataset endpoints: model API prices, agent benchmarks, GPU list prices."""
from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..datasets import gpu as gpu_mod
from ..datasets.runner import dataset_sources, run_datasets
from ..db import get_session, session_factory
from ..models import BenchmarkResult, GpuPrice, IngestionRun, ModelPrice

router = APIRouter(prefix="/api")
_lock = threading.Lock()

BENCH_NOTES = {
    "swe-bench": "SWE-bench: % of GitHub issues resolved. Each split (Verified/Lite/Full test/Multimodal/Multilingual) "
                 "is a different task set; results are only comparable within one split. Date = submission date.",
    "terminal-bench": "Terminal-Bench: % of terminal tasks solved (agent harness + model). Only comparable within the "
                      "same dataset version. CI = 95% half-width from the leaderboard.",
    "metr-horizon": "METR time horizon: task length (human-expert minutes) at which the model succeeds 50%/80% of the "
                    "time. Date = model release date. Estimates above ~16 h are flagged as unreliable by METR.",
}


def _cols(o) -> dict:
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}


def _current(session: Session, model):
    sup = select(model.supersedes_id).where(model.supersedes_id.is_not(None))
    return select(model).where(model.id.not_in(sup))


def _last_runs(session: Session, names) -> dict[str, dict]:
    out = {}
    for n in names:
        r = session.scalars(select(IngestionRun).where(IngestionRun.provider == n)
                            .order_by(IngestionRun.id.desc()).limit(1)).first()
        ok = session.scalars(select(IngestionRun).where(IngestionRun.provider == n, IngestionRun.status == "success")
                             .order_by(IngestionRun.id.desc()).limit(1)).first()
        out[n] = {"last_status": r.status if r else "never_run", "last_run_at": r.started_at if r else None,
                  "last_success_at": ok.finished_at if ok else None, "message": r.message if r else None}
    return out


@router.get("/datasets/status")
def datasets_status(session: Session = Depends(get_session)):
    return _last_runs(session, list(dataset_sources()))


@router.post("/datasets/refresh", status_code=202)
def datasets_refresh(source: str | None = Query(None)):
    srcs = dataset_sources()
    if source and source not in srcs:
        raise HTTPException(404, f"unknown source {source}")
    if not _lock.acquire(blocking=False):
        raise HTTPException(409, "dataset refresh already running")

    def work():
        s = session_factory()()
        try:
            run_datasets(s, [source] if source else None, trigger="api")
        finally:
            s.close(); _lock.release()
    threading.Thread(target=work, daemon=True).start()
    return {"started": True, "sources": [source] if source else list(srcs)}


@router.get("/model-prices")
def model_prices(vendor: str | None = None, open_weight: bool | None = None, q: str | None = None,
                 session: Session = Depends(get_session)):
    stmt = _current(session, ModelPrice)
    if vendor:
        stmt = stmt.where(ModelPrice.vendor == vendor)
    if open_weight is not None:
        stmt = stmt.where(ModelPrice.open_weight == open_weight)
    if q:
        stmt = stmt.where(ModelPrice.model_id.ilike(f"%{q}%"))
    rows = [_cols(r) for r in session.scalars(stmt.order_by(ModelPrice.vendor, ModelPrice.model_id))]
    names = {"openai": "pricing_openai", "anthropic": "pricing_anthropic", "google": "pricing_google",
             "openrouter": "pricing_openrouter"}
    return {"rows": rows, "sources": _last_runs(session, names.values()),
            "notes": ["Prices are USD per 1M tokens, list/standard tier as published by the vendor.",
                      "observed = first_seen_at/last_seen_at (UTC) when this app saw the price; effective_from/to "
                      "only when the vendor documents it. History before the first observation is shown only where "
                      "the vendor documents it (price_status=documented_history)."]}


@router.get("/model-prices/changes")
def model_price_changes(session: Session = Depends(get_session)):
    """Observed revisions (row superseding an older row) and vendor-documented scheduled/historical prices."""
    out = []
    for new in session.scalars(select(ModelPrice).where(ModelPrice.supersedes_id.is_not(None))):
        old = session.get(ModelPrice, new.supersedes_id)
        if old and old.usd_per_mtok:
            out.append({"kind": "observed_change", "vendor": new.vendor, "model_id": new.model_id,
                        "tier": new.tier, "price_type": new.price_type, "old": old.usd_per_mtok,
                        "new": new.usd_per_mtok, "pct": (new.usd_per_mtok - old.usd_per_mtok) / old.usd_per_mtok,
                        "observed_at": new.first_seen_at, "source_url": new.source_url})
    for r in session.scalars(_current(session, ModelPrice).where(
            ModelPrice.price_status.in_(["scheduled", "documented_history"]))):
        out.append({"kind": r.price_status, **_cols(r)})
    return out


@router.get("/model-prices/history")
def model_price_history(vendor: str, model_id: str, session: Session = Depends(get_session)):
    rows = session.scalars(select(ModelPrice).where(ModelPrice.vendor == vendor, ModelPrice.model_id == model_id)
                           .order_by(ModelPrice.id))
    return [_cols(r) for r in rows]


@router.get("/benchmarks")
def benchmarks(session: Session = Depends(get_session)):
    """Grouped by (benchmark, version, split, metric). Groups are never merged or cross-ranked."""
    groups: dict[tuple, list] = {}
    for r in session.scalars(_current(session, BenchmarkResult)):
        groups.setdefault((r.benchmark, r.benchmark_version, r.split, r.metric), []).append(_cols(r))
    out = []
    for (b, v, s, m), rows in sorted(groups.items()):
        rows.sort(key=lambda x: -(x["value"] or 0))
        out.append({"benchmark": b, "benchmark_version": v, "split": s, "metric": m, "n": len(rows),
                    "latest_result_date": max((x["result_date"] for x in rows if x["result_date"]), default=None),
                    "note": BENCH_NOTES.get(b), "rows": rows})
    return {"groups": out, "sources": _last_runs(session, ["bench_swebench", "bench_metr", "bench_terminalbench"])}


@router.get("/gpu-prices")
def gpu_prices(session: Session = Depends(get_session)):
    rows = [_cols(r) for r in session.scalars(_current(session, GpuPrice).order_by(GpuPrice.gpu_model))]
    return {"rows": rows, "placeholders": gpu_mod.PLACEHOLDERS,
            "sources": _last_runs(session, list(gpu_mod.SOURCES)),
            "notes": ["Azure list prices (pay-as-you-go and Spot), Linux, region eastus. Not negotiated, reserved "
                      "or marketplace rental rates. usd_per_gpu_hour = instance price / GPU count."]}


@router.get("/datasets/counts")
def counts(session: Session = Depends(get_session)):
    return {t.__tablename__: session.scalar(select(func.count()).select_from(t))
            for t in (ModelPrice, BenchmarkResult, GpuPrice)}
