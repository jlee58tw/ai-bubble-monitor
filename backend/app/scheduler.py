from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings
from .db import session_factory
from .logging_setup import get_logger
from .providers import PROVIDERS
from .services.ingest import RefreshInProgress, run_ingestion

log = get_logger(__name__)


def scheduled_refresh() -> None:
    s = session_factory()()
    try:
        run_ingestion(s, list(PROVIDERS), trigger="scheduled")
    except RefreshInProgress:
        log.info("scheduled_refresh_skipped", reason="already running")
    finally:
        s.close()


def scheduled_datasets() -> None:
    """Weekly: model API prices, benchmarks, GPU list prices (+ a risk snapshot)."""
    from .datasets.runner import run_datasets
    s = session_factory()()
    try:
        run_datasets(s, trigger="scheduled")
        try:
            from .services.risk import snapshot_risk
            snapshot_risk(s)
        except ImportError:
            pass
    finally:
        s.close()


def start_scheduler() -> BackgroundScheduler | None:
    st = get_settings()
    if not st.scheduler_enabled:
        return None
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(scheduled_refresh, CronTrigger.from_crontab(st.scheduler_cron, timezone="UTC"),
                  id="refresh_all", max_instances=1, coalesce=True)
    sched.add_job(scheduled_datasets, CronTrigger.from_crontab(st.datasets_cron, timezone="UTC"),
                  id="datasets_weekly", max_instances=1, coalesce=True)
    sched.start()
    log.info("scheduler_started", cron=st.scheduler_cron, datasets_cron=st.datasets_cron)
    return sched
