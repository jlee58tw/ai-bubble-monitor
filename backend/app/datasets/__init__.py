"""Phase 2 non-metric datasets (model API prices, benchmarks, GPU prices).

Each source module exposes `NAME`, `SOURCE_URL`, a pure `parse(...)` function (unit-tested on recorded real
payloads) and `fetch(client) -> list[dict]`. `runner.run_datasets` stores rows append-only and records an
IngestionRun per source so failures are visible in the ingestion-status page.
"""
