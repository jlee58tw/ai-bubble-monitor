"""Alpha Vantage TIME_SERIES_DAILY adapter (official API, free key) - OPTIONAL.

Only active when ALPHAVANTAGE_API_KEY is set. Without a key the provider reports itself unavailable and every
`us_price_close` series is shown as UNAVAILABLE (never zero / never filled from another source).
Free tier: 25 requests/day; we space calls 15 s apart and fetch the 'compact' (~100 sessions) series.
Terms: https://www.alphavantage.co/terms_of_service/
"""
from __future__ import annotations

import datetime as dt

import httpx

from ..config import get_settings
from ..registry.registry import Registry
from .base import (ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus,
                   RateLimiter, get_with_retry)

AV_URL = "https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={sym}&outputsize=compact&apikey={key}"
PUBLIC_URL = "https://www.alphavantage.co/documentation/#daily"


def parse_daily(doc: dict, entity_id: str, symbol: str) -> list[ObservationRecord]:
    for k in ("Error Message", "Note", "Information"):
        if k in doc and "Time Series (Daily)" not in doc:
            raise ValueError(f"Alpha Vantage {k}: {str(doc[k])[:200]}")
    ts = doc.get("Time Series (Daily)")
    if not isinstance(ts, dict):
        raise ValueError("Alpha Vantage: no 'Time Series (Daily)' in response")
    out = []
    for d, row in ts.items():
        try:
            day = dt.date.fromisoformat(d); close = float(row["4. close"])
        except (KeyError, ValueError):
            continue
        out.append(ObservationRecord(
            metric_id="us_price_close", entity_id=entity_id, value=close, unit="USD", period_start=None,
            period_end=day, publication_date=day, source_type="alphavantage", classification="reported",
            confidence="medium", source_url=PUBLIC_URL, source_ref=f"AV:TIME_SERIES_DAILY:{symbol}",
            methodology="Alpha Vantage TIME_SERIES_DAILY '4. close' (unadjusted). Third-party aggregator, "
                        "confidence medium."))
    return sorted(out, key=lambda r: r.period_end)


class AlphaVantageProvider(Provider):
    name = "alphavantage"
    description = "Alpha Vantage daily prices (optional; needs ALPHAVANTAGE_API_KEY)"
    SYMBOLS = {"TSM": "TSM"}  # entity -> ticker when they differ

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None,
                 min_interval_s: float = 15.0):
        self.key = (api_key if api_key is not None else get_settings().alphavantage_api_key).strip()
        self._client = client
        self.limiter = RateLimiter(1.0 / max(min_interval_s, 0.001))

    def status(self) -> ProviderStatus:
        if not self.key:
            return ProviderStatus(self.name, False, "ALPHAVANTAGE_API_KEY not set (optional free key)")
        return ProviderStatus(self.name, True)

    def fetch(self, registry: Registry, entity_ids: list[str] | None = None) -> ProviderResult:
        res = ProviderResult()
        st = self.status()
        if not st.available:
            res.errors.append(ProviderError(st.reason or "unavailable", level="warning"))
            return res
        ents = sorted({e for m in registry.metrics_for_provider(self.name) for e in m.entities})
        if entity_ids:
            ents = [e for e in ents if e in entity_ids]
        client = self._client or httpx.Client(timeout=60)
        try:
            for e in ents:
                sym = self.SYMBOLS.get(e, e)
                try:
                    doc = get_with_retry(client, AV_URL.format(sym=sym, key=self.key), self.limiter).json()
                    recs = parse_daily(doc, e, sym)
                    res.records.extend(recs); res.fetched += len(recs)
                except Exception as exc:  # noqa: BLE001
                    msg = str(exc).replace(self.key, "***")
                    res.errors.append(ProviderError(f"Alpha Vantage {sym}: {msg}", entity_id=e))
        finally:
            if self._client is None:
                client.close()
        return res
