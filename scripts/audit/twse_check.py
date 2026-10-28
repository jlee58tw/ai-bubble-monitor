"""Family (2): TWSE 2330/2382/2317 - independent re-fetch from TWSE (www.twse.com.tw month files,
BWIBBU_d daily P/E file which our provider does NOT use, and the OpenAPI company profile).
>= 3 s between TWSE requests."""
import datetime as dt, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import db, fetch, latest_rows, Results, close

R = Results("twse")
con = db()
CODES = ["2330", "2382", "2317"]
import hashlib
_fetch = fetch
def fetch(url, headers=None, min_gap=5.5):  # small on-disk cache so re-runs don't hammer TWSE
    p = "/tmp/aibm_audit_cache_" + hashlib.md5(url.encode()).hexdigest()
    if os.path.exists(p) and "STOCK_DAY" in url and dt.date.today().strftime("%Y%m") not in url:
        return open(p).read()
    for attempt in range(5):  # TWSE answers 307 when throttling; back off and retry
        try:
            t = _fetch(url, headers, min_gap=min_gap)
            break
        except RuntimeError:
            if attempt == 4:
                raise
            import time; time.sleep(45 * (attempt + 1))
    open(p, "w").write(t)
    return t
H = {"User-Agent": "Mozilla/5.0 (ai-bubble-monitor audit)"}

def num(s):
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

def roc(d):  # '115/10/22' -> date
    y, m, dd = d.strip().split("/")
    return dt.date(int(y) + 1911, int(m), int(dd))

last = max(r[4] for r in latest_rows(con, "tw_price_close", "2330"))
L = dt.date.fromisoformat(last)
months = []
d = dt.date(L.year - 1, L.month, 1)
while d <= L:
    months.append(d)
    d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)

closes = {}
for c in CODES:
    closes[c] = {}
    for m in months:
        url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={m:%Y%m}01&stockNo={c}"
        j = json.loads(fetch(url, H, min_gap=5.5))
        for row in j.get("data", []):
            closes[c][roc(row[0]).isoformat()] = num(row[6])

for c in CODES:
    stored = {r[4]: r[6] for r in latest_rows(con, "tw_price_close", c)}
    common_days = sorted(set(stored) & set(closes[c]))
    bad = [(k, stored[k], closes[c][k]) for k in common_days if not close(stored[k], closes[c][k], 0, 1e-9)]
    miss = sorted(k for k in closes[c] if k >= min(stored) and k <= max(stored) and k not in stored)
    extra = sorted(k for k in stored if k not in closes[c])
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=YYYYMM01&stockNo={c}"
    R.add(f"{c} daily closes {common_days[0]}..{common_days[-1]} ({len(common_days)} days)",
          f"{len(common_days) - len(bad)} match", f"{len(bad)} mismatch", not bad, url,
          f"mismatches {bad[:3]}; source days missing in DB {miss[:5]}; DB days not in source {extra[:5]}")
    R.add(f"{c} trading-day completeness in stored range", len(stored), len(stored) + len(miss), not miss and not extra, url,
          f"missing {miss[:5]} extra {extra[:5]}")
    for k in sorted(stored)[-3:]:
        R.add(f"{c} close {k}", stored[k], closes[c].get(k), close(stored[k], closes[c].get(k), 0, 1e-9), url.replace("YYYYMM", k[:7].replace("-", "")))
    # 52w drawdown recomputed: close_t / max(close over (t-365d, t]) - 1
    for r in latest_rows(con, "tw_drawdown_52w", c)[-3:]:
        t = dt.date.fromisoformat(r[4])
        win = {k: v for k, v in closes[c].items() if t - dt.timedelta(days=365) < dt.date.fromisoformat(k) <= t}
        hk = max(win, key=win.get)
        dd = closes[c][r[4]] / win[hk] - 1
        R.add(f"{c} 52w drawdown {r[4]}", round(r[6], 6), round(dd, 6), close(r[6], dd, 1e-9, 1e-9), url,
              f"high {win[hk]} on {hk}; close {closes[c][r[4]]}; window from {min(win)}")

