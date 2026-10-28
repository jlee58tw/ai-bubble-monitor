"""Phase 3: point-in-time backtest, filing events, watchlist."""
import datetime as dt
import json

from fastapi.testclient import TestClient

from app.models import Observation
from app.services import backtest as bt
from tests.conftest import FIX

D = dt.date


def _obs(s, metric, ent, value, end, pub, supersedes=None):
    o = Observation(metric_id=metric, entity_id=ent, value=value, unit="x", period_end=end, publication_date=pub,
                    source_type="t", classification="reported", confidence="high", supersedes_id=supersedes)
    s.add(o); s.flush()
    return o


def _seed_registry(s):
    from app.registry.registry import sync_registry
    sync_registry(s)


def test_pit_cache_no_lookahead_and_revisions(db_session):
    s = db_session
    _seed_registry(s)
    a = _obs(s, "capex_total", "MSFT", 10, D(2025, 3, 31), D(2025, 4, 30))
    _obs(s, "capex_total", "MSFT", 12, D(2025, 3, 31), D(2025, 8, 1), supersedes=a.id)   # later revision
    _obs(s, "capex_total", "MSFT", 20, D(2025, 6, 30), D(2025, 7, 30))
    c = bt.PitCache(s, ["capex_total"])
    assert c.rows(["capex_total"], None, D(2025, 4, 29)) == []                       # not yet published
    assert [r.value for r in c.rows(["capex_total"], ["MSFT"], D(2025, 5, 1))] == [10]
    assert sorted(r.value for r in c.rows(["capex_total"], None, D(2025, 7, 31))) == [10, 20]   # revision invisible
    assert sorted(r.value for r in c.rows(["capex_total"], None, D(2025, 8, 1))) == [12, 20]    # revision replaces


def test_forward_returns_and_episodes():
    days = [D(2026, 1, 1) + dt.timedelta(days=i) for i in range(6)]
    p = dict(zip(days, [100, 105, 90, 95, 110, 99]))
    f = bt.fwd_min_returns(p, 2)
    assert f[days[0]] == 90 / 100 - 1 and f[days[4]] is None and f[days[5]] is None
    eps = bt.correction_episodes(p, 0.10)
    assert len(eps) == 2
    assert eps[0]["peak_date"] == days[1] and eps[0]["trigger_date"] == days[2] and eps[0]["recovered_date"] == str(days[4])
    assert eps[1]["peak_date"] == days[4] and eps[1]["recovered_date"] is None


def test_evaluate_signal_statuses():
    days = [D(2026, 1, 1) + dt.timedelta(days=i) for i in range(40)]
    fwd = {d: (-0.2 if i % 4 == 0 else 0.0) for i, d in enumerate(days)}
    # too short
    assert bt.evaluate_signal({d: True for d in days[:9]}, dict(list(fwd.items())[:9]), 5, 0.1)["status"] == "insufficient_data"
    # never on
    assert bt.evaluate_signal({d: False for d in days}, fwd, 5, 0.1)["status"] == "insufficient_data"
    # always on -> no timing information
    r = bt.evaluate_signal({d: True for d in days}, fwd, 5, 0.1)
    assert r["status"] == "no_variation" and r["hit_rate_on"] == r["base_rate"] == 0.25
    # missing signal days are excluded, never counted as OFF
    on = {d: (True if i % 4 == 0 else None) for i, d in enumerate(days)}
    on.update({days[1]: False, days[2]: False, days[3]: False} | {d: False for d in days[20:40] if days.index(d) % 4})
    r = bt.evaluate_signal(on, fwd, 5, 0.1)
    assert r["n_on"] == 10 and r["hits_on"] == 10 and r["hits_off"] == 0
    assert r["n_signal_known_days"] == r["n_on"] + r["n_off"] < 40
    assert r["status"] == "small_sample"


def test_lead_times_censoring_and_unknown():
    days = [D(2026, 1, 1) + dt.timedelta(days=i) for i in range(10)]
    ep = [{"peak_date": days[5], "trigger_date": days[8], "max_drawdown": -0.12, "peak_at_history_start": False}]
    on = {d: (i >= 3) for i, d in enumerate(days)}
    r = bt.lead_times(on, ep, 30)[0]
    assert r["status"] == "preceded" and r["lead_days_to_trigger"] == 5 and r["lead_days_to_peak"] == 2 and not r["left_censored"]
    assert bt.lead_times({d: True for d in days}, ep, 30)[0]["left_censored"]
    assert bt.lead_times({d: None for d in days}, ep, 30)[0]["status"] == "insufficient_data"
    assert bt.lead_times({d: False for d in days}, ep, 30)[0]["status"] == "no_preceding_signal"


