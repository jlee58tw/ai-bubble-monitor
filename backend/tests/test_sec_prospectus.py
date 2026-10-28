"""S-1 prospectus adapter (Anthropic, PBC). Fixture = real text-normalised excerpt of the EDGAR S-1 filed 2026-10-26."""
import datetime as dt
from pathlib import Path

import httpx
import pytest

from app.providers import sec_prospectus as SP
from app.registry.registry import get_registry

FIX = Path(__file__).parent / "fixtures" / "anthropic_s1_quarterly_excerpt.htm"


def test_parse_quarterly_table_real_excerpt():
    ends, rows = SP.parse_quarterly_table(SP.html_to_text(FIX.read_text()))
    assert ends == [dt.date(2025, 3, 31), dt.date(2025, 6, 30), dt.date(2025, 9, 30), dt.date(2025, 12, 31),
                    dt.date(2026, 3, 31), dt.date(2026, 6, 30)]
    assert rows["Revenue"] == [376, 787, 1382, 2040, 4731, 11555]
    assert sum(rows["Revenue"][:4]) == 4585          # = FY2025 revenue in the annual table
    assert sum(rows["Revenue"][4:]) == 16286         # = H1 2026 revenue
    assert rows["Personnel"][0] == 218               # footnote marker "(1)" must not shift columns
    assert rows["Operating income (loss)"] == [-935, -1200, -3089, -2836, -1667, 974]
    assert rows["Bartz settlement"] == [0, 0, 1500, 0, 0, 0]


def test_parse_rejects_misaligned_table():
    bad = SP.TABLE_START + " March 31, 2025 June 30, 2025 Revenue $ 10 $ 20 Total operating expenses 5 5 Operating income (loss) 5 99"
    with pytest.raises(ValueError, match="does not foot"):
        SP.parse_quarterly_table(bad)


def test_provider_records_are_disclosed_not_reported():
    sub = {"filings": {"recent": {"form": ["S-1", "DRS/A"], "accessionNumber": ["0001628280-26-067168", "x"],
                                  "filingDate": ["2026-10-26", "2026-10-09"],
                                  "primaryDocument": ["anthropicpbc-sx1.htm", "f.htm"]}}}

    def handler(req: httpx.Request) -> httpx.Response:
        if "submissions" in str(req.url):
            return httpx.Response(200, json=sub)
        assert str(req.url).endswith("/2130357/000162828026067168/anthropicpbc-sx1.htm")
        return httpx.Response(200, text=FIX.read_text())

    p = SP.SecProspectusProvider(user_agent="test test@example.com",
                                 client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler)))
    res = p.fetch(get_registry())
    assert not [e for e in res.errors if e.level != "warning"]
    recs = {(r.metric_id, r.period_end): r for r in res.records}
    assert len(recs) == 18
    r = recs[("ai_lab_revenue", dt.date(2026, 6, 30))]
    assert r.value == 11_555e6 and r.classification == "disclosed" and r.entity_id == "ANTHROPIC"
    assert r.publication_date == dt.date(2026, 10, 26) and r.period_start == dt.date(2026, 4, 1)
    assert r.fiscal_period == "CY2026 Q2" and r.source_url.startswith("https://www.sec.gov/Archives/")
    assert recs[("ai_lab_operating_income", dt.date(2025, 9, 30))].value == -3_089e6
    assert all(x.classification != "reported" for x in res.records)
