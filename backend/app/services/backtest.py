"""Historical signal backtest (research prototype - NOT evidence of predictive validity).

Point-in-time rule (no look-ahead): the signal on date d is computed only from observations whose
publication_date <= d, using the version of each value that was current on d (later revisions are invisible).
Only risk indicators that read the append-only observations table can be reconstructed this way; dataset-based
indicators (model prices, GPU list prices, benchmarks) were first collected recently and are marked
`not_point_in_time` (excluded, which widens the score range - never counted as zero risk).

Outcomes: forward minimum return over the next H trading days on TWSE daily closes (2330, 2382, 2317 and an
equal-weight basket). US prices are used only if us_price_close history exists (needs ALPHAVANTAGE_API_KEY).
A "hit" = signal ON at d and the close falls >= X% below d's close within H trading days.
Lead time = days from the start of the signal's ON run to the date a >= X% peak-to-trough correction was
confirmed (and to its peak). With ~13 months of prices there are only a handful of independent windows, so
every number is reported with sample sizes, an overlap-adjusted interval and explicit caveats.
"""
from __future__ import annotations

import bisect
import csv
import datetime as dt
import io
import math
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Observation
from . import risk as risk_svc
from .queries import query_observations

TW_CODES = ["2330", "2382", "2317"]
CAVEATS = [
    "Research prototype. Not investment advice and NOT evidence that any signal predicts drawdowns.",
    "Price history is ~13 months of TWSE daily closes (3 stocks + basket); US prices are not stored. "
    "That is a handful of independent outcome windows - far too few for statistical validity.",
    "Forward windows overlap day to day; intervals use an overlap-adjusted effective sample size (n / H) and are "
    "approximate.",
    "Thresholds are the same research hypotheses as the live risk engine; they were not fitted to this window, "
    "but nothing here is out-of-sample validation either.",
    "Fundamental signals (SEC quarterly data) change only at filing dates; a signal that is ON for the whole window "
    "carries no timing information (its hit rate equals the base rate).",
    "Dataset-based indicators (model prices, GPU prices, benchmarks) have no stored history before they were first "
    "collected and are excluded (not_point_in_time); missing indicators widen the range and never count as zero risk.",
]


@dataclass(slots=True)
class Row:
    id: int
    metric_id: str
    entity_id: str
    value: float
    period_end: dt.date
    publication_date: dt.date
    fiscal_period: str | None
    supersedes_id: int | None


class PitCache:
    """In-memory, point-in-time view of the append-only observations (all vintages)."""

    def __init__(self, session: Session, metric_ids: list[str]):
        self.series: dict[str, dict[str, list[Row]]] = defaultdict(lambda: defaultdict(list))
        for o in query_observations(session, metric_ids, include_history=True):
            self.series[o.metric_id][o.entity_id].append(Row(o.id, o.metric_id, o.entity_id, o.value, o.period_end,
                                                             o.publication_date, o.fiscal_period, o.supersedes_id))
        self.pubs: dict[tuple, list[dt.date]] = {}
        for m, ents in self.series.items():
            for e, rows in ents.items():
                rows.sort(key=lambda r: (r.publication_date, r.id))
                self.pubs[(m, e)] = [r.publication_date for r in rows]

    def rows(self, metrics: list[str], entities: list[str] | None, as_of: dt.date) -> list[Row]:
        out = []
        for m in metrics:
            for e, rows in self.series.get(m, {}).items():
                if entities and e not in entities:
                    continue
                vis = rows[:bisect.bisect_right(self.pubs[(m, e)], as_of)]
                sup = {r.supersedes_id for r in vis if r.supersedes_id}
                out.extend(r for r in vis if r.id not in sup)
        return out


def _metrics_of(ind: dict) -> list[str]:
    a = ind.get("args") or {}
    out = []
    for k in ("metric", "metric_a", "metric_b"):
        v = a.get(k)
        out += v if isinstance(v, list) else ([v] if v else [])
    return out


def pit_risk(cache: PitCache, cfg: dict, d: dt.date) -> dict:
    vals = {}
    for i in cfg["indicators"]:
        c = i.get("calc")
        if c == "unavailable":
            vals[i["id"]] = risk_svc.Value(None, "unavailable")
        elif c in risk_svc.OBS_CALCS:
            vals[i["id"]] = risk_svc.CALCS[c](cache, i, d)
        else:
            vals[i["id"]] = risk_svc.Value(None, "not_point_in_time")
    r = risk_svc.score(cfg, vals)
    ind = {x["id"]: x for dim in r["dimensions"] for x in dim["indicators"]}
    return {"coverage": r["coverage"], "score_gated": r["score"], "composite_partial": r["score_if_shown"],
            "score_low": r["score_low"], "score_high": r["score_high"],
            "indicators": {k: {"score": v["score"], "value": v["value"], "status": v["status"]} for k, v in ind.items()}}


