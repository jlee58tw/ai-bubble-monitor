"""Family (4): API pricing rows vs official pricing pages fetched fresh (independent line-based parsers).
Compares every non-superseded 'current'/'scheduled' row (USD per 1M tokens) and lists rows missing either side."""
import datetime as dt, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import db, fetch, Results, close

R = Results("pricing")
con = db()
OPENAI = "https://developers.openai.com/api/docs/pricing.md"
ANTH = "https://platform.claude.com/docs/en/about-claude/pricing.md"
GEM = "https://ai.google.dev/gemini-api/docs/pricing.md.txt"
M = re.compile(r"\$([0-9][0-9,]*(?:\.[0-9]+)?)")
f = lambda s: float(s.replace(",", ""))
MON = "january february march april may june july august september october november december".split()
def ld(s):
    m, d, y = re.match(r"([A-Za-z]+) (\d+), (\d{4})", s).groups()
    return dt.date(int(y), MON.index(m.lower()) + 1, int(d)).isoformat()

def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]

src = {}  # (vendor, model_id, tier, ptype, status) -> (value, eff_from, eff_to)
# --- OpenAI: the block between the first "### Standard pricing data" and "### Batch pricing data"
md = fetch(OPENAI)
blk = md[md.index("### Standard pricing data"): md.index("### Batch pricing data")]
hdr = None
for ln in blk.splitlines():
    if not ln.startswith("|") or ln.startswith("| ---"):
        hdr = None if not ln.startswith("|") else hdr
        continue
    c = cells(ln)
    if c[0] == "Model":
        hdr = [h.lower().replace("short context ", "") for h in c]; short = "Short context input" in c
        continue
    mid = re.sub(r"\s*\(.*\)$", "", c[0])
    tier = "standard (short context)" if short else "standard"
    for name, pt in (("input", "input"), ("output", "output"), ("cached input", "cached_input")):
        v = M.search(c[hdr.index(name)]) if name in hdr else None
        if v:
            src[("openai", mid, tier, pt, "current")] = (f(v.group(1)), None, None)
# --- Anthropic: main model table (first table whose header starts with Model and has 'Base input tokens')
md = fetch(ANTH)
lines = md.splitlines()
i0 = next(i for i, l in enumerate(lines) if l.startswith("| Model") and "Base input tokens" in l)
h = cells(lines[i0])
for ln in lines[i0 + 2:]:
    if not ln.startswith("|"):
        break
    c = cells(ln)
    lab = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", c[0])
    name = re.sub(r"\s*\(.*\)$", "", lab).strip()
    p = re.search(r"\((for prompts[^)]*)\)", lab)
    tier = f"standard ({p.group(1)})" if p else "standard"
    mid = name.lower().replace("claude ", "claude-").replace(" ", "-")
    for col, pt in (("Base input tokens", "input"), ("Output tokens", "output"), ("Cache hits and refreshes", "cached_input")):
        src[("anthropic", mid, tier, pt, "current")] = (f(M.search(c[h.index(col)]).group(1)), None, None)
# --- Gemini: per "## " section, model id from the first *[`gemini-...`] marker, "### Standard" table, Paid column
md = fetch(GEM)
unit_skips = []
for sec in re.split(r"\n## ", md)[1:]:
    ids = re.findall(r"\*\[`(gemini-[^`]+)`\]", sec)
    if not ids or "### Standard" not in sec:
        continue
    st = sec[sec.index("### Standard"):]
    st = st[: st.find("\n### ", 5)] if st.find("\n### ", 5) > 0 else st
    for ln in st.splitlines():
        if not ln.startswith("| ") or ln.startswith("|   |"):
            continue
        c = cells(ln)
        k = c[0].lower()
        pt = "input" if k.startswith("input price") else "output" if k.startswith("output price") else \
            "cached_input" if k.startswith("context caching") else None
        if not pt or len(c) < 3:
            continue
        cell = c[2]
        sch = re.search(r"\$([\d.,]+)((?:\s*\([^)]*\))?) through ([A-Z][a-z]+ \d+, \d{4})\.\s*\$([\d.,]+)(?:\s*\([^)]*\))? starting ([A-Z][a-z]+ \d+, \d{4})", cell)
        first = re.match(r"\s*\$([\d.,]+)(\s*(?:or [^()]*?)?\s*\(([^)]*)\))?(\s*per\s+\w+)?", cell)
        if not first:
            continue
        mods = (first.group(3) or "text").lower()
        if first.group(4) or "/min" in (first.group(2) or "") and "text" not in mods:
            unit_skips.append((ids[0], pt, cell[:60])); continue
        if "text" not in mods and "and thinking" not in mods:
            continue  # first price is audio/image-only -> not a per-1M text-token price
        if sch:
            src[("google", ids[0], "standard (paid)", pt, "current")] = (f(sch.group(1)), None, ld(sch.group(3)))
            src[("google", ids[0], "standard (paid)", pt, "scheduled")] = (f(sch.group(4)), ld(sch.group(5)), None)
        else:
            src[("google", ids[0], "standard (paid)", pt, "current")] = (f(first.group(1)), None, None)

