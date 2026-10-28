"""(1) EDGAR audit: hyperscaler CapEx / OCF / revenue (latest 3 quarters), derived metrics, NVDA Data Center (16 q).
Independent path: SEC companyconcept API (our ingester uses companyfacts) + own YTD->quarter derivation; NVDA from
the human-readable 10-Q/10-K HTML tables (our ingester uses the XBRL instance)."""
import datetime as dt, html, json, re
from common import Results, close, db, fetch, latest_rows, sec_headers

H = sec_headers()
CIK = {"MSFT": 789019, "GOOGL": 1652044, "AMZN": 1018724, "META": 1326801, "ORCL": 1341439, "NVDA": 1045810}
D = dt.date.fromisoformat
R = Results("edgar")
con = db()
_cc = {}


def concept(cik, tag):
    k = (cik, tag)
    if k not in _cc:
        url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{tag}.json"
        _cc[k] = (url, json.loads(fetch(url, H, min_gap=0.15)))
    return _cc[k]


def facts(cik, tag):
    url, j = concept(cik, tag)
    fs = [f for f in j["units"].get("USD", []) if f.get("form") in ("10-Q", "10-K", "10-Q/A", "10-K/A") and "start" in f]
    return url, fs


def quarter_value(fs, start, end):
    """Return (value, how, filed) for the 3-month period [start, end], from the ORIGINAL filing (earliest filed)."""
    e = D(end)
    disc = sorted([f for f in fs if f["end"] == end and 80 <= (e - D(f["start"])).days <= 100], key=lambda f: f["filed"])
    if disc:
        return disc[0]["val"], "reported 3m", disc[0]["filed"], disc
    # YTD difference: longest-duration fact ending at `end`, minus the fact with same start ending ~3 months earlier
    ytd = sorted([f for f in fs if f["end"] == end and (e - D(f["start"])).days > 100], key=lambda f: (f["filed"]))
    for y in ytd:
        prev = [f for f in fs if f["start"] == y["start"] and 80 <= (D(start) - D(f["end"])).days + 91 <= 100
                and (D(start) - D(f["end"])).days in (0, 1)]
        if prev:
            p = sorted(prev, key=lambda f: f["filed"])[0]
            return y["val"] - p["val"], f"YTD({y['start']}..{end}) - YTD(..{p['end']})", y["filed"], [y, p]
    return None, "not derivable", None, []


def label(fs, end):
    """Convention label: fiscal year = calendar year in which the fiscal year ENDS (MSFT June, ORCL May, NVDA Jan);
    quarter = position after the previous fiscal year end. FYE taken from annual (10-K, ~1 year) facts in the source.
    Also returns the filer's own DEI fy/fp tag for the period for reference."""
    fye = sorted({D(f["end"]) for f in fs if f["form"].startswith("10-K") and 350 <= (D(f["end"]) - D(f["start"])).days <= 380})
    e = D(end)
    m, dday = fye[-1].month, fye[-1].day
    y = e.year if (e.month, e.day) <= (m, dday + 7 if dday < 25 else 31) else e.year + 1
    prev = dt.date(y - 1, m, min(dday, 28))
    q = max(1, min(4, round(((e - prev).days) / 91.3)))
    own = sorted([f for f in fs if f["end"] == end and f.get("fp")], key=lambda f: f["filed"])
    dei = f"DEI fy={own[0]['fy']} fp={own[0]['fp']}" if own else "DEI n/a"
    return f"FY{y} Q{q}", dei


