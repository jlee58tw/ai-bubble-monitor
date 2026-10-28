"""Family (3): Tiingo/FRED/SEC-shares - independent re-fetch (urllib/curl, not app.providers) and recompute of
split-adjusted price, 52w drawdown, market cap, 1y relative returns. The Tiingo key is read from settings and sent
only in the Authorization header; it is never printed, logged, or written to results."""
import csv, datetime as dt, io, json, os, sys, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from common import db, fetch, latest_rows, Results, close, settings, sec_headers

R = Results("tiingo_fred")
con = db()
KEY = settings().tiingo_api_key
assert KEY, "tiingo key not configured"
D = dt.date.fromisoformat
START = "2024-06-01"

def tiingo(sym):
    url = f"https://api.tiingo.com/tiingo/daily/{sym}/prices?startDate={START}"
    cache = f"/tmp/aibm_audit_tiingo_{sym}_{dt.date.today()}.json"  # response body only (no credentials)
    if os.path.exists(cache):
        return url, json.load(open(cache))
    req = urllib.request.Request(url, headers={"Authorization": "Token " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)
    json.dump(data, open(cache, "w"))
    return url, data

def fred(sid):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}&cosd=2025-09-01"
    out = {}
    for attempt in range(4):  # FRED's CDN intermittently stalls; retry politely
        try:
            import httpx  # plain HTTP client (urllib/curl get stalled by FRED's CDN); not our provider code
            r = httpx.get(url, headers={"User-Agent": "ai-bubble-monitor-audit"}, timeout=60)
            r.raise_for_status()
            text = r.text
            break
        except Exception:
            import time; time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError("FRED unreachable: " + url)
    for row in csv.DictReader(io.StringIO(text)):
        k = [c for c in row if c != "observation_date" and c != "DATE"][0]
        if row[k] not in (".", ""):
            out[row.get("observation_date") or row["DATE"]] = float(row[k])
    return url, out

def dd52(series, t):
    win = {k: v for k, v in series.items() if D(t) - dt.timedelta(days=365) < D(k) <= D(t)}
    hk = max(win, key=win.get)
    return series[t] / win[hk] - 1, hk, win[hk]

def base(series, t, tol=7):
    target = D(t) - dt.timedelta(days=365)
    ks = [k for k in series if D(k) <= target]
    if not ks:
        return None
    k = max(ks)
    return k if (target - D(k)).days <= tol else None

SYMS = [r[0] for r in con.execute("select distinct entity_id from observations where metric_id='us_price_close'")]
adj = {}
for s in SYMS:
    url, rows = tiingo(s)
    raw = {r["date"][:10]: r["close"] for r in rows}
    splits = {r["date"][:10]: r["splitFactor"] for r in rows if r.get("splitFactor", 1) != 1}
    # split-only adjustment: divide by product of split factors strictly after t (fetch window covers 2024-06 split)
    a = {}
    for k, v in raw.items():
        f = 1.0
        for sd, sf in splits.items():
            if sd > k:
                f *= sf
        a[k] = v / f
    adj[s] = a
    st = {r[4]: r[6] for r in latest_rows(con, "us_price_close", s)}
    common = sorted(set(st) & set(raw))
    bad = [(k, st[k], raw[k]) for k in common if not close(st[k], raw[k], 1e-9, 1e-6)]
    R.add(f"{s} raw close {common[0]}..{common[-1]} ({len(common)} days)", f"{len(common)-len(bad)} match", f"{len(bad)} mismatch",
          not bad, url, f"mismatch sample {bad[:3]}; last {common[-1]} stored {st[common[-1]]} source {raw[common[-1]]}")
    sa = {r[4]: r[6] for r in latest_rows(con, "us_price_split_adj", s)}
    c2 = sorted(set(sa) & set(a))
    bad2 = [(k, sa[k], a[k]) for k in c2 if not close(sa[k], a[k], 1e-9, 1e-6)]
    R.add(f"{s} split-adjusted close ({len(c2)} days)", f"{len(c2)-len(bad2)} match", f"{len(bad2)} mismatch", not bad2, url,
          f"source splits in window {splits}; sample {bad2[:3]}")
    # cross-check with Tiingo adjClose for a non-dividend payer (adjClose = split+dividend adjusted)
    if s == "AMZN":
        adjc = {r["date"][:10]: r["adjClose"] for r in rows}
        k = "2022-06-03" if "2022-06-03" in a else min(a)
        R.add("AMZN split-adj vs Tiingo adjClose (no dividends)", round(a[k], 4), round(adjc[k], 4), close(a[k], adjc[k], 1e-6), url, k)
    if s in ("NVDA",):
        k = "2024-06-07"
        R.add("NVDA 10:1 split 2024-06-10 handled: 2024-06-07 split-adj close", sa.get(k), round(a[k], 4), close(sa.get(k), a[k], 1e-9, 1e-6), url,
              f"raw {raw[k]} / 10")
    dd = {r[4]: r[6] for r in latest_rows(con, "us_drawdown_52w", s)}
    for t in sorted(dd)[-2:]:
        v, hk, hv = dd52(a, t)
        R.add(f"{s} 52w drawdown {t}", round(dd[t], 6), round(v, 6), close(dd[t], v, 1e-9, 1e-9), url, f"high {hv:.4f} on {hk}")
    R.last = max(raw)
    adj[s + "_last"] = max(raw)

