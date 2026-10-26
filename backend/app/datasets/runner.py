"""Fetch + append-only store for Phase 2 datasets, with one IngestionRun per source."""
from __future__ import annotations

from collections.abc import Callable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..logging_setup import get_logger
from ..models import BenchmarkResult, GpuPrice, IngestionError, IngestionRun, ModelPrice, utcnow
from ..providers.base import RateLimiter, get_with_retry

log = get_logger(__name__)

TABLES = {
    "model_prices": (ModelPrice, ("vendor", "model_id", "tier", "price_type", "price_status", "effective_from"),
                     ("usd_per_mtok", "effective_to")),
    "benchmark_results": (BenchmarkResult, ("benchmark", "benchmark_version", "split", "metric", "entry_key"),
                          ("value", "ci_low", "ci_high", "result_date")),
    "gpu_prices": (GpuPrice, ("source", "price_kind", "sku", "region"), ("usd_per_hour", "effective_from")),
}


def store_rows(session: Session, table: str, run: IngestionRun, rows: list[dict]) -> dict[str, int]:
    """Unchanged -> bump last_seen_at; changed -> new row superseding the old one; new key -> insert."""
    model, key_cols, val_cols = TABLES[table]
    now = utcnow()
    latest: dict[tuple, object] = {}
    for obj in session.scalars(select(model).order_by(model.id)):
        latest[tuple(getattr(obj, c) for c in key_cols)] = obj  # highest id wins = current
    counts = {"inserted": 0, "revised": 0, "unchanged": 0}
    seen = set()
    for r in rows:
        k = tuple(r.get(c) for c in key_cols)
        if k in seen:
            continue  # duplicate rows inside one payload (e.g. repeated tables) - keep first
        seen.add(k)
        cur = latest.get(k)
        if cur is not None and all(getattr(cur, c) == r.get(c) for c in val_cols):
            cur.last_seen_at = now; counts["unchanged"] += 1
            continue
        obj = model(**r, first_seen_at=now, last_seen_at=now, run_id=run.id,
                    supersedes_id=cur.id if cur is not None else None)
        session.add(obj)
        counts["revised" if cur is not None else "inserted"] += 1
    session.flush()
    return counts


def http_client() -> httpx.Client:
    ua = get_settings().sec_user_agent or "no contact set"
    return httpx.Client(timeout=90, follow_redirects=True,
                        headers={"User-Agent": f"ai-bubble-monitor/0.2 (research; contact {ua})"})


def run_source(session: Session, name: str, table: str, fetch: Callable[[httpx.Client], list[dict]],
               trigger: str = "manual", client: httpx.Client | None = None) -> IngestionRun:
    run = IngestionRun(provider=name, trigger=trigger, status="running", started_at=utcnow())
    session.add(run); session.commit()
    own = client is None
    client = client or http_client()
    try:
        rows = fetch(client)
        c = store_rows(session, table, run, rows)
        run.records_fetched = len(rows)
        run.records_inserted, run.records_revised, run.records_unchanged = c["inserted"], c["revised"], c["unchanged"]
        run.status = "success" if rows else "partial"
        if not rows:
            session.add(IngestionError(run_id=run.id, level="warning", message="source returned 0 rows"))
            run.error_count = 1
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        run = session.get(IngestionRun, run.id)
        run.status = "failed"; run.error_count = 1; run.message = str(exc)[:500]
        session.add(IngestionError(run_id=run.id, level="error", message=str(exc)[:2000]))
        log.warning("dataset_failed", source=name, error=str(exc))
    finally:
        if own:
            client.close()
    run.finished_at = utcnow(); session.commit()
    log.info("dataset_done", source=name, status=run.status, inserted=run.records_inserted,
             revised=run.records_revised)
    return run


def simple_fetch(url: str, kind: str, parse: Callable, min_interval_s: float = 1.0):
    lim = RateLimiter(1.0 / min_interval_s)

    def f(client: httpx.Client) -> list[dict]:
        r = get_with_retry(client, url, lim)
        return parse(r.json() if kind == "json" else r.text)
    return f


def dataset_sources() -> dict[str, tuple[str, Callable]]:
    """name -> (table, fetch). Imported lazily to keep modules independent."""
    from . import benchmarks, gpu, pricing
    out: dict[str, tuple[str, Callable]] = {}
    for n, (url, kind, parse) in pricing.SOURCES.items():
        out[n] = ("model_prices", simple_fetch(url, kind, parse))
    for n, fetch in benchmarks.SOURCES.items():
        out[n] = ("benchmark_results", fetch)
    for n, fetch in gpu.SOURCES.items():
        out[n] = ("gpu_prices", fetch)
    return out


def run_datasets(session: Session, names: list[str] | None = None, trigger: str = "manual") -> list[IngestionRun]:
    srcs = dataset_sources()
    runs = []
    for n in names or list(srcs):
        if n not in srcs:
            raise KeyError(f"unknown dataset source {n}")
        table, fetch = srcs[n]
        runs.append(run_source(session, n, table, fetch, trigger))
    return runs