def _prices(session: Session, metric: str, entities: list[str] | None = None) -> dict[str, dict[dt.date, float]]:
    out: dict[str, dict[dt.date, float]] = defaultdict(dict)
    for o in query_observations(session, [metric], entities):
        out[o.entity_id][o.period_end] = o.value
    return out


def _basket(series: dict[str, dict[dt.date, float]]) -> dict[dt.date, float]:
    if len(series) < 2:
        return {}
    common = sorted(set.intersection(*(set(s) for s in series.values())))
    if not common:
        return {}
    base = {k: s[common[0]] for k, s in series.items()}
    return {d: sum(s[d] / base[k] for k, s in series.items()) / len(series) * 100 for d in common}


def fwd_min_returns(prices: dict[dt.date, float], horizon: int) -> dict[dt.date, float | None]:
    ds = sorted(prices)
    out = {}
    for i, d in enumerate(ds):
        out[d] = (min(prices[x] for x in ds[i + 1:i + horizon + 1]) / prices[d] - 1) if i + horizon < len(ds) else None
    return out


def correction_episodes(prices: dict[dt.date, float], dd: float) -> list[dict]:
    """Peak-to-trough declines >= dd measured from the running peak within the AVAILABLE history only."""
    ds = sorted(prices)
    eps, peak_d, cur = [], None, None
    for d in ds:
        p = prices[d]
        if peak_d is None or p >= prices[peak_d]:
            if cur:
                cur["recovered_date"] = str(d); eps.append(cur); cur = None
            peak_d = d
            continue
        if cur is None and p <= prices[peak_d] * (1 - dd):
            cur = {"peak_date": peak_d, "peak": prices[peak_d], "trigger_date": d, "trough_date": d, "trough": p,
                   "recovered_date": None, "peak_at_history_start": peak_d == ds[0]}
        if cur and p < cur["trough"]:
            cur["trough_date"], cur["trough"] = d, p
    if cur:
        eps.append(cur)
    for e in eps:
        e["max_drawdown"] = round(e["trough"] / e["peak"] - 1, 4)
    return eps


def wilson(h: int, n: float, z: float = 1.96) -> tuple[float, float] | None:
    if n <= 0:
        return None
    p = h / n if n >= h else 1.0
    p = min(max(p, 0.0), 1.0)
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(max(0.0, c - w), 4), round(min(1.0, c + w), 4)


def evaluate_signal(on: dict[dt.date, bool | None], fwd: dict[dt.date, float | None], horizon: int, dd: float) -> dict:
    ev = [(d, on.get(d), f) for d, f in sorted(fwd.items()) if f is not None]
    known = [(d, s, f) for d, s, f in ev if s is not None]
    res = {"n_outcome_days": len(ev), "n_signal_known_days": len(known),
           "n_independent_windows": round(len(known) / horizon, 1)}
    if len(known) < 2 * horizon:
        return {**res, "status": "insufficient_data",
                "reason": f"{len(known)} days with both a point-in-time signal and an observable {horizon}-day outcome "
                          f"(need >= {2 * horizon})"}
    hit = lambda f: f <= -dd  # noqa: E731
    n_on = sum(1 for _, s, _ in known if s)
    n_off = len(known) - n_on
    h_on = sum(1 for _, s, f in known if s and hit(f))
    h_off = sum(1 for _, s, f in known if not s and hit(f))
    base = (h_on + h_off) / len(known)
    res.update({"n_on": n_on, "n_off": n_off, "hits_on": h_on, "hits_off": h_off, "base_rate": round(base, 4),
                "hit_rate_on": round(h_on / n_on, 4) if n_on else None,
                "hit_rate_off": round(h_off / n_off, 4) if n_off else None})
    res["ci95_on_overlap_adjusted"] = wilson(round(h_on / horizon), n_on / horizon) if n_on else None
    if n_on == 0:
        return {**res, "status": "insufficient_data", "reason": "signal never ON in the evaluable window"}
    if n_off == 0:
        return {**res, "status": "no_variation",
                "reason": "signal ON on every evaluable day: hit rate = base rate, no timing information"}
    res["lift_vs_base"] = round(res["hit_rate_on"] / base, 3) if base else None
    return {**res, "status": "small_sample",
            "reason": f"only ~{res['n_independent_windows']} independent {horizon}-day windows"}


