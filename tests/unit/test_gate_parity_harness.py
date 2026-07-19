"""P3.4 (roadmap 260703): parity-harness как постоянный CI-guard.

Развитие P0.1 (инцидент G-1: оркестратор при GATE_ORCHESTRATOR_ENABLE=1 не энфорсил
Sonar-hard, т.к. его политики реплицировали лишь recall/capture/research). Этот harness —
генератор синтетических Stop-контекстов (полная матрица сигналов) + прогон ОБОИХ путей
решения (single-source `_compute_hard_ok` живого хука vs `onec_completion_policy` оркестратора)
+ композиция `evaluate_gates`. Инвариант, который harness закрепляет:

  «правишь block-условие живого хука → политика оркестратора обязана дать тот же вердикт,
   иначе parity-тест валит CI» (OPA-стиль policy-тестов, кеш pattern-pipeline-orchestration-2026).

marker: unit. Быстрый in-process (без subprocess) — детерминирован.
"""

from __future__ import annotations

import importlib.util
import sys
from itertools import product
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

_spec = importlib.util.spec_from_file_location(
    "onec_task_completion_stop_harness", _HOOKS / "onec-task-completion-stop.py"
)
oc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oc)

from shared.gate_policies import DEFAULT_POLICIES, onec_completion_policy, pipeline_policy
from shared.gate_policy import evaluate_gates

# Полный набор ключей sig (как отдаёт _collect_signals + sonar_rescan). Значения задаёт матрица.
_SIG_KEYS = (
    "recall",
    "capture",
    "research",
    "skill",
    "config_edit",
    "sonar_rescan",
    "impact",
    "debug_trace",
    "ref_search",
    "callers",
    "form_screenshot",
    "platform_ctx",
    "analyze_method",
    "yaxunit_smoke",
)


def _full_sig(recall, capture, research, sonar_ok, impact=False, debug_trace=False):
    return {
        **{k: False for k in _SIG_KEYS},
        "recall": recall,
        "capture": capture,
        "research": research,
        "skill": True,
        "config_edit": True,
        "sonar_rescan": sonar_ok,
        "impact": impact,
        "debug_trace": debug_trace,
    }


def _onec_result(sig, sonar_ok, sonar_hard, impact_hard, debug_hard):
    hard_ok = oc._compute_hard_ok(sig, sonar_ok, sonar_hard, impact_hard, debug_hard)
    hard_on = impact_hard or debug_hard
    # НАСТОЯЩИЙ reason (как строит evaluate_completion) — иначе reason-проверка тестировала бы мок
    reason = oc._build_reason(
        sig, sonar_ok, "n/a", "", sonar_hard, impact_hard, debug_hard, hard_on
    )
    return {
        "is_1c": True,
        "task_slug": "HARNESS-1",
        "sig": sig,
        "sonar_ok": sonar_ok,
        "sonar_status": "n/a",
        "sonar_detail": "",
        "sonar_hard": sonar_hard,
        "impact_hard": impact_hard,
        "debug_hard": debug_hard,
        "hard_ok": hard_ok,
        "reason": reason,
    }


def _live_onec_allow(is_1c, hard_ok):
    """Решение ЖИВОГО onec-хука main(): allow, если не-1С ИЛИ hard_ok (evaluate_completion→main)."""
    return (not is_1c) or hard_ok


def _live_pipeline_allow(sid, had_edits, pipeline_used):
    """Решение ЖИВОГО pipeline-protocol-stop.execute(): allow, если нет sid / нет правок / пайплайн использован."""
    if not sid:
        return True
    if not had_edits:
        return True
    return bool(pipeline_used)


# ─── Матрица 1: onec — политика оркестратора == вердикт единого источника ────────────────


@pytest.mark.parametrize(
    "recall,capture,research,sonar_ok,sonar_hard",
    list(product([True, False], repeat=5)),
)
def test_onec_policy_matches_single_source(
    monkeypatch, recall, capture, research, sonar_ok, sonar_hard
):
    """32 комбинации: onec_completion_policy.allow == _compute_hard_ok (единый источник)."""
    monkeypatch.delenv("ONEC_TASK_GATE_DISABLE", raising=False)
    sig = _full_sig(recall, capture, research, sonar_ok)
    res = _onec_result(sig, sonar_ok, sonar_hard, impact_hard=False, debug_hard=False)
    ctx = {"is_1c": True, "onec_result": res}
    v = onec_completion_policy(ctx)
    assert v["allow"] is res["hard_ok"]
    if not v["allow"]:
        # deny-reason должен КОНКРЕТНО называть незакрытые петли (не общий текст) — оператору
        # нужно знать, ЧТО чинить. Каждая незакрытая петля → её имя (RECALL/…) в reason.
        rlow = v["reason"].lower()
        for k in ("recall", "capture", "research"):
            if not sig[k]:
                assert k in rlow, f"reason не называет незакрытую петлю {k}"
        if not sonar_ok and sonar_hard:
            assert "sonar" in rlow, "reason не называет провал Sonar"


