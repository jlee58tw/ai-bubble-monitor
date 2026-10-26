"""Agent-reliability leaderboards. Comparability key = (benchmark, benchmark_version, split, metric).

* SWE-bench   https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/master/data/leaderboards.json
              (the JSON behind swebench.com; MIT-licensed repo). Each named leaderboard (Verified, Lite,
              Multimodal, Multilingual, Test, ...) is a SEPARATE split - never mixed.
* METR        https://metr.org/assets/benchmark_results_1_1.yaml  (METR-Horizon-v1.1; minutes; 95% CI)
* Terminal-Bench  https://www.tbench.ai/leaderboard/terminal-bench/<ver>  - no JSON API; rows are read from the
              page's embedded React-Server-Component payload. BRITTLE: fails loudly (run 'failed') if the
              layout changes. Version taken from the payload (e.g. '4-0-0'), not from the URL.
"""
from __future__ import annotations

import datetime as dt
import json
import re

import httpx
import yaml

from ..providers.base import RateLimiter, get_with_retry

SWE_URL = "https://raw.githubusercontent.com/SWE-bench/swe-bench.github.io/master/data/leaderboards.json"
SWE_PUBLIC = "https://www.swebench.com/"
METR_URL = "https://metr.org/assets/benchmark_results_1_1.yaml"
METR_PUBLIC = "https://metr.org/time-horizons/"
TB_URL = "https://www.tbench.ai/leaderboard/terminal-bench/2.0"


def _date(v) -> dt.date | None:
    if v is None:
        return None
    if isinstance(v, dt.date):
        return v
    try:
        return dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def parse_swebench(doc: dict) -> list[dict]:
    out = []
    for lb in doc.get("leaderboards", []):
        split = str(lb.get("name"))
        for r in lb.get("results", []):
            if r.get("resolved") is None:
                continue
            checked = r.get("checked") is True
            out.append(dict(
                benchmark="swe-bench", benchmark_version="swebench.com leaderboard", split=split.lower(),
                metric="resolved_pct", model=r.get("model_display") or r.get("name") or "?",
                harness=r.get("agent") or r.get("name"), entry_key=r.get("folder") or r.get("name"),
                value=float(r["resolved"]), ci_low=None, ci_high=None, result_date=_date(r.get("date")),
                source_url=SWE_PUBLIC,
                extra={"checked": checked, "agent_org": r.get("agent_org"), "model_org": r.get("model_org"),
                       "open_weights_model": r.get("os_model"), "open_source_system": r.get("os_system"),
                       "cost_usd": r.get("cost"), "attempts": next((t.split(" - ", 1)[1] for t in r.get("tags", [])
                                                                   if str(t).startswith("System: Attempts")), None),
                       "reasoning_effort": r.get("reasoning_effort"), "site": r.get("site")}))
    if not out:
        raise ValueError("SWE-bench leaderboards.json: no results")
    return out


def parse_metr(text: str) -> list[dict]:
    d = yaml.safe_load(text)
    ver = d.get("benchmark_name") or "METR-Horizon"
    out = []
    for key, r in (d.get("results") or {}).items():
        m = r.get("metrics") or {}
        scaff = "; ".join(str(x) for x in (r.get("scaffolds") or []) if x)[:300] or None
        for metric, unit in (("p50_horizon_length", "p50_horizon_min"), ("p80_horizon_length", "p80_horizon_min")):
            h = m.get(metric)
            if not h or h.get("estimate") is None:
                continue
            out.append(dict(
                benchmark="metr-horizon", benchmark_version=ver, split="-", metric=unit, model=key,
                harness=scaff, entry_key=key, value=float(h["estimate"]),
                ci_low=h.get("ci_low"), ci_high=h.get("ci_high"), result_date=_date(r.get("release_date")),
                source_url=METR_URL,
                extra={"date_kind": "model release date (METR does not publish evaluation date here)",
                       "is_sota": m.get("is_sota"), "average_score": (m.get("average_score") or {}).get("estimate"),
                       "reliability_note": "METR notes estimates > 16 h are unreliable" if h["estimate"] > 960 else None,
                       "doubling_time_days": d.get("doubling_time_in_days")}))
    if not out:
        raise ValueError("METR yaml: no results")
    return out


def parse_terminal_bench(html: str, url: str = TB_URL) -> list[dict]:
    h = html.replace('\\\\', '\x00').replace('\\"', '"').replace('\x00', '\\')
    dec = json.JSONDecoder()
    i = h.find('"leaderboard":{')
    if i < 0:
        raise ValueError("Terminal-Bench: leaderboard payload not found (layout changed?)")
    lb, end = dec.raw_decode(h, i + len('"leaderboard":'))
    j = h.find('"rows":[', end)
    if j < 0 or j - end > 50:
        raise ValueError("Terminal-Bench: rows not adjacent to leaderboard object")
    rows, _ = dec.raw_decode(h, j + len('"rows":'))
    version = f"{lb.get('title')} ({lb.get('package')}@{lb.get('name')})"
    out = []
    for r in rows:
        md, mt = r.get("metadata") or {}, r.get("metrics") or {}
        if mt.get("accuracy") is None:
            continue
        hw = mt.get("accuracy_ci95_half_width")
        agent = (md.get("agent_display") or {}).get("label")
        model = (md.get("model_display") or {}).get("label") or "?"
        out.append(dict(
            benchmark="terminal-bench", benchmark_version=version, split="-", metric="accuracy_pct",
            model=model, harness=agent, entry_key=r.get("id"), value=float(mt["accuracy"]),
            ci_low=float(mt["accuracy"]) - hw if hw is not None else None,
            ci_high=float(mt["accuracy"]) + hw if hw is not None else None,
            result_date=_date(md.get("date")), source_url=url,
            extra={"rank": r.get("rank"), "n_trials": mt.get("n_trials"), "total_cost_usd": mt.get("total_cost_usd"),
                   "reasoning_effort": md.get("reasoning_effort"), "model_org": (md.get("model_org") or {}).get("label"),
                   "agent_org": (md.get("agent_org") or {}).get("label"),
                   "leaderboard_updated_at": lb.get("updated_at")}))
    if not out:
        raise ValueError("Terminal-Bench: 0 rows parsed")
    return out


def _f(url, kind, parse):
    lim = RateLimiter(1.0)

    def fetch(client: httpx.Client) -> list[dict]:
        r = get_with_retry(client, url, lim)
        return parse(r.json() if kind == "json" else r.text)
    return fetch


SOURCES = {
    "bench_swebench": _f(SWE_URL, "json", parse_swebench),
    "bench_metr": _f(METR_URL, "text", parse_metr),
    "bench_terminalbench": _f(TB_URL, "text", parse_terminal_bench),
}
