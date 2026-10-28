"""Step 1 (equity valuation) parsers + derive ops, against real payloads captured 2026-10-27 (UTC+8)."""
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from app.providers import alphavantage as AV
from app.providers import sec_filing_xbrl as SX
from app.providers import twse as T
from app.registry.registry import get_registry
from app.services import derive as D

FIX = Path(__file__).parent / "fixtures"
d = dt.date
CODES = {"2330", "2382", "2317"}


def test_roc_dates():
    assert T.roc_date("115/10/22") == d(2026, 10, 22)
    assert T.roc_date("1151022") == d(2026, 10, 22)
    assert T.num("2,385.00") == 2385.0 and T.num("--") is None


def test_twse_bwibbu_real():
    recs = T.parse_bwibbu(json.loads((FIX / "twse_bwibbu.json").read_text()), CODES)
    by = {(r.metric_id, r.entity_id): r for r in recs}
    assert by[("tw_pe_trailing", "2330")].value == pytest.approx(27.65)
    assert by[("tw_pb_ratio", "2330")].value == pytest.approx(9.61)
    assert by[("tw_dividend_yield", "2330")].value == pytest.approx(0.0092)
    assert by[("tw_pe_trailing", "2382")].value == pytest.approx(14.03)
    assert by[("tw_pe_trailing", "2317")].value == pytest.approx(16.15)
    assert all(r.period_end == d(2026, 10, 22) and r.classification == "reported" for r in recs)
    assert "1101" not in {r.entity_id for r in recs}


def test_twse_profile_shares_real():
    recs = T.parse_profile(json.loads((FIX / "twse_t187ap03_L.json").read_text()), CODES)
    by = {r.entity_id: r.value for r in recs}
    assert by == {"2330": 25_932_370_067, "2382": 4_107_627_432, "2317": 14_075_746_497}


def test_twse_stock_day_real():
    recs = T.parse_stock_day(json.loads((FIX / "twse_stock_day_2330_202610.json").read_text()), "2330", "u")
    last = max(recs, key=lambda r: r.period_end)
    assert last.period_end == d(2026, 10, 22) and last.value == 2385.0
    assert all(r.period_end.month == 10 for r in recs)


def test_twse_stock_day_bad_stat():
    with pytest.raises(ValueError):
        T.parse_stock_day({"stat": "很抱歉，沒有符合條件的資料!"}, "2330", "u")


def test_month_starts():
    assert T.month_starts(d(2026, 2, 5), 3) == ["202512", "202601", "202602"]


def test_alphavantage_demo_parse_and_errors():
    recs = AV.parse_daily(json.loads((FIX / "av_daily_ibm_demo.json").read_text()), "IBM", "IBM")
    assert len(recs) >= 90 and all(r.unit == "USD" and r.value > 0 for r in recs)
    assert recs == sorted(recs, key=lambda r: r.period_end)
    with pytest.raises(ValueError):
        AV.parse_daily({"Information": "rate limit"}, "X", "X")


def test_alphavantage_unconfigured_is_unavailable():
    p = AV.AlphaVantageProvider(api_key="")
    assert not p.status().available
    res = p.fetch(get_registry())
    assert res.records == [] and res.errors


def test_nvda_datacenter_instance_real():
    xml = (FIX / "nvda_10q_20260726_revenues_subset.xml").read_bytes()
    facts = SX.parse_instance(xml, ["Revenues"], "srt:ProductOrServiceAxis", "nvda:DataCenterMember",
                              d(2026, 8, 26), "0001045810-26-000075", "10-Q")
    by = {(f.start, f.end): f.val for f in facts}
    q = [v for (s, e), v in by.items() if e == d(2026, 7, 26) and (e - s).days < 100]
    assert q == [89_023_000_000]
    ytd = [v for (s, e), v in by.items() if e == d(2026, 7, 26) and (e - s).days > 150]
    assert ytd == [164_269_000_000]
    # HyperscaleMember etc. must NOT leak in (exactly-one-member rule)
    assert 48_710_000_000 not in by.values()


