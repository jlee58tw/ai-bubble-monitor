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
    a = p.parse_args()
    s = get_settings(); configure_logging(s.log_level, s.log_json)
    sess = session_factory()()
    runs = run_ingestion(sess, a.provider or list(PROVIDERS), trigger="cli", entity_ids=a.entity)
    for run in runs:
        print(f"run {run.id} {run.provider}: {run.status} inserted={run.records_inserted} "
              f"revised={run.records_revised} unchanged={run.records_unchanged} errors={run.error_count}")


if __name__ == "__main__":
    main()
