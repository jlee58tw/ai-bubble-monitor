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


# ---------------------------------------------------------------- Phase 2 datasets
# These are NOT time series of one metric, so they live in their own tables. Same principles:
# every row carries source URL, observation time and (where published) the documented date; rows are
# append-only - an unchanged value only bumps last_seen_at, a changed value inserts a new row.

class ModelPrice(Base):
    """Published API list price (USD per 1M tokens) for one model / tier / token type."""
    __tablename__ = "model_prices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor: Mapped[str] = mapped_column(String(32), index=True)      # openai / anthropic / google / openrouter
    model_id: Mapped[str] = mapped_column(String(160), index=True)
    model_label: Mapped[str] = mapped_column(String(300))
    tier: Mapped[str] = mapped_column(String(64))                    # standard / <=200k / host name ...
    price_type: Mapped[str] = mapped_column(String(32))              # input / output / cached_input
    usd_per_mtok: Mapped[float] = mapped_column(Float)
    price_status: Mapped[str] = mapped_column(String(24))            # current / scheduled / documented_history
    effective_from: Mapped[dt.date | None] = mapped_column(Date)     # only when the source states it
    effective_to: Mapped[dt.date | None] = mapped_column(Date)
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    source_url: Mapped[str] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    open_weight: Mapped[bool] = mapped_column(Boolean, default=False)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("model_prices.id"))

    __table_args__ = (Index("ix_model_price_key", "vendor", "model_id", "tier", "price_type", "price_status"),)


class BenchmarkResult(Base):
    """One leaderboard entry. (benchmark, benchmark_version, split, metric) defines comparability."""
    __tablename__ = "benchmark_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    benchmark: Mapped[str] = mapped_column(String(64), index=True)   # swe-bench / terminal-bench / metr-horizon
    benchmark_version: Mapped[str] = mapped_column(String(64))
    split: Mapped[str] = mapped_column(String(64))                   # e.g. verified / lite / -
    metric: Mapped[str] = mapped_column(String(64))                  # resolved_pct / accuracy_pct / p50_horizon_min
    model: Mapped[str] = mapped_column(String(300))
    harness: Mapped[str | None] = mapped_column(String(300))         # agent / scaffold
    entry_key: Mapped[str] = mapped_column(String(300))
    value: Mapped[float] = mapped_column(Float)
    ci_low: Mapped[float | None] = mapped_column(Float)
    ci_high: Mapped[float | None] = mapped_column(Float)
    result_date: Mapped[dt.date | None] = mapped_column(Date)        # as published by the leaderboard
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    source_url: Mapped[str] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSON)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("benchmark_results.id"))

    __table_args__ = (Index("ix_bench_key", "benchmark", "benchmark_version", "split", "metric", "entry_key"),)


class GpuPrice(Base):
    """GPU instance list price. price_kind distinguishes list on-demand vs marketplace rental."""
    __tablename__ = "gpu_prices"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), index=True)      # azure_retail
    price_kind: Mapped[str] = mapped_column(String(32))              # list_on_demand / list_spot
    sku: Mapped[str] = mapped_column(String(120))
    gpu_model: Mapped[str] = mapped_column(String(64))
    gpu_count: Mapped[int] = mapped_column(Integer)
    region: Mapped[str] = mapped_column(String(64))
    usd_per_hour: Mapped[float] = mapped_column(Float)               # whole instance
    usd_per_gpu_hour: Mapped[float] = mapped_column(Float)
    effective_from: Mapped[dt.date | None] = mapped_column(Date)     # source 'effectiveStartDate'
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    source_url: Mapped[str] = mapped_column(Text)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("gpu_prices.id"))

    __table_args__ = (Index("ix_gpu_key", "source", "price_kind", "sku", "region"),)


class RiskSnapshot(Base):
    """Result of one risk-engine evaluation (kept so 'risk rising' can be detected from history)."""
    __tablename__ = "risk_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    config_hash: Mapped[str] = mapped_column(String(64))
    coverage: Mapped[float] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float)              # null when coverage < minimum
    score_low: Mapped[float] = mapped_column(Float)
    score_high: Mapped[float] = mapped_column(Float)
    detail: Mapped[dict] = mapped_column(JSON)


# ---------------------------------------------------------------- Phase 3
class FilingEvent(Base):
    """One SEC filing event (10-Q / 10-K / 20-F / 8-K Item 2.02) from EDGAR submissions metadata.
    report_date = period the filing covers (observation date); filing_date = publication date.
    Append-only like the Phase 2 datasets: unchanged -> last_seen_at bump, changed -> new superseding row."""
    __tablename__ = "filing_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    cik: Mapped[str] = mapped_column(String(10))
    accession_number: Mapped[str] = mapped_column(String(32), index=True)
    form: Mapped[str] = mapped_column(String(16))
    event_type: Mapped[str] = mapped_column(String(32))          # periodic_report / earnings_release_8k
    filing_date: Mapped[dt.date] = mapped_column(Date, index=True)
    acceptance_datetime: Mapped[str | None] = mapped_column(String(32))  # as published by EDGAR (UTC 'Z')
    report_date: Mapped[dt.date | None] = mapped_column(Date)
    items: Mapped[str | None] = mapped_column(String(200))       # 8-K item numbers, e.g. "2.02,9.01"
    primary_document: Mapped[str | None] = mapped_column(String(300))
    primary_doc_description: Mapped[str | None] = mapped_column(String(300))
    source_url: Mapped[str] = mapped_column(Text)                # filing index page
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("ingestion_runs.id"))
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("filing_events.id"))


class GuidanceItem(Base):
    """Company guidance. Rows exist ONLY with a source URL + quote; nothing is inferred or estimated.
    (No guidance source is connected yet, so this table is empty and the UI shows a placeholder.)"""
    __tablename__ = "guidance_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id"), index=True)
    metric_id: Mapped[str | None] = mapped_column(ForeignKey("metrics.id"))
    target_period: Mapped[str] = mapped_column(String(64))
    value_low: Mapped[float | None] = mapped_column(Float)
    value_high: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str | None] = mapped_column(String(32))
    publication_date: Mapped[dt.date] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    filing_event_id: Mapped[int | None] = mapped_column(ForeignKey("filing_events.id"))
    first_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class WatchlistItem(Base):
    """User-configured watchlist: an entity, a metric, or an (entity, metric) series."""
    __tablename__ = "watchlist_items"
    __table_args__ = (UniqueConstraint("entity_id", "metric_id", name="uq_watch"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("entities.id"))
    metric_id: Mapped[str | None] = mapped_column(ForeignKey("metrics.id"))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
