"""Registry loader: YAML -> typed objects, and sync into the DB."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from ..models import Entity, Metric

HERE = Path(__file__).parent
VALID_STATUS = {"connected", "unavailable", "placeholder"}
VALID_CLASS = {"reported", "guidance", "estimated", "derived", "qualitative"}


@dataclass
class MetricDef:
    id: str
    name: str
    description: str
    unit: str
    frequency: str
    category: str
    default_classification: str
    provider: str | None
    status: str
    is_ai_specific: bool = False
    warning: str | None = None
    methodology: str | None = None
    entities: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    concept_overrides: dict[str, list[str]] = field(default_factory=dict)
    derive: dict[str, Any] | None = None
    series_id: str | None = None
    params: dict[str, Any] = field(default_factory=dict)  # provider-specific options

    def concepts_for(self, entity_id: str) -> list[str]:
        return self.concept_overrides.get(entity_id, self.concepts)


@dataclass
class EntityDef:
    id: str
    name: str
    entity_type: str
    group: str | None = None
    cik: str | None = None
    notes: str | None = None


@dataclass
class Registry:
    metrics: dict[str, MetricDef]
    entities: dict[str, EntityDef]

    def metrics_for_provider(self, provider: str) -> list[MetricDef]:
        return [m for m in self.metrics.values() if m.provider == provider and m.status == "connected"]


def load_registry(metrics_path: Path | None = None, entities_path: Path | None = None) -> Registry:
    mdata = yaml.safe_load((metrics_path or HERE / "metrics.yaml").read_text())
    edata = yaml.safe_load((entities_path or HERE / "entities.yaml").read_text())
    entities = {e["id"]: EntityDef(**e) for e in edata["entities"]}
    metrics: dict[str, MetricDef] = {}
    for m in mdata["metrics"]:
        md = MetricDef(**m)
        if md.status not in VALID_STATUS:
            raise ValueError(f"{md.id}: bad status {md.status}")
        if md.default_classification not in VALID_CLASS:
            raise ValueError(f"{md.id}: bad classification {md.default_classification}")
        for e in md.entities:
            if e not in entities:
                raise ValueError(f"{md.id}: unknown entity {e}")
        if md.id in metrics:
            raise ValueError(f"duplicate metric {md.id}")
        metrics[md.id] = md
    for md in metrics.values():  # derived inputs must exist
        for inp in (md.derive or {}).get("inputs", []):
            if inp not in metrics:
                raise ValueError(f"{md.id}: derive input {inp} not in registry")
    return Registry(metrics=metrics, entities=entities)


@lru_cache
def get_registry() -> Registry:
    return load_registry()


def sync_registry(session: Session, reg: Registry | None = None) -> None:
    """Upsert registry definitions into metrics/entities tables (definitions, not data)."""
    reg = reg or get_registry()
    for e in reg.entities.values():
        session.merge(Entity(id=e.id, name=e.name, entity_type=e.entity_type, group=e.group,
                             cik=e.cik, notes=e.notes))
    for m in reg.metrics.values():
        session.merge(Metric(
            id=m.id, name=m.name, description=m.description.strip(), unit=m.unit, frequency=m.frequency,
            category=m.category, default_classification=m.default_classification, provider=m.provider,
            status=m.status, is_ai_specific=m.is_ai_specific, warning=m.warning,
            methodology=(m.methodology or "").strip() or None,
            config={"entities": m.entities, "concepts": m.concepts, "concept_overrides": m.concept_overrides,
                    "derive": m.derive, "series_id": m.series_id, "params": m.params},
        ))
    session.commit()
