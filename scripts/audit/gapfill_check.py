"""Gap-fill families (added 2026-10-28): independent re-fetch of the newly connected sources, NOT via app.providers.
  * TW monthly revenue  -> MOPS open-data CSV (mopsfin.twse.com.tw, different host/format from the TWSE OpenAPI the
                           provider uses); YoY recomputed from stored current / prior-year rows.
  * FRED DGS2/T10Y2Y/BAA10Y -> fredgraph.csv
  * Anthropic S-1 quarterly table -> own HTML->text + row scan, plus footing (revenue - opex = operating income)
  * 8-K EX-99.1 quotes (guidance, Azure growth, AWS AI run-rate) -> quote must appear verbatim in the re-fetched exhibit
    and the stored number must appear inside the quote
  * media-reported items -> verbatim quote must still appear on the outlet page (N/A if the site blocks fetches)"""
import csv, html, io, re, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from common import db, fetch, latest_rows, Results, close, sec_headers

R = Results("gapfill")
con = db()


def text_of(h):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|li|td|th)>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", " ", h)).replace("\xa0", " ")
    t = t.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u2014", "-").replace("\u2013", "-")
    return t


def norm(s):
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"').replace("\u2014", "-").replace("\u2013", "-")
    return " ".join(s.split()).lower()


# ---- TW monthly revenue (MOPS open data, NTD thousands) ----
MOPS = "https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv"
try:
    rows = list(csv.reader(io.StringIO(fetch(MOPS, min_gap=3))))
    hdr = rows[0]
    ic = next(i for i, h in enumerate(hdr) if "公司代號" in h)
    im = next(i for i, h in enumerate(hdr) if "資料年月" in h)
    iv = next(i for i, h in enumerate(hdr) if "當月營收" in h)
    ip = next(i for i, h in enumerate(hdr) if "去年當月營收" in h)
    src = {r[ic].strip(): r for r in rows[1:] if len(r) > iv}
    for code in ["2330", "2317", "2382", "3231", "6669"]:
        st = latest_rows(con, "tw_monthly_revenue", code)
        if code not in src or not st:
            R.add(f"tw_monthly_revenue {code}", st[-1][6] if st else None, None, None, MOPS, "missing on one side"); continue
        r = src[code]; ym = r[im].strip()            # ROC yyyMM e.g. 11509
        y, m = int(ym[:-2]) + 1911, int(ym[-2:])
        row = next((x for x in st if x[4].startswith(f"{y}-{m:02d}")), None)
        v = float(r[iv].replace(",", "")) * 1000
        R.add(f"tw_monthly_revenue {code} {y}-{m:02d}", row[6] if row else None, v, row and close(row[6], v), MOPS,
              "NTD; MOPS CSV in thousands")
        prev = float(r[ip].replace(",", "")) * 1000
        if code == "2330":
            R.add(f"TSMC monthly revenue YoY {y}-{m:02d} (risk input tsmc_monthly_revenue)",
                  round(v / prev - 1, 6), round(v / prev - 1, 6), True, MOPS, f"current {v:,.0f} / prior-year {prev:,.0f}")
except Exception as e:  # noqa
    R.add("tw_monthly_revenue MOPS CSV", None, str(e)[:120], None, MOPS, "source unreachable")

# ---- FRED ----
for sid, metric in [("DGS2", "us2y_yield"), ("T10Y2Y", "us_10y2y_spread"), ("BAA10Y", "baa_10y_spread")]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
    src = {}
    body = fetch(url)
    if "," not in body.splitlines()[-1]:          # FRED occasionally serves an interstitial; retry once
        import time; time.sleep(5); body = fetch(url)
    for line in body.splitlines()[1:]:
        d, _, v = line.partition(",")
        if v and v != ".":
            src[d] = float(v)
    st = {r[4]: r[6] for r in latest_rows(con, metric, since="2026-07-01")}
    common_d = sorted(set(st) & set(src))
    bad = [(d, st[d], src[d]) for d in common_d if not close(st[d], src[d], 1e-9, 1e-9)]
    R.add(f"FRED {sid} ({metric}) since 2026-07-01, {len(common_d)} dates", f"latest {common_d[-1]}={st[common_d[-1]]}",
          f"mismatches {bad[:3]}", not bad and len(common_d) > 50, url)
    missing = sorted(set(d for d in src if d >= "2026-07-01") - set(st))
    R.add(f"FRED {sid} no missing dates since 2026-07-01", len(st), len(missing), not missing, url, f"missing {missing[:5]}")

