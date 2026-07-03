"""Parity-тест оркестратора гейтов ↔ живого onec-хука (roadmap 260703 P0.1, инцидент G-1).

Инцидент: GATE_ORCHESTRATOR_ENABLE=1 с ~2026-06-21, а политики оркестратора
(gate_policies) реплицировали лишь recall/capture/research — Sonar-hard (ADR-037) и
side-effects (LOOPS.md, advisory-event) жили только в main() живого хука → при включённом
оркестраторе молча не исполнялись. Фикс: оба пути зовут ЕДИНЫЙ oc.evaluate_completion.

Этот тест закрепляет инвариант «вердикт политики == вердикт evaluate_completion»
(parity by construction) на матрице сигналов + отдельно проверяет, что Sonar теперь
участвует в блок-решении оркестратора (сам инцидент). marker: unit.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from itertools import product
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

_HOOK_FILE = _HOOKS / "onec-task-completion-stop.py"
_spec = importlib.util.spec_from_file_location("onec_task_completion_stop_parity", _HOOK_FILE)
oc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oc)

from shared.gate_policies import onec_completion_policy


def _sig(recall, capture, research, sonar_ok=True):
    """Полный sig-словарь (все ключи _collect_signals) с заданными петлями."""
    return {
        "recall": recall,
        "capture": capture,
        "research": research,
        "skill": True,
        "config_edit": True,
        "sonar_rescan": sonar_ok,
        "impact": False,
        "debug_trace": False,
        "ref_search": False,
        "callers": False,
        "form_screenshot": False,
        "platform_ctx": False,
        "analyze_method": False,
    }


# --- Уровень 1: чистое решение _compute_hard_ok (единый источник вердикта) ----------------


@pytest.mark.parametrize("recall,capture,research", list(product([True, False], repeat=3)))
def test_compute_hard_ok_core_loops(recall, capture, research):
    """recall/capture/research — ВСЕГДА hard (sonar не-hard). 8 комбинаций."""
    sig = _sig(recall, capture, research)
    expected = recall and capture and research
    assert (
        oc._compute_hard_ok(
            sig, sonar_ok=True, sonar_hard=False, impact_hard=False, debug_hard=False
        )
        is expected
    )


@pytest.mark.parametrize("sonar_ok,sonar_hard", list(product([True, False], repeat=2)))
def test_compute_hard_ok_sonar(sonar_ok, sonar_hard):
    """Sonar блокирует ТОЛЬКО когда sonar_hard И not sonar_ok; иначе не влияет. Петли закрыты."""
    sig = _sig(True, True, True, sonar_ok=sonar_ok)
    expected = sonar_ok or not sonar_hard
    assert (
        oc._compute_hard_ok(
            sig, sonar_ok=sonar_ok, sonar_hard=sonar_hard, impact_hard=False, debug_hard=False
        )
        is expected
    )


def test_compute_hard_ok_toolgate_hard():
    """ADR-036: при impact_hard требуется sig['impact']; debug_hard → sig['debug_trace']."""
    sig = _sig(True, True, True)
    assert oc._compute_hard_ok(sig, True, False, impact_hard=True, debug_hard=False) is False
    sig["impact"] = True
    assert oc._compute_hard_ok(sig, True, False, impact_hard=True, debug_hard=False) is True
    assert oc._compute_hard_ok(sig, True, False, impact_hard=True, debug_hard=True) is False
    sig["debug_trace"] = True
    assert oc._compute_hard_ok(sig, True, False, impact_hard=True, debug_hard=True) is True


# --- Уровень 2: политика оркестратора зеркалит вердикт evaluate_completion -----------------


def _res(hard_ok, sig):
    """Мок результата evaluate_completion (как его кладёт build_context в ctx['onec_result'])."""
    return {
        "is_1c": True,
        "task_slug": "GKSTCPLK-9999",
        "sig": sig,
        "sonar_ok": sig["sonar_rescan"],
        "sonar_status": "n/a",
        "sonar_detail": "",
        "sonar_hard": True,
        "impact_hard": False,
        "debug_hard": False,
        "hard_ok": hard_ok,
        "reason": "[ONEC-TASK-GATE] mock reason",
    }


@pytest.mark.parametrize(
    "recall,capture,research,sonar_ok",
    list(product([True, False], repeat=4)),
)
def test_policy_mirrors_evaluate_result(monkeypatch, recall, capture, research, sonar_ok):
    """PARITY: политика allow ⟺ hard_ok из evaluate_completion. 16 комбинаций (матрица ≥12)."""
    monkeypatch.delenv("ONEC_TASK_GATE_DISABLE", raising=False)
    sig = _sig(recall, capture, research, sonar_ok=sonar_ok)
    hard_ok = oc._compute_hard_ok(
        sig, sonar_ok=sonar_ok, sonar_hard=True, impact_hard=False, debug_hard=False
    )
    ctx = {"is_1c": True, "onec_result": _res(hard_ok, sig)}
    verdict = onec_completion_policy(ctx)
    assert verdict["allow"] is hard_ok


def test_incident_g1_sonar_now_denies(monkeypatch):
    """Сам инцидент: петли recall/capture/research закрыты, но Sonar провален → оркестратор
    ТЕПЕРЬ deny (до P0.1 политика игнорила Sonar и ошибочно allow'ила)."""
    monkeypatch.delenv("ONEC_TASK_GATE_DISABLE", raising=False)
    sig = _sig(True, True, True, sonar_ok=False)
    hard_ok = oc._compute_hard_ok(
        sig, sonar_ok=False, sonar_hard=True, impact_hard=False, debug_hard=False
    )
    assert hard_ok is False
    ctx = {"is_1c": True, "onec_result": _res(hard_ok, sig)}
    assert onec_completion_policy(ctx)["allow"] is False


def test_policy_optout(monkeypatch):
    """opt-out ONEC_TASK_GATE_DISABLE=1 → allow даже при провале (инвариант сохранён)."""
    monkeypatch.setenv("ONEC_TASK_GATE_DISABLE", "1")
    sig = _sig(False, False, False, sonar_ok=False)
    ctx = {"is_1c": True, "onec_result": _res(False, sig)}
    assert onec_completion_policy(ctx)["allow"] is True


def test_policy_legacy_fallback_without_onec_result(monkeypatch):
    """Back-compat: ctx без onec_result → прежняя логика recall/capture/research (старые тесты)."""
    monkeypatch.delenv("ONEC_TASK_GATE_DISABLE", raising=False)
    assert (
        onec_completion_policy({"is_1c": True, "recall": True, "capture": True, "research": True})[
            "allow"
        ]
        is True
    )
    assert (
        onec_completion_policy({"is_1c": True, "recall": True, "capture": False, "research": True})[
            "allow"
        ]
        is False
    )
