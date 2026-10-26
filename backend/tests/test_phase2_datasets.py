"""Phase 2 steps 2-4: pricing / benchmark / GPU parsers on real snapshots + append-only store."""
import datetime as dt
import json
from pathlib import Path

from sqlalchemy import select

from app.datasets import benchmarks as B
from app.datasets import gpu as G
from app.datasets import pricing as P
from app.datasets.runner import store_rows
from app.models import IngestionRun, ModelPrice, utcnow

FX = Path(__file__).parent / "fixtures"


def _t(n):
    return (FX / n).read_text(encoding="utf-8")


def test_openai_pricing():
    rows = P.parse_openai(_t("openai_pricing.md"))
    assert len(rows) == 97
    assert all(r["vendor"] == "openai" and r["price_status"] == "current" for r in rows)
    assert all(r["usd_per_mtok"] >= 0 for r in rows)


def test_anthropic_pricing_and_documented_history():
    rows = P.parse_anthropic(_t("anthropic_pricing.md"))
    assert len(rows) == 65
    hist = [r for r in rows if r["price_status"] == "documented_history"]
    assert {(r["price_type"], r["usd_per_mtok"]) for r in hist} == {("input", 2.0), ("output", 10.0)}
    assert all(r["effective_to"] == dt.date(2026, 8, 31) and "Sonnet 5" in r["raw_text"] for r in hist)


def test_gemini_scheduled_price_kept_separate():
    rows = P.parse_gemini(_t("gemini_pricing.md"))
    assert len(rows) == 60
    argon = [r for r in rows if r["model_id"] == "gemini-4-argon" and r["price_type"] == "input"]
    by = {r["price_status"]: r for r in argon}
    assert by["current"]["usd_per_mtok"] == 2.0 and by["current"]["effective_to"] == dt.date(2026, 11, 30)
    assert by["scheduled"]["usd_per_mtok"] == 4.0 and by["scheduled"]["effective_from"] == dt.date(2026, 12, 1)


def test_openrouter_open_weight_only_paid():
    rows = P.parse_openrouter(json.loads(_t("openrouter_models_trim.json")))
    ids = {r["model_id"] for r in rows}
    assert not any(i.endswith(":free") for i in ids)
    assert "moonshotai/kimi-k3.1-pro" not in ids  # no hugging_face_id -> not treated as open-weight
    r = next(r for r in rows if r["model_id"] == "minimax/minimax-m3.1-flash" and r["price_type"] == "input")
    assert abs(r["usd_per_mtok"] - 0.15) < 1e-9 and r["open_weight"] is True


def test_swebench_splits_never_mixed():
    rows = B.parse_swebench(json.loads(_t("swebench_leaderboards_trim.json")))
    assert {r["split"] for r in rows} == {"multilingual", "test", "verified", "lite", "multimodal"}
    top = max((r for r in rows if r["split"] == "verified"), key=lambda r: r["value"])
    assert top["value"] == 79.2 and top["model"] == "Claude 4.5 Opus" and top["harness"]
    assert all(r["metric"] == "resolved_pct" and r["entry_key"] for r in rows)


def test_metr_horizon():
    rows = B.parse_metr(_t("metr_benchmark_results_1_1.yaml"))
    assert len(rows) == 52
    r = next(r for r in rows if r["model"] == "claude_mythos_preview_early_inspect" and r["metric"] == "p50_horizon_min")
    assert round(r["value"], 1) == 1044.8 and r["ci_low"] < r["value"] < r["ci_high"]
    assert r["result_date"] == dt.date(2026, 4, 7) and r["benchmark_version"] == "METR-Horizon-v1.1"
    assert r["extra"]["reliability_note"]  # > 16 h flagged


def test_terminal_bench_embedded_payload():
    rows = B.parse_terminal_bench(_t("tbench_leaderboard.html"))
    assert len(rows) == 35
    top = max(rows, key=lambda r: r["value"])
    assert top["value"] == 64.85 and top["harness"] == "Claude Code" and top["model"] == "Opus 5.5"
    assert "4-0-0" in top["benchmark_version"] and top["result_date"] == dt.date(2026, 9, 22)
    assert abs((top["ci_high"] - top["ci_low"]) / 2 - 3.11) < 0.01


def test_terminal_bench_layout_change_fails_loudly():
    import pytest
    with pytest.raises(ValueError):
        B.parse_terminal_bench("<html>nothing here</html>")


def test_azure_gpu_linux_only_and_per_gpu():
    rows = G.parse_azure(json.loads(_t("azure_retail_gpu.json"))["Items"])
    assert len(rows) == 8
    h = next(r for r in rows if r["sku"] == "Standard_ND96isr_H100_v5" and r["price_kind"] == "list_on_demand")
    assert h["usd_per_hour"] == 98.32 and h["usd_per_gpu_hour"] == 12.29 and h["gpu_count"] == 8


def test_store_rows_append_only(db_session):
    s = db_session
    run = IngestionRun(provider="t", trigger="test", status="running", started_at=utcnow())
    s.add(run); s.flush()
    base = dict(vendor="v", model_id="m", model_label="m", tier="standard", price_type="input",
                price_status="current", effective_from=None, effective_to=None, usd_per_mtok=5.0,
                source_url="u", raw_text="$5", note=None, open_weight=False)
    assert store_rows(s, "model_prices", run, [base]) == {"inserted": 1, "revised": 0, "unchanged": 0}
    assert store_rows(s, "model_prices", run, [base]) == {"inserted": 0, "revised": 0, "unchanged": 1}
    cut = dict(base, usd_per_mtok=2.5, raw_text="$2.50")
    assert store_rows(s, "model_prices", run, [cut]) == {"inserted": 0, "revised": 1, "unchanged": 0}
    rows = s.scalars(select(ModelPrice).order_by(ModelPrice.id)).all()
    assert [r.usd_per_mtok for r in rows] == [5.0, 2.5] and rows[1].supersedes_id == rows[0].id
