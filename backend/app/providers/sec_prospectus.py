"""SEC EDGAR registration-statement (S-1 / S-1/A / 424B4) adapter for PRE-IPO AI labs (e.g. Anthropic, PBC).

The S-1 financial statements are NOT XBRL-tagged (only the cover page / fee exhibit are), so this adapter reads the
prospectus HTML and parses ONE table: "Quarterly Consolidated Statements of Operations ... Three Months Ended
(in millions)". Rows are matched by their exact label (metric.params.row_label). Values are stored with
classification "disclosed" (company-disclosed in a registration statement, pre-IPO), never "reported", so they are
never mixed with listed-company 10-Q/10-K financials. publication_date = EDGAR filing date of the S-1.

  1. https://data.sec.gov/submissions/CIK##########.json  -> latest S-1 / S-1/A / 424B4 accession + primary document
  2. https://www.sec.gov/Archives/edgar/data/<cik>/<acc>/<primary document>
Same SEC fair-access policy as sec_edgar (User-Agent with contact e-mail, <= 10 req/s).
"""
from __future__ import annotations

import datetime as dt
import html as htmllib
import re
from collections.abc import Callable

import httpx

from ..config import get_settings
from ..logging_setup import get_logger
from ..registry.registry import Registry
from .base import (ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus, RateLimiter,
                   get_with_retry)
from .sec_filing_xbrl import ARCHIVE, SUBMISSIONS_URL

log = get_logger(__name__)
FORMS = ("S-1", "S-1/A", "424B4", "424B1")
TABLE_START = "Quarterly Consolidated Statements of Operations Three Months Ended (in millions)"
DATE_RE = r"(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2}), (\d{4})"
NUM = r"\(?\$?\s?[\d,]+\)?|—"


def html_to_text(raw: str) -> str:
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", raw)).split())


def _num(tok: str) -> float | None:
    tok = tok.replace("$", "").replace(",", "").strip()
    if tok == "—":
        return 0.0
    neg = tok.startswith("(") and tok.endswith(")")
    tok = tok.strip("()").strip()
    try:
        v = float(tok)
    except ValueError:
        return None
    return -v if neg else v


def parse_quarterly_table(text: str) -> tuple[list[dt.date], dict[str, list[float | None]]]:
    """-> (quarter end dates, {row label text that precedes the numbers: values in USD millions})."""
    i = text.find(TABLE_START)
    if i < 0:
        raise ValueError("quarterly statements-of-operations table not found")
    body = text[i + len(TABLE_START):]
    ends = []
    pos = 0
    for m in re.finditer(DATE_RE, body):
        if m.start() - pos > 3 and ends:
            break
        ends.append(dt.datetime.strptime(" ".join(m.groups()), "%B %d %Y").date())
        pos = m.end()
    n = len(ends)
    if n < 2:
        raise ValueError("quarter header not parsed")
    body = re.sub(r"(?<=[A-Za-z]) \(\d\)(?= )", "", body[pos:pos + 6000])  # drop footnote markers like 'Personnel (1)'
    rows: dict[str, list[float | None]] = {}
    pat = re.compile(rf"([A-Za-z][A-Za-z ,()\-’'&]*?(?:\(\d\))?)\s+((?:(?:{NUM})\s+){{{n - 1}}}(?:{NUM}))(?=\s|$)")
    for m in pat.finditer(body):
        label = re.sub(r"\s*\(\d\)$", "", m.group(1)).strip()
        vals = [_num(t) for t in re.findall(NUM, m.group(2))]
        if len(vals) == n and label not in rows:
            rows[label] = vals
    rev, opex, oi = (rows.get(k) for k in ("Revenue", "Total operating expenses", "Operating income (loss)"))
    if rev and opex and oi:  # the table must foot: revenue - total opex = operating income (+-1 rounding)
        bad = [e for e, a, b, c in zip(ends, rev, opex, oi) if abs((a - b) - c) > 1.5]
        if bad:
            raise ValueError(f"quarterly table does not foot for {bad}; parser misaligned")
    return ends, rows


class SecProspectusProvider(Provider):
    name = "sec_prospectus"
    description = "SEC EDGAR S-1 prospectus tables for pre-IPO AI labs (company-disclosed, not reported financials)"

    def __init__(self, user_agent: str | None = None, client_factory: Callable[[], httpx.Client] | None = None):
        s = get_settings()
        self.user_agent = (user_agent if user_agent is not None else s.sec_user_agent).strip()
        self.limiter = RateLimiter(min(s.sec_max_rps, 10.0))
        self._client_factory = client_factory

    def status(self) -> ProviderStatus:
        if not self.user_agent or "@" not in self.user_agent:
            return ProviderStatus(self.name, False, "SEC_USER_AGENT not set (must contain contact e-mail)")
        return ProviderStatus(self.name, True)

    def _client(self) -> httpx.Client:
        if self._client_factory:
            return self._client_factory()
        return httpx.Client(timeout=120, headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"})

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
                try:
                    r = get_with_retry(client, SUBMISSIONS_URL.format(cik=cik.zfill(10)), self.limiter).json()
                    rec = r["filings"]["recent"]
                    idx = next((i for i, f in enumerate(rec["form"]) if f in FORMS), None)
                    if idx is None:
                        res.errors.append(ProviderError("no S-1/424B filing on EDGAR", entity_id=eid))
                        continue
                    accn, filed, doc = rec["accessionNumber"][idx], rec["filingDate"][idx], rec["primaryDocument"][idx]
                    url = ARCHIVE.format(cik=int(cik), acc=accn.replace("-", "")) + doc
                    text = html_to_text(get_with_retry(client, url, self.limiter).text)
                    ends, rows = parse_quarterly_table(text)
                except Exception as exc:  # noqa: BLE001
                    res.errors.append(ProviderError(f"prospectus fetch/parse failed: {exc}", entity_id=eid))
                    continue
                res.fetched += len(rows)
                pub = dt.date.fromisoformat(filed)
                for m in (m for m in metrics if eid in m.entities):
                    label = m.params["row_label"]
                    vals = rows.get(label)
                    if vals is None:
                        res.errors.append(ProviderError(f"row {label!r} not in quarterly table ({accn})",
                                                        entity_id=eid, metric_id=m.id))
                        continue
                    for end, v in zip(ends, vals):
                        if v is None:
                            continue
                        sm = end.month - 2  # calendar quarter start (table periods are calendar quarter ends)
                        start = dt.date(end.year, sm, 1) if sm >= 1 else dt.date(end.year - 1, sm + 12, 1)
                        res.records.append(ObservationRecord(
                            metric_id=m.id, entity_id=eid, value=v * 1e6, unit=m.unit, period_start=start,
                            period_end=end, fiscal_period=f"CY{end.year} Q{(end.month - 1) // 3 + 1}",
                            publication_date=pub, source_type="sec_prospectus", classification="disclosed",
                            confidence="high", source_url=url, source_ref=f"{rec['form'][idx]}:{accn}:{label}",
                            methodology=(f"Company-disclosed (pre-IPO {rec['form'][idx]}, filed {filed}), quarterly "
                                         f"statements-of-operations table, row '{label}', USD millions x 1e6. "
                                         "Unaudited quarterly data; NOT a listed company's reported financials.")))
                log.info("sec_prospectus_parsed", entity=eid, accn=accn, quarters=len(ends), rows=len(rows))
        return res
