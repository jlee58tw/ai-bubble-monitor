"""In-app alerts. Every alert is derived from stored real observations / dataset rows and carries its evidence.
No alert is produced from missing data except explicit data-quality alerts (coverage, failed sources)."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import IngestionRun, ModelPrice, RiskSnapshot
from .queries import query_observations
from .risk import load_config


def _latest(session, metric, entities):
    out = {}
    for o in query_observations(session, [metric], entities):
        if o.entity_id not in out or o.period_end > out[o.entity_id].period_end:
            out[o.entity_id] = o
    return out


def compute_alerts(session: Session, today: dt.date | None = None) -> list[dict]:
    cfg, _ = load_config()
    rules = cfg.get("alerts", {})
    today = today or dt.date.today()
    cos = rules.get("companies", [])
    out: list[dict] = []

    # 1. capex growth vs revenue growth
    cy, ry = _latest(session, "capex_yoy", cos), _latest(session, "revenue_yoy", cos)
    for e, c in sorted(cy.items()):
        r = ry.get(e)
        if r and r.period_end == c.period_end and c.value - r.value >= rules.get("capex_vs_revenue_gap", 0.3):
            out.append({"id": f"capex_gap:{e}:{c.period_end}", "severity": "warning", "category": "capex",
                        "title": f"{e}: capex growth {c.value:+.0%} vs revenue growth {r.value:+.0%} ({c.fiscal_period})",
                        "detail": "Capex YoY exceeds revenue YoY by "
                                  f"{(c.value - r.value) * 100:.0f} pp (threshold {rules['capex_vs_revenue_gap']:.0%}).",
                        "as_of": str(c.period_end), "classification": "derived", "source_url": c.source_url,
                        "evidence": {"capex_yoy_obs": c.id, "revenue_yoy_obs": r.id}})
    # 2. negative FCF
    if rules.get("negative_fcf"):
        for e, f in sorted(_latest(session, "fcf", cos).items()):
            if f.value < 0:
                out.append({"id": f"neg_fcf:{e}:{f.period_end}", "severity": "warning", "category": "capex",
                            "title": f"{e}: negative free cash flow ${f.value / 1e9:,.1f}B ({f.fiscal_period})",
                            "detail": "FCF = operating cash flow - capex (derived from SEC XBRL).",
                            "as_of": str(f.period_end), "classification": "derived", "source_url": f.source_url,
                            "evidence": {"fcf_obs": f.id}})
    # 3. rising risk (only snapshots with the same config hash are comparable)
    snaps = list(session.scalars(select(RiskSnapshot).order_by(RiskSnapshot.computed_at.desc()).limit(50)))
    if snaps:
        cur = snaps[0]
        prev = next((s for s in snaps[1:] if s.config_hash == cur.config_hash), None)
        mid = lambda s: s.score if s.score is not None else (s.score_low + s.score_high) / 2  # noqa: E731
        if prev and mid(cur) - mid(prev) >= rules.get("risk_rise_points", 5):
            out.append({"id": f"risk_rise:{cur.id}", "severity": "warning", "category": "risk",
                        "title": f"Risk score rose {mid(prev):.1f} -> {mid(cur):.1f}",
                        "detail": f"Snapshots {prev.id} -> {cur.id}, config {cur.config_hash}. "
                                  f"{'Point score' if cur.score is not None else 'Range midpoint (coverage too low for point score)'}.",
                        "as_of": str(cur.computed_at.date()), "classification": "derived", "source_url": None,
                        "evidence": {"snapshots": [prev.id, cur.id]}})
        min_cov = float(cfg["min_coverage"])
        if cur.coverage < min_cov:
            out.append({"id": f"coverage:{cur.id}", "severity": "info", "category": "data_quality",
                        "title": f"Risk coverage {cur.coverage:.0%} below minimum {min_cov:.0%} - no point score",
                        "detail": "Missing indicators are not treated as zero risk.", "as_of": str(cur.computed_at.date()),
                        "classification": "derived", "source_url": None, "evidence": {"snapshot": cur.id}})
    # 4. observed price cuts / increases
    since = today - dt.timedelta(days=rules.get("price_change_lookback_days", 120))
    rows = {r.id: r for r in session.scalars(select(ModelPrice))}
    for r in rows.values():
        old = rows.get(r.supersedes_id) if r.supersedes_id else None
        if old and old.usd_per_mtok and r.first_seen_at.date() >= since:
            pct = r.usd_per_mtok / old.usd_per_mtok - 1
            if pct <= rules.get("price_cut_pct", -0.1) or pct >= 0.10:
                out.append({"id": f"price:{r.id}", "severity": "info", "category": "pricing",
                            "title": f"{r.vendor} {r.model_label} {r.price_type}: ${old.usd_per_mtok:g} -> "
                                     f"${r.usd_per_mtok:g}/MTok ({pct:+.0%})",
                            "detail": f"Observed change between {old.last_seen_at.date()} and {r.first_seen_at.date()} "
                                      f"(tier: {r.tier}).", "as_of": str(r.first_seen_at.date()),
                            "classification": "reported", "source_url": r.source_url, "evidence": {"rows": [old.id, r.id]}})
    # 5. vendor-documented scheduled price changes
    horizon = today + dt.timedelta(days=rules.get("scheduled_change_horizon_days", 120))
    sup = {r.supersedes_id for r in rows.values() if r.supersedes_id}
    for r in rows.values():
        if r.id in sup or r.price_status != "scheduled" or not r.effective_from:
            continue
        if today <= r.effective_from <= horizon:
            cur = next((c for c in rows.values() if c.id not in sup and c.price_status == "current"
                        and (c.vendor, c.model_id, c.tier, c.price_type) == (r.vendor, r.model_id, r.tier, r.price_type)),
                       None)
            pct = f" ({r.usd_per_mtok / cur.usd_per_mtok - 1:+.0%} vs current ${cur.usd_per_mtok:g})" \
                if cur and cur.usd_per_mtok else ""
            out.append({"id": f"sched:{r.id}", "severity": "info", "category": "pricing",
                        "title": f"{r.vendor} {r.model_label} {r.price_type}: scheduled ${r.usd_per_mtok:g}/MTok "
                                 f"from {r.effective_from}{pct}",
                        "detail": f"Vendor text: \"{(r.raw_text or '')[:160]}\"", "as_of": str(r.last_seen_at.date()),
                        "classification": "reported", "source_url": r.source_url, "evidence": {"row": r.id}})
    # 6. drawdowns
    for m in ("tw_drawdown_52w", "us_drawdown_52w"):
        for e, o in sorted(_latest(session, m, None).items()):
            if o.value <= rules.get("drawdown", -0.2) and (today - o.period_end).days <= 14:
                out.append({"id": f"dd:{e}:{o.period_end}", "severity": "warning", "category": "valuation",
                            "title": f"{e}: {o.value:.1%} from 52-week high (close {o.period_end})",
                            "detail": "Derived from exchange closing prices.", "as_of": str(o.period_end),
                            "classification": "derived", "source_url": o.source_url, "evidence": {"obs": o.id}})
    # 7. failed sources (latest run per source)
    latest_runs: dict[str, IngestionRun] = {}
    for r in session.scalars(select(IngestionRun).order_by(IngestionRun.id)):
        latest_runs[r.provider] = r
    for name, r in sorted(latest_runs.items()):
        if r.status in ("failed", "partial"):
            out.append({"id": f"run:{r.id}", "severity": "info", "category": "data_quality",
                        "title": f"Source {name}: last run {r.status}", "detail": (r.message or "")[:300],
                        "as_of": str(r.started_at.date()), "classification": "derived", "source_url": None,
                        "evidence": {"run": r.id}})
    order = {"warning": 0, "info": 1}
    return sorted(out, key=lambda a: (order.get(a["severity"], 9), a["category"], a["id"]))
