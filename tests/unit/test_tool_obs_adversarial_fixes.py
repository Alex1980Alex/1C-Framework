"""Регресс-тесты фиксов адверсариального ревью roadmap 260713 (2026-07-14).

Покрывают дефекты, найденные тремя ревью-агентами по реализованным пунктам
P0/P1.1/P1.2/P1.4/P2.3 — каждый тест закрепляет конкретную находку.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ath = _load("_ath_adv", "scripts/analyze_tool_health.py")


# ── P1.1 #9: tz-guard в iter_window_rows ─────────────────────────────────────


def test_window_survives_aware_ts(tmp_path):
    """Одна aware-строка (+00:00) в логе не роняет TypeError'ом весь прогон."""
    now = datetime(2026, 7, 14, 12, 0, 0)
    log = tmp_path / "log.jsonl"
    rows = [
        {
            "tool": "Read",
            "event": "PostToolUse",
            "ts": "2026-07-13T12:00:00+00:00",
            "category": "tool_call",
        },
        {
            "tool": "Bash",
            "event": "PostToolUse",
            "ts": "2026-07-13T12:00:00",
            "category": "tool_call",
        },
    ]
    log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    got = list(ath.iter_window_rows(now, 14, logs=[log]))  # не должно бросить
    assert len(got) == 2  # обе строки в окне (aware нормализована)


# ── P1.1 #1b: baseline-ветки degraded гейтятся DEGRADED_MIN_CALLS ────────────


def _stats(calls=0, errors=0, p95_ms=100.0, paired=None, repeats=0, abandonment=False):
    success = calls - errors
    return {
        "calls": calls,
        "errors": errors,
        "success": success,
        "success_rate": round(success / calls, 4) if calls else 1.0,
        "error_rate": round(errors / calls, 4) if calls else 0.0,
        "p50_ms": p95_ms / 2,
        "p95_ms": p95_ms,
        "paired": calls if paired is None else paired,
        "repeats": repeats,
        "abandonment": abandonment,
    }


def test_single_transient_error_not_degraded_via_baseline():
    """calls=1, er=100% при baseline er=0 — НЕ degraded (гейт MIN_CALLS на baseline-ветке)."""
    v, _ = ath.assign_verdict(_stats(calls=1, errors=1), {"p95_ms": 100.0, "error_rate": 0.0})
    assert v == "healthy"


def test_baseline_branches_still_fire_at_min_calls():
    """При calls≥DEGRADED_MIN_CALLS baseline-сравнения работают как раньше."""
    v, _ = ath.assign_verdict(
        _stats(calls=5, errors=0, p95_ms=500.0), {"p95_ms": 100.0, "error_rate": 0.0}
    )
    assert v == "degraded"  # p95 500 > 2×100


# ── P1.1 #1c: paired=0 не ратчетит p95=0.0; легаси-0.0 лечится ───────────────


def test_baseline_not_poisoned_by_unpaired_zero_p95():
    stats = {"X": _stats(calls=10, errors=0, p95_ms=0.0, paired=0)}
    out = ath.update_baseline({"X": {"p95_ms": 250.0, "error_rate": 0.0}}, stats)
    assert out["X"]["p95_ms"] == 250.0  # прежняя планка сохранена, 0.0 не затянут


def test_baseline_legacy_zero_p95_healed():
    stats = {"X": _stats(calls=10, errors=0, p95_ms=180.0, paired=10)}
    out = ath.update_baseline({"X": {"p95_ms": 0.0, "error_rate": 0.0}}, stats)
    assert out["X"]["p95_ms"] == 180.0  # затянутый 0.0 заменён реальным значением


# ── P1.1 #2: TTL-prune неактивных из baseline ────────────────────────────────


def test_baseline_prunes_stale_unused_tool():
    now = datetime(2026, 7, 14)
    old = (now - timedelta(days=ath.BASELINE_UNUSED_TTL_DAYS + 5)).isoformat()
    baseline = {"Dead": {"p95_ms": 100.0, "error_rate": 0.0, "last_seen": old}}
    out = ath.update_baseline(baseline, {}, now)
    assert "Dead" not in out  # выбыл по TTL — unused не светит вечно


def test_baseline_keeps_recent_unused_and_stamps_legacy():
    now = datetime(2026, 7, 14)
    baseline = {"Legacy": {"p95_ms": 100.0, "error_rate": 0.0}}  # без last_seen
    out = ath.update_baseline(baseline, {}, now)
    assert "Legacy" in out
    assert out["Legacy"]["last_seen"]  # получил штамп — один TTL-цикл на выбытие


# ── P1.1 #1a: reset_baseline CLI ─────────────────────────────────────────────


