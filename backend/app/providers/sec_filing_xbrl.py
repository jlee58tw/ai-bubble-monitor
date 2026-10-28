"""SEC EDGAR filing-level XBRL instance adapter (DIMENSIONAL facts).

companyfacts (providers/sec_edgar.py) only carries non-dimensional facts. Segment / market-platform numbers
such as NVIDIA Data Center revenue are dimensional, so this adapter reads each 10-Q / 10-K XBRL instance:

  1. https://data.sec.gov/submissions/CIK##########.json            -> recent 10-Q/10-K accessions
  2. https://www.sec.gov/Archives/edgar/data/<cik>/<acc>/<doc>_htm.xml  (inline-XBRL extracted instance)
     fallback: the filing's index.json to locate the instance file
  3. keep facts whose context has EXACTLY one explicit member == metric.params (axis, member), where the member may be
     per entity (params.member_by_entity) and params.extra_members may allow one extra fixed member (segment notes)

Same SEC fair-access policy as sec_edgar (User-Agent with contact e-mail, <= 10 req/s).
"""
from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from collections.abc import Callable

import httpx

from ..config import get_settings
from ..logging_setup import get_logger
from ..registry.registry import MetricDef, Registry
from ..services.periods import Fact, fiscal_label, fiscal_year_starts, quarterize
from .base import (ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus,
                   RateLimiter, get_with_retry)
from .sec_edgar import filing_index_url

log = get_logger(__name__)
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
XBRLI = "{http://www.xbrl.org/2003/instance}"
XBRLDI = "{http://xbrl.org/2006/xbrldi}"
FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A"}


def recent_filings(sub: dict, limit: int) -> list[dict]:
    r = sub.get("filings", {}).get("recent", {})
    out = []
    for i, form in enumerate(r.get("form", [])):
        if form in FORMS:
            out.append({"form": form, "accn": r["accessionNumber"][i], "filed": r["filingDate"][i],
                        "report_date": r["reportDate"][i], "doc": r["primaryDocument"][i]})
    return out[:limit]


def _qname(el_tag: str, nsmap_rev: dict[str, str]) -> str:
    uri, local = el_tag[1:].split("}", 1)
    return f"{nsmap_rev.get(uri, uri)}:{local}"


def parse_instance(xml_bytes: bytes, concepts: list[str], axis: str, member: str, filed: dt.date,
                   accn: str, form: str, extra_members: dict[str, str] | None = None) -> list[Fact]:
    """Duration facts for `concepts` (local names, any namespace) whose context = {axis: member} only, or
    {axis: member} plus exactly the `extra_members` (e.g. srt:ConsolidationItemsAxis = us-gaap:OperatingSegmentsMember,
    which ASU 2023-07 segment notes add to some segment facts)."""
    allowed = [sorted([(axis, member)])]
    if extra_members:
        allowed.append(sorted([(axis, member), *extra_members.items()]))
    root = ET.fromstring(xml_bytes)
    ctx_ok: dict[str, tuple[dt.date, dt.date]] = {}
    for c in root.iter(f"{XBRLI}context"):
        mems = [(m.get("dimension"), (m.text or "").strip()) for m in c.iter(f"{XBRLDI}explicitMember")]
        typed = list(c.iter(f"{XBRLDI}typedMember"))
        if typed or sorted(mems) not in allowed:
            continue
        p = c.find(f"{XBRLI}period")
        s, e = p.find(f"{XBRLI}startDate"), p.find(f"{XBRLI}endDate")
        if s is None or e is None:
            continue
        ctx_ok[c.get("id")] = (dt.date.fromisoformat(s.text.strip()), dt.date.fromisoformat(e.text.strip()))
    out = []
    want = set(concepts)
    for el in root:
        cid = el.get("contextRef")
        if not cid or cid not in ctx_ok or not isinstance(el.tag, str) or "}" not in el.tag:
            continue
        local = el.tag.split("}", 1)[1]
        if local not in want or el.get(f"{{http://www.w3.org/2001/XMLSchema-instance}}nil") == "true":
            continue
        try:
            val = float((el.text or "").strip())
        except ValueError:
            continue
        s, e = ctx_ok[cid]
        out.append(Fact(start=s, end=e, val=val, filed=filed, accn=accn, form=form, concept=local))
    # duplicates (same concept/period repeated in one instance) collapse to one
    return list({(f.concept, f.start, f.end): f for f in out}.values())


