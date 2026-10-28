import datetime as dt

from app.datasets.runner import store_rows
from app.models import IngestionRun, RiskSnapshot, utcnow
from app.services.alerts import compute_alerts


def _run(s):
    r = IngestionRun(provider="t", trigger="test", status="success", started_at=utcnow()); s.add(r); s.flush()
    return r


def test_price_cut_and_scheduled_alerts(db_session):
    s = db_session
    base = dict(vendor="v", model_id="m", model_label="M", tier="std", price_type="input", price_status="current",
                effective_from=None, effective_to=None, usd_per_mtok=10.0, source_url="u", raw_text="$10",
                note=None, open_weight=False)
    store_rows(s, "model_prices", _run(s), [base])
    store_rows(s, "model_prices", _run(s), [dict(base, usd_per_mtok=5.0)])
    store_rows(s, "model_prices", _run(s), [dict(base, price_status="scheduled", usd_per_mtok=8.0,
                                                 effective_from=dt.date.today() + dt.timedelta(days=30))])
    titles = [a["title"] for a in compute_alerts(s)]
    assert any("$10 -> $5/MTok (-50%)" in t for t in titles)
    assert any("scheduled $8/MTok" in t and "+60% vs current $5" in t for t in titles)


def test_no_alerts_from_empty_data(db_session):
    assert compute_alerts(db_session) == []


def test_risk_rise_only_same_config(db_session):
    s = db_session
    t0 = dt.datetime(2026, 10, 1)
    s.add_all([RiskSnapshot(computed_at=t0, config_hash="A", coverage=0.6, score=40, score_low=20, score_high=70, detail={}),
               RiskSnapshot(computed_at=t0 + dt.timedelta(days=1), config_hash="B", coverage=0.6, score=10,
                            score_low=5, score_high=50, detail={}),
               RiskSnapshot(computed_at=t0 + dt.timedelta(days=7), config_hash="A", coverage=0.6, score=48,
                            score_low=25, score_high=75, detail={})])
    s.flush()
    a = [x for x in compute_alerts(s) if x["category"] == "risk"]
    assert len(a) == 1 and "40.0 -> 48.0" in a[0]["title"]


def test_model_price_change_ignores_metadata_only_revisions(db_session):
    """Audit 2026-10-28: a revision that only fills effective_to (same price) is not a price change."""
    from app.models import ModelPrice
    from app.services.risk import calc_model_price_change
    s = db_session
    base = dict(vendor="openai", model_id="m", model_label="M", tier="std", price_type="input",
                price_status="current", effective_from=None, effective_to=None, usd_per_mtok=10.0,
                source_url="u", raw_text="$10", note=None, open_weight=False)
    store_rows(s, "model_prices", _run(s), [base])
    for row in s.query(ModelPrice):  # pretend the first observation is old enough
        row.first_seen_at = utcnow() - dt.timedelta(days=200)
    store_rows(s, "model_prices", _run(s), [dict(base, effective_to=dt.date(2026, 12, 31))])  # metadata only
    store_rows(s, "model_prices", _run(s), [dict(base, model_id="m2")])
    store_rows(s, "model_prices", _run(s), [dict(base, model_id="m2", usd_per_mtok=5.0, effective_to=dt.date(2026, 12, 31))])
    ind = {"args": {"vendors": ["openai"], "min_history_days": 90, "min_changes": 1}}
    v = calc_model_price_change(s, ind, dt.date.today())
    assert v.status == "ok" and v.value == -0.5 and v.detail.startswith("1 observed")
