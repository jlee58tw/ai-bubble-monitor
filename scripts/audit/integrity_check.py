"""Family (8): duplicates, units/ranges, period labels, look-ahead (publication dates) and freshness, straight SQL."""
import datetime as dt, os, re, statistics, sys
from collections import defaultdict
import yaml
sys.path.insert(0, os.path.dirname(__file__))
from common import db, Results

R = Results("integrity")
con = db()
TODAY = dt.date.today()
D = lambda s: dt.date.fromisoformat(str(s)[:10])
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CUR = "id not in (select supersedes_id from {t} where supersedes_id is not null)"

rows = con.execute(f"select id, metric_id, entity_id, value, unit, fiscal_period, period_start, period_end, publication_date, "
                   f"classification, methodology, {CUR.format(t='observations')} from observations").fetchall()
pub = {r[0]: D(r[8]) for r in rows}
cur = [r for r in rows if r[11]]
print(f"{len(rows)} observation rows, {len(cur)} current")

# 1. duplicates among current rows
k = defaultdict(list)
for r in cur:
    k[(r[1], r[2], r[6], r[7])].append(r[0])
dups = {kk: v for kk, v in k.items() if len(v) > 1}
R.add("observations: >1 current row per (metric, entity, period_start, period_end)", len(dups), 0, not dups, "db",
      str(list(dups.items())[:5]))
