"""Model API list prices from official, robots-permitted machine-readable docs.

* OpenAI     https://developers.openai.com/api/docs/pricing.md     (robots.txt: Allow /)
* Anthropic  https://platform.claude.com/docs/en/about-claude/pricing.md
* Google     https://ai.google.dev/gemini-api/docs/pricing.md
* OpenRouter https://openrouter.ai/api/v1/models  (public API; open-weight = has hugging_face_id)

The pages carry NO publication date, so each row stores observed time (first_seen_at/last_seen_at).
A documented date is stored only when the page itself states one (Gemini "through X / starting Y",
Anthropic footnote about Sonnet 5 introductory pricing). History otherwise accrues from weekly observation.
All values are USD per 1M tokens, standard (non-batch) tier unless `tier` says otherwise.
"""
from __future__ import annotations

import datetime as dt
import re

OPENAI_URL = "https://developers.openai.com/api/docs/pricing.md"
ANTHROPIC_URL = "https://platform.claude.com/docs/en/about-claude/pricing.md"
GEMINI_URL = "https://ai.google.dev/gemini-api/docs/pricing.md.txt"
OPENROUTER_URL = "https://openrouter.ai/api/v1/models"
OPENROUTER_PUBLIC = "https://openrouter.ai/models"

MONEY = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)")
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                       "september", "october", "november", "december"], 1)}


def money(cell: str) -> float | None:
    m = MONEY.search(cell or "")
    return float(m.group(1).replace(",", "")) if m else None


def _table_rows(lines: list[str]) -> list[list[str]]:
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln.startswith("|") or set(ln.replace("|", "").strip()) <= set("-: "):
            continue
        out.append([c.strip() for c in ln.strip("|").split("|")])
    return out


def _tables(text: str) -> list[list[list[str]]]:
    """Split markdown into tables (header row first)."""
    tables, cur = [], []
    for ln in text.splitlines():
        if ln.strip().startswith("|"):
            cur.append(ln)
        elif cur:
            tables.append(_table_rows(cur)); cur = []
    if cur:
        tables.append(_table_rows(cur))
    return [t for t in tables if t]


def _row(vendor, model_id, label, tier, ptype, val, url, raw, status="current", eff_from=None, eff_to=None,
         note=None, open_weight=False):
    return dict(vendor=vendor, model_id=model_id, model_label=label, tier=tier, price_type=ptype,
                usd_per_mtok=val, price_status=status, effective_from=eff_from, effective_to=eff_to,
                source_url=url, raw_text=raw, note=note, open_weight=open_weight)


# ------------------------------------------------------------------ OpenAI
def parse_openai(md: str) -> list[dict]:
    """First 'Standard pricing data' section (flagship + other models) up to 'Batch pricing data'."""
    start = md.find("### Standard pricing data")
    end = md.find("### Batch pricing data", start)
    if start < 0 or end < 0:
        raise ValueError("OpenAI pricing.md: 'Standard pricing data' section not found (layout changed?)")
    out = []
    for t in _tables(md[start:end]):
        hdr = [h.lower() for h in t[0]]
        if hdr[0] != "model":
            continue
        cols = {"input": None, "output": None, "cached_input": None}
        for i, h in enumerate(hdr):
            if h in ("input", "short context input"):
                cols["input"] = i
            elif h in ("output", "short context output"):
                cols["output"] = i
            elif h in ("cached input", "short context cached input"):
                cols["cached_input"] = i
        tier = "standard (short context)" if "short context input" in hdr else "standard"
        for r in t[1:]:
            label = r[0]
            mid = re.sub(r"\s*\(.*\)\s*$", "", label).strip()
            ctx = re.search(r"\((.*)\)", label)
            for ptype, i in cols.items():
                if i is None or i >= len(r):
                    continue
                v = money(r[i])
                if v is None:
                    continue
                out.append(_row("openai", mid, label, tier, ptype, v, OPENAI_URL, r[i],
                                note=ctx.group(1) if ctx else None))
    if not out:
        raise ValueError("OpenAI pricing.md: no price rows parsed")
    return out


# ------------------------------------------------------------------ Anthropic
def parse_anthropic(md: str) -> list[dict]:
    start = md.find("## Model pricing")
    if start < 0:
        raise ValueError("Anthropic pricing.md: '## Model pricing' not found")
    nxt = md.find("\n## ", start + 5)
    sec = md[start: nxt if nxt > 0 else None]
    t = next((t for t in _tables(sec) if t[0][0].lower() == "model"), None)
    if not t:
        raise ValueError("Anthropic pricing.md: model table not found")
    hdr = [h.lower() for h in t[0]]
    idx = {"input": next(i for i, h in enumerate(hdr) if h.startswith("base input")),
           "output": next(i for i, h in enumerate(hdr) if h.startswith("output")),
           "cached_input": next((i for i, h in enumerate(hdr) if h.startswith("cache hits")), None)}
    out = []
    for r in t[1:]:
        label = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", r[0]).strip()
        name = re.sub(r"\s*\(.*\)\s*$", "", label).strip()
        paren = re.search(r"\((.*)\)", label)
        tier = "standard"
        note = paren.group(1) if paren else None
        if note and "prompts" in note:
            tier = f"standard ({note})"; note = None
        mid = name.lower().replace("claude ", "claude-").replace(" ", "-")
        for ptype, i in idx.items():
            if i is None:
                continue
            v = money(r[i])
            if v is not None:
                out.append(_row("anthropic", mid, name, tier, ptype, v, ANTHROPIC_URL, re.sub(r"\s+", " ", r[i]),
                                note=note))
    out.extend(_anthropic_documented_history(md))
    return out


