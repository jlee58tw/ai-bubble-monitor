"""Database schema.

Observations are APPEND-ONLY: a revised value is inserted as a new row whose
``supersedes_id`` points at the row it replaces. Rows are never updated or
deleted by the ingestion pipeline. The "current" value for a series/period is
the row that no other row supersedes.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # e.g. MSFT
    name: Mapped[str] = mapped_column(String(200))
    entity_type: Mapped[str] = mapped_column(String(32))  # company / aggregate / macro
    group: Mapped[str | None] = mapped_column(String(64))  # hyperscaler / ai_supplier / ...
    cik: Mapped[str | None] = mapped_column(String(10))
    notes: Mapped[str | None] = mapped_column(Text)


class Metric(Base):
    __tablename__ = "metrics"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    unit: Mapped[str] = mapped_column(String(32))
    frequency: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(64))
    default_classification: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))  # connected / unavailable / placeholder
    is_ai_specific: Mapped[bool] = mapped_column(Boolean, default=False)
    warning: Mapped[str | None] = mapped_column(Text)
    methodology: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict | None] = mapped_column(JSON)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    trigger: Mapped[str] = mapped_column(String(16))  # manual / scheduled / cli / test
    status: Mapped[str] = mapped_column(String(16))  # running / success / partial / failed
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    records_fetched: Mapped[int] = mapped_column(Integer, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0)
    records_revised: Mapped[int] = mapped_column(Integer, default=0)
    records_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)


class IngestionError(Base):
    __tablename__ = "ingestion_errors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    level: Mapped[str] = mapped_column(String(16))  # warning / error
    entity_id: Mapped[str | None] = mapped_column(String(32))
    metric_id: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict | None] = mapped_column(JSON)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("metric_id", "entity_id", "period_start", "period_end", "version",
                         name="uq_obs_version"),
        Index("ix_obs_series", "metric_id", "entity_id", "period_end"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_id: Mapped[str] = mapped_column(ForeignKey("metrics.id"))
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"))
    value: Mapped[float] = mapped_column(Float)  # never NULL: missing data is simply absent
    unit: Mapped[str] = mapped_column(String(32))
    fiscal_period: Mapped[str | None] = mapped_column(String(32))  # e.g. "FY2026 Q1"
    period_start: Mapped[dt.date | None] = mapped_column(Date)
    period_end: Mapped[dt.date] = mapped_column(Date)  # = observation_date
    publication_date: Mapped[dt.date] = mapped_column(Date, index=True)  # SEC filed date
    ingestion_ts: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32))  # sec_edgar_xbrl / fred / derived
    classification: Mapped[str] = mapped_column(String(16))  # reported/derived/guidance/estimated/qualitative
    confidence: Mapped[str] = mapped_column(String(8))  # high / medium / low
    methodology: Mapped[str | None] = mapped_column(Text)
    source_ref: Mapped[str | None] = mapped_column(String(200))  # XBRL concept / accession / series id
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("observations.id"), index=True)
    ingestion_run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))

    @property
    def observation_date(self) -> dt.date:
        return self.period_end
