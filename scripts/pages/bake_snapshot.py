"""Bake a read-only JSON/CSV snapshot of the API for the static GitHub Pages build.

Runs the FastAPI app in-process (TestClient, no lifespan => no scheduler, no network) against the
local SQLite DB and writes frontend/public/snapshot/. The output is scanned for secrets and the
script fails (printing counts only, never values) if anything token-like is found.

Usage: (cd backend && ../.venv/bin/python ../scripts/pages/bake_snapshot.py)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import parse_qsl, urlencode
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend" / "public" / "snapshot"
TPE = ZoneInfo("Asia/Taipei")
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
os.environ["SCHEDULER_ENABLED"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)  # not used as a context manager: lifespan (scheduler) never starts


def key_for(path: str) -> str:
    """Must match keyFor() in frontend/lib/static.ts."""
    p, _, qs = path.partition("?")
    q = "&".join(f"{k}={v}" for k, v in sorted(parse_qsl(qs, keep_blank_values=True), key=lambda kv: kv[0]))
    base = p.lstrip("/").replace("/", "_")
    return re.sub(r"[^A-Za-z0-9.,=-]", "_", f"{base}__{q}" if q else base) + ".json"


def get(path: str):
    r = client.get(path)
    if r.status_code != 200:
        raise SystemExit(f"bake failed: {path} -> HTTP {r.status_code}")
    return r


def dump(rel: Path, obj) -> None:
    f = OUT / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def bake_api(path: str):
    data = get(path).json()
    dump(Path("api") / key_for(path), data)
    return data


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    simple = ["/api/overview", "/api/risk", "/api/risk/history", "/api/alerts", "/api/benchmarks", "/api/gpu-prices",
              "/api/guidance", "/api/methodology", "/api/metrics", "/api/entities", "/api/watchlist", "/api/health",
              "/api/ingestion/status", "/api/ingestion/runs?limit=20", "/api/ingestion/runs?limit=2",
              "/api/ingestion/errors?limit=50", "/api/roi"]
    res = {p: bake_api(p) for p in simple}
    for v in ["openai", "anthropic", "google", "openrouter"]:
        bake_api(f"/api/model-prices?vendor={v}")
    bt_default = {"horizon": "20", "drawdown": "0.1", "composite_threshold": "60", "indicator_threshold": "70"}
    bake_api("/api/backtest?" + urlencode(bt_default))
    ev = bake_api("/api/events?limit=400")
    ents = [""] + [c["entity_id"] for c in ev.get("coverage", [])]
    for e in ents:
        for t in ["", "periodic_report", "earnings_release_8k"]:
            q = {**({"entity_id": e} if e else {}), **({"event_type": t} if t else {}), "limit": "400"}
            bake_api("/api/events?" + urlencode(q))

    # Observations: current vintages, split metric/entity/year so pages download only what they filter for.
    index: dict[str, dict[str, list[int]]] = {}
    n_obs = 0
    for m in res["/api/metrics"]:
        rows = get(f"/api/observations?metric_id={m['id']}&limit=50000").json()
        if len(rows) >= 50000:
            raise SystemExit(f"bake failed: {m['id']} hit the 50000-row page limit")
        groups: dict[tuple[str, int], list] = defaultdict(list)
        for o in rows:
            groups[(o["entity_id"], int((o["period_end"] or "0000")[:4]))].append(o)
        for (e, y), g in groups.items():
            dump(Path("obs") / m["id"] / e / f"{y}.json", g)
            index.setdefault(m["id"], {}).setdefault(e, []).append(y)
        n_obs += len(rows)
    for m in index.values():
        for e in m:
            m[e].sort()
    dump(Path("obs") / "index.json", index)

    # CSV downloads (baked files; same columns as the live /api/*.csv endpoints).
    capex_metrics = "capex_total,revenue,operating_cash_flow,fcf,capex_yoy,revenue_yoy,ocf_yoy,fcf_yoy,capex_to_ocf,capex_to_revenue"
    (OUT / "csv").mkdir()
    for c in ["MSFT", "GOOGL", "AMZN", "META", "ORCL"]:
        (OUT / "csv" / f"capex_{c}.csv").write_bytes(get(f"/api/observations.csv?metric_id={capex_metrics}&entity_id={c}").content)
    (OUT / "csv" / "backtest_default.csv").write_bytes(get("/api/backtest.csv?" + urlencode(bt_default)).content)

    risk = res["/api/risk"]
    runs = res["/api/ingestion/runs?limit=20"]
    last = max((r.get("finished_at") or r.get("started_at") for r in runs if r.get("started_at")), default=None)

    def tpe(s: str | None) -> str | None:
        if not s:
            return None
        d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        d = d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)  # API stores UTC
        return d.astimezone(TPE).strftime("%Y-%m-%d %H:%M")

    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    meta = {"snapshot_at_taipei": dt.datetime.now(TPE).strftime("%Y-%m-%d %H:%M"), "latest_ingestion_taipei": tpe(last),
            "risk_score": risk.get("score"), "risk_coverage": risk.get("coverage"), "risk_low": risk.get("score_low"),
            "risk_high": risk.get("score_high"), "computed_for": risk.get("computed_for"),
            "git_commit": commit or "unknown", "observations": n_obs,
            "note": "Static snapshot, not live. Generated by scripts/publish_pages.sh from the local SQLite DB."}
    dump(Path("meta.json"), meta)
    scan()
    print(json.dumps({k: meta[k] for k in ("snapshot_at_taipei", "latest_ingestion_taipei", "risk_score", "risk_coverage", "observations")}))


def scan() -> None:
    """Fail if any baked file contains a secret. Prints counts only, never matched text."""
    secrets = []
    env = ROOT / "backend" / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            k, _, v = line.partition("=")
            v = v.strip().strip("'\"")
            if re.search(r"(KEY|TOKEN|SECRET|PASSWORD)", k) and len(v) >= 8:
                secrets.append(v)
    pat = re.compile(r"(token=[A-Za-z0-9]{16,}|api_key=[A-Za-z0-9]{16,}|Authorization:\s*Token|ghp_|github_pat_)", re.I)
    hits = 0
    files = 0
    for f in OUT.rglob("*"):
        if f.is_file():
            files += 1
            t = f.read_text(errors="ignore")
            if any(s in t for s in secrets) or pat.search(t):
                hits += 1
    print(f"secret_scan files={files} env_secrets_checked={len(secrets)} files_with_hits={hits}")
    if hits:
        raise SystemExit("bake aborted: secret-like content found in snapshot (see counts above)")


if __name__ == "__main__":
    main()