def _anthropic_documented_history(md: str) -> list[dict]:
    """Sonnet 5 footnote: '$2/$10 ... introductory pricing through August 31, 2026, is now the standard price.'
    Recorded verbatim as a documented history note (the $3/$15 increase was cancelled -> NOT stored as a price)."""
    m = re.search(r"The \$(\d+(?:\.\d+)?)/\$(\d+(?:\.\d+)?) per million input/output token pricing for "
                  r"(Claude [A-Za-z]+ [0-9.]+), announced at launch as introductory pricing through "
                  r"([A-Z][a-z]+ \d{1,2}, \d{4}), is now the standard price\.([^*<]*)", md)
    if not m:
        return []
    inp, outp, name, through, rest = m.groups()
    raw = re.sub(r"\s+", " ", m.group(0)).strip()
    mid = name.lower().replace("claude ", "claude-").replace(" ", "-")
    to = parse_long_date(through)
    rows = []
    for ptype, v in (("input", float(inp)), ("output", float(outp))):
        rows.append(_row("anthropic", mid, name, "standard", ptype, v, ANTHROPIC_URL, raw,
                         status="documented_history", eff_to=to,
                         note="Introductory price documented in footnote; it became the standard price "
                              "(scheduled increase cancelled)."))
    return rows


def parse_long_date(s: str) -> dt.date | None:
    m = re.match(r"([A-Za-z]+) (\d{1,2}), (\d{4})", s.strip())
    if not m or m.group(1).lower() not in MONTHS:
        return None
    return dt.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))


# ------------------------------------------------------------------ Gemini
SCHED = re.compile(r"\$([0-9.,]+) through ([A-Z][a-z]+ \d{1,2}, \d{4})\.\s*\$([0-9.,]+) starting "
                   r"([A-Z][a-z]+ \d{1,2}, \d{4})")


def parse_gemini(md: str) -> list[dict]:
    out = []
    sections = re.split(r"\n## ", "\n" + md)
    for sec in sections[1:]:
        title = sec.splitlines()[0].strip()
        ids = re.findall(r"\*\[`(gemini-[^`]+)`\]", sec)
        if not ids:
            continue
        mid = ids[0]
        std = sec.find("### Standard")
        if std < 0:
            continue
        nxt = sec.find("\n### ", std + 5)
        tbls = _tables(sec[std: nxt if nxt > 0 else None])
        if not tbls:
            continue
        t = tbls[0]
        paid = next((i for i, h in enumerate(t[0]) if h.lower().startswith("paid tier")), None)
        if paid is None:
            continue
        for r in t[1:]:
            key = r[0].lower()
            ptype = "input" if key.startswith("input price") else "output" if key.startswith("output price") \
                else "cached_input" if key.startswith("context caching price") else None
            if not ptype or paid >= len(r):
                continue
            cell = r[paid]
            if "(text)" not in cell and "(audio)" in cell:
                continue  # audio-only models priced per minute/audio tokens: not comparable, skip
            sm = SCHED.search(cell)
            if sm:
                v1, through, v2, starting = sm.groups()
                to, fr = parse_long_date(through), parse_long_date(starting)
                out.append(_row("google", mid, title, "standard (paid)", ptype, float(v1.replace(",", "")),
                                GEMINI_URL, cell, status="current", eff_to=to))
                out.append(_row("google", mid, title, "standard (paid)", ptype, float(v2.replace(",", "")),
                                GEMINI_URL, cell, status="scheduled", eff_from=fr,
                                note="Scheduled change stated on the pricing page."))
                continue
            v = money(cell)
            if v is None:
                continue
            note = None
            if "<=" in cell or "prompts" in cell or "(text)" in cell:
                note = "first listed price (tiered/modal cell; see raw_text)"
            out.append(_row("google", mid, title, "standard (paid)", ptype, v, GEMINI_URL, cell, note=note))
    if not out:
        raise ValueError("Gemini pricing.md: no price rows parsed (layout changed?)")
    return out


# ------------------------------------------------------------------ OpenRouter (open-weight hosted)
def parse_openrouter(doc: dict) -> list[dict]:
    out = []
    for m in doc.get("data", []):
        if not m.get("hugging_face_id") or m["id"].endswith(":free"):
            continue
        p = m.get("pricing") or {}
        for ptype, key in (("input", "prompt"), ("output", "completion"), ("cached_input", "input_cache_read")):
            try:
                v = float(p.get(key)) * 1e6
            except (TypeError, ValueError):
                continue
            if v <= 0:
                continue  # zero / negative ("-1" = variable) are not list prices
            out.append(_row("openrouter", m["id"], m.get("name") or m["id"], "openrouter (routed)", ptype,
                            round(v, 6), f"{OPENROUTER_PUBLIC}/{m['id']}", str(p.get(key)),
                            note=f"open-weight: {m['hugging_face_id']}", open_weight=True))
    return out


SOURCES = {
    "pricing_openai": (OPENAI_URL, "text", parse_openai),
    "pricing_anthropic": (ANTHROPIC_URL, "text", parse_anthropic),
    "pricing_google": (GEMINI_URL, "text", parse_gemini),
    "pricing_openrouter": (OPENROUTER_URL, "json", parse_openrouter),
}