db_rows, hidden = {}, []
snap = {v: con.execute("select max(started_at) from ingestion_runs where provider=? and status='success'",
                       ("pricing_" + v,)).fetchone()[0] for v in ("openai", "anthropic", "google")}
for v, mid, tier, pt, val, stt, ef, et, seen in con.execute(
        "select vendor, model_id, tier, price_type, usd_per_mtok, price_status, effective_from, effective_to, last_seen_at "
        "from model_prices where id not in (select supersedes_id from model_prices where supersedes_id is not null) "
        "and vendor in ('openai','anthropic','google') and price_status in ('current','scheduled')"):
    if seen[:19].replace("T", " ") < snap[v][:19].replace("T", " "):
        hidden.append((v, mid, tier, pt, stt, val, seen)); continue  # not in latest snapshot -> API hides it
    db_rows[(v, mid, tier, pt, stt)] = (val, ef, et)
URL = {"openai": OPENAI, "anthropic": ANTH, "google": GEM}
for k in sorted(set(src) | set(db_rows)):
    s, d = src.get(k), db_rows.get(k)
    name = " ".join(k)
    if s and d:
        ok = close(s[0], d[0], 1e-9, 1e-12) and (s[1] or None) == (d[1] or None) and (s[2] or None) == (d[2] or None)
        R.add(name, d, s, ok, URL[k[0]], "value per 1M tokens, effective_from, effective_to")
    elif d:
        R.add(name + " (in DB, not on page)", d, None, False, URL[k[0]], "stale or mis-parsed row")
    else:
        R.add(name + " (on page, missing in DB)", None, s, False, URL[k[0]], "missing row (stale snapshot or parser gap)")
for h in hidden:
    R.add(f"hidden (not in latest snapshot): {' '.join(map(str, h[:5]))}", h[5], "not on page / not per-1M", True,
          URL[h[0]], f"last_seen_at {h[6]}; excluded by /api/model-prices (include_stale=false)")
for u in unit_skips:
    R.add(f"google {u[0]} {u[1]} non-token unit on page", "should not be stored as per-1M", u[2], None, GEM, "per image / per minute")
# documented_history: Sonnet 5 footnote
fn = re.search(r"\$2/\$10 per million input/output token pricing for (Claude Sonnet 5)[^<]*", fetch(ANTH))
dh = con.execute("select count(*) from model_prices where id not in (select supersedes_id from model_prices where supersedes_id is not null) and price_status='documented_history' and model_id='claude-sonnet-5'").fetchone()[0]
R.add("anthropic claude-sonnet-5 documented_history footnote", dh, 2 if fn else 0, dh == (2 if fn else 0), ANTH, (fn.group(0)[:200] if fn else ""))
last = con.execute("select max(last_seen_at) from model_prices where vendor in ('openai','anthropic','google')").fetchone()[0]
R.add("freshness: last pricing snapshot (stored UTC, source=now Asia/Taipei)", last, dt.datetime.now().isoformat(timespec="minutes"),
      (dt.datetime.now() - dt.datetime.fromisoformat(last[:19])).days <= 2, OPENAI, "expected daily refresh")
R.save()
