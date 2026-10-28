"""Earnings / filing events from SEC EDGAR submissions metadata (no API key).

Source: https://data.sec.gov/submissions/CIK##########.json (SEC fair-access policy: User-Agent with contact
e-mail from SEC_USER_AGENT, <= 10 req/s; we use 2 req/s). Only the `filings.recent` block is read (EDGAR's
latest ~1,000 filings per company), so for prolific filers the oldest events may be missing - the API reports
the earliest stored filing date per company instead of implying completeness.

Events kept:
  * periodic_report        10-Q, 10-K, 20-F, 40-F (+ /A amendments): report_date = period end (observation date),
                           filing_date = publication date.
  * earnings_release_8k    8-K whose `items` contain 2.02 (Results of Operations and Financial Condition).
                           report_date = EDGAR "period of report" (the event date).
Guidance is NOT parsed from these filings (see GuidanceItem: rows only with a source URL + quote).
"""
from __future__ import annotations

import datetime as dt

import httpx

from ..config import get_settings
from ..providers.base import RateLimiter, get_with_retry
from ..registry.registry import load_registry

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
PERIODIC = {"10-Q", "10-K", "20-F", "40-F", "10-Q/A", "10-K/A", "20-F/A", "40-F/A"}


def index_url(cik: str, accn: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn.replace('-', '')}/{accn}-index.htm"


def _d(s: str | None) -> dt.date | None:
    return dt.date.fromisoformat(s) if s else None


def parse_submissions(sub: dict, entity_id: str, cik: str) -> list[dict]:
    """Pure transform: submissions JSON -> filing_events rows (periodic reports + 8-K Item 2.02)."""
    r = sub.get("filings", {}).get("recent", {})
    out = []
    n = len(r.get("form", []))
    col = lambda k, i: (r.get(k) or [None] * n)[i]  # noqa: E731 - columns may be absent in old payloads
    for i in range(n):
        form = r["form"][i]
        items = col("items", i) or ""
        if form in PERIODIC:
            et = "periodic_report"
        elif form in ("8-K", "8-K/A") and "2.02" in items.split(","):
            et = "earnings_release_8k"
        else:
            continue
        accn = r["accessionNumber"][i]
        out.append({"entity_id": entity_id, "cik": cik, "accession_number": accn, "form": form, "event_type": et,
                    "filing_date": _d(r["filingDate"][i]), "acceptance_datetime": col("acceptanceDateTime", i),
                    "report_date": _d(col("reportDate", i)), "items": items or None,
                    "primary_document": col("primaryDocument", i),
                    "primary_doc_description": col("primaryDocDescription", i),
                    "source_url": index_url(cik, accn)})
    return out


def fetch_filing_events(client: httpx.Client) -> list[dict]:
    reg = load_registry()
    ua = get_settings().sec_user_agent.strip()
    if "@" not in ua:
        raise RuntimeError("SEC_USER_AGENT not set (must contain a contact e-mail, per SEC policy)")
    lim = RateLimiter(2.0)
    rows: list[dict] = []
    for e in reg.entities.values():
        if not e.cik:
            continue
        url = SUBMISSIONS_URL.format(cik=e.cik.zfill(10))
        doc = get_with_retry(client, url, lim).json()
        rows.extend(parse_submissions(doc, e.id, e.cik.zfill(10)))
    return rows


def sec_client() -> httpx.Client:
    return httpx.Client(timeout=60, headers={"User-Agent": get_settings().sec_user_agent.strip(),
                                             "Accept-Encoding": "gzip, deflate"})


SOURCES = {"sec_filing_events": fetch_filing_events}
