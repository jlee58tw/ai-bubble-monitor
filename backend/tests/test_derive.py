import datetime as dt

import pandas as pd
import pytest

from app.services import derive as D

d = dt.date


def frame(entity, rows):
    out = []
    for i, (s, e, v, pub) in enumerate(rows):
        out.append({"id": hash((entity, e)) % 10000, "entity_id": entity, "period_start": s, "period_end": e,
                    "value": v, "publication_date": pub, "confidence": "high", "source_url": "u",
                    "fiscal_period": None})
    return pd.DataFrame(out)


Q = [(d(2024, 1, 1), d(2024, 3, 31)), (d(2024, 4, 1), d(2024, 6, 30)),
     (d(2025, 1, 1), d(2025, 3, 31)), (d(2025, 4, 1), d(2025, 6, 30))]


def test_fcf_subtract_and_pub_date_is_max():
    ocf = frame("X", [(*Q[0], 100.0, d(2024, 5, 1))])
    capex = frame("X", [(*Q[0], 30.0, d(2024, 5, 3))])
    out = D.subtract(ocf, capex)
    assert out["value"].tolist() == [70.0]
    assert out["publication_date"].tolist() == [d(2024, 5, 3)]


def test_ratio_skips_nonpositive_denominator():
    capex = frame("X", [(*Q[0], 30.0, d(2024, 5, 1)), (*Q[1], 30.0, d(2024, 8, 1))])
    ocf = frame("X", [(*Q[0], 60.0, d(2024, 5, 1)), (*Q[1], -5.0, d(2024, 8, 1))])
    out = D.ratio(capex, ocf, positive_denominator=True)
    assert out["value"].tolist() == [0.5]


def test_yoy_matches_same_quarter_prior_year():
    s = frame("X", [(*Q[0], 10.0, d(2024, 5, 1)), (*Q[1], 20.0, d(2024, 8, 1)),
                    (*Q[2], 15.0, d(2025, 5, 1)), (*Q[3], 30.0, d(2025, 8, 1))])
    out = D.yoy(s).set_index("period_end")["value"]
    assert out[d(2025, 3, 31)] == pytest.approx(0.5)
    assert out[d(2025, 6, 30)] == pytest.approx(0.5)
    assert len(out) == 2  # no prior-year data for 2024 -> no value (NOT zero)


def test_yoy_skips_negative_base():
    s = frame("X", [(*Q[0], -10.0, d(2024, 5, 1)), (*Q[2], 15.0, d(2025, 5, 1))])
    assert D.yoy(s).empty


def test_sum_entities_requires_all_members():
    a = pd.concat([frame("A", [(*Q[0], 1.0, d(2024, 5, 1)), (*Q[1], 1.0, d(2024, 8, 1))]),
                   frame("B", [(*Q[0], 2.0, d(2024, 5, 2))])])
    out = D.sum_entities(a, ["A", "B"], "AB")
    assert out["value"].tolist() == [3.0]
    assert out["fiscal_period"].tolist() == ["CY2024 Q1"]