def test_backtest_empty_db_is_explicit(db_session):
    _seed_registry(db_session)
    r = bt.run_backtest(db_session, today=D(2026, 10, 28))
    assert r["series_status"]["2330"]["status"] == "insufficient_data"
    assert r["series_status"]["US"]["status"] == "unavailable"
    assert r["window"]["trading_days"] == 0
    assert all(sg["status"] == "insufficient_data" for sg in r["signals"])
    assert all(h["composite_partial"] is None and h["score_high"] == 100 for h in r["history_monthly"])  # missing != 0 risk
    assert "research only" in bt.to_csv(r)


def test_parse_submissions_fixture_and_8k():
    from app.datasets.filings import parse_submissions
    rows = parse_submissions(json.loads((FIX / "nvda_submissions_trim.json").read_text()), "NVDA", "0001045810")
    assert rows and all(r["event_type"] == "periodic_report" for r in rows)
    assert all(r["filing_date"] >= r["report_date"] for r in rows)
    sub = {"filings": {"recent": {"form": ["8-K", "8-K", "4"], "accessionNumber": ["1-26-1", "1-26-2", "1-26-3"],
                                  "filingDate": ["2026-05-01"] * 3, "reportDate": ["2026-04-30", "2026-04-30", ""],
                                  "items": ["2.02,9.01", "5.02", ""]}}}
    r = parse_submissions(sub, "X", "0000000001")
    assert len(r) == 1 and r[0]["event_type"] == "earnings_release_8k" and r[0]["report_date"] == D(2026, 4, 30)


def test_events_guidance_watchlist_api(db_session):
    from app.datasets.runner import store_rows
    from app.main import app
    from app.models import IngestionRun, utcnow
    _seed_registry(db_session)
    run = IngestionRun(provider="sec_filing_events", trigger="test", status="success", started_at=utcnow())
    db_session.add(run); db_session.flush()
    store_rows(db_session, "filing_events", run, [{
        "entity_id": "MSFT", "cik": "0000789019", "accession_number": "0000950170-26-000001", "form": "10-Q",
        "event_type": "periodic_report", "filing_date": D(2026, 4, 29), "acceptance_datetime": None,
        "report_date": D(2026, 3, 31), "items": None, "primary_document": "x.htm", "primary_doc_description": "10-Q",
        "source_url": "https://www.sec.gov/x-index.htm"}])
    _obs(db_session, "capex_total", "MSFT", 1.0, D(2026, 3, 31), D(2026, 4, 29))
    db_session.commit()
    with TestClient(app) as c:
        ev = c.get("/api/events").json()
        assert ev["events"][0]["lag_days"] == 29 and ev["events"][0]["observation_date"] == "2026-03-31"
        assert any(n["entity_id"] == "2330" for n in ev["not_connected"])
        assert c.get("/api/guidance").json()["status"] == "placeholder"
        assert c.post("/api/watchlist", json={}).status_code == 422
        assert c.post("/api/watchlist", json={"entity_id": "NOPE"}).status_code == 404
        r = c.post("/api/watchlist", json={"entity_id": "MSFT", "metric_id": "capex_total", "note": "n"})
        assert r.status_code == 201 and r.json()["status"] == "ok" and r.json()["latest"][0]["value"] == 1.0
        assert r.json()["latest_filing"]["form"] == "10-Q"
        assert c.post("/api/watchlist", json={"entity_id": "MSFT", "metric_id": "capex_total"}).status_code == 409
        m = c.post("/api/watchlist", json={"metric_id": "us_price_close"}).json()
        assert m["status"] in ("unavailable", "missing") and m["latest"] == []
        assert len(c.get("/api/watchlist").json()) == 2
        assert c.delete(f"/api/watchlist/{r.json()['id']}").status_code == 200
        assert c.delete(f"/api/watchlist/{r.json()['id']}").status_code == 404
        b = c.get("/api/backtest", params={"include_daily": False}).json()
        assert b["series_status"]["US"]["status"] == "unavailable" and "daily" not in b
        assert c.get("/api/backtest.csv").status_code == 200


def test_backtest_uses_stored_us_split_adjusted_prices(db_session):
    s = db_session
    _seed_registry(s)
    days = [D(2024, 1, 1) + dt.timedelta(days=i) for i in range(330)]
    for i, d in enumerate(days):
        _obs(s, "us_price_split_adj", "NVDA", 100 + i, d, d)
        _obs(s, "us_price_split_adj", "AMD", 200 - 0.1 * i, d, d)
    _obs(s, "us_price_split_adj", "QQQ", 400, days[-1], days[-1])          # too short -> explicit, not dropped
    r = bt.run_backtest(s, today=D(2025, 1, 1))
    st = r["series_status"]
    assert "US" not in st and st["NVDA"]["status"] == "ok" and st["AMD"]["status"] == "ok"
    assert st["US_AI_BASKET"]["status"] == "ok" and st["QQQ"]["status"] == "insufficient_data"
    assert r["window"]["trading_days"] == 330
    assert any("survivorship" in c for c in r["caveats"]) and any("volatility" in c for c in r["caveats"])
