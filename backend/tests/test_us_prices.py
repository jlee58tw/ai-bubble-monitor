"""US prices: Tiingo adapter (SYNTHETIC payloads only - no key on this box), FRED index series, SEC dei share
counts (REAL trimmed companyfacts fixtures), and the split / market-cap / relative-return derivations."""
import datetime as dt
import json
from pathlib import Path

import httpx
import pandas as pd
import pytest

from app.providers.fred import parse_fred_csv
from app.providers.sec_edgar import records_from_companyfacts
from app.providers.tiingo import TiingoProvider, parse_prices
from app.registry.registry import load_registry
from app.services import derive as D

FIX = Path(__file__).parent / "fixtures"
d = dt.date

# SYNTHETIC: shape follows https://www.tiingo.com/documentation/end-of-day ; values are made up for tests and
# are never written to the application database.
SYNTHETIC_TIINGO = [
    {"date": "2024-06-06T00:00:00.000Z", "close": 1200.0, "adjClose": 120.0, "splitFactor": 1.0, "divCash": 0.0,
     "open": 1190.0, "high": 1210.0, "low": 1180.0, "volume": 100},
    {"date": "2024-06-07T00:00:00.000Z", "close": 1210.0, "adjClose": 121.0, "splitFactor": 1.0, "divCash": 0.0,
     "open": 1200.0, "high": 1220.0, "low": 1190.0, "volume": 100},
    {"date": "2024-06-10T00:00:00.000Z", "close": 122.0, "adjClose": 122.0, "splitFactor": 10.0, "divCash": 0.0,
     "open": 121.0, "high": 123.0, "low": 120.0, "volume": 1000},
]


def frame(entity, rows, conf="high"):
    return pd.DataFrame([{"id": i + 1 + 100 * len(entity), "entity_id": entity, "period_start": None,
                          "period_end": e, "value": v, "publication_date": e, "confidence": conf,
                          "source_url": "u", "fiscal_period": None} for i, (e, v) in enumerate(rows)])


def test_tiingo_parse_raw_close_and_split_days_only():
    recs = parse_prices(SYNTHETIC_TIINGO, "NVDA", "NVDA")
    closes = [r for r in recs if r.metric_id == "us_price_close"]
    splits = [r for r in recs if r.metric_id == "us_split_factor"]
    assert [r.value for r in closes] == [1200.0, 1210.0, 122.0]          # raw close, not adjClose
    assert closes[0].period_end == d(2024, 6, 6)
    assert [(r.period_end, r.value) for r in splits] == [(d(2024, 6, 10), 10.0)]
    assert all(r.classification == "reported" for r in recs)


def test_tiingo_parse_rejects_error_payload():
    with pytest.raises(Exception, match="Tiingo"):
        parse_prices({"detail": "Error: Ticker 'xxx' not found"}, "NVDA", "NVDA")


def test_tiingo_without_key_is_unavailable_and_fetches_nothing():
    p = TiingoProvider(api_key="")
    assert p.status().available is False and "TIINGO_API_KEY" in p.status().reason
    res = p.fetch(load_registry())
    assert res.records == [] and res.errors[0].level == "warning"