src = {}   # (entity, metric, period_end) -> value from source
for ent in ["MSFT", "GOOGL", "AMZN", "META", "ORCL"]:
    for metric in ["capex_total", "operating_cash_flow", "revenue"]:
        rows = latest_rows(con, metric, ent)
        # latest 3 quarters + the year-ago quarters needed to recompute YoY
        recent = rows[-3:]
        ends = {r[4] for r in recent}
        yago = [r for r in rows if any(abs((D(r[4]) - (D(e) - dt.timedelta(days=365))).days) <= 20 for e in ends)]
        for r in sorted(set(recent) | set(yago), key=lambda r: r[4]):
            _id, _e, fp, ps, pe, pub, val, cls, url, meth = r
            tag = re.search(r"us-gaap:(\w+)", meth or "") or re.search(r"(PaymentsTo\w+|NetCash\w+|Revenue\w*|Revenues)", meth or "")
            tag = tag.group(1)
            curl, fs = facts(CIK[ent], tag)
            v, how, filed, used = quarter_value(fs, ps, pe)
            src[(ent, metric, pe)] = v
            lab, dei = label(fs, pe)
            ok = close(val, v, rel=1e-9)
            note = f"{how}; source filed {filed}; stored pub {pub}"
            if r in recent:
                R.add(f"{ent} {metric} {fp} ({ps}..{pe}) value", val, v, ok, curl, note)
                R.add(f"{ent} {metric} {pe} fiscal label", fp, lab, fp == lab, curl,
                      f"convention: FY named for the year it ends; filer {dei}")
                R.add(f"{ent} {metric} {pe} publication_date >= original filing date", pub, filed,
                      filed is not None and pub >= filed, curl,
                      "pub earlier than filing = look-ahead" if filed and pub < filed else
                      ("pub later than original filing (delayed, conservative)" if filed and pub > filed else ""))
                R.add(f"{ent} {metric} {pe} classification", cls, "reported" if how == "reported 3m" else "derived",
                      cls == ("reported" if how == "reported 3m" else "derived"), curl)

# derived metrics, recomputed from source values
for ent in ["MSFT", "GOOGL", "AMZN", "META", "ORCL"]:
    for r in latest_rows(con, "capex_total", ent)[-3:]:
        pe, fp = r[4], r[2]
        cap, ocf, rev = (src.get((ent, m, pe)) for m in ["capex_total", "operating_cash_flow", "revenue"])
        def stored(m):
            x = [z for z in latest_rows(con, m, ent) if z[4] == pe]
            return x[-1][6] if x else None
        def yago(m):
            for (e2, m2, p2), v in src.items():
                if e2 == ent and m2 == m and abs((D(p2) - (D(pe) - dt.timedelta(days=365))).days) <= 20:
                    return v
        u = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{CIK[ent]:010d}/us-gaap/…"
        checks = {"fcf": ocf - cap if None not in (ocf, cap) else None,
                  "capex_to_ocf": cap / ocf if cap is not None and ocf and ocf > 0 else None,
                  "capex_to_revenue": cap / rev if cap is not None and rev else None,
                  "capex_yoy": (cap / yago("capex_total") - 1) if cap is not None and yago("capex_total") else None,
                  "revenue_yoy": (rev / yago("revenue") - 1) if rev is not None and yago("revenue") else None,
                  "ocf_yoy": (ocf / yago("operating_cash_flow") - 1) if ocf is not None and yago("operating_cash_flow") else None}
        for m, v in checks.items():
            s = stored(m)
            R.add(f"{ent} {m} {fp} recomputed", s, v, close(s, v, rel=1e-6), u, "independent recomputation from source values")

# NVDA Data Center: human-readable filing tables
subs = json.loads(fetch(f"https://data.sec.gov/submissions/CIK{CIK['NVDA']:010d}.json", H))
rec = subs["filings"]["recent"]
filings = [dict(form=f, date=d, rd=r, acc=a, doc=p) for f, d, r, a, p in
           zip(rec["form"], rec["filingDate"], rec["reportDate"], rec["accessionNumber"], rec["primaryDocument"])
           if f in ("10-Q", "10-K")]


def dc_numbers(f):
    url = f"https://www.sec.gov/Archives/edgar/data/{CIK['NVDA']}/{f['acc'].replace('-', '')}/{f['doc']}"
    t = fetch(url, H, min_gap=0.2)
    txt = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    ms = [[int(x.replace(",", "")) for x in re.findall(r"\$? ?([\d,]{4,})", m.group(1))]
          for m in re.finditer(r"Data Center ((?:\$ ?[\d,]{4,} ?|[\d,]{4,} ?){2,4})", txt)]
    return url, ms