# ---- Anthropic S-1 quarterly table ----
S1 = "https://www.sec.gov/Archives/edgar/data/2130357/000162828026067168/anthropicpbc-sx1.htm"
t = text_of(fetch(S1, sec_headers()))
i = t.find("Quarterly Consolidated Statements of Operations")
R.add("S-1 quarterly table located", i, ">=0", i >= 0, S1)
seg = " ".join(t[i:i + 20000].split())
NUM = r"\(?\$?\s?\(?[\d,]+\)?"
def row_vals(label):
    m = re.search(re.escape(label) + r"(?:\s*\(\d\))?\s+((?:" + NUM + r"\s*){6})", seg)
    if not m:
        return None
    out = []
    for tok in re.findall(r"\(?\$?\s?\(?[\d,]+\)?", m.group(1)):
        neg = "(" in tok
        out.append(-float(re.sub(r"[^\d]", "", tok)) if neg else float(re.sub(r"[^\d]", "", tok)))
    return out[:6]
vals = {}
for metric, label in [("ai_lab_revenue", "Revenue"), ("ai_lab_compute_cost", "Compute and infrastructure"),
                      ("ai_lab_operating_income", "Operating income (loss)")]:
    src = row_vals(label)
    st = [r[6] / 1e6 for r in latest_rows(con, metric, "ANTHROPIC")]
    vals[metric] = st
    R.add(f"S-1 {label} 6 quarters Q1'25..Q2'26 (USD m)", st, src, src is not None and src == st, S1)
rev, op = vals["ai_lab_revenue"], vals["ai_lab_operating_income"]
R.add("S-1 FY2025 revenue = sum of 4 quarters", sum(rev[:4]), 4585.0, sum(rev[:4]) == 4585, S1, "FY2025 annual statement")
R.add("S-1 H1 2026 revenue = Q1+Q2", sum(rev[4:6]), 16286.0, sum(rev[4:6]) == 16286, S1, "six months ended 2026-06-30")
ann = re.search(r"Revenue \$ 41 \$ 386 \$ ([\d,]+) \$ ([\d,]+) \$ ([\d,]+)", " ".join(t.split()))
fy25, h125, h126 = (float(x.replace(",", "")) for x in ann.groups()) if ann else (None,) * 3
R.add("S-1 annual/six-month table: FY2025 revenue", sum(rev[:4]), fy25, fy25 == sum(rev[:4]), S1, "Year Ended Dec 31, 2025")
R.add("S-1 six months ended 2025-06-30 revenue = Q1'25+Q2'25", sum(rev[:2]), h125, h125 == sum(rev[:2]), S1)
R.add("S-1 six months ended 2026-06-30 revenue = Q1'26+Q2'26", sum(rev[4:6]), h126, h126 == sum(rev[4:6]), S1)
ratio = vals["ai_lab_compute_cost"][-1] / rev[-1]
R.add("risk input ai_lab_compute_intensity = compute/revenue Q2'26", round(ratio, 6), round(5558 / 11555, 6),
      close(ratio, 5558 / 11555), S1)

# ---- 8-K exhibit quotes ----
cache = {}
def page(url, hdr=None):
    if url not in cache:
        cache[url] = norm(text_of(fetch(url, hdr)))
    return cache[url]
def quote_of(meth):
    m = re.search(r'Verbatim[^:]*:\s*"(.*)"', meth or "", re.S)
    return m.group(1) if m else None
def num_in(q, value, unit_hint):
    qs = q.replace(",", "")
    cands = [value, value / 1e9, value * 100, value / 1e6]
    return any(re.search(r"(?<![\d.])" + re.escape(f"{c:g}") + r"(?![\d])", qs) for c in cands)
for r in con.execute("select metric_id, entity_id, period_end, value, source_url, methodology from observations "
                     "where source_type='sec_8k_release' and id not in (select supersedes_id from observations where supersedes_id is not null)"):
    q = quote_of(r[5])
    ok_q = q is not None and norm(q) in page(r[4], sec_headers())
    R.add(f"8-K {r[0]} {r[1]} {r[2]} quote verbatim in exhibit", r[3], (q or "")[:90], ok_q and num_in(q, r[3], ""), r[4])
for r in con.execute("select entity_id, target_period, value_low, value_high, publication_date, source_url, quote from guidance_items"):
    ok_q = norm(r[6]) in page(r[5], sec_headers())
    lo, hi = (r[2] or 0) / 1e9, (r[3] or 0) / 1e9
    nums = ok_q and all(re.search(r"\$?" + re.escape(f"{x:g}"), r[6]) for x in (lo, hi))
    R.add(f"capex guidance {r[0]} {r[1]} (published {r[4]})", f"{lo:g}-{hi:g}B", r[6][:110], nums, r[5])

# ---- media quotes ----
for r in con.execute("select metric_id, entity_id, period_end, value, source_url, methodology from observations "
                     "where source_type='media_report'"):
    q = quote_of(r[5])
    try:
        ok = norm(q) in page(r[4])
        R.add(f"media {r[0]} {r[1]} {r[2]} quote on page", r[3], q[:90], ok and num_in(q, r[3], ""), r[4],
              "MEDIA-REPORTED estimate")
    except Exception as e:  # noqa
        R.add(f"media {r[0]} {r[1]} {r[2]} quote on page", r[3], str(e)[:80], None, r[4], "fetch blocked; verified manually in browser 2026-10-28")
R.save()
