import datetime as dt

from app.providers.sec_edgar import records_from_companyfacts
from app.registry.registry import load_registry


def current(recs):
    cur = {}
    for r in sorted(recs, key=lambda r: r.publication_date):
        cur[r.key] = r
    return cur


def test_msft_fixture_capex_quarters(msft_doc):
    reg = load_registry()
    recs, n = records_from_companyfacts(msft_doc, "MSFT", "0000789019", reg.metrics_for_provider("sec_edgar"))
    assert n > 0
    cur = current(recs)
    k = ("capex_total", "MSFT", dt.date(2025, 4, 1), dt.date(2025, 6, 30))
    r = cur[k]
    # FY2025 Q4 = FY2025 (64,551m) - 9M YTD (47,472m) = 17,079m ; labeled DERIVED
    assert r.value == 17_079_000_000
    assert r.classification == "derived"
    assert r.fiscal_period == "FY2025 Q4"
    assert r.publication_date == dt.date(2025, 7, 30)
    assert "sec.gov/Archives/edgar/data/789019/" in r.source_url
    # link points at the filing that PUBLISHED the derived value (the 10-K), not the older 10-Q input
    assert r.methodology.split("Filings: ")[1].split(",")[0] in r.source_url
    q1 = cur[("capex_total", "MSFT", dt.date(2025, 7, 1), dt.date(2025, 9, 30))]
    assert q1.classification == "reported" and q1.value == 19_394_000_000


def test_amzn_uses_discrete_quarters_not_ttm(amzn_doc):
    reg = load_registry()
    recs, _ = records_from_companyfacts(amzn_doc, "AMZN", "0001018724", reg.metrics_for_provider("sec_edgar"))
    cur = current(recs)
    q = cur[("capex_total", "AMZN", dt.date(2026, 4, 1), dt.date(2026, 6, 30))]
    assert q.value == 54_208_000_000 and q.classification == "reported"
    assert q.source_ref == "us-gaap:PaymentsToAcquireProductiveAssets"
    # Q4 2025 derived from FY - 9M: 131,819 - 92,297 = 39,522
    q4 = cur[("capex_total", "AMZN", dt.date(2025, 10, 1), dt.date(2025, 12, 31))]
    assert q4.value == 39_522_000_000 and q4.classification == "derived"
    # no record spans 12 months (TTM values must never be stored as a quarter)
    assert all((r.period_end - r.period_start).days < 100 for r in recs)


def test_total_capex_is_not_labeled_ai():
    reg = load_registry()
    m = reg.metrics["capex_total"]
    assert m.is_ai_specific is False
    assert "not ai" in m.warning.lower()
    assert reg.metrics["nvda_datacenter_revenue"].status == "unavailable"


def test_fred_csv_skips_missing_values():
    from app.providers.fred import parse_fred_csv
    text = "observation_date,DGS10\n2026-10-20,5.12\n2026-10-21,.\n2026-10-22,4.96\n"
    recs = parse_fred_csv(text, "us10y_yield", "US", "pct_points", "https://fred.stlouisfed.org/series/DGS10", "DGS10")
    assert [r.value for r in recs] == [5.12, 4.96]  # '.' is missing -> skipped, never 0
    assert recs[0].source_ref == "FRED:DGS10"
