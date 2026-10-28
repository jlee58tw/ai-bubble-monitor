"""Derived-metric calculations (pure pandas, no DB access).

Input frames have columns:
  entity_id, period_start, period_end, value, publication_date, confidence, id, source_url, fiscal_period
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

CONF_RANK = {"low": 0, "medium": 1, "high": 2}
RANK_CONF = {v: k for k, v in CONF_RANK.items()}
KEY = ["entity_id", "period_start", "period_end"]


def _min_conf(*cols: pd.Series) -> pd.Series:
    ranks = pd.concat([c.map(CONF_RANK) for c in cols], axis=1).min(axis=1)
    return ranks.map(RANK_CONF)


def _pair(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    return a.merge(b, on=KEY, suffixes=("_a", "_b"), how="inner")


def _finish(m: pd.DataFrame, value: pd.Series, how: str) -> pd.DataFrame:
    out = m[KEY].copy()
    out["value"] = value
    out["publication_date"] = [max(x, y) for x, y in zip(m["publication_date_a"], m["publication_date_b"])]
    out["confidence"] = _min_conf(m["confidence_a"], m["confidence_b"])
    out["fiscal_period"] = m["fiscal_period_a"]
    out["source_url"] = m["source_url_a"]
    out["inputs"] = [f"{how}; input obs ids {int(x)}, {int(y)}" for x, y in zip(m["id_a"], m["id_b"])]
    return out.dropna(subset=["value"]).reset_index(drop=True)


def subtract(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    m = _pair(a, b)
    return _finish(m, m["value_a"] - m["value_b"], "a - b")


def ratio(a: pd.DataFrame, b: pd.DataFrame, positive_denominator: bool = False) -> pd.DataFrame:
    m = _pair(a, b)
    den = m["value_b"]
    ok = den > 0 if positive_denominator else den != 0
    m = m[ok]
    return _finish(m, m["value_a"] / m["value_b"], "a / b")


def yoy(a: pd.DataFrame, tolerance_days: int = 20) -> pd.DataFrame:
    """value_t / value_(t-1y) - 1, matching the period ending ~365 days earlier with similar length.

    Rows where the prior value is <= 0 are skipped (growth from a non-positive base is undefined).
    """
    rows = []
    for eid, g in a.groupby("entity_id"):
        g = g.sort_values("period_end")
        recs = g.to_dict("records")
        for r in recs:
            target = r["period_end"] - dt.timedelta(days=365)
            dur = (r["period_end"] - r["period_start"]).days if r["period_start"] is not None else None
            best = None
            for p in recs:
                if abs((p["period_end"] - target).days) > tolerance_days:
                    continue
                if dur is not None and p["period_start"] is not None:
                    if abs((p["period_end"] - p["period_start"]).days - dur) > 10:
                        continue
                best = p
            if best is None or best["value"] <= 0:
                continue
            rows.append({
                "entity_id": eid, "period_start": r["period_start"], "period_end": r["period_end"],
                "value": r["value"] / best["value"] - 1.0,
                "publication_date": max(r["publication_date"], best["publication_date"]),
                "confidence": RANK_CONF[min(CONF_RANK[r["confidence"]], CONF_RANK[best["confidence"]])],
                "fiscal_period": r["fiscal_period"], "source_url": r["source_url"],
                "inputs": f"yoy; input obs ids {int(r['id'])} vs {int(best['id'])}",
            })
    return pd.DataFrame(rows, columns=[*KEY, "value", "publication_date", "confidence", "fiscal_period",
                                       "source_url", "inputs"])


def sum_entities(a: pd.DataFrame, members: list[str], target_entity: str) -> pd.DataFrame:
    """Sum across members for identical (period_start, period_end); only when ALL members present."""
    sub = a[a["entity_id"].isin(members)]
    rows = []
    for (ps, pe), g in sub.groupby(["period_start", "period_end"]):
        if set(g["entity_id"]) != set(members) or len(g) != len(members):
            continue
        rows.append({
            "entity_id": target_entity, "period_start": ps, "period_end": pe, "value": g["value"].sum(),
            "publication_date": g["publication_date"].max(),
            "confidence": RANK_CONF[min(CONF_RANK[c] for c in g["confidence"])],
            "fiscal_period": f"CY{pe.year} Q{(pe.month - 1) // 3 + 1}", "source_url": None,
            "inputs": "sum; input obs ids " + ", ".join(str(int(i)) for i in g["id"]),
        })
    return pd.DataFrame(rows, columns=[*KEY, "value", "publication_date", "confidence", "fiscal_period",
                                       "source_url", "inputs"])


def drawdown_52w(a: pd.DataFrame, window_days: int = 365, min_coverage_days: int = 358) -> pd.DataFrame:
    """value_t / max(value over (t - window, t]) - 1 for daily series.

    Emitted only when the stored history reaches back at least `min_coverage_days` before t, so a short
    history never produces an understated drawdown. O(n) per entity (monotonic deque; ties -> latest high).
    """
    from collections import deque
    rows = []
    for eid, g in a.groupby("entity_id"):
        g = g.sort_values("period_end").reset_index(drop=True)
        dates = list(g["period_end"]); vals = list(g["value"]); ids = list(g["id"])
        first = dates[0]
        dq: deque[int] = deque()  # indices with strictly decreasing values
        for i, d in enumerate(dates):
            while dq and vals[dq[-1]] <= vals[i]:
                dq.pop()
            dq.append(i)
            lo = d - dt.timedelta(days=window_days)
            while dates[dq[0]] <= lo:
                dq.popleft()
            if (d - first).days < min_coverage_days:
                continue
            j = dq[0]; hi = vals[j]
            if hi <= 0:
                continue
            rows.append({
                "entity_id": eid, "period_start": None, "period_end": d, "value": vals[i] / hi - 1.0,
                "publication_date": g.loc[i, "publication_date"], "confidence": g.loc[i, "confidence"],
                "fiscal_period": None, "source_url": g.loc[i, "source_url"],
                "inputs": f"drawdown_52w; close obs id {int(ids[i])}, 52w-high obs id {int(ids[j])} "
                          f"({dates[j].isoformat()}, {hi:g})",
            })
    return pd.DataFrame(rows, columns=[*KEY, "value", "publication_date", "confidence", "fiscal_period",
                                       "source_url", "inputs"])


def _splits_by_entity(splits: pd.DataFrame | None) -> dict[str, list[tuple[dt.date, float]]]:
    out: dict[str, list[tuple[dt.date, float]]] = {}
    if splits is None or splits.empty:
        return out
    for r in splits.sort_values("period_end").to_dict("records"):
        if r["value"] and r["value"] > 0:
            out.setdefault(r["entity_id"], []).append((r["period_end"], float(r["value"])))
    return out


def split_adjust(prices: pd.DataFrame, splits: pd.DataFrame | None) -> pd.DataFrame:
    """Split-adjusted (NOT dividend-adjusted) close: close_t / prod(splitFactor_s for split dates s > t).

    Price-return series, comparable with price-return indices. Recomputed (revised) when a new split arrives.
    """
    sp = _splits_by_entity(splits)
    rows = []
    for eid, g in prices.groupby("entity_id"):
        events = sp.get(eid, [])
        for r in g.sort_values("period_end").to_dict("records"):
            f = 1.0
            for sd, sf in events:
                if sd > r["period_end"]:
                    f *= sf
            rows.append({
                "entity_id": eid, "period_start": r["period_start"], "period_end": r["period_end"],
                "value": r["value"] / f, "publication_date": r["publication_date"], "confidence": r["confidence"],
                "fiscal_period": None, "source_url": r["source_url"],
                "inputs": f"split_adjust; close obs id {int(r['id'])}, later-split factor {f:g}",
            })
    return pd.DataFrame(rows, columns=[*KEY, "value", "publication_date", "confidence", "fiscal_period",
                                       "source_url", "inputs"])


def market_cap_asof(prices: pd.DataFrame, shares: pd.DataFrame, splits: pd.DataFrame | None,
                    max_age_days: int = 120, max_age_overrides: dict | None = None,
                    scale: dict | None = None) -> pd.DataFrame:
    """raw close_t x (latest shares snapshot dated <= t, within max_age_days) x splits in (snapshot, t] x scale.

    Backward-looking only (no later snapshot is used). `scale` converts share units, e.g. TSM ADR = 5 ordinary
    shares -> 0.2. publication_date = max(price, shares filing date): the value is not known before both are.
    """
    sp = _splits_by_entity(splits)
    max_age_overrides = max_age_overrides or {}; scale = scale or {}
    rows = []
    for eid, ga in prices.groupby("entity_id"):
        gb = shares[shares["entity_id"] == eid]
        if gb.empty:
            continue
        snaps = sorted(gb.to_dict("records"), key=lambda x: x["period_end"])
        lim = int(max_age_overrides.get(eid, max_age_days)); k = float(scale.get(eid, 1.0))
        for r in ga.to_dict("records"):
            t = r["period_end"]
            prior = [x for x in snaps if x["period_end"] <= t]
            if not prior:
                continue
            b = prior[-1]
            if (t - b["period_end"]).days > lim:
                continue
            f = 1.0
            for sd, sf in sp.get(eid, []):
                if b["period_end"] < sd <= t:
                    f *= sf
            rows.append({
                "entity_id": eid, "period_start": None, "period_end": t,
                "value": r["value"] * b["value"] * f * k,
                "publication_date": max(r["publication_date"], b["publication_date"]),
                "confidence": RANK_CONF[min(CONF_RANK[r["confidence"]], CONF_RANK[b["confidence"]])],
                "fiscal_period": None, "source_url": r["source_url"],
                "inputs": f"market_cap_asof; close obs id {int(r['id'])} x shares obs id {int(b['id'])} "
                          f"(as of {b['period_end'].isoformat()}) x split {f:g} x scale {k:g}",
            })
    return pd.DataFrame(rows, columns=[*KEY, "value", "publication_date", "confidence", "fiscal_period",
                                       "source_url", "inputs"])


def rel_return(a: pd.DataFrame, bench: pd.DataFrame, bench_entity: str, window_days: int = 365,
               tolerance_days: int = 7) -> pd.DataFrame:
    """Relative price return over `window_days`: (a_t / a_base) / (B_t / B_base) - 1.

    base = last observation on or before t - window_days, required within `tolerance_days` of that date for
    BOTH series; t must exist in both series (no forward fill). Not emitted otherwise.
    """
    import bisect
    b = bench[bench["entity_id"] == bench_entity].sort_values("period_end")
    if b.empty:
        return pd.DataFrame(columns=[*KEY, "value", "publication_date", "confidence", "fiscal_period",
                                     "source_url", "inputs"])
    bd = list(b["period_end"]); bv = list(b["value"]); bid = list(b["id"]); bpub = list(b["publication_date"])
    bconf = list(b["confidence"]); bidx = {d: i for i, d in enumerate(bd)}
    rows = []
    for eid, g in a.groupby("entity_id"):
        g = g.sort_values("period_end").reset_index(drop=True)
        ad = list(g["period_end"]); av = list(g["value"])
        for i, t in enumerate(ad):
            if t not in bidx:
                continue
            target = t - dt.timedelta(days=window_days)
            ia = bisect.bisect_right(ad, target) - 1; ib = bisect.bisect_right(bd, target) - 1
            if ia < 0 or ib < 0:
                continue
            if (target - ad[ia]).days > tolerance_days or (target - bd[ib]).days > tolerance_days:
                continue
            jb = bidx[t]
            if av[ia] <= 0 or bv[ib] <= 0 or bv[jb] <= 0:
                continue
            val = (av[i] / av[ia]) / (bv[jb] / bv[ib]) - 1.0
            rows.append({
                "entity_id": eid, "period_start": None, "period_end": t, "value": val,
                "publication_date": max(g.loc[i, "publication_date"], bpub[jb]),
                "confidence": RANK_CONF[min(CONF_RANK[g.loc[i, "confidence"]], CONF_RANK[bconf[jb]])],
                "fiscal_period": None, "source_url": g.loc[i, "source_url"],
                "inputs": f"rel_return vs {bench_entity} from {ad[ia].isoformat()}; obs ids {int(g.loc[ia, 'id'])}->{int(g.loc[i, 'id'])}, "
                          f"bench {int(bid[ib])}->{int(bid[jb])}",
            })
    return pd.DataFrame(rows, columns=[*KEY, "value", "publication_date", "confidence", "fiscal_period",
                                       "source_url", "inputs"])


def multiply_asof(a: pd.DataFrame, b: pd.DataFrame, max_gap_days: int = 45) -> pd.DataFrame:
    """a_t x b_(nearest date within max_gap_days), per entity (e.g. price x shares snapshot)."""
    rows = []
    for eid, ga in a.groupby("entity_id"):
        gb = b[b["entity_id"] == eid]
        if gb.empty:
            continue
        bl = list(gb.sort_values("period_end").to_dict("records"))
        for r in ga.to_dict("records"):
            best = min(bl, key=lambda x: abs((x["period_end"] - r["period_end"]).days))
            if abs((best["period_end"] - r["period_end"]).days) > max_gap_days:
                continue
            rows.append({
                "entity_id": eid, "period_start": r["period_start"], "period_end": r["period_end"],
                "value": r["value"] * best["value"],
                "publication_date": max(r["publication_date"], best["publication_date"]),
                "confidence": RANK_CONF[min(CONF_RANK[r["confidence"]], CONF_RANK[best["confidence"]])],
                "fiscal_period": r["fiscal_period"], "source_url": r["source_url"],
                "inputs": f"a x b(asof); input obs ids {int(r['id'])}, {int(best['id'])} "
                          f"(b dated {best['period_end'].isoformat()})",
            })
    return pd.DataFrame(rows, columns=[*KEY, "value", "publication_date", "confidence", "fiscal_period",
                                       "source_url", "inputs"])