idx = {}
for sid, ent in [("NASDAQ100", "NDX"), ("NASDAQSOX", "SOX"), ("NASDAQCOM", "COMP")]:
    url, ser = fred(sid)
    idx[ent] = ser
    st = {r[4]: r[6] for r in latest_rows(con, "us_index_close", ent)}
    common = sorted(set(st) & set(ser))
    bad = [(k, st[k], ser[k]) for k in common if not close(st[k], ser[k], 1e-9, 1e-6)]
    R.add(f"FRED {sid} ({ent}) closes ({len(common)} days)", f"{len(common)-len(bad)} match", f"{len(bad)} mismatch", not bad,
          url, f"last stored {max(st)} last source {max(ser)}; sample {bad[:3]}")
    R.add(f"FRED {sid} freshness", max(st), max(ser), max(st) >= max(ser), url)
    dd = {r[4]: r[6] for r in latest_rows(con, "us_index_drawdown_52w", ent)}
    t = max(dd)
    v, hk, hv = dd52(ser, t)
    R.add(f"{ent} 52w drawdown {t}", round(dd[t], 6), round(v, 6), close(dd[t], v, 1e-9, 1e-9), url, f"high {hv} on {hk}")

for bench, metric in [("NDX", "us_rel_return_1y_vs_ndx"), ("SOX", "us_rel_return_1y_vs_sox")]:
    allr = latest_rows(con, metric)
    tmax = max(y[4] for y in allr)
    for r in [x for x in allr if x[4] == tmax]:
        s, t = r[1], r[4]
        a, b = adj[s], idx[bench]
        ka, kb = base(a, t), base(b, t)
        v = (a[t] / a[ka]) / (b[t] / b[kb]) - 1
        R.add(f"{s} rel return 1y vs {bench} {t}", round(r[6], 6), round(v, 6), close(r[6], v, 1e-9, 1e-9),
              "tiingo + https://fred.stlouisfed.org/series/" + {"NDX": "NASDAQ100", "SOX": "NASDAQSOX"}[bench],
              f"stock {a[ka]:.4f}({ka})->{a[t]:.4f}; index {b[kb]}({kb})->{b[t]}")

# market cap: close x SEC dei shares (fresh from companyconcept) x scale
CIK = {"AMD": 2488, "AMZN": 1018724, "MSFT": 789019, "NVDA": 1045810, "ORCL": 1341439, "TSM": 1046179}
for s, cik in CIK.items():
    rows = latest_rows(con, "market_cap", s)
    t = rows[-1][4]
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/dei/EntityCommonStockSharesOutstanding.json"
    j = json.loads(fetch(url, sec_headers(), min_gap=0.3))
    facts = [f for u in j["units"].values() for f in u if f["end"] <= t]
    end = max(f["end"] for f in facts)
    last_accn = max(x["accn"] for x in facts if x["end"] == end)
    sh = sum({f["val"] for f in facts if f["end"] == end and f["accn"] == last_accn})
    scale = 0.2 if s == "TSM" else 1.0
    raw = {r[4]: r[6] for r in latest_rows(con, "us_price_close", s)}
    v = raw[t] * sh * scale
    R.add(f"{s} market cap {t}", round(rows[-1][6]), round(v), close(rows[-1][6], v, 1e-9), url,
          f"close {raw[t]} x shares {sh:.0f} (as of {end}) x scale {scale}" + ("; TSM: 1 ADR = 5 ordinary shares" if s == "TSM" else ""))
    R.add(f"{s} market cap shares as-of age at {t} (days)", (D(t) - D(end)).days, "<=120 (TSM <=400)",
          (D(t) - D(end)).days <= (400 if s == "TSM" else 120), url)
for s in ("GOOGL", "META"):
    n = len(latest_rows(con, "market_cap", s))
    R.add(f"{s} market cap rows", n, "n/a (multi-class)", None, "https://data.sec.gov/api/xbrl/companyconcept/",
          "not computed: dei shares reported per share class; shown as unavailable in UI (not zero)")
R.save()