k2 = defaultdict(set)
for r in cur:
    if r[6]:
        k2[(r[1], r[2], r[7])].add((D(r[7]) - D(r[6])).days // 80)  # duration bucket
mixed = {kk: v for kk, v in k2.items() if len(v) > 1}
R.add("observations: same period_end with different-length periods (quarter vs YTD both current)", len(mixed), 0,
      not mixed, "db", str(list(mixed.items())[:5]))
for t, key in (("model_prices", "vendor, model_id, tier, price_type, price_status, coalesce(effective_from,'')"),
               ("gpu_prices", "sku, region, price_kind"),
               ("benchmark_results", "benchmark, benchmark_version, split, metric, entry_key")):
    try:
        n = con.execute(f"select count(*) from (select {key}, count(*) c from {t} where {CUR.format(t=t)} "
                        f"group by {key} having c>1)").fetchone()[0]
        R.add(f"{t}: duplicate current rows per natural key ({key})", n, 0, n == 0, "db")
    except Exception as e:  # noqa
        R.add(f"{t}: duplicate check", None, str(e)[:120], None, "db", "schema differs; check skipped")

# 2. units / plausible ranges (current rows)
reg = {m["id"]: m for m in yaml.safe_load(open(os.path.join(ROOT, "backend/app/registry/metrics.yaml")))["metrics"]}
bad_unit = sorted({(r[1], r[4], reg.get(r[1], {}).get("unit")) for r in cur if r[1] in reg and reg[r[1]].get("unit") and r[4] != reg[r[1]]["unit"]})
R.add("unit column equals registry unit", len(bad_unit), 0, not bad_unit, "metrics.yaml", str(bad_unit[:5]))
RANGES = {"tw_dividend_yield": (0, 0.25), "tw_pe_trailing": (0, 500), "tw_pb_ratio": (0, 100), "us10y_yield": (-1, 20),
          "tw_drawdown_52w": (-1, 0), "us_drawdown_52w": (-1, 0), "us_index_drawdown_52w": (-1, 0),
          "capex_to_revenue": (0, 5), "capex_to_ocf": (-50, 50), "revenue_yoy": (-1, 20), "capex_yoy": (-1, 50),
          "tw_price_close": (0, 1e5), "us_price_close": (0, 1e6), "us_index_close": (0, 1e6)}
for m, (lo, hi) in RANGES.items():
    out = [(r[2], r[7], r[3]) for r in cur if r[1] == m and not lo <= r[3] <= hi]
    R.add(f"range {m} in [{lo}, {hi}] (fractions, not %)", len(out), 0, not out, "db", str(out[:3]))
sh = defaultdict(list)
for r in cur:
    if r[1] in ("us_shares_outstanding", "tw_shares_outstanding"):
        sh[r[2]].append(r)
odd = []
for e, rs in sh.items():
    med = statistics.median(x[3] for x in rs)
    odd += [(e, x[7], x[3], x[0]) for x in rs if not 1e-3 <= x[3] / med <= 1e3]
R.add("shares outstanding >1000x off entity median (source filer scaling errors)", odd, "verified vs SEC companyconcept",
      None, "https://data.sec.gov/api/xbrl/companyconcept/CIK0001341439/dei/EntityCommonStockSharesOutstanding.json",
      "values are exactly as tagged in the filings (ORCL 0001193125-12-401697 = 4,819,056,000,000,000); kept as reported, "
      "now excluded from market-cap derivation (derive.market_cap_asof guard)")
mc = [r for r in cur if r[1] == "market_cap" and r[3] > 2e13]
R.add("market_cap rows > $20T (would indicate share-unit error)", len(mc), 0, not mc, "db")

# 3. period labels
lab = []
for r in cur:
    fp = r[5]
    if not fp or not r[6]:
        continue
    m = re.match(r"^(FY|CY)(\d{4}) (Q[1-4]|FY)$", fp)
    if not m:
        lab.append((r[1], r[2], fp, "format")); continue
    days = (D(r[7]) - D(r[6])).days + 1
    if m.group(3).startswith("Q") and not 80 <= days <= 100:
        lab.append((r[1], r[2], fp, r[6], r[7], days))
    if m.group(1) == "CY" and m.group(3).startswith("Q") and D(r[7]).month != 3 * int(m.group(3)[1]):
        lab.append((r[1], r[2], fp, r[7], "CY quarter/month mismatch"))
R.add("fiscal_period label vs period length (Qn = 80-100 d) and CY quarter month", len(lab), 0, not lab, "db", str(lab[:5]))

# 4. look-ahead
la = [(r[1], r[2], r[7], r[8]) for r in cur if D(r[8]) < D(r[7])]
R.add("publication_date >= period_end", len(la), 0, not la, "db", str(la[:5]))
fut = [(r[1], r[2], r[8]) for r in cur if D(r[8]) > TODAY]
R.add("publication_date not in the future", len(fut), 0, not fut, "db", str(fut[:5]))
bad, checked, unparsed = [], 0, defaultdict(int)
for r in cur:
    if r[9] != "derived" or not r[10] or "obs id" not in r[10]:
        if r[9] == "derived":
            unparsed[r[1]] += 1
        continue
    s = r[10][r[10].index("obs id"):]
    s = re.sub(r"\([^)]*\)", "", s).replace("52w-high", "")
    s = re.sub(r"(split|scale|factor) [\d.]+", "", s)
    ids = [int(x) for x in re.findall(r"\d+", s)]
    checked += 1
    late = [i for i in ids if i in pub and pub[i] > D(r[8])]
    miss = [i for i in ids if i not in pub]
    if late or miss:
        bad.append((r[0], r[1], r[2], r[7], r[8], late[:3], miss[:3]))
R.add(f"derived publication_date >= every input's publication_date ({checked} derived rows with input ids)", len(bad), 0,
      not bad, "db", str(bad[:5]))
R.add("derived rows without input-id lineage (YTD-differenced EDGAR rows; checked in edgar.json)", dict(unparsed), "-", None, "db")

# 5. freshness per metric (latest current period_end)
risk = yaml.safe_load(open(os.path.join(ROOT, "backend/app/registry/risk.yaml")))
maxage = {}
for i in risk["indicators"]:
    a = i.get("args", {})
    for mm in (a.get("metric"), a.get("metric_a"), a.get("metric_b")):
        for mm in (mm if isinstance(mm, list) else [mm]):
          if mm and i.get("max_age_days"):
            maxage[mm] = min(maxage.get(mm, 10**6), i["max_age_days"])
last = defaultdict(lambda: dt.date(1900, 1, 1))
for r in cur:
    last[r[1]] = max(last[r[1]], D(r[7]))
for m in sorted(last):
    age = (TODAY - last[m]).days
    lim = maxage.get(m)
    R.add(f"freshness {m}", f"latest period_end {last[m]} ({age} d)", f"max_age {lim}" if lim else "no risk max_age",
          (age <= lim) if lim else None, "db")
for t, col in (("model_prices", "last_seen_at"), ("gpu_prices", "last_seen_at"), ("benchmark_results", "last_seen_at")):
    v = con.execute(f"select max({col}) from {t}").fetchone()[0]
    R.add(f"freshness {t}.{col} (UTC)", v, "<= 7 d", (TODAY - D(v)).days <= 7, "db")
R.save()
