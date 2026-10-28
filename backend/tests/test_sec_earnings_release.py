"""8-K EX-99.1 earnings-release adapter. Fixtures = real text-normalised excerpts fetched from EDGAR 2026-10-28."""
import datetime as dt
from pathlib import Path

import httpx

from app.providers import sec_earnings_release as ER
from app.registry.registry import get_registry

FX = Path(__file__).parent / "fixtures"
FILINGS = {  # entity: (cik, accession, filed, EX-99.1 name, fixture)
    "META": ("1326801", "0001628280-26-066700", "2026-10-21", "meta-09302026xexhibit991.htm", "ex991_meta_excerpt.htm"),
    "MSFT": ("789019", "0001193125-26-323632", "2026-07-29", "msft-ex99_1.htm", "ex991_msft_excerpt.htm"),
    "AMZN": ("1018724", "0001018724-26-000024", "2026-07-30", "amzn-20260630xex991.htm", "ex991_amzn_excerpt.htm"),
}


def _handler(req: httpx.Request) -> httpx.Response:
    u = str(req.url)
    for eid, (cik, acc, filed, doc, fx) in FILINGS.items():
        if f"CIK{cik.zfill(10)}" in u:
            return httpx.Response(200, json={"filings": {"recent": {
                "form": ["10-Q", "8-K", "8-K"], "accessionNumber": ["x", "y", acc],
                "filingDate": [filed, filed, filed], "items": ["", "5.02", "2.02,9.01"]}}})
        base = f"/{cik}/{acc.replace('-', '')}/"
        if u.endswith(base + "index.json"):
            return httpx.Response(200, json={"directory": {"item": [{"name": doc}, {"name": "ex99_2.htm"}]}})
        if u.endswith(base + doc):
            return httpx.Response(200, text=(FX / fx).read_text())
    return httpx.Response(404)


def test_fetch_extracts_verbatim_statements():
    p = ER.SecEarningsReleaseProvider(user_agent="t t@example.com",
                                      client_factory=lambda: httpx.Client(transport=httpx.MockTransport(_handler)))
    res = p.fetch(get_registry())
    assert [e.message for e in res.errors if e.level == "error"] == []
    (g,) = res.guidance
    assert (g.entity_id, g.target_period, g.value_low, g.value_high) == ("META", "2026", 135e9, 145e9)
    assert g.quote.startswith("We anticipate 2026 capital expenditures") and "$135-145 billion" in g.quote
    assert g.publication_date == dt.date(2026, 10, 21) and g.source_url.endswith("meta-09302026xexhibit991.htm")
    recs = {r.metric_id: r for r in res.records}
    az = recs["azure_growth_yoy"]
    assert az.value == 0.43 and az.period_end == dt.date(2026, 6, 30) and az.classification == "reported"
    assert az.period_start == dt.date(2026, 4, 1) and "Azure and other cloud services revenue increased 43%" in az.methodology
    ai = recs["ai_revenue_disclosed"]
    assert ai.value == 25e9 and ai.classification == "qualitative" and "LOWER BOUND" in ai.methodology
    assert ai.period_end == dt.date(2026, 6, 30) and ai.publication_date == dt.date(2026, 7, 30)


def test_pick_ex991_and_releases():
    assert ER.pick_ex991(["a-ex99_2.htm", "a-ex99_1.htm", "R1.htm"]) == "a-ex99_1.htm"
    assert ER.pick_ex991(["googexhibit991q22026.htm"]) == "googexhibit991q22026.htm"
    assert ER.pick_ex991(["x-ex991.htm", "x-ex9910.htm"]) == "x-ex991.htm"
    assert ER.pick_ex991(["R1.htm"]) is None


def test_quarter_end_infers_year_and_rejects_far_dates():
    assert ER.quarter_end("Three Months Ended September 30, % Change", dt.date(2026, 10, 21)) == dt.date(2026, 9, 30)
    assert ER.quarter_end("Three Months Ended March 31, 2025", dt.date(2026, 10, 21)) is None


def test_missing_statement_is_warning_not_value():
    text = "<p>Three Months Ended June 30, 2026 We expect capital expenditures to grow.</p>"
    assert ER.extract(ER.html_to_text(text), get_registry().metrics["capex_guidance"].params["patterns"]["META"]) == []
