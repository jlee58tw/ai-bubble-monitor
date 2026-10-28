"""Phase 2 risk engine. Config: app/registry/risk.yaml (thresholds = research hypotheses).

Rules
* Indicator score = linear interpolation between `benign` (0) and `stretched` (100), clamped.
* Missing / unavailable / stale indicators are EXCLUDED from the point score and never treated as 0 risk:
  they widen the [low, high] range (missing = 0 for low, 100 for high).
* coverage = sum of (dimension weight x indicator share) actually available.
* Below min_coverage no precise overall score is returned (score=None), only the range.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import BenchmarkResult, GpuPrice, ModelPrice, RiskSnapshot, utcnow
from .queries import query_observations

CONFIG_PATH = Path(__file__).resolve().parents[1] / "registry" / "risk.yaml"


@dataclass
class Value:
    value: float | None
    status: str  # ok | missing | stale | unavailable | insufficient
    as_of: str | None = None
    detail: str | None = None
    inputs: list = field(default_factory=list)


def load_config(path: Path = CONFIG_PATH) -> tuple[dict, str]:
    raw = path.read_bytes()
    cfg = yaml.safe_load(raw)
    env_min = get_settings().risk_min_coverage
    if env_min is not None:
        cfg["min_coverage"] = float(env_min)
    return cfg, hashlib.sha256(raw + str(cfg["min_coverage"]).encode()).hexdigest()[:12]


def interp(v: float, benign: float, stretched: float) -> float:
    if benign == stretched:
        raise ValueError("benign == stretched")
    t = (v - benign) / (stretched - benign)
    return round(100 * min(1.0, max(0.0, t)), 2)


# ---------------------------------------------------------------------------- data access (calcs)
def _age_ok(d: dt.date | None, max_age: int | None, today: dt.date) -> bool:
    return d is not None and (max_age is None or (today - d).days <= max_age)


OBS_CALCS = {"obs_mean_latest", "obs_median_latest", "obs_spread_latest", "obs_ratio_latest", "obs_latest",
             "obs_yoy_latest"}  # calcs that read only the append-only observations table (point-in-time capable)


def _obs(s, metrics: list[str], entities: list[str], today: dt.date) -> list:
    """Current observations as known on `today` (publication_date <= today): no look-ahead.
    `s` is a Session, or any object with .rows(metrics, entities, as_of) (e.g. services.backtest.PitCache)."""
    if hasattr(s, "rows"):
        return s.rows(metrics, entities, today)
    return query_observations(s, metrics, entities, as_of=today)


def _latest_per_entity(s: Session, metrics, entities, today: dt.date) -> dict[str, object]:
    metrics = metrics if isinstance(metrics, list) else [metrics]
    out = {}
    for o in _obs(s, metrics, entities, today):
        cur = out.get(o.entity_id)
        if cur is None or o.period_end > cur.period_end:
            out[o.entity_id] = o
    return out


def _agg_latest(s, ind, today, fn) -> Value:
    a = ind["args"]
    latest = _latest_per_entity(s, a["metric"], a["entities"], today)
    fresh = {e: o for e, o in latest.items() if _age_ok(o.period_end, ind.get("max_age_days"), today)}
    if len(fresh) < a.get("min_entities", 1):
        st = "stale" if latest else "missing"
        return Value(None, st, detail=f"{len(fresh)} fresh of {len(latest)} entities with data "
                                      f"(need {a.get('min_entities', 1)})")
    vals = [o.value for o in fresh.values()]
    return Value(fn(vals), "ok", as_of=str(min(o.period_end for o in fresh.values())),
                 detail=", ".join(f"{e} {o.fiscal_period or o.period_end}: {o.value:.4g}" for e, o in sorted(fresh.items())),
                 inputs=[o.id for o in fresh.values()])


def calc_obs_mean_latest(s, ind, today):
    return _agg_latest(s, ind, today, statistics.fmean)


def calc_obs_median_latest(s, ind, today):
    return _agg_latest(s, ind, today, statistics.median)


def calc_obs_spread_latest(s, ind, today):
    a = ind["args"]
    la, lb = _latest_per_entity(s, a["metric_a"], a["entities"], today), _latest_per_entity(s, a["metric_b"], a["entities"], today)
    pairs = {e: (la[e], lb[e]) for e in la if e in lb and la[e].period_end == lb[e].period_end
             and _age_ok(la[e].period_end, ind.get("max_age_days"), today)}
    if len(pairs) < a.get("min_entities", 1):
        return Value(None, "missing" if not la else "stale", detail=f"{len(pairs)} matched fresh entities")
    d = [x.value - y.value for x, y in pairs.values()]
    return Value(statistics.fmean(d), "ok", as_of=str(min(x.period_end for x, _ in pairs.values())),
                 detail=", ".join(f"{e}: {x.value:+.1%} vs {y.value:+.1%}" for e, (x, y) in sorted(pairs.items())),
                 inputs=[i.id for p in pairs.values() for i in p])


def calc_obs_ratio_latest(s, ind, today):
    a = ind["args"]
    la, lb = _latest_per_entity(s, a["metric_a"], a["entities"], today), _latest_per_entity(s, a["metric_b"], a["entities"], today)
    pairs = {e: (la[e], lb[e]) for e in la if e in lb and la[e].period_end == lb[e].period_end and lb[e].value
             and _age_ok(la[e].period_end, ind.get("max_age_days"), today)}
    if len(pairs) < a.get("min_entities", 1):
        return Value(None, "missing" if not la else "stale", detail=f"{len(pairs)} matched fresh entities")
    r = {e: x.value / y.value for e, (x, y) in pairs.items()}
    return Value(statistics.fmean(r.values()), "ok", as_of=str(min(x.period_end for x, _ in pairs.values())),
                 detail=", ".join(f"{e}: {v:.1%}" for e, v in sorted(r.items())),
                 inputs=[i.id for p in pairs.values() for i in p])


def calc_obs_latest(s, ind, today):
    a = ind["args"]
    o = _latest_per_entity(s, a["metric"], [a["entity"]], today).get(a["entity"])
    if o is None:
        return Value(None, "missing")
    if not _age_ok(o.period_end, ind.get("max_age_days"), today):
        return Value(None, "stale", as_of=str(o.period_end))
    return Value(o.value, "ok", as_of=str(o.period_end), inputs=[o.id])


def calc_obs_yoy_latest(s, ind, today):
    a = ind["args"]
    rows = sorted(_obs(s, [a["metric"]], [a["entity"]], today), key=lambda o: o.period_end)
    if not rows:
        return Value(None, "missing")
    cur = rows[-1]
    if not _age_ok(cur.period_end, ind.get("max_age_days"), today):
        return Value(None, "stale", as_of=str(cur.period_end))
    prev = [o for o in rows if abs((cur.period_end - o.period_end).days - 364) <= 20]
    if not prev or not prev[0].value:
        return Value(None, "insufficient", detail="no comparable quarter one year earlier")
    p = prev[0]
    return Value(cur.value / p.value - 1, "ok", as_of=str(cur.period_end),
                 detail=f"{cur.fiscal_period} {cur.value:,.0f} vs {p.fiscal_period} {p.value:,.0f}",
                 inputs=[cur.id, p.id])


def calc_model_price_change(s, ind, today):
    a = ind["args"]
    rows = list(s.scalars(select(ModelPrice).where(ModelPrice.vendor.in_(a["vendors"]))))
    if not rows:
        return Value(None, "missing")
    first = min(r.first_seen_at for r in rows).date()
    hist = (today - first).days
    if hist < a["min_history_days"]:
        return Value(None, "insufficient",
                     detail=f"observed price history is {hist} days (since {first}); need {a['min_history_days']}. "
                            "Undocumented past prices are never back-filled.")
    since = today - dt.timedelta(days=365)
    by_id = {r.id: r for r in rows}
    # Only real price moves: a revision that only fills effective_to / fixes metadata (same value) is not a
    # "change" and must not pull the median towards 0 (audit 2026-10-28).
    ch = [r.usd_per_mtok / by_id[r.supersedes_id].usd_per_mtok - 1 for r in rows
          if r.supersedes_id in by_id and r.first_seen_at.date() >= since and by_id[r.supersedes_id].usd_per_mtok
          and r.usd_per_mtok != by_id[r.supersedes_id].usd_per_mtok]
    if len(ch) < a["min_changes"]:
        return Value(None, "insufficient", detail=f"{len(ch)} observed price changes in 365 days "
                                                   f"(need {a['min_changes']})")
    return Value(statistics.median(ch), "ok", as_of=str(today), detail=f"{len(ch)} observed changes")


def calc_gpu_spot_discount(s, ind, today):
    sku = ind["args"]["sku"]
    sup = select(GpuPrice.supersedes_id).where(GpuPrice.supersedes_id.is_not(None))
    rows = {r.price_kind: r for r in s.scalars(select(GpuPrice).where(GpuPrice.sku == sku, GpuPrice.id.not_in(sup)))}
    od, sp = rows.get("list_on_demand"), rows.get("list_spot")
    if not od or not sp:
        return Value(None, "missing")
    seen = min(od.last_seen_at, sp.last_seen_at).date()
    if not _age_ok(seen, ind.get("max_age_days"), today):
        return Value(None, "stale", as_of=str(seen))
    return Value(1 - sp.usd_per_hour / od.usd_per_hour, "ok", as_of=str(seen),
                 detail=f"spot ${sp.usd_per_hour}/h vs list ${od.usd_per_hour}/h (eastus, Linux)",
                 inputs=[od.id, sp.id])


def _current_bench(s, bench):
    sup = select(BenchmarkResult.supersedes_id).where(BenchmarkResult.supersedes_id.is_not(None))
    return list(s.scalars(select(BenchmarkResult).where(BenchmarkResult.benchmark == bench,
                                                        BenchmarkResult.id.not_in(sup))))


def calc_metr_doubling(s, ind, today):
    rows = _current_bench(s, "metr-horizon")
    if not rows:
        return Value(None, "missing")
    seen = max(r.last_seen_at for r in rows).date()
    if not _age_ok(seen, ind.get("max_age_days"), today):
        return Value(None, "stale", as_of=str(seen))
    d = ((rows[0].extra or {}).get("doubling_time_days") or {}).get("from_2023_on") or {}
    if d.get("point_estimate") is None:
        return Value(None, "missing", detail="doubling time not present in METR file")
    return Value(float(d["point_estimate"]), "ok", as_of=str(seen),
                 detail=f"{rows[0].benchmark_version}; 95% CI {d.get('ci_low')}-{d.get('ci_high')} days")


def calc_bench_top(s, ind, today):
    a = ind["args"]
    rows = [r for r in _current_bench(s, a["benchmark"]) if r.metric == a["metric"]]
    if not rows:
        return Value(None, "missing")
    latest_ver = max(rows, key=lambda r: r.last_seen_at).benchmark_version
    rows = [r for r in rows if r.benchmark_version == latest_ver]  # never mix versions
    seen = max(r.last_seen_at for r in rows).date()
    if not _age_ok(seen, ind.get("max_age_days"), today):
        return Value(None, "stale", as_of=str(seen))
    top = max(rows, key=lambda r: r.value)
    return Value(top.value, "ok", as_of=str(top.result_date),
                 detail=f"{latest_ver}: {top.harness} + {top.model}", inputs=[top.id])


CALCS = {k[5:]: v for k, v in globals().items() if k.startswith("calc_")}


# ---------------------------------------------------------------------------- pure scoring
def score(cfg: dict, values: dict[str, Value]) -> dict:
    min_cov = float(cfg["min_coverage"])
    dims = {d["id"]: d for d in cfg["dimensions"]}
    total_w = sum(d["weight"] for d in dims.values())
    out_dims, num, den, lo, hi, cov = [], 0.0, 0.0, 0.0, 0.0, 0.0
    for did, d in dims.items():
        inds = [i for i in cfg["indicators"] if i["dimension"] == did]
        n = len(inds) or 1
        rows, dn, dd = [], 0.0, 0.0
        for i in inds:
            v = values.get(i["id"]) or Value(None, "missing")
            sc = None
            if v.status == "ok" and v.value is not None:
                sc = interp(v.value, i["thresholds"]["benign"], i["thresholds"]["stretched"])
            w = d["weight"] / total_w / n  # equal indicator weights within a dimension
            if sc is None:
                hi += w * 100
            else:
                num += w * sc; den += w; lo += w * sc; hi += w * sc; cov += w
                dn += sc; dd += 1
            rows.append({"id": i["id"], "name": i["name"], "status": v.status, "value": v.value, "score": sc,
                         "as_of": v.as_of, "detail": v.detail or i.get("reason"), "thresholds": i["thresholds"],
                         "rationale": i.get("rationale"), "weight_in_total": round(w, 4), "inputs": v.inputs})
        dcov = dd / n
        dlo = dn / n
        dhi = (dn + (n - dd) * 100) / n
        out_dims.append({"id": did, "name": d["name"], "weight": d["weight"], "coverage": round(dcov, 4),
                         "score": round(dn / dd, 2) if dd and dcov >= min_cov else None,
                         "score_low": round(dlo, 2), "score_high": round(dhi, 2), "indicators": rows})
    point = round(num / den, 2) if den and cov >= min_cov else None
    return {"coverage": round(cov, 4), "min_coverage": min_cov, "score": point,
            "score_low": round(lo, 2), "score_high": round(hi, 2),
            "score_if_shown": round(num / den, 2) if den else None,
            "precise_score_withheld": point is None, "dimensions": out_dims}


def evaluate(session: Session, today: dt.date | None = None) -> dict:
    cfg, h = load_config()
    today = today or dt.date.today()
    vals = {}
    for i in cfg["indicators"]:
        calc = i.get("calc")
        if calc == "unavailable":
            vals[i["id"]] = Value(None, "unavailable", detail=i.get("reason"))
            continue
        vals[i["id"]] = CALCS[calc](session, i, today)
    res = score(cfg, vals)
    res.pop("score_if_shown")
    res.update({"config_hash": h, "computed_for": str(today),
                "label": "Research prototype. Thresholds are research hypotheses, not validated predictions."})
    return res


def snapshot_risk(session: Session) -> RiskSnapshot:
    r = evaluate(session)
    snap = RiskSnapshot(computed_at=utcnow(), config_hash=r["config_hash"], coverage=r["coverage"],
                        score=r["score"], score_low=r["score_low"], score_high=r["score_high"],
                        detail=json.loads(json.dumps(r, default=str)))
    session.add(snap); session.commit()
    return snap


def methodology() -> dict:
    cfg, h = load_config()
    return {"config_hash": h, "config": cfg, "rules": [l.strip("* ") for l in (__doc__ or "").splitlines()
                                                         if l.startswith("*")]}
