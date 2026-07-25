"""Регрессия разбора degraded 2026-07-25: чистка сигнала провала built-in тулов.

Два независимых фикса, оба саботаж-проверяемы:

  1. **Блоки гардов ≠ провал инструмента.** Прежний инвариант («enforcer exit 2
     преемптит canonical-логгер, Write unpaired=0 при живом блоке») опровергнут
     замером: из 49 непарных Write 36 совпали с block-записью энфорсера, а native
     OTel о них не знает вовсе (тул не исполнялся). Часть энфорсеров блокирует
     через `decision:"block"`, при котором Pre-цепочка доходит до логгера.
     Живой эффект: Write error-rate 14% -> 1%, degraded -> healthy.

  2. **error-rate у shell-тулов не измеряет здоровье инструмента.** Непарный Pre
     у Bash/PowerShell — честный провал (native подтверждает success=false), но
     провал АВТОРСТВА ВЫЗЫВАЮЩЕГО: команда вернула non-zero. Гасим обе error-rate
     ветки degraded (абсолютный порог и baseline-ратчет), broken оставляем.
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
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import tool_effectiveness as te

_ATH_PATH = _SCRIPTS / "analyze_tool_health.py"
_spec = importlib.util.spec_from_file_location("_ath_guard_blocks", _ATH_PATH)
ath = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ath)

NOW = datetime(2026, 7, 25, 12, 0, 0)
OLD = NOW - timedelta(hours=1)


def _pre(tool, tcid, ts, session="s1"):
    return {
        "event": "PreToolUse",
        "tool": tool,
        "tool_call_id": tcid,
        "ts": ts.isoformat(),
        "session": session,
    }


# ── 1. блоки гардов не попадают в failed ──────────────────────────────────────


def test_blocked_unpaired_pre_is_not_failure():
    """САБОТАЖ-ИНВАРИАНТ: непарный Pre с парной block-записью → blocked, НЕ failed."""
    c = te.completion_stats([_pre("Write", "id1", OLD)], [], now=NOW, blocked=[("s1", OLD)])
    assert c["failed"] == 0
    assert c["blocked"] == 1


def test_block_consumed_one_to_one():
    """Один блок объясняет РОВНО один непарный Pre — иначе одна запись «оправдала»
    бы серию реальных провалов."""
    pres = [_pre("Write", "id1", OLD), _pre("Write", "id2", OLD + timedelta(seconds=1))]
    c = te.completion_stats(pres, [], now=NOW, blocked=[("s1", OLD)])
    assert c["blocked"] == 1
    assert c["failed"] == 1


def test_block_from_other_session_not_matched():
    """Блок в ДРУГОЙ сессии не оправдывает провал (сессии независимы)."""
    c = te.completion_stats(
        [_pre("Write", "id1", OLD, session="s1")], [], now=NOW, blocked=[("s2", OLD)]
    )
    assert c["blocked"] == 0 and c["failed"] == 1


def test_block_too_far_in_time_not_matched():
    """Блок вне окна ±5с — не тот вызов (блок и Pre идут одной Pre-цепочкой)."""
    c = te.completion_stats(
        [_pre("Write", "id1", OLD)], [], now=NOW, blocked=[("s1", OLD + timedelta(minutes=3))]
    )
    assert c["blocked"] == 0 and c["failed"] == 1


def test_without_blocked_arg_behavior_preserved():
    """Без аргумента blocked поведение бит-в-бит прежнее (аддитивность фикса)."""
    c = te.completion_stats([_pre("Write", "id1", OLD)], [], now=NOW)
    assert c["failed"] == 1 and c["blocked"] == 0


def test_in_flight_wins_over_block():
    """Свежий непарный Pre остаётся in_flight, даже если рядом был блок."""
    fresh = NOW - timedelta(seconds=5)
    c = te.completion_stats([_pre("Write", "idF", fresh)], [], now=NOW, blocked=[("s1", fresh)])
    assert c["in_flight"] == 1 and c["blocked"] == 0 and c["failed"] == 0


# ── guard_blocks_by_tool: что считается блокировкой ───────────────────────────


def _write_log(tmp_path: Path, records: list[dict]) -> Path:
    p = tmp_path / "hook-invocations.jsonl"
    p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8"
    )
    return p


def _block(tool, ts, session="s1", hook="ZAIWriteGuard", event="PreToolUse", outcome="block"):
    return {
        "category": "hook",
        "hook": hook,
        "event": event,
        "outcome": outcome,
        "tool": tool,
        "session": session,
        "ts": ts.isoformat(),
    }


def test_guard_blocks_collects_pretooluse_blocks(tmp_path):
    log = _write_log(tmp_path, [_block("Write", OLD), _block("Edit", OLD)])
    got = ath.guard_blocks_by_tool(NOW, 14, logs=[log])
    assert sorted(got) == ["Edit", "Write"]
    assert got["Write"] == [("s1", OLD)]


def test_guard_blocks_ignores_stop_hooks_without_tool(tmp_path):
    """Stop-хуки блокируют завершение сессии (tool=null) — это не отказ инструмента."""
    log = _write_log(tmp_path, [_block(None, OLD, hook="task-enforcer", event="Stop")])
    assert ath.guard_blocks_by_tool(NOW, 14, logs=[log]) == {}


def test_guard_blocks_ignores_allow_and_canonical_rows(tmp_path):
    log = _write_log(
        tmp_path,
        [
            _block("Write", OLD, outcome="allow"),
            {
                "category": "tool_call",
                "event": "PreToolUse",
                "tool": "Write",
                "ts": OLD.isoformat(),
            },
        ],
    )
    assert ath.guard_blocks_by_tool(NOW, 14, logs=[log]) == {}


def test_guard_blocks_respects_window_and_broken_lines(tmp_path):
    p = tmp_path / "hook-invocations.jsonl"
    stale = NOW - timedelta(days=30)
    p.write_text(
        json.dumps(_block("Write", OLD))
        + "\n{ битая строка\n"
        + json.dumps(_block("Write", stale))
        + "\n",
        encoding="utf-8",
    )
    got = ath.guard_blocks_by_tool(NOW, 14, logs=[p])
    assert got["Write"] == [("s1", OLD)]  # вне окна отброшен, битая строка не роняет


# ── 2. error-rate у shell-тулов не движет degraded ────────────────────────────


def _stats(calls, errors, **kw):
    st = {
        "calls": calls,
        "errors": errors,
        "success": calls - errors,
        "success_rate": round((calls - errors) / calls, 4) if calls else 1.0,
        "error_rate": round(errors / calls, 4) if calls else 0.0,
        "p95_ms": 100.0,
        "abandonment": False,
        "repeats": 0,
    }
    st.update(kw)
    return st


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_shell_high_error_rate_not_degraded(tool):
    """САБОТАЖ-ИНВАРИАНТ: 30% провалов команд у shell → НЕ degraded."""
    verdict, _ = ath.assign_verdict(_stats(10, 3), None, tool=tool)
    assert verdict == "healthy"


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_shell_error_rate_ratchet_also_suppressed(tool):
    """Вторая error-rate ветка (baseline-ратчет) гасится тем же правилом —
    живьём PowerShell держался degraded именно через неё (baseline error_rate 0.0)."""
    verdict, _ = ath.assign_verdict(_stats(10, 3), {"error_rate": 0.0, "p95_ms": 100.0}, tool=tool)
    assert verdict == "healthy"


@pytest.mark.parametrize("tool", ["Bash", "PowerShell"])
def test_shell_total_breakage_still_broken(tool):
    """Гасим ТОЛЬКО degraded: реальный слом shell-тула обязан всплыть как broken."""
    verdict, _ = ath.assign_verdict(_stats(5, 5), None, tool=tool)
    assert verdict == "broken"


def test_suppression_is_scoped_to_shell():
    """Тот же профиль у не-shell тула остаётся degraded (подавление не глобальное)."""
    verdict, reason = ath.assign_verdict(_stats(10, 3), None, tool="mcp__edt-mcp__list_projects")
    assert verdict == "degraded" and "error-rate" in reason
