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
