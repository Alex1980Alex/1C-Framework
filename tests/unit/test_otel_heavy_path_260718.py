"""Регрессия тяжёлого пути OTel→Langfuse (roadmap 260718 H-P0..H-P4).

H-P0.1 — захват прямого `duration_ms` из PostToolUse-payload (точнее пэйринга):
  - `invocation_logger.extract_duration_ms` — контракт извлечения (Post-only, числа,
    отбраковка bool/negative/missing, camelCase-страховка);
  - `tool_effectiveness.tool_durations` — предпочтение прямого поля паре Pre→Post,
    смешанный режим, и behavior-preserving на данных без поля (саботаж-проверяемо).
H-P3 — cross-check native OTel ↔ hook-JSONL (FP/FN unpaired-Pre, дельта латентности).
H-P4 — LLM-judge sampling contract.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import tool_effectiveness as te

_IL_PATH = _ROOT / ".claude" / "hooks" / "shared" / "invocation_logger.py"
_spec = importlib.util.spec_from_file_location("_invocation_logger_hp0", _IL_PATH)
il = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(il)


# ── H-P0.1: extract_duration_ms контракт ──────────────────────────────────────


def test_extract_duration_post_int():
    """PostToolUse с числовым duration_ms → int."""
    assert il.extract_duration_ms({"duration_ms": 1234}, "PostToolUse") == 1234


def test_extract_duration_post_float_coerced():
    """float → int (усечение)."""
    assert il.extract_duration_ms({"duration_ms": 42.9}, "PostToolUse") == 42


def test_extract_duration_pre_is_none():
    """PreToolUse → None даже если поле каким-то образом присутствует."""
    assert il.extract_duration_ms({"duration_ms": 100}, "PreToolUse") is None


def test_extract_duration_missing_is_none():
    """Нет поля (строка старого формата) → None."""
    assert il.extract_duration_ms({"tool_response": {}}, "PostToolUse") is None


def test_extract_duration_bool_rejected():
    """bool ⊂ int, но не длительность → None (иначе True=1мс шум)."""
    assert il.extract_duration_ms({"duration_ms": True}, "PostToolUse") is None


def test_extract_duration_negative_rejected():
    """Отрицательное значение невалидно → None."""
    assert il.extract_duration_ms({"duration_ms": -5}, "PostToolUse") is None


def test_extract_duration_camelcase_fallback():
    """camelCase-страховка на случай дрейфа payload."""
    assert il.extract_duration_ms({"durationMs": 77}, "PostToolUse") == 77


def test_extract_duration_zero_is_valid():
    """0мс — валидное значение (мгновенный тул), не None."""
    assert il.extract_duration_ms({"duration_ms": 0}, "PostToolUse") == 0


# ── H-P0.1: tool_durations предпочитает прямое поле ───────────────────────────


def _pre(tcid, ts):
    return {"event": "PreToolUse", "tool": "Bash", "tool_call_id": tcid, "ts": ts}


def _post(tcid, ts, duration_ms=None):
    e = {"event": "PostToolUse", "tool": "Bash", "tool_call_id": tcid, "ts": ts}
    if duration_ms is not None:
        e["duration_ms"] = duration_ms
    return e


def test_tool_durations_all_direct():
    """Все посты несут duration_ms → берём напрямую, пэйринг не нужен."""
    posts = [_post("a", "2026-07-18T12:00:01", 500), _post("b", "2026-07-18T12:00:02", 900)]
    assert sorted(te.tool_durations([], posts)) == [500, 900]


def test_tool_durations_prefers_direct_over_pairing():
    """САБОТАЖ-ИНВАРИАНТ: при наличии duration_ms берётся ОНО, а не длительность пары.
    Pre→Post дали бы 5000мс (5 сек), прямое поле = 500мс — должно победить прямое."""
    pres = [_pre("a", "2026-07-18T12:00:00")]
    posts = [_post("a", "2026-07-18T12:00:05", 500)]  # пара = 5000мс, direct = 500мс
    assert te.tool_durations(pres, posts) == [500]


def test_tool_durations_no_field_falls_back_to_pairing():
    """Данные старого формата (без duration_ms) → результат идентичен pair_durations
    (behavior-preserving: исторический лог не меняет поведение)."""
    pres = [_pre("a", "2026-07-18T12:00:00")]
    posts = [_post("a", "2026-07-18T12:00:02")]  # поля нет → пара = 2000мс
    assert te.tool_durations(pres, posts) == te.pair_durations(pres, posts) == [2000]


def test_tool_durations_mixed():
    """Смешанный лог: один Post с полем (взят напрямую), один без (добран пэйрингом)."""
    pres = [_pre("a", "2026-07-18T12:00:00"), _pre("b", "2026-07-18T12:00:00")]
    posts = [
        _post("a", "2026-07-18T12:00:05", 300),  # direct 300
        _post("b", "2026-07-18T12:00:03"),  # paired 3000
    ]
    got = sorted(te.tool_durations(pres, posts))
    assert got == [300, 3000]


def test_tool_durations_empty():
    assert te.tool_durations([], []) == []