def lead_times(on: dict[dt.date, bool | None], episodes: list[dict], lookback_days: int) -> list[dict]:
    """For each correction episode: did the signal turn ON before the correction was confirmed, and how early?
    Unknown (None) signal days are never treated as OFF; a run that starts at the first known day is left-censored."""
    ds = sorted(d for d, v in on.items() if v is not None)
    out = []
    for e in episodes:
        t = e["trigger_date"]
        row = {"peak_date": str(e["peak_date"]), "trigger_date": str(t), "max_drawdown": e["max_drawdown"],
               "peak_at_history_start": e["peak_at_history_start"]}
        known = [d for d in ds if d <= t]
        if not known:
            out.append({**row, "status": "insufficient_data", "reason": "no point-in-time signal value before the event"})
            continue
        prior = [d for d in known if on[d]]
        if not prior or (t - prior[-1]).days > lookback_days:
            out.append({**row, "status": "no_preceding_signal"})
            continue
        i = ds.index(prior[-1])
        while i > 0 and on[ds[i - 1]]:
            i -= 1
        start = ds[i]
        cens = i == 0
        out.append({**row, "status": "preceded", "signal_on_since": str(start),
                    "lead_days_to_trigger": (t - start).days, "lead_days_to_peak": (e["peak_date"] - start).days,
                    "left_censored": cens,
                    "note": "signal already ON at the first day it can be evaluated: true lead time unknown (longer)"
                    if cens else None})
    return out


_CACHE: dict[tuple, dict] = {}


