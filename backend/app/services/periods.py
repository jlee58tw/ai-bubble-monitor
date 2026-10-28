"""Pure functions turning SEC XBRL duration facts into quarterly series with vintages.

Terminology
-----------
fact     : one value as it appeared in one filing: (start, end, val, filed, accn, form)
vintage  : the value of a period as known on a given publication (filed) date.
           A period may have several vintages if a later filing restated it.

Cash-flow statements in 10-Qs are year-to-date (3, 6, 9 months); the 10-K has 12 months.
A quarter that isn't reported as a discrete 3-month fact is DERIVED as
YTD(m months) - YTD(m-3 months) with the same fiscal-year start date.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

ALLOWED_FORMS = {"10-Q", "10-K", "10-Q/A", "10-K/A", "10-KT", "10-KT/A"}


@dataclass(frozen=True)
class Fact:
    start: dt.date
    end: dt.date
    val: float
    filed: dt.date
    accn: str
    form: str
    concept: str


@dataclass
class Vintage:
    value: float
    filed: dt.date
    accns: tuple[str, ...]


@dataclass
class QuarterSeries:
    start: dt.date
    end: dt.date
    concept: str
    derived: bool
    vintages: list[Vintage]
    ytd_months: int | None = None  # for derived: m of YTD(m) - YTD(m-3)


def months_of(start: dt.date, end: dt.date) -> int | None:
    """Classify a duration as 3/6/9/12 months (tolerant of 52/53-week years); None otherwise."""
    days = (end - start).days + 1
    for m, lo, hi in ((3, 80, 100), (6, 170, 192), (9, 260, 283), (12, 350, 380)):
        if lo <= days <= hi:
            return m
    return None


def parse_facts(raw: list[dict], concept: str) -> list[Fact]:
    """Parse companyfacts unit entries (duration facts only, 10-Q/10-K family forms only)."""
    out = []
    for f in raw:
        if "start" not in f or f.get("form") not in ALLOWED_FORMS:
            continue
        try:
            out.append(Fact(
                start=dt.date.fromisoformat(f["start"]), end=dt.date.fromisoformat(f["end"]),
                val=float(f["val"]), filed=dt.date.fromisoformat(f["filed"]), accn=f["accn"],
                form=f["form"], concept=concept,
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def build_vintages(facts: list[Fact]) -> dict[tuple[dt.date, dt.date], list[Vintage]]:
    """Group facts by (start, end); keep only value CHANGES ordered by filed date.

    The first vintage's ``filed`` is the original publication date (point-in-time safe).
    """
    by_key: dict[tuple, list[Fact]] = defaultdict(list)
    for f in facts:
        by_key[(f.start, f.end)].append(f)
    out: dict[tuple, list[Vintage]] = {}
    for key, fs in by_key.items():
        fs.sort(key=lambda x: (x.filed, x.accn))
        vs: list[Vintage] = []
        for f in fs:
            if vs and abs(vs[-1].value - f.val) < 0.5:  # same value re-reported as comparative
                continue
            if vs and vs[-1].filed == f.filed:  # same-day conflict: keep the later accession
                vs[-1] = Vintage(f.val, f.filed, (f.accn,))
                continue
            vs.append(Vintage(f.val, f.filed, (f.accn,)))
        out[key] = vs
    return out


def value_asof(vs: list[Vintage], d: dt.date) -> Vintage | None:
    cur = None
    for v in vs:
        if v.filed <= d:
            cur = v
        else:
            break
    return cur


def subtract_vintages(a: list[Vintage], b: list[Vintage]) -> list[Vintage]:
    """Vintages of (a - b): evaluated at every date either input changed, once both exist."""
    da, db = {v.filed for v in a}, {v.filed for v in b}
    out: list[Vintage] = []
    for d in sorted(da | db):
        va, vb = value_asof(a, d), value_asof(b, d)
        if va is None or vb is None:
            continue
        # After the first value, a new vintage needs BOTH inputs restated on the same date. If only one side changed
        # (e.g. a 10-K recasts the full year for a segment re-organisation but the 9-month YTD is still on the old
        # basis), a - b mixes bases and is garbage (audit 2026-10-28: MSFT Intelligent Cloud FY2023 Q4 = 1,053M).
        # Allowed: the first pair, both inputs restated on this date, or both inputs already restated (e.g. a 10-Q
        # recast the 9M comparative and a later 10-K recast the full year -> consistent new basis).
        ra, rb = va is not a[0], vb is not b[0]
        if out and not (d in da and d in db) and ra != rb:
            continue
        val = va.value - vb.value
        if out and abs(out[-1].value - val) < 0.5:
            continue
        # most recently filed input first: that filing is the publication of this vintage
        first, second = (va, vb) if va.filed >= vb.filed else (vb, va)
        out.append(Vintage(val, d, tuple(dict.fromkeys(first.accns + second.accns))))
    return out


def quarterize(facts: list[Fact]) -> list[QuarterSeries]:
    """Discrete-quarter series from one concept's facts (reported 3-month facts preferred)."""
    if not facts:
        return []
    concept = facts[0].concept
    vint = build_vintages(facts)
    # bucket by duration
    by_months: dict[int, dict[tuple, list[Vintage]]] = defaultdict(dict)
    for (s, e), vs in vint.items():
        m = months_of(s, e)
        if m:
            by_months[m][(s, e)] = vs

    result: dict[dt.date, QuarterSeries] = {}
    for (s, e), vs in by_months[3].items():
        result[e] = QuarterSeries(s, e, concept, False, vs)

    for m in (6, 9, 12):
        for (s, e), vs in by_months[m].items():
            if e in result:  # discrete quarter already reported
                continue
            prev = [(ps, pe) for (ps, pe) in by_months[m - 3] if ps == s and 80 <= (e - pe).days <= 100]
            if len(prev) != 1:
                continue
            pk = prev[0]
            q_vs = subtract_vintages(vs, by_months[m - 3][pk])
            if q_vs:
                result[e] = QuarterSeries(pk[1] + dt.timedelta(days=1), e, concept, True, q_vs, ytd_months=m)
    return sorted(result.values(), key=lambda q: q.end)


def fiscal_year_starts(all_facts: list[Fact]) -> list[dt.date]:
    """Fiscal-year start dates inferred from 10-K annual facts and 10-Q 6/9-month YTD facts.

    (10-Q 12-month facts are excluded: Amazon reports trailing-twelve-month cash flows in 10-Qs.)
    """
    starts = set()
    for f in all_facts:
        m = months_of(f.start, f.end)
        if (m == 12 and f.form.startswith("10-K")) or (m in (6, 9) and f.form.startswith("10-Q")):
            starts.add(f.start)
    return sorted(starts)


def fiscal_label(q_start: dt.date, q_end: dt.date, fy_starts: list[dt.date]) -> str | None:
    """e.g. 'FY2026 Q1'. Fiscal year is named after the calendar year in which it ENDS."""
    cands = [s for s in fy_starts if s <= q_start + dt.timedelta(days=5)]
    if not cands:
        return None
    s = max(cands)
    n = round(((q_end - s).days + 1) / 91.3)
    if not 1 <= n <= 4:
        # FY start not yet observed (e.g. first quarter of a new fiscal year with no YTD yet)
        s2 = s.replace(year=s.year + 1) if n > 4 else s
        n = round(((q_end - s2).days + 1) / 91.3)
        if not 1 <= n <= 4:
            return None
        s = s2
    fy = (s + dt.timedelta(days=360)).year
    return f"FY{fy} Q{n}"