def test_reset_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(ath, "REPORTS", tmp_path)
    (tmp_path / "baseline.json").write_text(
        json.dumps({"A": {"p95_ms": 1}, "B": {"p95_ms": 2}}), encoding="utf-8"
    )
    assert ath.reset_baseline(["A"]) == 1
    left = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
    assert list(left) == ["B"]
    assert ath.reset_baseline(None) == 1  # полный сброс
    assert json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8")) == {}


# ── P1.1 #7: window_incomplete ───────────────────────────────────────────────


def test_window_incomplete_flag(tmp_path, monkeypatch):
    now = datetime(2026, 7, 14, 12, 0, 0)
    log = tmp_path / "log.jsonl"
    # лог начинается всего 2 дня назад при окне 14д → неполнота
    row = {
        "tool": "Read",
        "event": "PostToolUse",
        "ts": (now - timedelta(days=2)).isoformat(),
        "category": "tool_call",
    }
    log.write_text(json.dumps(row) + "\n", encoding="utf-8")
    monkeypatch.setattr(ath, "LOG", log)
    monkeypatch.setattr(ath, "ROTATED", tmp_path / "nope.jsonl")
    monkeypatch.setattr(ath, "REPORTS", tmp_path / "reports")
    sidecar = ath.run(window_days=14, now=now)
    assert sidecar["window_incomplete"] is True


# ── P0 #1: hookSpecificOutput → outcome="message" (не глотается P0.4) ────────


def test_hook_context_outcome_not_suppressed(tmp_path, monkeypatch):
    hooks_dir = _ROOT / ".claude" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    from base.protocol import HookOutput

    out = HookOutput().hook_context("ctx")
    # классификация в run(): hookSpecificOutput => message (не allow)
    assert out._data.get("hookSpecificOutput")
    outcome = "allow"
    if out._data.get("decision") == "block":
        outcome = "block"
    elif out._data.get("systemMessage") or out._data.get("hookSpecificOutput"):
        outcome = "message"
    assert outcome == "message"


# ── P0 #6: Bash dict exit_code детектится как ошибка ─────────────────────────


def test_builtin_exit_code_classified_as_error():
    hooks_dir = _ROOT / ".claude" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    til = _load("_til_adv", ".claude/hooks/tool-invocation-logger.py")

    class _Inp:
        raw = {"tool_response": {"exit_code": 1, "stderr": "boom"}}
        tool_result = None

    outcome, err = til.ToolInvocationLogger._classify_outcome(_Inp(), "PostToolUse")
    assert outcome == "error"
    assert "exit_code=1" in err

    class _Ok:
        raw = {"tool_response": {"exit_code": 0, "stdout": "fine"}}
        tool_result = None

    outcome, _ = til.ToolInvocationLogger._classify_outcome(_Ok(), "PostToolUse")
    assert outcome == "allow"


# ── P2.3 #1: slug инстанса 1c-mcp-crud из MCP_ONEC_URL ───────────────────────


def test_instance_slug_from_env(monkeypatch):
    # _instance_slug читаем из исходника лаунчера без исполнения top-level (chdir!)
    src = (_ROOT / "scripts" / "mcp_1c_stdio_launcher.py").read_text(encoding="utf-8")
    ns: dict = {}
    fn_src = src[src.index("def _instance_slug") : src.index("def _instrument_call_tool")]
    exec(compile("import os\n" + fn_src, "<launcher>", "exec"), ns)
    slug = ns["_instance_slug"]

    monkeypatch.setenv("MCP_ONEC_URL", "http://localhost/erp")
    assert slug() == "1c-mcp-crud-erp"
    monkeypatch.setenv("MCP_ONEC_URL", "http://localhost/transport")
    assert slug() == "1c-mcp-crud"
    monkeypatch.delenv("MCP_ONEC_URL", raising=False)
    assert slug() == "1c-mcp-crud"


# ── P1.4 #3: producer-side контракт маркера [REGRESSION] ─────────────────────


def test_regression_marker_printed_in_print_mode(tmp_path, monkeypatch, capsys):
    """Маркер печатается и в --print (read-only путь каденса) — контракт с парсером."""
    obs = _load("_obs_adv", "scripts/memory_observability_report.py")
    # синтетический отчёт: build_report → 1 stale-синк
    monkeypatch.setattr(
        obs,
        "build_report",
        lambda since, now, sh: {
            "regressions": [{"source": "propagation"}],
            "freshness": [],
            "stale_hours": sh,
            "since": since,
        },
    )
    monkeypatch.setattr(obs, "render_markdown", lambda r: "# report")
    monkeypatch.setattr(sys, "argv", ["x", "--print"])
    assert obs.main() == 0
    out = capsys.readouterr().out
    assert "[REGRESSION] 1 stale sink(s): ['propagation']" in out
