"""Family (5): benchmarks vs the source leaderboards fetched fresh (independent parsing)."""
import json, os, re, sys
import yaml
sys.path.insert(0, os.path.dirname(__file__))
from common import db, fetch, Results, close

R = Results("benchmarks")
con = db()
cur = lambda bm: con.execute(
    "select split, metric, entry_key, value, result_date, benchmark_version from benchmark_results where benchmark=? and "
    "id not in (select supersedes_id from benchmark_results where supersedes_id is not null)", (bm,)).fetchall()

def compare(name, stored, src, url, extra=""):
    common = set(stored) & set(src)
    bad = [(k, stored[k], src[k]) for k in sorted(common) if not close(stored[k], src[k], 1e-9, 1e-9)]
    R.add(f"{name}: values ({len(common)} entries)", f"{len(common)-len(bad)} match", f"{len(bad)} mismatch", not bad,
          url, f"sample {bad[:3]} {extra}")
    miss, extra_ = sorted(set(src) - set(stored)), sorted(set(stored) - set(src))
    R.add(f"{name}: entries on source missing in DB", len(miss), 0, not miss, url, str(miss[:5]))
    R.add(f"{name}: entries in DB no longer on source", len(extra_), 0, not extra_, url, str(extra_[:5]))

# SWE-bench: the JSON the swebench.com site renders
u = "https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/master/data/leaderboards.json"
d = json.loads(fetch(u))
src = {(lb["name"].lower(), r.get("folder") or r.get("name")): float(r["resolved"])
       for lb in d["leaderboards"] for r in lb["results"] if r.get("resolved") is not None}
st = {(s, k): v for s, m, k, v, _, _ in cur("swe-bench")}
compare("SWE-bench (all splits)", st, src, u)
for split in ("verified", "lite", "test", "multimodal", "multilingual"):
    s_top = max((v for (sp, _), v in src.items() if sp == split), default=None)
    d_top = max((v for (sp, _), v in st.items() if sp == split), default=None)
    R.add(f"SWE-bench {split} top resolved %", d_top, s_top, d_top == s_top, "https://www.swebench.com/")

# METR: yaml
u = "https://metr.org/assets/benchmark_results_1_1.yaml"
y = yaml.safe_load(fetch(u))
src = {}
for key, r in y["results"].items():
    for m, unit in (("p50_horizon_length", "p50_horizon_min"), ("p80_horizon_length", "p80_horizon_min")):
        e = ((r.get("metrics") or {}).get(m) or {}).get("estimate")
        if e is not None:
            src[(unit, key)] = float(e)
st = {(m, k): v for _, m, k, v, _, _ in cur("metr-horizon")}
compare("METR time horizon v1.1 (minutes)", st, src, u)
top = max(src.items(), key=lambda kv: kv[1] if kv[0][0] == "p50_horizon_min" else -1)
R.add("METR top p50 horizon (min)", st.get(top[0]), top[1], st.get(top[0]) == top[1], u, top[0][1])

# Terminal-Bench: regex over the page's embedded row objects ("id" ... "accuracy")
for u in ("https://www.tbench.ai/leaderboard/terminal-bench/2.0", "https://www.tbench.ai/leaderboard"):
    try:
        html = fetch(u).replace('\\"', '"')
    except Exception as e:  # noqa
        R.add(f"Terminal-Bench fetch {u}", None, str(e)[:80], False, u); continue
    title = re.search(r'"leaderboard":\{[^{}]*?"title":"([^"]+)"', html)
    R.add(f"Terminal-Bench page version {u}", None, title.group(1) if title else None, None, u,
          "URL path says 2.0; payload title is what is stored")
    if "2.0" in u:
        rows = re.findall(r'\{"id":"([0-9a-f-]{36})","leaderboard_id":"[^"]+","rank":\d+,"metadata":\{.*?\},'
                          r'"metrics":\{"accuracy":([0-9.]+),"n_trials":(\d+),.*?"successes":(\d+)', html)
        src = {r[0]: float(r[1]) for r in rows}
        inc = [(r[0][:8], r[1], r[3], r[2]) for r in rows if abs(100 * int(r[3]) / int(r[2]) - float(r[1])) > 0.01]
        R.add("Terminal-Bench accuracy == successes/n_trials on source", len(rows) - len(inc), len(rows), not inc, u, str(inc[:3]))
        stv = {k: v for _, _, k, v, _, ver in cur("terminal-bench")}
        compare("Terminal-Bench (accuracy %)", stv, src, u, f"stored version {cur('terminal-bench')[0][5]}")
R.save()