# P/E, P/B, yield on the latest STORED valuation day from the DAILY historical file (BWIBBU_d), not BWIBBU_ALL.
# BWIBBU_ALL (OpenAPI, what the provider reads) lags BWIBBU_d by about one trading day, so the latest close day may
# not have a valuation row yet; that lag is recorded separately below.
vlast = max(r[4] for c in CODES for r in latest_rows(con, "tw_pe_trailing", c))
R.add("valuation (P/E, P/B, yield) lag vs latest close", vlast, last, None,
      "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
      "OpenAPI BWIBBU_ALL is published ~1 trading day after BWIBBU_d; within risk max_age 14 d")
last_close = last
last = vlast
ymd = last.replace("-", "")
u = f"https://www.twse.com.tw/exchangeReport/BWIBBU_d?response=json&date={ymd}&selectType=ALL"
j = json.loads(fetch(u, H, min_gap=5.5))
f = j["fields"]
rows = {r[0]: dict(zip(f, r)) for r in j.get("data", [])}
for c in CODES:
    src = rows.get(c, {})
    def g(*names):
        for n in names:
            if n in src:
                return num(src[n])
    pe, pb, dy = g("本益比"), g("股價淨值比"), g("殖利率(%)")
    for metric, sv, scale in [("tw_pe_trailing", pe, 1), ("tw_pb_ratio", pb, 1), ("tw_dividend_yield", dy, 0.01)]:
        st = [r for r in latest_rows(con, metric, c) if r[4] == last]
        s = st[-1][6] if st else None
        v = None if sv is None else sv * scale
        R.add(f"{c} {metric} {last}", s, v, close(s, v, 1e-9, 1e-12), u, f"fields {f}; source raw {sv}")

last = last_close
# Shares (company profile) and market cap = close x shares
pu = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
prof = json.loads(fetch(pu, H, min_gap=5.5))
for c in CODES:
    p = next(x for x in prof if x.get("公司代號") == c)
    sh = num(p["已發行普通股數或TDR原股發行股數"])
    par = num(p["普通股每股面額"].replace("新台幣", "").replace("元", ""))
    cap_sh = num(p["實收資本額"]) / par - num(p.get("特別股", "0") or "0")
    s = latest_rows(con, "tw_shares_outstanding", c)[-1]
    R.add(f"{c} shares outstanding (profile 出表日期 {p.get('出表日期')})", s[6], sh, close(s[6], sh, 0, 0.5), pu,
          f"stored dated {s[4]}; field 已發行普通股數或TDR原股發行股數; cross-check 實收資本額/面額 - 特別股 = {cap_sh:.0f}")
    R.add(f"{c} shares cross-check: paid-in capital / par", sh, cap_sh, close(sh, cap_sh, 1e-4), pu,
          "difference can arise from preferred shares or capital not yet registered; tolerance 0.01%")
    mc = [r for r in latest_rows(con, "tw_market_cap", c) if r[4] == last][-1]
    v = closes[c][last] * sh
    R.add(f"{c} market cap {last} = close x shares", mc[6], v, close(mc[6], v, 1e-9), pu,
          f"{closes[c][last]} TWD x {sh:.0f}; stored pub {mc[5]} (shares snapshot date, so no look-ahead)")

# freshness: last stored trading day vs latest day TWSE has published
today = dt.date.today()
src_last = max(max(closes[c]) for c in CODES)
cur = json.loads(fetch(f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={today:%Y%m}01&stockNo=2330", H, min_gap=5.5))
src_last = max([src_last] + [roc(r[0]).isoformat() for r in cur.get("data", [])])
R.add("freshness: last stored TW close vs last TWSE trading day", last, src_last, last >= src_last,
      "https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=" + f"{today:%Y%m}01&stockNo=2330",
      "stale if source has newer trading days; fix = re-run refresh (scheduler/cron)")
R.save()