def original_filing_dates(sub: dict) -> dict[dt.date, dt.date]:
    """report period end -> filing date of the ORIGINAL 10-Q/10-K for that period (earliest filing)."""
    r = sub.get("filings", {}).get("recent", {})
    out: dict[dt.date, dt.date] = {}
    for i, form in enumerate(r.get("form", [])):
        if form in ("10-Q", "10-K") and r["reportDate"][i]:
            e, f = dt.date.fromisoformat(r["reportDate"][i]), dt.date.fromisoformat(r["filingDate"][i])
            out[e] = min(f, out.get(e, f))
    return out


def _original_filed(own: dict[dt.date, dt.date], end: dt.date) -> dt.date | None:
    cands = [f for e, f in own.items() if abs((e - end).days) <= 7]
    return min(cands) if cands else None


def member_for(m: MetricDef, entity_id: str) -> str:
    """params.member, or params.member_by_entity[entity] for segment metrics whose member is company specific."""
    return (m.params.get("member_by_entity") or {}).get(entity_id) or m.params["member"]


def records_from_facts(facts: list[Fact], m: MetricDef, entity_id: str, cik: str,
                       own_filed: dict[dt.date, dt.date] | None = None) -> list[ObservationRecord]:
    """`own_filed` (period end -> original filing date): quarters whose earliest available vintage was filed AFTER the
    period's own 10-Q/10-K (i.e. only seen as a prior-year comparative in a later filing, because the original filing
    is outside the fetched window) are dropped - storing them would date the number a year late."""
    fy_starts = fiscal_year_starts(facts)
    chosen: dict[dt.date, tuple[str, object]] = {}
    for c in m.concepts:
        for q in quarterize([f for f in facts if f.concept == c]):
            chosen.setdefault(q.end, (c, q))
    axis, member = m.params["axis"], member_for(m, entity_id)
    out = []
    for end, (c, q) in sorted(chosen.items()):
        if own_filed is not None:
            orig = _original_filed(own_filed, q.end)
            first = min(v.filed for v in q.vintages)
            if orig is None or first > orig + dt.timedelta(days=3):
                log.info("sec_filing_xbrl_skip_late_vintage", entity=entity_id, metric=m.id, end=str(q.end),
                         first_seen=str(first), original_filing=str(orig))
                continue
        label = fiscal_label(q.start, q.end, fy_starts)
        for v in q.vintages:
            if q.derived:
                meth = (f"DERIVED: {c} [{axis}={member}] YTD {q.ytd_months}m minus YTD {q.ytd_months - 3}m. "
                        f"Filings: {', '.join(v.accns)}")
                cls, conf = "derived", "medium"
            else:
                meth = f"REPORTED 3-month dimensional fact {c} [{axis}={member}]. Filing: {v.accns[0]}"
                cls, conf = "reported", "high"
            out.append(ObservationRecord(
                metric_id=m.id, entity_id=entity_id, value=v.value, unit=m.unit, period_start=q.start,
                period_end=q.end, fiscal_period=label, publication_date=v.filed, source_type="sec_filing_xbrl",
                classification=cls, confidence=conf, source_url=filing_index_url(cik, v.accns[0]),
                methodology=meth, source_ref=f"{c}[{member}]"))
    return out


