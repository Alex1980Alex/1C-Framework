"""Регрессия окна свежести LLM-делегирования (диагноз 2026-07-18).

Root cause «оркестратор не делегирует»: `has_llm_delegation` был one-shot флагом
без TTL, а state-файл переживает сессии → единственный llm_complete (даже вчерашний)
навсегда выключал z-ai-write-guard (живое наблюдение: 141 allow / 0 block за день).
Фикс: флаг годен только в окне свежести LLM_DELEGATION_FRESH_MINUTES (default 30);
отсутствие/непарсимость отметки → fail-closed False.

САБОТАЖ-ИНВАРИАНТ: откат фикса (return count > 0) валит test_stale_delegation_is_false.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SS_PATH = _ROOT / ".claude" / "hooks" / "shared" / "session_state.py"


@pytest.fixture()
def ss(tmp_path, monkeypatch):
    """Изолированный SessionState с state-файлом в tmp (env SESSION_STATE_PATH)."""
    monkeypatch.setenv("SESSION_STATE_PATH", str(tmp_path))
    spec = importlib.util.spec_from_file_location("_ss_fresh", _SS_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_ss_fresh"] = mod
    spec.loader.exec_module(mod)
    yield mod.SessionState
    sys.modules.pop("_ss_fresh", None)


def _write_state(state_cls, count: int, last: str | None):
    def _do(state):
        state["llm_delegation_count"] = count
        if last is None:
            state.pop("llm_delegation_last", None)
        else:
            state["llm_delegation_last"] = last

    state_cls._mutate(_do)


def test_fresh_delegation_is_true(ss):
    """Недавний llm_complete (5 мин назад) → True (рабочее окно делегирования)."""
    _write_state(ss, 1, (datetime.now() - timedelta(minutes=5)).isoformat())
    assert ss.has_llm_delegation() is True


def test_stale_delegation_is_false(ss):
    """САБОТАЖ-ИНВАРИАНТ: делегирование сутки назад (прошлая сессия) → False.
    Именно эта ветка была сломана one-shot флагом (гард мёртв навсегда)."""
    _write_state(ss, 2, (datetime.now() - timedelta(hours=24)).isoformat())
    assert ss.has_llm_delegation() is False


def test_zero_count_is_false(ss):
    """count=0 → False (прежнее поведение сохранено)."""
    _write_state(ss, 0, datetime.now().isoformat())
    assert ss.has_llm_delegation() is False


def test_missing_last_is_false(ss):
    """count>0, но отметки времени нет (легаси-state) → fail-closed False."""
    _write_state(ss, 3, None)
    assert ss.has_llm_delegation() is False


def test_unparseable_last_is_false(ss):
    """Непарсимая отметка → fail-closed False (гард требует делегирование)."""
    _write_state(ss, 1, "не-дата")
    assert ss.has_llm_delegation() is False


def test_window_env_override(ss, monkeypatch):
    """Окно тюнится env: 120 мин назад при окне 180 → True, при окне 30 → False."""
    _write_state(ss, 1, (datetime.now() - timedelta(minutes=120)).isoformat())
    monkeypatch.setenv("LLM_DELEGATION_FRESH_MINUTES", "180")
    assert ss.has_llm_delegation() is True
    monkeypatch.setenv("LLM_DELEGATION_FRESH_MINUTES", "30")
    assert ss.has_llm_delegation() is False


def test_invalid_env_falls_back_to_default(ss, monkeypatch):
    """Невалидный env → default 30 мин (5 мин назад всё ещё True)."""
    monkeypatch.setenv("LLM_DELEGATION_FRESH_MINUTES", "мусор")
    _write_state(ss, 1, (datetime.now() - timedelta(minutes=5)).isoformat())
    assert ss.has_llm_delegation() is True


def test_record_then_has_roundtrip(ss):
    """record_llm_delegation → has_llm_delegation True (живой цикл гарда)."""
    ss.record_llm_delegation()
    assert ss.has_llm_delegation() is True


def test_aware_timestamp_fail_closed(ss):
    """tz-guard (code-verify rec #1): aware-отметка от будущего писателя → naive−aware
    вычитание бросает TypeError → fail-closed False (гард требует делегирование),
    а не крэш, утекающий в allow. Саботаж: убрать except TypeError → тест краснеет TypeError'ом."""
    _write_state(ss, 1, datetime.now(UTC).isoformat())
    assert ss.has_llm_delegation() is False
