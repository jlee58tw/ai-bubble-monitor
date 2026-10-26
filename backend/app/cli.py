"""CLI: python -m app.cli refresh [--provider sec_edgar] [--entity MSFT]"""
from __future__ import annotations

import argparse

from .config import get_settings
from .db import session_factory
from .logging_setup import configure_logging
from .providers import PROVIDERS
from .services.ingest import run_ingestion


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("refresh")
    r.add_argument("--provider", action="append", choices=sorted(PROVIDERS))
    r.add_argument("--entity", action="append")
    d = sub.add_parser("datasets", help="model prices / benchmarks / GPU list prices")
    d.add_argument("--source", action="append")
    sub.add_parser("risk", help="compute and store a risk snapshot")
    a = p.parse_args()
    s = get_settings(); configure_logging(s.log_level, s.log_json)
    sess = session_factory()()
    if a.cmd == "datasets":
        from .datasets.runner import run_datasets
        for run in run_datasets(sess, a.source, trigger="cli"):
            print(f"run {run.id} {run.provider}: {run.status} fetched={run.records_fetched} "
                  f"inserted={run.records_inserted} revised={run.records_revised} "
                  f"unchanged={run.records_unchanged} {run.message or ''}")
        return
    if a.cmd == "risk":
        from .services.risk import snapshot_risk
        snap = snapshot_risk(sess)
        print(f"risk snapshot {snap.id}: coverage={snap.coverage:.0%} score={snap.score} "
              f"range=[{snap.score_low:.1f}, {snap.score_high:.1f}]")
        return
    runs = run_ingestion(sess, a.provider or list(PROVIDERS), trigger="cli", entity_ids=a.entity)
    for run in runs:
        print(f"run {run.id} {run.provider}: {run.status} inserted={run.records_inserted} "
              f"revised={run.records_revised} unchanged={run.records_unchanged} errors={run.error_count}")


if __name__ == "__main__":
    main()