class SecFilingXbrlProvider(Provider):
    name = "sec_filing_xbrl"
    description = "SEC EDGAR 10-Q/10-K XBRL instances (dimensional facts, e.g. NVDA Data Center revenue)"

    def __init__(self, user_agent: str | None = None, client_factory: Callable[[], httpx.Client] | None = None,
                 limit: int | None = None):
        s = get_settings()
        self.user_agent = (user_agent if user_agent is not None else s.sec_user_agent).strip()
        self.limiter = RateLimiter(min(s.sec_max_rps, 10.0))
        self._client_factory = client_factory
        self.limit = limit or s.sec_filings_limit

    def status(self) -> ProviderStatus:
        if not self.user_agent or "@" not in self.user_agent:
            return ProviderStatus(self.name, False, "SEC_USER_AGENT not set (must contain contact e-mail)")
        return ProviderStatus(self.name, True)

    def _client(self) -> httpx.Client:
        if self._client_factory:
            return self._client_factory()
        return httpx.Client(timeout=90, headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"})

    def _instance(self, client: httpx.Client, cik: str, f: dict) -> bytes:
        base = ARCHIVE.format(cik=int(cik), acc=f["accn"].replace("-", ""))
        doc = f["doc"]
        if doc.endswith(".htm"):
            try:
                return get_with_retry(client, base + doc[:-4] + "_htm.xml", self.limiter, retries=1).content
            except httpx.HTTPStatusError:
                pass
        idx = get_with_retry(client, base + "index.json", self.limiter).json()
        names = [i["name"] for i in idx.get("directory", {}).get("item", [])]
        cands = [n for n in names if n.endswith(".xml") and not any(
            n.endswith(s) for s in ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml", "FilingSummary.xml"))]
        if not cands:
            raise ValueError("no XBRL instance in filing index")
        return get_with_retry(client, base + cands[0], self.limiter).content

    def fetch(self, registry: Registry, entity_ids: list[str] | None = None) -> ProviderResult:
        res = ProviderResult()
        st = self.status()
        if not st.available:
            res.errors.append(ProviderError(st.reason or "unavailable"))
            return res
        metrics = registry.metrics_for_provider(self.name)
        eids = list(dict.fromkeys(e for m in metrics for e in m.entities if not entity_ids or e in entity_ids))
        with self._client() as client:
            for eid in eids:  # entity-outer so each filing instance is downloaded once and freed afterwards
                cik = registry.entities[eid].cik
                try:
                    sub = get_with_retry(client, SUBMISSIONS_URL.format(cik=cik.zfill(10)), self.limiter).json()
                except Exception as exc:  # noqa: BLE001
                    res.errors.append(ProviderError(f"submissions fetch failed: {exc}", entity_id=eid))
                    continue
                cache: dict[str, bytes] = {}
                for m in (m for m in metrics if eid in m.entities):
                    facts: list[Fact] = []
                    member = member_for(m, eid)
                    for f in recent_filings(sub, self.limit):
                        try:
                            if f["accn"] not in cache:
                                cache[f["accn"]] = self._instance(client, cik, f)
                            fs = parse_instance(cache[f["accn"]], m.concepts, m.params["axis"], member,
                                                dt.date.fromisoformat(f["filed"]), f["accn"], f["form"],
                                                m.params.get("extra_members"))
                            facts.extend(fs); res.fetched += len(fs)
                            if not fs:
                                res.errors.append(ProviderError(
                                    f"{f['accn']}: no {member} facts for {m.id}", level="warning",
                                    entity_id=eid, metric_id=m.id))
                        except Exception as exc:  # noqa: BLE001
                            res.errors.append(ProviderError(f"{f['accn']} instance failed: {exc}",
                                                            entity_id=eid, metric_id=m.id))
                    res.records.extend(records_from_facts(facts, m, eid, cik, original_filing_dates(sub)))
                    log.info("sec_filing_xbrl_parsed", entity=eid, metric=m.id, facts=len(facts))
        return res
