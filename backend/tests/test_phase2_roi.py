import pytest
from fastapi.testclient import TestClient

from app.services.roi import RoiInputs, compute


def test_spec_formulas_exact():
    x = RoiInputs(success_probability=0.6, review_minutes=15, reviewer_hourly_rate=60, inference_cost=0.5,
                  tool_cost=0.1, rework_cost=20, rework_share=0.7, failure_recovery_cost=40,
                  baseline_human_cost=50, task_volume=1000)
    r = compute(x)
    t = r["per_task"]
    assert t["human_review_cost"] == pytest.approx(15.0)
    assert t["expected_rework_cost"] == pytest.approx(0.4 * 0.7 * 20)        # 5.6
    assert t["expected_failure_loss"] == pytest.approx(0.4 * 0.3 * 40)       # 4.8
    etc = 0.5 + 0.1 + 15 + 5.6 + 4.8
    assert t["effective_task_cost"] == pytest.approx(etc)                    # sum of the five spec terms
    assert r["effective_roi"] == pytest.approx((50 - etc) / 50)              # divided by BASELINE, per spec
    assert r["totals"]["effective_task_cost"] == pytest.approx(etc * 1000)
    assert r["totals"]["net_savings"] == pytest.approx((50 - etc) * 1000)


def test_break_even_gives_zero_roi():
    x = RoiInputs(baseline_human_cost=30)
    be = compute(x)["break_even_success_probability"]
    assert be == pytest.approx(1 - (30 - 15.6) / (0.7 * 20 + 0.3 * 40))
    r = compute(RoiInputs(baseline_human_cost=30, success_probability=be))
    assert r["effective_roi"] == pytest.approx(0, abs=1e-12)
    assert r["per_task"]["effective_task_cost"] == pytest.approx(x.baseline_human_cost)


def test_edge_cases():
    assert compute(RoiInputs(baseline_human_cost=0))["effective_roi"] is None
    r = compute(RoiInputs(rework_cost=0, failure_recovery_cost=0))
    assert r["break_even_success_probability"] is None and "does not depend on p" in r["break_even_note"]
    assert compute(RoiInputs(baseline_human_cost=1000))["break_even_note"].startswith("always profitable")
    with pytest.raises(ValueError):
        compute(RoiInputs(success_probability=1.2))
    with pytest.raises(ValueError):
        compute(RoiInputs(tool_cost=-1))


def test_roi_api():
    from app.main import app
    c = TestClient(app)  # no lifespan needed: pure calculation
    r = c.get("/api/roi", params={"success_probability": 1, "tool_cost": 0.4})
    assert r.status_code == 200
    j = r.json()
    assert j["per_task"]["expected_rework_cost"] == 0 and j["per_task"]["expected_failure_loss"] == 0
    assert j["per_task"]["effective_task_cost"] == pytest.approx(0.5 + 0.4 + 15)
    assert j["formulas"]["effective_roi"] == "(Baseline Human Cost - Effective Task Cost) / Baseline Human Cost"
    assert c.get("/api/roi", params={"rework_share": 2}).status_code == 422