def test_nvda_records_from_facts():
    reg = get_registry()
    m = reg.metrics["nvda_datacenter_revenue"]
    xml = (FIX / "nvda_10q_20260726_revenues_subset.xml").read_bytes()
    facts = SX.parse_instance(xml, m.concepts, m.params["axis"], m.params["member"], d(2026, 8, 26), "A", "10-Q")
    recs = SX.records_from_facts(facts, m, "NVDA", "1045810")
    last = max(recs, key=lambda r: r.period_end)
    assert last.value == 89_023_000_000 and last.classification == "reported"
    assert last.source_url.startswith("https://www.sec.gov/Archives/edgar/data/1045810/")


def test_recent_filings():
    sub = json.loads((FIX / "nvda_submissions_trim.json").read_text())
    fs = SX.recent_filings(sub, 3)
    assert fs[0]["accn"] == "0001045810-26-000075" and fs[0]["doc"] == "nvda-20260726.htm"


def _px(entity, pts):
    return pd.DataFrame([{"id": i, "entity_id": entity, "period_start": None, "period_end": e, "value": v,
                          "publication_date": e, "confidence": "high", "source_url": "u", "fiscal_period": None}
                         for i, (e, v) in enumerate(pts)])


def test_drawdown_requires_full_window_and_uses_52w_high():
    pts = [(d(2025, 1, 1), 100.0), (d(2025, 6, 1), 200.0), (d(2025, 12, 31), 150.0), (d(2026, 7, 1), 120.0)]
    out = D.drawdown_52w(_px("X", pts))
    got = dict(zip(out["period_end"], out["value"]))
    assert d(2025, 6, 1) not in got  # history shorter than 358 days -> no value, not 0
    assert got[d(2025, 12, 31)] == pytest.approx(150 / 200 - 1)
    # 2025-06-01 high has rolled out of the window by 2026-07-01 (window (2025-07-01, 2026-07-01])
    assert got[d(2026, 7, 1)] == pytest.approx(120 / 150 - 1)


def test_multiply_asof_gap():
    px = _px("X", [(d(2026, 10, 22), 10.0), (d(2026, 1, 2), 9.0)])
    sh = _px("X", [(d(2026, 10, 25), 1000.0)])
    out = D.multiply_asof(px, sh, max_gap_days=45)
    assert out["value"].tolist() == [10_000.0]
    assert out["publication_date"].tolist() == [d(2026, 10, 25)]


def test_nvda_comparative_only_quarters_are_dropped_not_dated_late():
    """Audit finding: quarters seen only as prior-year comparatives in a later filing were stored with that later
    filing's date (a year late). With the original-filing map they are dropped instead."""
    reg = get_registry()
    m = reg.metrics["nvda_datacenter_revenue"]
    xml = (FIX / "nvda_10q_20260726_revenues_subset.xml").read_bytes()
    facts = SX.parse_instance(xml, m.concepts, m.params["axis"], m.params["member"], d(2026, 8, 26), "A", "10-Q")
    own = {d(2026, 7, 26): d(2026, 8, 26), d(2025, 7, 27): d(2025, 8, 27)}
    recs = SX.records_from_facts(facts, m, "NVDA", "1045810", own)
    ends = {r.period_end for r in recs}
    assert d(2026, 7, 26) in ends and d(2025, 7, 27) not in ends
    assert all(r.publication_date >= r.period_end for r in recs)
    sub = {"filings": {"recent": {"form": ["10-Q", "8-K", "10-Q"], "reportDate": ["2026-07-26", "2026-08-26", "2025-07-27"],
                                  "filingDate": ["2026-08-26", "2026-08-26", "2025-08-27"]}}}
    assert SX.original_filing_dates(sub) == own
