import datetime as dt

from app.services.periods import (Fact, Vintage, build_vintages, fiscal_label, fiscal_year_starts,
                                  months_of, quarterize, subtract_vintages)

D = dt.date


def F(s, e, v, filed, accn="a", form="10-Q", c="X"):
    return Fact(D.fromisoformat(s), D.fromisoformat(e), v, D.fromisoformat(filed), accn, form, c)


def test_months_of_handles_52_53_week_years():
    assert months_of(D(2025, 7, 1), D(2025, 9, 30)) == 3
    assert months_of(D(2025, 1, 27), D(2025, 4, 27)) == 3          # NVIDIA 13-week quarter
    assert months_of(D(2025, 1, 27), D(2026, 1, 25)) == 12          # 52-week year
    assert months_of(D(2025, 1, 1), D(2025, 6, 30)) == 6
    assert months_of(D(2025, 1, 1), D(2025, 2, 15)) is None


def test_ytd_to_quarterly_derivation():
    facts = [
        F("2025-07-01", "2025-09-30", 100, "2025-10-30", "q1", "10-Q"),
        F("2025-07-01", "2025-12-31", 250, "2026-01-28", "q2", "10-Q"),
        F("2025-07-01", "2026-03-31", 450, "2026-04-29", "q3", "10-Q"),
        F("2025-07-01", "2026-06-30", 700, "2026-07-29", "k", "10-K"),
    ]
    qs = quarterize(facts)
    assert [(q.end.isoformat(), q.vintages[-1].value, q.derived) for q in qs] == [
        ("2025-09-30", 100, False), ("2025-12-31", 150, True), ("2026-03-31", 200, True), ("2026-06-30", 250, True)]
    q4 = qs[-1]
    assert q4.start == D(2026, 4, 1)
    # publication date of a derived quarter = the later of its inputs (no look-ahead)
    assert q4.vintages[0].filed == D(2026, 7, 29)


def test_discrete_quarter_preferred_over_derivation():
    facts = [
        F("2025-01-01", "2025-03-31", 10, "2025-05-01"),
        F("2025-04-01", "2025-06-30", 12, "2025-08-01"),
        F("2025-01-01", "2025-06-30", 22, "2025-08-01"),
        # trailing-twelve-month value in a 10-Q (Amazon style) must be ignored
        F("2024-07-01", "2025-06-30", 99, "2025-08-01"),
    ]
    qs = {q.end: q for q in quarterize(facts)}
    assert qs[D(2025, 6, 30)].derived is False and qs[D(2025, 6, 30)].vintages[-1].value == 12
    assert fiscal_year_starts(facts) == [D(2025, 1, 1)]


def test_revision_creates_new_vintage_and_comparatives_do_not():
    facts = [
        F("2024-01-01", "2024-03-31", 10, "2024-05-01", "orig"),
        F("2024-01-01", "2024-03-31", 10, "2025-05-01", "comparative"),   # same value -> not a vintage
        F("2024-01-01", "2024-03-31", 11, "2025-08-01", "restated"),
    ]
    vs = build_vintages(facts)[(D(2024, 1, 1), D(2024, 3, 31))]
    assert [(v.value, v.filed) for v in vs] == [(10, D(2024, 5, 1)), (11, D(2025, 8, 1))]


def test_subtract_vintages_point_in_time():
    a = [Vintage(300, D(2025, 1, 10), ("a1",)), Vintage(310, D(2025, 6, 1), ("a2",))]
    b = [Vintage(100, D(2025, 2, 1), ("b1",))]
    out = subtract_vintages(a, b)
    assert [(v.value, v.filed) for v in out] == [(200, D(2025, 2, 1)), (210, D(2025, 6, 1))]


def test_fiscal_labels():
    starts = [D(2024, 7, 1), D(2025, 7, 1)]                    # Microsoft, FY ends June
    assert fiscal_label(D(2025, 7, 1), D(2025, 9, 30), starts) == "FY2026 Q1"
    assert fiscal_label(D(2026, 4, 1), D(2026, 6, 30), starts) == "FY2026 Q4"
    # new fiscal year not yet in starts list -> rolled forward
    assert fiscal_label(D(2026, 7, 1), D(2026, 9, 30), starts) == "FY2027 Q1"
    assert fiscal_label(D(2025, 1, 27), D(2025, 4, 27), [D(2024, 1, 29), D(2025, 1, 27)]) == "FY2026 Q1"  # NVDA
