"""Регрессия N-P0 (roadmap 260718): честность данных tool-observability.

Три корректностных фикса, каждый саботаж-проверяем (откат фикса → тест краснеет):

  N-P0.1 — error-детект built-in через НЕПАРНЫЙ Pre. Платформа НЕ шлёт PostToolUse
           на неуспешный built-in вызов (эмпирически: Bash non-zero exit / Edit
           «строка не найдена» / Read miss — дамп формы 2026-07-18). Post = только
           успехи → error-rate из Post ≡ 0. Честный провал = Pre без парного Post.
  N-P0.2 — каскадная ротация архивов лога (окно 14д реально покрывается).
  N-P0.3 — p95-degraded отключён у content-variable тулов (латентность зависит от
           содержимого вызова, не здоровья) — конец FP-фабрики (NB2).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import tool_effectiveness as te

_ATH_PATH = _SCRIPTS / "analyze_tool_health.py"
_spec = importlib.util.spec_from_file_location("_ath_np0", _ATH_PATH)
ath = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ath)

NOW = datetime(2026, 7, 18, 12, 0, 0)


def _pre(tool, tcid, ts):
    return {"event": "PreToolUse", "tool": tool, "tool_call_id": tcid, "ts": ts.isoformat()}


def _post(tool, tcid, ts, outcome="allow", error=None):
    return {
        "event": "PostToolUse",
        "tool": tool,
        "tool_call_id": tcid,
        "ts": ts.isoformat(),
        "outcome": outcome,
        "error": error,
    }


# ── N-P0.1: completion_stats (непарный Pre = провал) ──────────────────────────


def test_completion_all_paired_no_failure():
    """Каждый Pre получил Post → 0 провалов (успешные вызовы)."""
    old = NOW - timedelta(hours=1)
    pres = [_pre("Bash", f"id{i}", old) for i in range(5)]
    posts = [_post("Bash", f"id{i}", old + timedelta(seconds=1)) for i in range(5)]
    c = te.completion_stats(pres, posts, now=NOW)
    assert c["failed"] == 0 and c["completed"] == 5


def test_completion_unpaired_old_pre_is_failure():
    """Pre без Post, старше grace → провал (NB1: платформа не шлёт Post на фейл)."""
    old = NOW - timedelta(hours=1)
    pres = [_pre("Bash", "id1", old), _pre("Bash", "id2", old)]
    posts = [_post("Bash", "id1", old + timedelta(seconds=1))]  # id2 без Post
    c = te.completion_stats(pres, posts, now=NOW)
    assert c["failed"] == 1 and c["in_flight"] == 0


def test_completion_recent_unpaired_is_in_flight_not_failure():
    """Непарный Pre моложе grace → in_flight (Post ещё может прийти), НЕ провал."""
    pres = [_pre("Bash", "idR", NOW - timedelta(seconds=10))]  # 10с < grace 120
    c = te.completion_stats(pres, [], now=NOW)
    assert c["failed"] == 0 and c["in_flight"] == 1


def test_completion_fifo_fallback_without_ids():
    """Пары без tool_call_id добираются FIFO (совместимость со старым payload)."""
    old = NOW - timedelta(hours=1)
    pres = [_pre("Grep", "", old), _pre("Grep", "", old)]
    posts = [_post("Grep", "", old + timedelta(seconds=1))]  # 1 Post на 2 Pre
    c = te.completion_stats(pres, posts, now=NOW)
    assert c["failed"] == 1  # один Pre остался непарным


# ── N-P0.1 в аналитике: aggregate_tools + broken достижим ─────────────────────


def test_aggregate_incomplete_makes_error_rate_honest():
    """Bash 4 успеха + 2 провала (Pre без Post) → error_rate 33%, не 0."""
    old = NOW - timedelta(hours=1)
    rows = []
    for i in range(4):
        rows.append(_pre("Bash", f"ok{i}", old))
        rows.append(_post("Bash", f"ok{i}", old + timedelta(seconds=1)))
    rows.append(_pre("Bash", "fail1", old))  # непарные = провалы
    rows.append(_pre("Bash", "fail2", old))
    agg = ath.aggregate_tools(rows, now=NOW)["Bash"]
    assert agg["incomplete"] == 2
    assert agg["calls"] == 6 and agg["success"] == 4
    assert agg["error_rate"] == pytest.approx(2 / 6, abs=0.01)


def test_broken_reachable_all_failed_builtin():
    """Инструмент, где все Pre непарные (все провалились) → broken (0 success)."""
    old = NOW - timedelta(hours=1)
    rows = [_pre("Bash", f"f{i}", old) for i in range(4)]  # 0 Post → всё провал
    agg = ath.aggregate_tools(rows, now=NOW)["Bash"]
    v, _ = ath.assign_verdict(agg, None, tool="Bash")
    assert agg["success"] == 0 and v == "broken"


def test_successful_bash_still_healthy():
    """Контроль: все успешны → error_rate 0, healthy (нет ложных провалов)."""
    old = NOW - timedelta(hours=1)
    rows = []
    for i in range(10):
        rows.append(_pre("Bash", f"s{i}", old))
        rows.append(_post("Bash", f"s{i}", old + timedelta(seconds=1)))
    agg = ath.aggregate_tools(rows, now=NOW)["Bash"]
    assert agg["error_rate"] == 0.0
    assert ath.assign_verdict(agg, None, tool="Bash")[0] == "healthy"


# ── N-P0.3: p95-FP отключён у content-variable тулов (NB2) ─────────────────────


def _stats_p95(p95, calls=10):
    return {
        "calls": calls,
        "errors": 0,
        "success": calls,
        "success_rate": 1.0,
        "error_rate": 0.0,
        "p50_ms": 100.0,
        "p95_ms": p95,
        "paired": calls,
        "incomplete": 0,
        "in_flight": 0,
        "completed": calls,
        "repeats": 0,
        "abandonment": False,
    }


def test_p95_fp_suppressed_for_content_variable_tool():
    """Bash (content-variable) с p95 65s vs baseline 1.2s → НЕ degraded (NB2)."""
    v, _ = ath.assign_verdict(
        _stats_p95(65000.0), {"p95_ms": 1236.0, "error_rate": 0.0}, tool="Bash"
    )
    assert v == "healthy"  # раньше был degraded (FP-фабрика)


def test_p95_fp_suppressed_for_execute_code():
    """MCP execute_code (content-variable по суффиксу) с p95-скачком → не degraded."""
    v, _ = ath.assign_verdict(
        _stats_p95(4956.0),
        {"p95_ms": 1876.0, "error_rate": 0.0},
        tool="mcp__1c-mcp-crud-mfm__execute_code",
    )
    assert v == "healthy"


def test_p95_regression_still_fires_for_stable_tool():
    """Не content-variable инструмент с реальным p95-скачком выше пола → degraded."""
    v, _ = ath.assign_verdict(
        _stats_p95(1084.0),
        {"p95_ms": 404.0, "error_rate": 0.0},
        tool="mcp__edt-mcp__get_project_errors",
    )
    assert v == "degraded"


def test_p95_below_floor_never_degrades():
    """p95 ниже абсолютного пола (500мс) не degraded даже при 2×baseline (NB2)."""
    v, _ = ath.assign_verdict(
        _stats_p95(408.0),
        {"p95_ms": 189.0, "error_rate": 0.0},
        tool="mcp__edt-mcp__get_symbol_info",  # не content-variable, но p95<пол
    )
    assert v == "healthy"  # 408 > 2×189 но < пол 500


def test_error_rate_degraded_still_applies_to_content_variable():
    """У content-variable error-rate degraded ОСТАЁТСЯ (отключён только p95)."""
    st = _stats_p95(100.0, calls=20)
    st.update(errors=4, success=16, success_rate=0.8, error_rate=0.2)
    v, _ = ath.assign_verdict(st, {"p95_ms": 50.0, "error_rate": 0.0}, tool="Agent")
    assert v == "degraded"  # 20% error > 10%, несмотря на content-variable


# ── N-P0.2: каскадная ротация архивов ─────────────────────────────────────────


def test_cascade_rotation_shifts_archives(tmp_path, monkeypatch):
    """LOG→.1, .1→.2 при ротации; старый .1 не затирается (окно 14д покрывается)."""
    il_path = _ROOT / ".claude" / "hooks" / "shared" / "invocation_logger.py"
    spec = importlib.util.spec_from_file_location("_il_np0", il_path)
    il = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(il)

    log = tmp_path / "hook-invocations.jsonl"
    arch1 = tmp_path / "hook-invocations.1.jsonl"
    arch1.write_text("OLD-ARCHIVE\n", encoding="utf-8")
    log.write_text("x" * (11 * 1024 * 1024), encoding="utf-8")  # > 10MB → ротация

    monkeypatch.setattr(il, "MAX_LOG_SIZE", 10 * 1024 * 1024)
    monkeypatch.setattr(il, "HOOK_LOG_ARCHIVES", 12)
    il._rotate_if_needed(log)

    assert (tmp_path / "hook-invocations.2.jsonl").read_text(encoding="utf-8") == "OLD-ARCHIVE\n"
    assert arch1.exists() and arch1.stat().st_size > 10 * 1024 * 1024  # бывший LOG
    assert not log.exists()  # переехал в .1


def test_all_logs_discovers_archives(tmp_path, monkeypatch):
    """_all_logs находит LOG + все .N архивы (раньше читались только LOG+.1)."""
    monkeypatch.setattr(ath, "LOG", tmp_path / "hook-invocations.jsonl")
    (tmp_path / "hook-invocations.jsonl").write_text("", encoding="utf-8")
    for n in (1, 2, 3):
        (tmp_path / f"hook-invocations.{n}.jsonl").write_text("", encoding="utf-8")
    logs = ath._all_logs()
    assert len(logs) == 4  # LOG + .1 + .2 + .3
    assert logs[0].name == "hook-invocations.jsonl"
    assert logs[-1].name == "hook-invocations.3.jsonl"
