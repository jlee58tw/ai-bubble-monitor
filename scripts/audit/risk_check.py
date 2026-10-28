"""Family (7): recompute every risk indicator, the weighted score, range and coverage straight from the DB + risk.yaml
(no app.services code), compare with GET /api/risk (live) and the latest stored snapshot; re-check alert rules."""
import datetime as dt, json, os, statistics, sys, urllib.request
import yaml
sys.path.insert(0, os.path.dirname(__file__))
from common import db, Results, close

R = Results("risk")
con = db()
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
cfg = yaml.safe_load(open(os.path.join(ROOT, "backend/app/registry/risk.yaml")))
API = os.environ.get("AIBM_API", "http://localhost:8000")
TODAY = dt.date.today()
D = lambda s: dt.date.fromisoformat(str(s)[:10])
NOT_SUP = "id not in (select supersedes_id from {t} where supersedes_id is not null)"

def obs(metrics, entities):
    metrics = metrics if isinstance(metrics, list) else [metrics]
    q = (f"select id, entity_id, period_end, value, fiscal_period from observations where {NOT_SUP.format(t='observations')} "
         f"and metric_id in ({','.join('?'*len(metrics))}) and entity_id in ({','.join('?'*len(entities))}) "
         "and publication_date <= ?")
    return con.execute(q, metrics + list(entities) + [TODAY.isoformat()]).fetchall()

def latest(metrics, entities):
    out = {}
    for i, e, pe, v, fp in obs(metrics, entities):
        if e not in out or D(pe) > D(out[e][2]):
            out[e] = (i, e, pe, v, fp)
    return out

fresh = lambda pe, ind: (TODAY - D(pe)).days <= ind.get("max_age_days", 10**6)

def value(ind):
    c, a = ind["calc"], ind.get("args", {})
    if c == "unavailable":
        return None, "unavailable"
    if c == "obs_mean_latest":
        l = {e: r for e, r in latest(a["metric"], a["entities"]).items() if fresh(r[2], ind)}
        return (statistics.fmean(r[3] for r in l.values()), "ok") if len(l) >= a.get("min_entities", 1) else (None, "stale/missing")
    if c in ("obs_spread_latest", "obs_ratio_latest"):
        la, lb = latest(a["metric_a"], a["entities"]), latest(a["metric_b"], a["entities"])
        pr = [(la[e][3], lb[e][3]) for e in la if e in lb and la[e][2] == lb[e][2] and fresh(la[e][2], ind)
              and (c == "obs_spread_latest" or lb[e][3])]
        if len(pr) < a.get("min_entities", 1):
            return None, "stale/missing"
        return statistics.fmean(x - y if c == "obs_spread_latest" else x / y for x, y in pr), "ok"
    if c == "obs_latest":
        r = latest(a["metric"], [a["entity"]]).get(a["entity"])
        return (r[3], "ok") if r and fresh(r[2], ind) else (None, "stale/missing")
    if c == "obs_yoy_latest":
        rows = sorted(obs(a["metric"], [a["entity"]]), key=lambda r: r[2])
        cur = rows[-1]
        if not fresh(cur[2], ind):
            return None, "stale"
        p = [r for r in rows if abs((D(cur[2]) - D(r[2])).days - 364) <= 20]
        return (cur[3] / p[0][3] - 1, "ok") if p and p[0][3] else (None, "insufficient")
    if c == "model_price_change":
        rows = con.execute("select id, supersedes_id, usd_per_mtok, first_seen_at from model_prices where vendor in (%s)"
                           % ",".join("?" * len(a["vendors"])), a["vendors"]).fetchall()
        first = min(D(r[3]) for r in rows)
        if (TODAY - first).days < a["min_history_days"]:
            return None, f"insufficient (history {(TODAY - first).days} d since {first})"
        by = {r[0]: r for r in rows}
        ch = [r[2] / by[r[1]][2] - 1 for r in rows if r[1] in by and by[r[1]][2] and r[2] != by[r[1]][2]
              and D(r[3]) >= TODAY - dt.timedelta(days=365)]
        return (statistics.median(ch), "ok") if len(ch) >= a["min_changes"] else (None, f"insufficient ({len(ch)} changes)")
    if c == "gpu_spot_discount":
        r = dict((k, (v, s)) for k, v, s in con.execute(
            f"select price_kind, usd_per_hour, last_seen_at from gpu_prices where sku=? and {NOT_SUP.format(t='gpu_prices')}", (a["sku"],)))
        if (TODAY - min(D(r["list_on_demand"][1]), D(r["list_spot"][1]))).days > ind["max_age_days"]:
            return None, "stale"
        return 1 - r["list_spot"][0] / r["list_on_demand"][0], "ok"
    if c == "metr_doubling":
        ex, seen = con.execute(f"select extra, last_seen_at from benchmark_results where benchmark='metr-horizon' and "
                               f"{NOT_SUP.format(t='benchmark_results')} order by last_seen_at desc limit 1").fetchone()
        d = json.loads(ex)["doubling_time_days"]["from_2023_on"]
        return (float(d["point_estimate"]), "ok") if (TODAY - D(seen)).days <= ind["max_age_days"] else (None, "stale")
    if c == "bench_top":
        rows = con.execute(f"select benchmark_version, value, last_seen_at from benchmark_results where benchmark=? and metric=? "
                           f"and {NOT_SUP.format(t='benchmark_results')}", (a["benchmark"], a["metric"])).fetchall()
        ver = max(rows, key=lambda r: r[2])[0]
        rows = [r for r in rows if r[0] == ver]
        return (max(r[1] for r in rows), "ok") if (TODAY - D(max(r[2] for r in rows))).days <= ind["max_age_days"] else (None, "stale")
    raise KeyError(c)

