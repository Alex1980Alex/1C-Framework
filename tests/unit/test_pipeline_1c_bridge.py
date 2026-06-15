"""Unit-тесты pipeline_1c_bridge (ADR-019 B′ F-1, ядро G3). marker: unit.

Покрытие: slug-деривация (JIRA приоритет / ASCII-fallback / общий слот), гарантия
«один slug на задачу» (analyze↔implement), best-effort (не кидает при сбое импорта
pipeline_state). Тесты **collision-immune** к src/shared↔hooks/shared (см. memory
feedback-hook-src-shared-collision): не делают runtime `from shared import pipeline_state`,
который в общем pytest-прогоне резолвится в src/shared. Реальное создание `.pipeline-state.json`
покрыто live-DoD-2 (синтетический analyze-preflight) — см. 04-testing.md.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"

_spec = importlib.util.spec_from_file_location(
    "pipeline_1c_bridge_t", _HOOKS / "shared" / "pipeline_1c_bridge.py"
)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


def test_derive_slug_jira():
    # JIRA-код = стабильный ID задачи
    assert bridge.derive_slug("/implement-1c-task GKSTCPLK-2182 доработать") == "GKSTCPLK-2182"


def test_derive_slug_fallback_ascii():
    s = bridge.derive_slug("Refactor unload direction form")
    assert s and s == s.lower() and all(c.isalnum() or c == "-" for c in s)


def test_derive_slug_empty_and_cyrillic():
    # пусто и чистая кириллица-без-JIRA → общий слот (ASCII-decompose пуст)
    assert bridge.derive_slug("") == "1c-task"
    assert bridge.derive_slug("Доработать форму") == "1c-task"


def test_same_jira_one_slug():
    # «один пайплайн на задачу»: analyze и implement одного JIRA → один slug
    a = bridge.derive_slug("/analyze-1c-task GKSTCPLK-5 анализ")
    i = bridge.derive_slug("/implement-1c-task GKSTCPLK-5 реализация")
    assert a == i == "GKSTCPLK-5"


def test_best_effort_never_raises(monkeypatch):
    # форсируем сбой импорта pipeline_state (пустой `shared` без сабмодуля) →
    # ensure_pipeline_1c обязан вернуть None, НЕ кинуть (инвариант «не ломать preflight»)
    monkeypatch.setitem(sys.modules, "shared", types.ModuleType("shared"))
    assert bridge.ensure_pipeline_1c("/analyze-1c-task GKSTCPLK-1 x", "analyze-1c-task") is None


# --- F-1.5: advance_for_artifact (collision-immune; live-движение этапов — в 04-testing DoD) ---


def test_advance_regex_mapping():
    # артефакт→этапы (чистый regex, без pipeline_state)
    a = next(st for rx, st in bridge._ARTIFACT_STAGES if rx.search("GKSTCPLK-1-ANALYSIS-REPORT.md"))
    i = next(st for rx, st in bridge._ARTIFACT_STAGES if rx.search("IMPLEMENTATION-PROGRESS.md"))
    assert a == (1, 2) and i == (3,)


def test_advance_non_artifact_none():
    # путь без 1С-артефакта → None (ранний выход, pipeline_state не трогается)
    assert bridge.advance_for_artifact("/x/some_random.py") is None
    assert bridge.advance_for_artifact("") is None


def test_advance_best_effort(monkeypatch):
    # матч есть, но pipeline_state недоступен (пустой shared) → None, не кидает
    monkeypatch.setitem(sys.modules, "shared", types.ModuleType("shared"))
    assert bridge.advance_for_artifact("GKSTCPLK-1-ANALYSIS-REPORT.md") is None
