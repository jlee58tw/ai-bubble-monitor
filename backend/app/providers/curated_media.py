"""Curated MEDIA-REPORTED figures for private / pre-IPO AI labs (app/registry/curated/ai_lab_media.yaml).

No network access: the file is hand-curated from articles whose verbatim quote is stored alongside each value.
Records are ALWAYS classification "estimated", confidence "low", source_type "media_report" - they are never
"reported" financials and are kept in separate metrics (suffix _media) from company-disclosed S-1 data.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import yaml

from ..registry.registry import Registry
from .base import ObservationRecord, Provider, ProviderError, ProviderResult, ProviderStatus

CURATED = Path(__file__).resolve().parent.parent / "registry" / "curated" / "ai_lab_media.yaml"
REQUIRED = ("metric", "entity", "period_start", "period_end", "value", "published", "outlet", "url", "quote")


def _d(x) -> dt.date:
    return x if isinstance(x, dt.date) else dt.date.fromisoformat(str(x))


def validate_item(it: dict) -> str | None:
    missing = [k for k in REQUIRED if it.get(k) in (None, "")]
    if missing:
        return f"missing {missing}"
    if not str(it["url"]).startswith("https://"):
        return "url must be https"
    if _d(it["published"]) < _d(it["period_end"]):
        return "published before period end (look-ahead)"
    return None


class CuratedMediaProvider(Provider):
    name = "curated_media"
    description = "Hand-curated media-reported AI-lab figures (estimated, low confidence, verbatim quote + URL)"

    def __init__(self, path: Path | None = None):
        self.path = path or CURATED

    def status(self) -> ProviderStatus:
        return ProviderStatus(self.name, self.path.exists(), None if self.path.exists() else f"{self.path} missing")

    def fetch(self, registry: Registry, entity_ids: list[str] | None = None) -> ProviderResult:
        res = ProviderResult()
        metrics = {m.id: m for m in registry.metrics_for_provider(self.name)}
        items = (yaml.safe_load(self.path.read_text()) or {}).get("items", [])
        for n, it in enumerate(items):
            err = validate_item(it)
            m = metrics.get(it.get("metric"))
            if err is None and (m is None or it["entity"] not in m.entities):
                err = f"metric/entity {it.get('metric')}/{it.get('entity')} not registered for {self.name}"
            if err:
                res.errors.append(ProviderError(f"item {n}: {err}", metric_id=it.get("metric"),
                                                entity_id=it.get("entity")))
                continue
            if entity_ids and it["entity"] not in entity_ids:
                continue
            res.fetched += 1
            res.records.append(ObservationRecord(
                metric_id=m.id, entity_id=it["entity"], value=float(it["value"]), unit=m.unit,
                period_start=_d(it["period_start"]), period_end=_d(it["period_end"]), fiscal_period=None,
                publication_date=_d(it["published"]), source_type="media_report", classification="estimated",
                confidence="low", source_url=it["url"], source_ref=f"media:{it['outlet']}",
                methodology=f"MEDIA-REPORTED ({it['outlet']}, {it['published']}), not company financials. "
                            f"Verbatim: \"{it['quote']}\""))
        return res