@pytest.mark.parametrize("impact_hard,debug_hard", list(product([True, False], repeat=2)))
def test_onec_toolgate_hard_matches(monkeypatch, impact_hard, debug_hard):
    """ADR-036 conditional-hard: политика учитывает impact/debug_trace как единый источник."""
    monkeypatch.delenv("ONEC_TASK_GATE_DISABLE", raising=False)
    # петли закрыты, но impact/debug не проставлены → при hard-флагах должно быть deny
    sig = _full_sig(True, True, True, sonar_ok=True, impact=False, debug_trace=False)
    res = _onec_result(sig, True, False, impact_hard, debug_hard)
    ctx = {"is_1c": True, "onec_result": res}
    expected = not (impact_hard or debug_hard)  # если любой hard-флаг → deny (сигнал не проставлен)
    assert onec_completion_policy(ctx)["allow"] is expected


# ─── Матрица 2: pipeline — политика == живой хук ─────────────────────────────────────────


@pytest.mark.parametrize("had_edits,pipeline_used", list(product([True, False], repeat=2)))
def test_pipeline_policy_matches_live(monkeypatch, had_edits, pipeline_used):
    monkeypatch.delenv("PIPELINE_PROTOCOL_DISABLE", raising=False)
    ctx = {"sid": "s", "had_edits": had_edits, "pipeline_used": pipeline_used}
    assert pipeline_policy(ctx)["allow"] is _live_pipeline_allow("s", had_edits, pipeline_used)


# ─── Матрица 3: КОМПОЗИЦИЯ evaluate_gates == AND живых решений обоих хуков ────────────────


@pytest.mark.parametrize(
    "had_edits,pipeline_used,is_1c,recall,capture,research,sonar_ok,sonar_hard",
    list(product([True, False], repeat=8)),
)
def test_composition_equals_and_of_live_hooks(
    monkeypatch, had_edits, pipeline_used, is_1c, recall, capture, research, sonar_ok, sonar_hard
):
    """256 комбинаций: evaluate_gates([pipeline,onec]).allow == live_pipeline ∧ live_onec.

    Это ГЛАВНЫЙ инвариант harness: оркестратор (композиция) даёт ровно то же, что два
    живых Stop-хука по-отдельности. Рассинхрон любой политики с её хуком → падение здесь."""
    monkeypatch.delenv("PIPELINE_PROTOCOL_DISABLE", raising=False)
    monkeypatch.delenv("ONEC_TASK_GATE_DISABLE", raising=False)
    sig = _full_sig(recall, capture, research, sonar_ok)
    ctx = {
        "sid": "s",
        "had_edits": had_edits,
        "pipeline_used": pipeline_used,
        "is_1c": is_1c,
    }
    if is_1c:
        ctx["onec_result"] = _onec_result(sig, sonar_ok, sonar_hard, False, False)
    hard_ok = ctx["onec_result"]["hard_ok"] if is_1c else True
    expected = _live_pipeline_allow("s", had_edits, pipeline_used) and _live_onec_allow(
        is_1c, hard_ok
    )
    v = evaluate_gates(ctx, DEFAULT_POLICIES)
    assert v["allow"] is expected


# ─── Контракт single-source: onec_result перекрывает legacy recall/capture/research ──────


def test_single_source_wins_over_legacy(monkeypatch):
    """Инцидент G-1 regression: recall/capture/research=True, но Sonar провален (hard_ok=False)
    → оркестратор ДЕНАИТ (не смотрит на «зелёные» флаги, читает единый вердикт)."""
    monkeypatch.delenv("ONEC_TASK_GATE_DISABLE", raising=False)
    sig = _full_sig(True, True, True, sonar_ok=False)
    res = _onec_result(sig, sonar_ok=False, sonar_hard=True, impact_hard=False, debug_hard=False)
    assert res["hard_ok"] is False
    ctx = {
        "is_1c": True,
        "recall": True,
        "capture": True,
        "research": True,
        "onec_result": res,
    }
    assert onec_completion_policy(ctx)["allow"] is False  # onec_result выигрывает у legacy


def test_hard_signal_coverage_contract():
    """Контракт покрытия: все hard-ключи, от которых зависит блок, есть в sig-контракте.

    Живой хук блокирует по sig[recall/capture/research/impact/debug_trace] (+sonar_rescan).
    Если _collect_signals/evaluate_completion перестанет их отдавать — оркестратор «слепнет»
    к сигналу (корень инцидента G-1). Тест ловит выпадение ключа из контракта."""
    hard_keys = {"recall", "capture", "research", "impact", "debug_trace"}
    dummy = _full_sig(True, True, True, sonar_ok=True)
    assert hard_keys <= set(dummy), "sig-контракт не покрывает все hard-ключи _compute_hard_ok"
    assert "sonar_rescan" in dummy
    # реальный _collect_signals (пустой транскрипт) обязан нести те же ключи
    real = oc._collect_signals("")
    assert hard_keys - {"sonar_rescan"} <= set(real), "_collect_signals потерял hard-ключ"