def test_tiingo_sends_key_in_header_not_url_and_redacts_errors():
    seen = []

    def handler(req: httpx.Request):
        seen.append(req)
        if "/nvda/" in str(req.url):
            return httpx.Response(200, json=SYNTHETIC_TIINGO)
        return httpx.Response(404, json={"detail": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(handler),
                          headers={"Authorization": "Token SECRETKEY123"})
    res = TiingoProvider(api_key="SECRETKEY123", client=client, min_interval_s=0.001).fetch(
        load_registry(), entity_ids=["NVDA", "AMD"])
    assert {r.entity_id for r in res.records} == {"NVDA"}
    assert all("SECRETKEY123" not in str(r.url) for r in seen)
    assert all("startDate=" in str(r.url) for r in seen)
    assert res.errors and all("SECRETKEY123" not in e.message for e in res.errors)


def test_tiingo_covers_stocks_and_etf_proxies():
    reg = load_registry()
    ents = {e for m in reg.metrics_for_provider("tiingo") for e in m.entities}
    assert {"NVDA", "AMD", "MSFT", "GOOGL", "AMZN", "META", "ORCL", "TSM", "QQQ", "SOXX", "SMH"} <= ents
    assert "us_price_close" in [m.id for m in reg.metrics_for_provider("alphavantage")]   # alternative source


def test_fred_index_real_csv_and_series_mapping():
    reg = load_registry()
    m = reg.metrics["us_index_close"]
    assert m.params["series_by_entity"] == {"NDX": "NASDAQ100", "COMP": "NASDAQCOM", "SOX": "NASDAQSOX"}
    text = (FIX / "fred_nasdaqsox_2025_2026.csv").read_text()   # REAL FRED download (2026-10-28)
    recs = parse_fred_csv(text, "us_index_close", "SOX", "index", "https://fred.stlouisfed.org/series/NASDAQSOX",
                          "NASDAQSOX")
    assert recs[0].period_end == d(2025, 10, 1) and recs[0].value == pytest.approx(6500.28)
    assert len(recs) > 250 and all(r.value > 0 for r in recs)


def _dei_metric():
    return load_registry().metrics["us_shares_outstanding"]


def test_dei_shares_real_nvda():
    doc = json.loads((FIX / "companyfacts_dei_shares_nvda.json").read_text())
    errors = []
    recs, _ = records_from_companyfacts(doc, "NVDA", "0001045810", [_dei_metric()], errors)
    assert recs and all(r.metric_id == "us_shares_outstanding" and r.unit == "shares" for r in recs)
    assert all(r.value > 1e8 for r in recs)                    # pre-split counts are real (2009: 5.5e8)
    late = [r for r in recs if r.period_end >= d(2024, 8, 1)]
    assert late and all(r.value > 2e10 for r in late)          # after the 2024 10:1 split
    keys = [(r.period_end, r.publication_date) for r in recs]
    assert len(keys) == len(set(keys))                         # de-duplicated (cover date, filed)
    assert all(r.publication_date >= r.period_end for r in recs)


def test_dei_shares_multiclass_meta_is_warning_not_zero():
    doc = json.loads((FIX / "companyfacts_dei_shares_meta.json").read_text())
    errors = []
    recs, _ = records_from_companyfacts(doc, "META", "0001326801", [_dei_metric()], errors)
    assert recs == [] and errors and errors[0].level == "warning"


def test_split_adjust_divides_pre_split_prices():
    p = frame("NVDA", [(d(2024, 6, 7), 1210.0), (d(2024, 6, 10), 122.0)])
    s = frame("NVDA", [(d(2024, 6, 10), 10.0)])
    out = D.split_adjust(p, s)
    assert out["value"].tolist() == pytest.approx([121.0, 122.0])
    assert D.split_adjust(p, None)["value"].tolist() == [1210.0, 122.0]


def test_market_cap_asof_split_scale_and_max_age():
    p = frame("NVDA", [(d(2024, 6, 7), 1200.0), (d(2024, 6, 10), 120.0), (d(2024, 12, 31), 130.0)])
    sh = frame("NVDA", [(d(2024, 5, 15), 2.46e9)])
    s = frame("NVDA", [(d(2024, 6, 10), 10.0)])
    out = D.market_cap_asof(p, sh, s, max_age_days=120).set_index("period_end")["value"]
    assert out[d(2024, 6, 7)] == pytest.approx(1200.0 * 2.46e9)
    assert out[d(2024, 6, 10)] == pytest.approx(120.0 * 2.46e9 * 10)      # same cap across the split
    assert d(2024, 12, 31) not in out.index                               # snapshot too old -> no value
    t = D.market_cap_asof(frame("TSM", [(d(2025, 3, 3), 200.0)]), frame("TSM", [(d(2025, 2, 28), 25.9e9)]),
                          None, max_age_overrides={"TSM": 400}, scale={"TSM": 0.2})
    assert t["value"].iloc[0] == pytest.approx(200.0 * 25.9e9 * 0.2)


def test_market_cap_never_uses_future_snapshot():
    out = D.market_cap_asof(frame("AMD", [(d(2024, 1, 2), 140.0)]), frame("AMD", [(d(2024, 1, 20), 1.6e9)]), None)
    assert out.empty


def test_rel_return_against_index():
    days = [d(2024, 1, 2) + dt.timedelta(days=i) for i in range(0, 400)]
    a = frame("NVDA", [(x, 100.0 * (1 + i / 365)) for i, x in enumerate(days)])
    b = frame("SOX", [(x, 50.0 * (1 + 0.5 * i / 365)) for i, x in enumerate(days)])
    out = D.rel_return(a, b, "SOX")
    last = out.sort_values("period_end").iloc[-1]
    i = len(days) - 1; j = i - 365
    exp = ((1 + i / 365) / (1 + j / 365)) / ((1 + 0.5 * i / 365) / (1 + 0.5 * j / 365)) - 1
    assert last["value"] == pytest.approx(exp)
    assert out["period_end"].min() == days[365]                          # needs a full year of history
    gap = frame("SOX", [(x, 50.0) for x in days[300:]])                   # bench lacks the base date
    assert D.rel_return(a, gap, "SOX").empty


def test_fast_drawdown_matches_bruteforce():
    import random
    rnd = random.Random(7)
    days = [d(2023, 1, 2) + dt.timedelta(days=i) for i in range(0, 900) if rnd.random() > 0.3]
    vals = [100.0]
    for _ in days[1:]:
        vals.append(max(1.0, vals[-1] * (1 + rnd.uniform(-0.05, 0.05))))
    a = frame("X", list(zip(days, vals)))
    out = D.drawdown_52w(a).set_index("period_end")["value"]
    for i, t in enumerate(days):
        if (t - days[0]).days < 358:
            assert t not in out.index; continue
        hi = max(v for x, v in zip(days, vals) if t - dt.timedelta(days=365) < x <= t)
        assert out[t] == pytest.approx(vals[i] / hi - 1)


def test_effective_status_alternatives_and_upstream():
    from app.api.routes import effective_status
    st = {"tiingo": (False, "no tiingo key"), "alphavantage": (False, "no av key"), "fred": (True, None)}
    eff, why = effective_status("connected", "tiingo", st, {"alt_providers": ["alphavantage"]})
    assert eff == "unavailable" and "tiingo" in why and "av" in why
    st2 = dict(st, alphavantage=(True, None))
    assert effective_status("connected", "tiingo", st2, {"alt_providers": ["alphavantage"]})[0] == "connected"
    assert effective_status("connected", "derived", st, {"upstream": ["tiingo", "alphavantage"]})[0] == "unavailable"
    assert effective_status("connected", "derived", st, None)[0] == "connected"
    assert effective_status("connected", "fred", st, {})[0] == "connected"
