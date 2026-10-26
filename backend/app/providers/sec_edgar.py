"""SEC EDGAR XBRL 'companyfacts' adapter.

Endpoint : https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json
Policy   : SEC fair access - declare a User-Agent with contact info (env SEC_USER_AGENT)
           and stay <= 10 requests/second (env SEC_MAX_RPS, hard-capped at 10).
Limits   : companyfacts contains only NON-dimensional facts (no segment breakdowns).
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Callable

import httpx

from ..config import get_settings
from ..logging_setup import get_logger
from ..registry.registry import MetricDef, Registry
from ..services.periods import Fact, fiscal_label, fiscal_year_starts, parse_facts, quarterize
from .base import (ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus,
                   RateLimiter, get_with_retry)

log = get_logger(__name__)
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def filing_index_url(cik: str, accn: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/{accn}-index.htm"


def records_from_companyfacts(doc: dict, entity_id: str, cik: str, metrics: list[MetricDef],
                              errors: list[ProviderError] | None = None) -> tuple[list[ObservationRecord], int]:
    """Pure transform: companyfacts JSON -> quarterly ObservationRecords (all vintages)."""
    errors = errors if errors is not None else []
    usgaap = doc.get("facts", {}).get("us-gaap", {})
    fetched = 0
    # facts per concept actually used, plus fiscal-year starts from all of them
    concept_facts: dict[str, list[Fact]] = {}
    for m in metrics:
        for c in m.concepts_for(entity_id):
            if c in usgaap and c not in concept_facts:
                raw = usgaap[c].get("units", {}).get("USD", [])
                fetched += len(raw)
                concept_facts[c] = parse_facts(raw, c)
    fy_starts = fiscal_year_starts([f for fs in concept_facts.values() for f in fs])

    out: list[ObservationRecord] = []
    for m in metrics:
        concepts = m.concepts_for(entity_id)
        chosen: dict[dt.date, tuple[str, object]] = {}
        # per-concept quarterization; earlier concept in the list wins for a given period
        for c in concepts:
            for q in quarterize(concept_facts.get(c, [])):
                chosen.setdefault(q.end, (c, q))
        if not chosen:
            errors.append(ProviderError(
                f"No usable XBRL facts for any of {concepts}", level="warning",
                entity_id=entity_id, metric_id=m.id))
            continue
        for end, (c, q) in sorted(chosen.items()):
            label = fiscal_label(q.start, q.end, fy_starts)
            for v in q.vintages:
                if q.derived:
                    meth = (f"DERIVED: {c} YTD {q.ytd_months}m minus YTD {q.ytd_months - 3}m "
                            f"(same fiscal-year start). Filings: {', '.join(v.accns)}")
                    cls, conf = "derived", "medium"
                else:
                    meth = f"REPORTED discrete 3-month value, us-gaap:{c}. Filing: {v.accns[0]}"
                    cls, conf = "reported", "high"
                out.append(ObservationRecord(
                    metric_id=m.id, entity_id=entity_id, value=v.value, unit=m.unit,
                    period_start=q.start, period_end=q.end, fiscal_period=label,
                    publication_date=v.filed, source_type="sec_edgar_xbrl", classification=cls,
                    confidence=conf, source_url=filing_index_url(cik, v.accns[0]),
                    methodology=meth, source_ref=f"us-gaap:{c}",
                ))
    return out, fetched


class SecEdgarProvider(Provider):
    name = "sec_edgar"
    description = "SEC EDGAR XBRL companyfacts API (10-Q / 10-K, non-dimensional facts)"

    def __init__(self, user_agent: str | None = None, max_rps: float | None = None,
                 client_factory: Callable[[], httpx.Client] | None = None):
        s = get_settings()
        self.user_agent = (user_agent if user_agent is not None else s.sec_user_agent).strip()
        self.limiter = RateLimiter(min(max_rps or s.sec_max_rps, 10.0))
        self._client_factory = client_factory
        self.timeout = s.http_timeout_s

    def status(self) -> ProviderStatus:
        if not self.user_agent or "@" not in self.user_agent:
            return ProviderStatus(self.name, False,
                                  "SEC_USER_AGENT not set (must contain app name + contact e-mail, per SEC policy)")
        return ProviderStatus(self.name, True)

    def _client(self) -> httpx.Client:
        if self._client_factory:
            return self._client_factory()
        return httpx.Client(timeout=self.timeout, headers={
            "User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"})

    def fetch(self, registry: Registry, entity_ids: list[str] | None = None) -> ProviderResult:
        res = ProviderResult()
        st = self.status()
        if not st.available:
            res.errors.append(ProviderError(st.reason or "unavailable"))
            return res
        metrics = registry.metrics_for_provider(self.name)
        wanted = sorted({e for m in metrics for e in m.entities})
        if entity_ids:
            wanted = [e for e in wanted if e in entity_ids]
        with self._client() as client:
            for eid in wanted:
                ent = registry.entities[eid]
                if not ent.cik:
                    res.errors.append(ProviderError("entity has no CIK", entity_id=eid))
                    continue
                url = COMPANYFACTS_URL.format(cik=ent.cik.zfill(10))
                try:
                    doc = get_with_retry(client, url, self.limiter).json()
                except Exception as exc:  # noqa: BLE001 - logged and surfaced, run continues
                    log.warning("sec_fetch_failed", entity=eid, url=url, error=str(exc))
                    res.errors.append(ProviderError(f"fetch failed: {exc}", entity_id=eid,
                                                    context={"url": url}))
                    continue
                ms = [m for m in metrics if eid in m.entities]
                recs, n = records_from_companyfacts(doc, eid, ent.cik, ms, res.errors)
                res.records.extend(recs)
                res.fetched += n
                log.info("sec_entity_parsed", entity=eid, facts=n, records=len(recs))
        return res