def interp(v, b, s):
    return round(100 * min(1, max(0, (v - b) / (s - b))), 2)

api = json.load(urllib.request.urlopen(API + "/api/risk", timeout=60))
api_ind = {i["id"]: i for d in api["dimensions"] for i in d["indicators"]}
tw = sum(d["weight"] for d in cfg["dimensions"])
num = den = lo = hi = 0.0
for d in cfg["dimensions"]:
    inds = [i for i in cfg["indicators"] if i["dimension"] == d["id"]]
    for ind in inds:
        w = d["weight"] / tw / len(inds)
        v, st = value(ind)
        sc = interp(v, ind["thresholds"]["benign"], ind["thresholds"]["stretched"]) if v is not None else None
        a = api_ind[ind["id"]]
        ok = (v is None and a["value"] is None) or (v is not None and a["value"] is not None and close(v, a["value"], 1e-9, 1e-12))
        R.add(f"indicator {ind['id']}", (a["value"], a["score"], a["status"]), (v, sc, st),
              ok and a["score"] == sc, API + "/api/risk",
              f"weight {w:.4f}; thresholds {ind['thresholds']}; api as_of {a.get('as_of')}")
        if sc is None:
            hi += w * 100
        else:
            num += w * sc; den += w; lo += w * sc; hi += w * sc
cov = den
score = round(num / den, 2) if den and cov >= cfg["min_coverage"] else None
R.add("coverage", api["coverage"], round(cov, 4), close(api["coverage"], cov, 1e-6), API + "/api/risk", "sum of weights of scored indicators")
R.add("score (point, shown only if coverage >= min_coverage)", api["score"], score, api["score"] == score, API + "/api/risk")
R.add("score range [low, high] (missing = 0 / 100)", (api["score_low"], api["score_high"]), (round(lo, 2), round(hi, 2)),
      (api["score_low"], api["score_high"]) == (round(lo, 2), round(hi, 2)), API + "/api/risk")
snap = con.execute("select id, computed_at, coverage, score, score_low, score_high from risk_snapshots order by id desc limit 1").fetchone()
R.add(f"latest stored snapshot #{snap[0]} ({snap[1]} UTC) vs live recompute", snap[2:], (round(cov, 4), score, round(lo, 2), round(hi, 2)),
      close(snap[2], cov, 1e-6) and snap[3] == score, "risk_snapshots", "differs only if data changed after the snapshot")

# alerts: recompute the threshold rules and compare ids with GET /api/alerts
al = cfg["alerts"]
exp = set()
cy, ry = latest("capex_yoy", al["companies"]), latest("revenue_yoy", al["companies"])
for e, c in cy.items():
    if e in ry and ry[e][2] == c[2] and c[3] - ry[e][3] >= al["capex_vs_revenue_gap"]:
        exp.add(f"capex_gap:{e}:{c[2][:10]}")
for e, f in latest("fcf", al["companies"]).items():
    if f[3] < 0:
        exp.add(f"neg_fcf:{e}:{f[2][:10]}")
for m in ("tw_drawdown_52w", "us_drawdown_52w"):
    ents = [r[0] for r in con.execute("select distinct entity_id from observations where metric_id=?", (m,))]
    for e, o in latest(m, ents).items():
        if o[3] <= al["drawdown"] and (TODAY - D(o[2])).days <= 14:
            exp.add(f"dd:{e}:{o[2][:10]}")
try:
    got = json.load(urllib.request.urlopen(API + "/api/alerts", timeout=60))
    got = got.get("alerts", got) if isinstance(got, dict) else got
    gids = {a["id"] for a in got if a["id"].split(":")[0] in ("capex_gap", "neg_fcf", "dd")}
    R.add("alerts (capex gap / negative FCF / drawdown) ids", sorted(gids), sorted(exp), gids == exp, API + "/api/alerts",
          f"missing {sorted(exp - gids)} extra {sorted(gids - exp)}")
except Exception as e:  # noqa
    R.add("alerts endpoint", None, str(e)[:100], False, API + "/api/alerts")
R.save()
