"""SEC EDGAR 8-K (Item 2.02) earnings-release exhibits (EX-99.1): verbatim statements, NOT XBRL.

Earnings press releases are unstructured. This adapter therefore extracts ONLY sentences that match an explicit,
per-metric regular expression (metrics.yaml params.pattern) and stores each with its verbatim sentence:
  * kind "guidance"  -> GuidanceItem rows (value_low/value_high + quote + URL), e.g. META capex outlook.
  * kind "value"     -> Observation rows (classification from the metric) with the quote in `methodology`.
If a company does not state the item in its release (e.g. capex guidance given only on the call), nothing is stored
and the metric stays unavailable for that company - no inference, no transcripts.

  1. https://data.sec.gov/submissions/CIK##########.json  -> 8-K filings whose items include 2.02
  2. https://www.sec.gov/Archives/edgar/data/<cik>/<acc>/index.json -> EX-99.1 document
Same SEC fair-access policy as sec_edgar (User-Agent with contact e-mail, <= 10 req/s).
"""
from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable

import httpx

from ..config import get_settings
from ..logging_setup import get_logger
from ..registry.registry import Registry
from .base import (GuidanceRecord, ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus,
                   RateLimiter, get_with_retry)
from .sec_filing_xbrl import ARCHIVE, SUBMISSIONS_URL
from .sec_prospectus import DATE_RE, html_to_text

log = get_logger(__name__)
PERIOD_RE = re.compile(r"(?:Three Months Ended|quarter ended)\s+(January|February|March|April|May|June|July|August|"
                       r"September|October|November|December) (\d{1,2}),?(?: (\d{4}))?", re.I)
SCALE = {"billion": 1e9, "million": 1e6, None: 1.0, "": 1.0}


def earnings_releases(sub: dict, n: int) -> list[dict]:
    r = sub["filings"]["recent"]
    out = []
    for i, form in enumerate(r["form"]):
        if form == "8-K" and "2.02" in (r.get("items", [""] * len(r["form"]))[i] or ""):
            out.append({"accn": r["accessionNumber"][i], "filed": r["filingDate"][i]})
            if len(out) >= n:
                break
    return out


def pick_ex991(names: list[str]) -> str | None:
    c = [x for x in names if x.lower().endswith(".htm") and re.search(r"ex-?99[._-]?1(?!\d)|exhibit-?991|xex991", x.lower())]
    return sorted(c, key=len)[0] if c else None


def quarter_end(text: str, filed: dt.date) -> dt.date | None:
    """Quarter end = first 'Three Months Ended <date>' within 100 days before filing (year inferred if omitted)."""
    for m in PERIOD_RE.finditer(text):
        years = [int(m.group(3))] if m.group(3) else [filed.year, filed.year - 1]
        for y in years:
            d = dt.datetime.strptime(f"{m.group(1).title()} {m.group(2)} {y}", "%B %d %Y").date()
            if dt.timedelta(0) < filed - d < dt.timedelta(days=100):
                return d
    return None


def sentence_at(text: str, start: int, end: int) -> str:
    """The sentence / bullet containing [start, end): bounded by '. ' or a '•' bullet, capped at 400 chars."""
    a = max(text.rfind(". ", 0, start), text.rfind("• ", 0, start))
    ends = [x for x in (text.find(". ", end), text.find(" •", end)) if x >= 0]
    b = min(ends) if ends else len(text)
    b = min(b, end + 400)
    s = text[a + 2 if a >= 0 else 0: b].strip()
    return s if s.endswith(".") or b == len(text) else s + (" [...]" if b == end + 400 else "")


def extract(text: str, pattern: str) -> list[tuple[re.Match, str]]:
    return [(m, sentence_at(text, m.start(), m.end())) for m in re.finditer(pattern, text)]


