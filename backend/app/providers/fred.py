"""FRED public CSV adapter (no API key): https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIES

Limitation: the public CSV gives the latest data only (no vintages), so publication_date
is approximated as the observation date. Missing values ('.') are skipped, never zero-filled.
"""
from __future__ import annotations

import csv
import datetime as dt
import io

import httpx

from ..config import get_settings
from ..registry.registry import Registry
from .base import (ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus,
                   RateLimiter, get_with_retry)

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd={start}"


def parse_fred_csv(text: str, metric_id: str, entity_id: str, unit: str, url: str, series_id: str) -> list[ObservationRecord]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or len(rows[0]) < 2:
        raise ValueError("unexpected FRED CSV header")
    out = []
    for r in rows[1:]:
        if len(r) < 2 or r[1] in ("", "."):
            continue
        try:
            d = dt.date.fromisoformat(r[0]); v = float(r[1])
        except ValueError:
            continue
        out.append(ObservationRecord(
            metric_id=metric_id, entity_id=entity_id, value=v, unit=unit, period_start=None,
            period_end=d, publication_date=d, fiscal_period=None, source_type="fred",
            classification="reported", confidence="high", source_url=url,
            methodology="FRED public CSV; publication_date approximated as observation date (no vintage).",
            source_ref=f"FRED:{series_id}"))
    return out


class FredProvider(Provider):
    name = "fred"
    description = "FRED public graph CSV download (no key)"

    def __init__(self, client: httpx.Client | None = None):
        self._client = client
        self.limiter = RateLimiter(1)  # robots.txt: Crawl-delay 1

    def status(self) -> ProviderStatus:
        return ProviderStatus(self.name, True)

    def fetch(self, registry: Registry, entity_ids: list[str] | None = None) -> ProviderResult:
        res = ProviderResult()
        s = get_settings()
        client = self._client or httpx.Client(timeout=60, headers={"User-Agent": "ai-bubble-monitor"})
        try:
            for m in registry.metrics_for_provider(self.name):
                by_entity = (m.params or {}).get("series_by_entity") or {}
                for eid in m.entities:
                    if entity_ids and eid not in entity_ids:
                        continue
                    sid = by_entity.get(eid, m.series_id)
                    url = FRED_CSV.format(sid=sid, start=s.fred_start)
                    try:
                        text = get_with_retry(client, url, self.limiter).text
                        recs = parse_fred_csv(text, m.id, eid, m.unit, f"https://fred.stlouisfed.org/series/{sid}", sid)
                        res.records.extend(recs); res.fetched += len(recs)
                    except Exception as exc:  # noqa: BLE001
                        res.errors.append(ProviderError(f"FRED fetch failed: {exc}", metric_id=m.id,
                                                        entity_id=eid, context={"url": url}))
        finally:
            if self._client is None:
                client.close()
        return res
