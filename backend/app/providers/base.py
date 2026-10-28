"""Provider adapter interface.

A provider turns an external source into a list of ``ObservationRecord`` objects
(one per value *vintage*) plus a list of non-fatal errors. Providers never write
to the database; ``services.ingest`` does that (append-only).
"""
from __future__ import annotations

import abc
import datetime as dt
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..registry.registry import Registry


@dataclass
class ObservationRecord:
    metric_id: str
    entity_id: str
    value: float
    unit: str
    period_end: dt.date
    publication_date: dt.date
    source_type: str
    classification: str
    confidence: str
    period_start: dt.date | None = None
    fiscal_period: str | None = None
    source_url: str | None = None
    methodology: str | None = None
    source_ref: str | None = None

    @property
    def key(self) -> tuple:
        return (self.metric_id, self.entity_id, self.period_start, self.period_end)


@dataclass
class ProviderError:
    message: str
    level: str = "error"
    entity_id: str | None = None
    metric_id: str | None = None
    context: dict[str, Any] | None = None


@dataclass
class GuidanceRecord:
    """Management guidance quoted VERBATIM from a filing; never inferred."""
    entity_id: str
    metric_id: str
    target_period: str
    value_low: float | None
    value_high: float | None
    unit: str
    publication_date: dt.date
    source_url: str
    quote: str


@dataclass
class ProviderResult:
    records: list[ObservationRecord] = field(default_factory=list)
    errors: list[ProviderError] = field(default_factory=list)
    fetched: int = 0  # raw facts / rows read from source
    guidance: list[GuidanceRecord] = field(default_factory=list)  # verbatim-quoted guidance (GuidanceItem rows)


@dataclass
class ProviderStatus:
    name: str
    available: bool
    reason: str | None = None


class Provider(abc.ABC):
    name: str = "base"
    description: str = ""

    @abc.abstractmethod
    def status(self) -> ProviderStatus:
        """Cheap configuration check (no network)."""

    @abc.abstractmethod
    def fetch(self, registry: Registry, entity_ids: list[str] | None = None) -> ProviderResult:
        """Fetch all connected metrics this provider owns."""


class RateLimiter:
    """Minimum-interval limiter shared by all calls of one provider (thread-safe)."""

    def __init__(self, max_per_second: float):
        self.min_interval = 1.0 / max_per_second
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._last + self.min_interval - now
            if delay > 0:
                time.sleep(delay)
            self._last = time.monotonic()


def get_with_retry(client: httpx.Client, url: str, limiter: RateLimiter | None = None,
                   retries: int = 3, backoff_s: float = 2.0,
                   retry_statuses: tuple[int, ...] = ()) -> httpx.Response:
    """GET with polite exponential backoff on 429/5xx (plus any extra ``retry_statuses``, e.g. TWSE answers
    307 when it throttles a client)."""
    last_exc: Exception | None = None
    for attempt in range(retries):
        if limiter:
            limiter.wait()
        try:
            r = client.get(url)
            if r.status_code in (429, 500, 502, 503, 504) + tuple(retry_statuses):
                last_exc = httpx.HTTPStatusError(f"HTTP {r.status_code}", request=r.request, response=r)
                time.sleep(backoff_s * (2 ** attempt))
                continue
            r.raise_for_status()
            return r
        except httpx.TransportError as exc:
            last_exc = exc
            time.sleep(backoff_s * (2 ** attempt))
    assert last_exc is not None
    raise last_exc
