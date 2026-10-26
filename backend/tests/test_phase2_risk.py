"""Risk engine: interpolation, missing != zero risk, coverage gate."""
import datetime as dt

from app.services.risk import Value, interp, load_config, score

CFG = {
    "min_coverage": 0.5,
    "dimensions": [{"id": "a", "name": "A", "weight": 60}, {"id": "b", "name": "B", "weight": 40}],
    "indicators": [
        {"id": "a1", "dimension": "a", "name": "a1", "thresholds": {"benign": 0, "stretched": 10}},
        {"id": "a2", "dimension": "a", "name": "a2", "thresholds": {"benign": 10, "stretched": 0}},
        {"id": "b1", "dimension": "b", "name": "b1", "thresholds": {"benign": 0, "stretched": 1}},
    ],
}


def test_interp_clamped_and_reversed():
    assert interp(5, 0, 10) == 50 and interp(-3, 0, 10) == 0 and interp(30, 0, 10) == 100
    assert interp(2.5, 10, 0) == 75  # reversed direction


def test_missing_is_not_zero_risk():
    r = score(CFG, {"a1": Value(5, "ok"), "a2": Value(None, "missing"), "b1": Value(None, "unavailable")})
    assert r["coverage"] == 0.3
    assert r["score"] is None and r["precise_score_withheld"]  # 30% < 50%
    assert r["score_low"] == 15.0 and r["score_high"] == 85.0  # missing spans 0..100, never assumed 0


def test_point_score_when_coverage_sufficient():
    r = score(CFG, {"a1": Value(5, "ok"), "a2": Value(5, "ok"), "b1": Value(None, "stale")})
    assert r["coverage"] == 0.6 and r["score"] == 50.0
    assert (r["score_low"], r["score_high"]) == (30.0, 70.0)
    b = next(d for d in r["dimensions"] if d["id"] == "b")
    assert b["score"] is None and b["coverage"] == 0


def test_stale_value_is_not_scored():
    r = score(CFG, {"a1": Value(9, "stale"), "a2": Value(0, "ok"), "b1": Value(1, "ok")})
    a1 = r["dimensions"][0]["indicators"][0]
    assert a1["score"] is None and a1["status"] == "stale"


def test_shipped_config_weights_and_hypothesis_label():
    cfg, h = load_config()
    assert [d["weight"] for d in cfg["dimensions"]] == [25, 20, 20, 15, 10, 10] and len(h) == 12
    for i in cfg["indicators"]:
        assert i["calc"] == "unavailable" or i["thresholds"]["benign"] != i["thresholds"]["stretched"]


def test_evaluate_on_empty_db(db_session):
    from app.services.risk import evaluate
    r = evaluate(db_session, dt.date(2026, 10, 27))
    assert r["coverage"] == 0 and r["score"] is None and r["score_low"] == 0 and r["score_high"] == 100
