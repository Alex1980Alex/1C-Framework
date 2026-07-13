"""Регрессия P1.1 (roadmap 260713 §6): вердикты здоровья инструментов.

Критично: retry-цикл = повтор ПАДАЮЩЕГО вызова (не идемпотентный опрос) —
100%-success тул с повторами args_hash = healthy, НЕ ineffective (защита от FP,
найденного на реальном логе: debug_ping/debug_targets/get_metadata_structure).
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "analyze_tool_health.py"
_spec = importlib.util.spec_from_file_location("_analyze_tool_health", _PATH)
ath = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ath)


def _stats(**kw):
    """Собрать stats-словарь с дефолтами (успешный, без повторов)."""
    calls = kw.get("calls", 10)
    errors = kw.get("errors", 0)
    success = calls - errors
    base = {
        "calls": calls,
        "errors": errors,
        "success": success,
        "success_rate": round(success / calls, 4) if calls else 1.0,
        "error_rate": round(errors / calls, 4) if calls else 0.0,
        "p50_ms": kw.get("p50_ms", 100.0),
        "p95_ms": kw.get("p95_ms", 200.0),
        "paired": calls,
        "repeats": kw.get("repeats", 0),
        "abandonment": kw.get("abandonment", False),
    }
    return base


# ── verdict: broken ──────────────────────────────────────────────────────────


def test_broken_zero_success():
    v, _ = ath.assign_verdict(_stats(calls=3, errors=3), None)
    assert v == "broken"


def test_broken_low_success_rate():
    v, _ = ath.assign_verdict(_stats(calls=10, errors=6), None)  # 40% success
    assert v == "broken"


def test_not_broken_below_min_calls():
    """success-rate плохой, но calls < 5 и success>0 → не broken (мало данных)."""
    v, _ = ath.assign_verdict(_stats(calls=2, errors=1), None)  # 1 success, 1 fail
    assert v != "broken"


# ── verdict: degraded ────────────────────────────────────────────────────────


def test_degraded_high_error_rate():
    v, _ = ath.assign_verdict(_stats(calls=20, errors=3), None)  # 15% error
    assert v == "degraded"


def test_single_transient_error_not_degraded():
    """calls=1, errors=1 → НЕ degraded (порог DEGRADED_MIN_CALLS): транзиент не светит 14д."""
    v, _ = ath.assign_verdict(_stats(calls=1, errors=1), None)
    assert v != "degraded"  # insufficient data → healthy (abandonment требует calls≥3)


def test_degraded_p95_regression():
    v, _ = ath.assign_verdict(
        _stats(calls=10, errors=0, p95_ms=500.0), {"p95_ms": 200.0, "error_rate": 0.0}
    )
    assert v == "degraded"  # 500 > 2×200


def test_degraded_error_ratchet():
    v, _ = ath.assign_verdict(
        _stats(calls=20, errors=1, p95_ms=200.0), {"p95_ms": 200.0, "error_rate": 0.0}
    )  # 5% error, baseline 0 → +5пп ровно не превышает; делаем 2 ошибки
    v2, _ = ath.assign_verdict(
        _stats(calls=20, errors=2, p95_ms=200.0), {"p95_ms": 400.0, "error_rate": 0.0}
    )  # 10% error, baseline 0 → +10пп > 5пп
    assert v2 == "degraded"


# ── verdict: ineffective (abandonment при низком общем error-rate) ───────────


def test_ineffective_abandonment_low_error_rate():
    """Свежая попытка провалилась (abandonment), но общий error-rate низкий (не degraded)."""
    v, _ = ath.assign_verdict(_stats(calls=20, errors=1, abandonment=True), None)  # 5% error
    assert v == "ineffective"


def test_abandonment_shadowed_by_degraded_when_error_high():
    """abandonment, но error-rate > 10% → degraded (сильнее, приоритетнее ineffective)."""
    v, _ = ath.assign_verdict(_stats(calls=5, errors=1, abandonment=True), None)  # 20% error
    assert v == "degraded"


# ── КРИТИЧНО: idempotent-polling НЕ ineffective (repeats не движут вердикт) ───


def test_polling_100pct_success_with_repeats_is_healthy():
    """100% success + много повторов args_hash (ping/targets/get_metadata) → healthy.
    Регрессия FP найденного на реальном логе (debug_targets 9/10 повторов, но 100% success)."""
    v, _ = ath.assign_verdict(_stats(calls=10, errors=0, repeats=9), None)
    assert v == "healthy"


def test_repeats_do_not_drive_verdict():
    """Даже repeats=calls при 100% success → healthy (repeats — информативная колонка)."""
    v, _ = ath.assign_verdict(_stats(calls=15, errors=0, repeats=15), None)
    assert v == "healthy"


def test_healthy_baseline_case():
    v, _ = ath.assign_verdict(_stats(calls=8, errors=0), {"p95_ms": 200.0, "error_rate": 0.0})
    assert v == "healthy"


# ── aggregate_tools + pairing + percentiles ──────────────────────────────────


def _row(tool, event, ts, **kw):
    return {"tool": tool, "event": event, "ts": ts, "category": "tool_call", **kw}


def test_aggregate_pairs_pre_post_real_latency():
    rows = [
        _row("Read", "PreToolUse", "2026-07-14T10:00:00.000", tool_call_id="a"),
        _row("Read", "PostToolUse", "2026-07-14T10:00:00.150", tool_call_id="a"),
    ]
    agg = ath.aggregate_tools(rows)
    assert agg["Read"]["calls"] == 1
    assert agg["Read"]["p95_ms"] == 150.0  # реальная Pre→Post
    assert agg["Read"]["success_rate"] == 1.0


def test_aggregate_error_counted():
    rows = [
        _row("Bash", "PostToolUse", "2026-07-14T10:00:00.000", outcome="error"),
        _row("Bash", "PostToolUse", "2026-07-14T10:00:01.000", outcome="allow"),
    ]
    agg = ath.aggregate_tools(rows)
    assert agg["Bash"]["calls"] == 2
    assert agg["Bash"]["errors"] == 1
    assert agg["Bash"]["success_rate"] == 0.5


def test_pct_interpolation():
    assert ath._pct([100], 0.95) == 100.0
    assert ath._pct([], 0.5) == 0.0
    assert ath._pct([0, 100], 0.5) == 50.0


# ── unused detection + ratchet baseline ──────────────────────────────────────


def test_unused_detected_from_baseline():
    """Тул в baseline, но 0 вызовов в окне → unused."""
    now = datetime(2026, 7, 14, 12, 0, 0)
    rows = [_row("Read", "PostToolUse", now.isoformat())]
    baseline = {"OldTool": {"p95_ms": 100, "error_rate": 0.0}}
    health = ath.compute_health(rows, baseline, now)
    assert health["tools"]["OldTool"]["verdict"] == "unused"
    assert health["tools"]["Read"]["verdict"] == "healthy"


def test_baseline_ratchet_keeps_best():
    """update_baseline берёт min (лучший) p95/error — ухудшение не пишется."""
    baseline = {"Read": {"p95_ms": 100.0, "error_rate": 0.0}}
    stats = {"Read": _stats(calls=10, errors=1, p95_ms=500.0)}  # хуже
    out = ath.update_baseline(baseline, stats)
    assert out["Read"]["p95_ms"] == 100.0  # baseline не ухудшился
    assert out["Read"]["error_rate"] == 0.0


def test_baseline_ratchet_low_calls_skipped():
    """Тул с calls < MIN_CALLS_FOR_BROKEN не двигает baseline (мало данных)."""
    stats = {"X": _stats(calls=2, errors=0, p95_ms=10.0)}
    out = ath.update_baseline({}, stats)
    assert "X" not in out


# ── window filtering ─────────────────────────────────────────────────────────


def test_window_excludes_old_and_noncanonical(tmp_path):
    import json

    now = datetime(2026, 7, 14, 12, 0, 0)
    log = tmp_path / "log.jsonl"
    old = (now - timedelta(days=30)).isoformat()
    recent = (now - timedelta(days=1)).isoformat()
    rows = [
        {"tool": "Read", "event": "PostToolUse", "ts": recent, "category": "tool_call"},
        {"tool": "Read", "event": "PostToolUse", "ts": old, "category": "tool_call"},  # вне окна
        {"tool": "Bash", "event": "PostToolUse", "ts": recent, "category": "hook"},  # не канон
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    got = list(ath.iter_window_rows(now, 14, logs=[log]))
    assert len(got) == 1
    assert got[0]["tool"] == "Read"


# ── P2.2 rule-слой: per-server rollup в отчёте + sidecar ─────────────────────


def test_compute_health_includes_server_rollup():
    now = datetime(2026, 7, 14, 12, 0, 0)
    rows = [
        _row("mcp__srv__a", "PostToolUse", now.isoformat(), outcome="error", args_hash="h"),
        _row("mcp__srv__a", "PostToolUse", now.isoformat(), outcome="allow", args_hash="h"),
    ]
    health = ath.compute_health(rows, {}, now)
    assert "srv" in health["servers"]
    srv = health["servers"]["srv"]
    assert srv["calls"] == 2
    assert srv["success_rate"] == 0.5
    assert srv["step_efficiency"] == 0.5  # 1 repeat / 2 calls


def test_render_md_has_effectiveness_section():
    health = {
        "generated": "2026-07-14T12:00:00",
        "tools": {
            "mcp__srv__a": {
                "calls": 4,
                "errors": 0,
                "success": 4,
                "success_rate": 1.0,
                "error_rate": 0.0,
                "p50_ms": 10.0,
                "p95_ms": 20.0,
                "paired": 4,
                "repeats": 1,
                "abandonment": False,
                "verdict": "healthy",
                "reason": "ok",
            }
        },
        "servers": {
            "srv": {
                "calls": 4,
                "errors": 0,
                "success": 4,
                "success_rate": 1.0,
                "error_rate": 0.0,
                "repeats": 1,
                "step_efficiency": 0.25,
                "abandonment_tools": 0,
                "tools": 1,
            }
        },
    }
    md = ath.render_md(health, 14)
    assert "Эффективность (rule-слой, per-server)" in md
    assert "`srv`" in md


def test_sidecar_carries_servers(tmp_path, monkeypatch):
    now = datetime(2026, 7, 14, 12, 0, 0)
    monkeypatch.setattr(ath, "REPORTS", tmp_path)
    rows = [_row("mcp__srv__a", "PostToolUse", now.isoformat())]
    monkeypatch.setattr(ath, "iter_window_rows", lambda *a, **k: rows)
    sidecar = ath.run(window_days=14, now=now)
    assert "servers" in sidecar
    assert "srv" in sidecar["servers"]