nv = latest_rows(con, "nvda_datacenter_revenue", "NVDA")
ytd9 = {}
for r in nv:
    _id, _e, fp, ps, pe, pub, val, cls, url, meth = r
    f = min([f for f in filings if abs((D(f["rd"]) - D(pe)).days) <= 3], key=lambda f: f["date"], default=None)
    if not f:
        R.add(f"NVDA DC {fp} original filing", val, None, None, "", "original filing not in submissions 'recent' list")
        continue
    furl, ms = dc_numbers(f)
    if f["form"] == "10-Q":
        four = [m for m in ms if len(m) == 4]
        two = [m for m in ms if len(m) >= 2]
        v = (four[0][0] if four else two[0][0]) if (four or two) else None
        if four:
            ytd9[pe] = four[0][2]
        how = "10-Q table, 3 months ended"
    else:
        # Q4 = FY (10-K) - 9M YTD (Q3 10-Q, same fiscal year)
        fy = ms[0][0] if ms else None
        q3 = [k for k in ytd9 if 70 <= (D(pe) - D(k)).days <= 110]
        if not q3:   # need the Q3 10-Q for the same FY
            q3f = min([g for g in filings if g["form"] == "10-Q" and 70 <= (D(pe) - D(g["rd"])).days <= 110], key=lambda g: g["date"], default=None)
            if q3f:
                _, m3 = dc_numbers(q3f)
                four = [m for m in m3 if len(m) == 4]
                if four:
                    ytd9[q3f["rd"]] = four[0][2]; q3 = [q3f["rd"]]
        v = fy - ytd9[q3[0]] if fy is not None and q3 else None
        how = f"10-K FY {fy:,} - 9M YTD {ytd9.get(q3[0]) if q3 else None:,}" if fy else "10-K parse failed"
    R.add(f"NVDA DataCenter {fp} ({pe}) value $M", val / 1e6, v, close(val / 1e6, v, rel=1e-9), furl, how)
    R.add(f"NVDA DataCenter {fp} publication_date vs original filing {f['date']}", pub, f["date"], pub == f["date"], furl,
          "" if pub == f["date"] else ("LATE: value taken from a later filing's comparative column" if pub > f["date"] else "LOOK-AHEAD"))
# freshness: latest period in the source vs stored, per company/metric
for ent in ["MSFT", "GOOGL", "AMZN", "META", "ORCL", "NVDA"]:
    for metric, tag in [("capex_total", None), ("revenue", None), ("operating_cash_flow", "NetCashProvidedByUsedInOperatingActivities")]:
        rows = latest_rows(con, metric, ent)
        if not rows:
            continue
        t = tag or con.execute("select source_ref from observations where id=?", (rows[-1][0],)).fetchone()[0].split(":")[-1]
        curl, fs = facts(CIK[ent], t)
        R.add(f"{ent} {metric} freshness (latest period end)", rows[-1][4], max(f["end"] for f in fs),
              rows[-1][4] >= max(f["end"] for f in fs), curl)

# calendar-quarter aggregate (MSFT+GOOGL+AMZN+META capex, calendar quarters)
for r in latest_rows(con, "capex_total_big4_cal")[-3:]:
    pe = r[4]
    vals = []
    for ent in ["MSFT", "GOOGL", "AMZN", "META"]:
        x = [z for z in latest_rows(con, "capex_total", ent) if z[4] == pe]
        tag = con.execute("select source_ref from observations where id=?", (x[-1][0],)).fetchone()[0].split(":")[-1] if x else "PaymentsToAcquirePropertyPlantAndEquipment"
        curl, fs = facts(CIK[ent], tag)
        ps = D(pe).replace(day=1, month=D(pe).month - 2).isoformat()
        vals.append(quarter_value(fs, ps, pe)[0])
    v = sum(vals) if None not in vals else None
    R.add(f"capex_total_big4_cal {pe} (calendar quarter sum MSFT+GOOGL+AMZN+META)", r[6], v, close(r[6], v, rel=1e-9),
          "https://data.sec.gov/api/xbrl/companyconcept/", f"components {vals}")
R.save()