def run_backtest(session: Session, horizon: int = 20, drawdown: float = 0.10, composite_threshold: float = 60,
                 indicator_threshold: float = 70, lookback_days: int = 120, history_start: dt.date = dt.date(2010, 1, 31),
                 today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    cfg, h = risk_svc.load_config()
    stamp = session.execute(select(func.count(Observation.id), func.max(Observation.id))).one()
    key = (tuple(stamp), h, horizon, drawdown, composite_threshold, indicator_threshold, lookback_days,
           history_start, today)
    if key in _CACHE:
        return _CACHE[key]
    obs_inds = [i for i in cfg["indicators"] if i.get("calc") in risk_svc.OBS_CALCS]
    cache = PitCache(session, sorted({m for i in obs_inds for m in _metrics_of(i)}))

    # ---- outcome series (realized prices; outcomes may use the future, signals may not)
    series_status: dict[str, dict] = {}
    tw = _prices(session, "tw_price_close", TW_CODES)
    prices: dict[str, dict[dt.date, float]] = {}
    for c in TW_CODES:
        if len(tw.get(c, {})) >= 2 * horizon:
            prices[c] = tw[c]; series_status[c] = {"status": "ok", "days": len(tw[c]), "source": "TWSE STOCK_DAY"}
        else:
            series_status[c] = {"status": "insufficient_data", "days": len(tw.get(c, {}))}
    b = _basket({c: prices[c] for c in prices})
    if b:
        prices["TW_BASKET"] = b
        series_status["TW_BASKET"] = {"status": "ok", "days": len(b), "source": "equal-weight of available TWSE codes"}
    us = _prices(session, "us_price_close")
    series_status["US"] = ({"status": "unavailable", "reason": "no us_price_close history stored "
                                                               "(ALPHAVANTAGE_API_KEY not set); US outcomes not evaluated"}
                           if not us else {"status": "insufficient_data", "reason": f"{sum(map(len, us.values()))} rows; "
                                           "US outcome evaluation not implemented for <52 weeks of history"})

    days = sorted(set().union(*(set(p) for p in prices.values()))) if prices else []
    days = [d for d in days if d <= today]
    pit = {d: pit_risk(cache, cfg, d) for d in days}

    # ---- signals: missing indicator -> None (excluded), never "off"
    sig_defs = [{"id": "composite_partial", "name": "Composite risk score over point-in-time indicators (partial coverage)",
                 "threshold": composite_threshold, "get": lambda r: r["composite_partial"]},
                {"id": "score_gated", "name": "Official coverage-gated risk score",
                 "threshold": composite_threshold, "get": lambda r: r["score_gated"]}]
    for i in obs_inds:
        sig_defs.append({"id": i["id"], "name": i["name"], "threshold": indicator_threshold,
                         "get": (lambda r, k=i["id"]: r["indicators"][k]["score"])})
    fwd = {k: fwd_min_returns(p, horizon) for k, p in prices.items()}
    eps = {k: correction_episodes(p, drawdown) for k, p in prices.items()}
    signals = []
    for sd in sig_defs:
        on = {}
        for d in days:
            v = sd["get"](pit[d])
            on[d] = None if v is None else v >= sd["threshold"]
        known = [v for v in on.values() if v is not None]
        s = {"id": sd["id"], "name": sd["name"], "threshold": sd["threshold"],
             "days_known": len(known), "share_on": round(sum(known) / len(known), 4) if known else None,
             "per_series": {}, "lead_times": {}}
        if not known:
            s["status"] = "insufficient_data"
            s["reason"] = ("no point-in-time value in the price window"
                           + (" (coverage below min_coverage, so the gated score is withheld)" if sd["id"] == "score_gated" else ""))
        else:
            s["status"] = "computed"
            for k in prices:
                s["per_series"][k] = evaluate_signal({d: on[d] for d in prices[k] if d in on}, fwd[k], horizon, drawdown)
                s["lead_times"][k] = lead_times({d: on[d] for d in prices[k] if d in on}, eps[k], lookback_days)
        signals.append(s)

    # ---- long point-in-time history (month ends) of the composite: no outcomes (no stored prices that far back)
    hist, d = [], history_start
    while d <= today:
        r = pit_risk(cache, cfg, d)
        hist.append({"date": str(d), "coverage": r["coverage"], "composite_partial": r["composite_partial"],
                     "score_gated": r["score_gated"], "score_low": r["score_low"], "score_high": r["score_high"]})
        nd = (d.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
        d = (nd + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)

    daily = []
    for d in days:
        r = pit[d]
        daily.append({"date": str(d), "coverage": r["coverage"], "composite_partial": r["composite_partial"],
                      "score_gated": r["score_gated"],
                      "indicators": {k: v["score"] for k, v in r["indicators"].items() if k in {i["id"] for i in obs_inds}},
                      "close": {k: (round(p[d], 4) if d in p else None) for k, p in prices.items()},
                      "fwd_min_return": {k: (round(f[d], 4) if f.get(d) is not None else None) for k, f in fwd.items()}})
    out = {"computed_for": str(today), "config_hash": h,
           "params": {"horizon_trading_days": horizon, "drawdown": drawdown, "composite_threshold": composite_threshold,
                      "indicator_threshold": indicator_threshold, "lead_lookback_days": lookback_days},
           "caveats": CAVEATS,
           "label": "Backtest of research-hypothesis thresholds on a very short window. No predictive validity is claimed.",
           "window": {"start": str(days[0]) if days else None, "end": str(days[-1]) if days else None,
                      "trading_days": len(days)},
           "series_status": series_status,
           "excluded_indicators": [{"id": i["id"], "status": "unavailable" if i.get("calc") == "unavailable"
                                    else "not_point_in_time"} for i in cfg["indicators"] if i not in obs_inds],
           "episodes": {k: [{**e, "peak_date": str(e["peak_date"]), "trigger_date": str(e["trigger_date"]),
                             "trough_date": str(e["trough_date"])} for e in v] for k, v in eps.items()},
           "signals": signals, "daily": daily, "history_monthly": hist}
    _CACHE.clear(); _CACHE[key] = out
    return out


def to_csv(res: dict) -> str:
    daily = res["daily"]
    inds = sorted({k for r in daily for k in r["indicators"]})
    ser = sorted({k for r in daily for k in r["close"]})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"# AI Bubble Monitor backtest - research only, not investment advice. config {res['config_hash']}, "
                f"params {res['params']}. Signals are point-in-time (publication_date <= date). Empty cell = missing."])
    w.writerow(["date", "coverage", "composite_partial", "score_gated", *[f"ind_{i}" for i in inds],
                *[f"close_{s}" for s in ser], *[f"fwd_min_return_{s}" for s in ser]])
    blank = lambda v: "" if v is None else v  # noqa: E731
    for r in daily:
        w.writerow([r["date"], r["coverage"], blank(r["composite_partial"]), blank(r["score_gated"]),
                    *[blank(r["indicators"].get(i)) for i in inds], *[blank(r["close"].get(s)) for s in ser],
                    *[blank(r["fwd_min_return"].get(s)) for s in ser]])
    return buf.getvalue()
