"""Tiingo End-of-Day prices adapter (official REST API, free 'Starter' key) - OPTIONAL.

Only active when TIINGO_API_KEY is set. Without a key the provider reports itself unavailable and every
`us_price_close` series is shown as UNAVAILABLE (never zero, never filled from another source).

Endpoint : https://api.tiingo.com/tiingo/daily/<ticker>/prices?startDate=YYYY-MM-DD   (docs: /documentation/end-of-day)
Auth     : header ``Authorization: Token <key>`` (the key is never put in URLs or logs)
Free tier: 50 requests/hour, 1,000/day, 500 unique symbols/month, 30+ years of EOD history; internal /
           personal use (see https://www.tiingo.com/about/pricing and the Terms of Use).
We fetch 11 symbols per refresh with >= 2 s spacing, i.e. far below the hourly cap.

Stored (all REPORTED, confidence medium = licensed third-party aggregator):
  * us_price_close   - raw (unadjusted) close, used for market cap (price x shares).
  * us_split_factor  - Tiingo `splitFactor` on days where it is != 1 (splits / reverse splits), used to
                       split-adjust prices and EDGAR share counts. Dividends are NOT adjusted (price return,
                       comparable with the FRED price-return indices NASDAQ100 / NASDAQSOX).
"""
from __future__ import annotations

import datetime as dt

import httpx

from ..config import get_settings
from ..registry.registry import Registry
from .base import (ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus,
                   RateLimiter, get_with_retry)

TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{sym}/prices?startDate={start}"
PUBLIC_URL = "https://www.tiingo.com/documentation/end-of-day"


def parse_prices(doc, entity_id: str, symbol: str) -> list[ObservationRecord]:
    """Tiingo daily prices JSON (list of rows) -> close + split-factor records."""
    if isinstance(doc, dict):  # error payloads are objects, e.g. {"detail": "..."}
        raise ValueError(f"Tiingo error: {str(doc.get('detail') or doc)[:200]}")
    if not isinstance(doc, list):
        raise ValueError("Tiingo: unexpected response (expected a JSON list)")
    out: list[ObservationRecord] = []
    for row in doc:
        try:
            day = dt.date.fromisoformat(str(row["date"])[:10])
            close = float(row["close"])
        except (KeyError, TypeError, ValueError):
            continue
        if close <= 0:
            continue
        common = dict(entity_id=entity_id, period_start=None, period_end=day, publication_date=day,
                      source_type="tiingo", classification="reported", confidence="medium",
                      source_url=PUBLIC_URL)
        out.append(ObservationRecord(
            metric_id="us_price_close", value=close, unit="USD", source_ref=f"TIINGO:daily:{symbol}:close",
            methodology="Tiingo EOD 'close' (raw, unadjusted). Licensed third-party aggregator, confidence medium.",
            **common))
        sf = row.get("splitFactor")
        try:
            sf = float(sf) if sf is not None else 1.0
        except (TypeError, ValueError):
            sf = 1.0
        if sf > 0 and abs(sf - 1.0) > 1e-12:
            out.append(ObservationRecord(
                metric_id="us_split_factor", value=sf, unit="ratio",
                source_ref=f"TIINGO:daily:{symbol}:splitFactor",
                methodology="Tiingo EOD 'splitFactor' on the ex-date (new shares per old share).", **common))
    return sorted(out, key=lambda r: (r.metric_id, r.period_end))


class TiingoProvider(Provider):
    name = "tiingo"
    description = "Tiingo end-of-day prices (optional; needs TIINGO_API_KEY, free Starter plan)"
    SYMBOLS: dict[str, str] = {}  # entity -> ticker when they differ

    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None,
                 min_interval_s: float = 2.0, start: str | None = None):
        s = get_settings()
        self.key = (api_key if api_key is not None else s.tiingo_api_key).strip()
        self.start = start or s.us_price_start
        self._client = client
        self.limiter = RateLimiter(1.0 / max(min_interval_s, 0.001))

    def status(self) -> ProviderStatus:
        if not self.key:
            return ProviderStatus(self.name, False, "TIINGO_API_KEY not set (optional free key)")
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
        client = self._client or httpx.Client(timeout=60, headers={
            "Authorization": f"Token {self.key}", "Content-Type": "application/json",
            "User-Agent": "ai-bubble-monitor"})
        try:
            for e in ents:
                sym = self.SYMBOLS.get(e, e)
                url = TIINGO_URL.format(sym=sym.lower(), start=self.start)
                try:
                    doc = get_with_retry(client, url, self.limiter).json()
                    recs = parse_prices(doc, e, sym)
                    res.records.extend(recs); res.fetched += len(recs)
                except Exception as exc:  # noqa: BLE001
                    msg = str(exc).replace(self.key, "***")
                    res.errors.append(ProviderError(f"Tiingo {sym}: {msg}", entity_id=e))
        finally:
            if self._client is None:
                client.close()
        return res