class SecEarningsReleaseProvider(Provider):
    name = "sec_earnings_release"
    description = "SEC 8-K Item 2.02 EX-99.1 earnings releases: regex-matched verbatim statements (guidance, KPIs)"

    def __init__(self, user_agent: str | None = None, client_factory: Callable[[], httpx.Client] | None = None,
                 releases: int = 4):
        s = get_settings()
        self.user_agent = (user_agent if user_agent is not None else s.sec_user_agent).strip()
        self.limiter = RateLimiter(min(s.sec_max_rps, 10.0))
        self._client_factory = client_factory
        self.n = releases

    def status(self) -> ProviderStatus:
        if not self.user_agent or "@" not in self.user_agent:
            return ProviderStatus(self.name, False, "SEC_USER_AGENT not set (must contain contact e-mail)")
        return ProviderStatus(self.name, True)

    def _client(self) -> httpx.Client:
        if self._client_factory:
            return self._client_factory()
        return httpx.Client(timeout=90, headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"})

    def fetch(self, registry: Registry, entity_ids: list[str] | None = None) -> ProviderResult:
        res = ProviderResult()
        st = self.status()
        if not st.available:
            res.errors.append(ProviderError(st.reason or "unavailable"))
            return res
        metrics = registry.metrics_for_provider(self.name)
        eids = list(dict.fromkeys(e for m in metrics for e in m.entities if not entity_ids or e in entity_ids))
        with self._client() as client:
            for eid in eids:
                cik = registry.entities[eid].cik
                mets = [m for m in metrics if eid in m.entities and (m.params.get("patterns") or {}).get(eid)]
                if not mets:
                    continue
                try:
                    sub = get_with_retry(client, SUBMISSIONS_URL.format(cik=cik.zfill(10)), self.limiter).json()
                except Exception as exc:  # noqa: BLE001
                    res.errors.append(ProviderError(f"submissions fetch failed: {exc}", entity_id=eid))
                    continue
                for f in earnings_releases(sub, self.n):
                    base = ARCHIVE.format(cik=int(cik), acc=f["accn"].replace("-", ""))
                    try:
                        idx = get_with_retry(client, base + "index.json", self.limiter).json()
                        doc = pick_ex991([i["name"] for i in idx.get("directory", {}).get("item", [])])
                        if not doc:
                            res.errors.append(ProviderError(f"{f['accn']}: no EX-99.1", level="warning",
                                                            entity_id=eid))
                            continue
                        text = html_to_text(get_with_retry(client, base + doc, self.limiter).text)
                    except Exception as exc:  # noqa: BLE001
                        res.errors.append(ProviderError(f"{f['accn']} fetch failed: {exc}", entity_id=eid))
                        continue
                    res.fetched += 1
                    filed = dt.date.fromisoformat(f["filed"])
                    url = base + doc
                    for m in mets:
                        hits = extract(text, m.params["patterns"][eid])
                        if not hits:
                            res.errors.append(ProviderError(f"{f['accn']}: statement not found in release",
                                                            level="warning", entity_id=eid, metric_id=m.id))
                            continue
                        mt, quote = hits[0]
                        g = mt.groupdict()
                        scale = SCALE.get(g.get("scale"), 1.0) * float(m.params.get("scale", 1.0))
                        if m.params.get("kind") == "guidance":
                            res.guidance.append(GuidanceRecord(
                                entity_id=eid, metric_id=m.id, target_period=g.get("target") or "unspecified",
                                value_low=float(g["low"]) * scale if g.get("low") else None,
                                value_high=float(g["high"]) * scale if g.get("high") else None,
                                unit=m.unit, publication_date=filed, source_url=url, quote=quote))
                            continue
                        qe = quarter_end(text, filed)
                        if qe is None:
                            res.errors.append(ProviderError(f"{f['accn']}: quarter end not found", entity_id=eid,
                                                            metric_id=m.id))
                            continue
                        sm = qe.month - 2
                        start = dt.date(qe.year, sm, 1) if sm >= 1 else dt.date(qe.year - 1, sm + 12, 1)
                        res.records.append(ObservationRecord(
                            metric_id=m.id, entity_id=eid, value=float(g["v"]) * scale, unit=m.unit,
                            period_start=start, period_end=qe, fiscal_period=None, publication_date=filed,
                            source_type="sec_8k_release", classification=m.default_classification,
                            confidence="high" if m.default_classification == "reported" else "medium",
                            source_url=url, source_ref=f"8-K:{f['accn']}:EX-99.1",
                            methodology=f"{m.params.get('note', '')} Verbatim (8-K EX-99.1 filed {f['filed']}): "
                                        f"\"{quote}\"".strip()))
                log.info("sec_earnings_release_parsed", entity=eid)
        return res
