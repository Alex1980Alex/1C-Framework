#!/usr/bin/env python3
"""ADR-034 R3 (полная композиция): build_context + политики для evaluate_gates.

Переиспользует ПРОВЕРЕННЫЕ хелперы живых хуков (pipeline-protocol-stop /
onec-task-completion-stop) через importlib (имена файлов с дефисом не импортируются обычно).
build_context — ОДИН проход (start/sig посчитаны один раз, общий контекст для всех политик).
Политики — чистые функции ctx -> decision; реплицируют ТОЧНЫЕ block-условия живых хуков
+ per-policy opt-out. Graceful: ошибка в build → safe-allow дефолты (оркестратор не падает).
"""

import importlib.util
import os
from pathlib import Path

from shared.gate_policy import decision

_HOOKS_DIR = Path(__file__).resolve().parent.parent  # .claude/hooks


def _log_degraded(where: str, err: Exception) -> None:
    """P1.8: пишет degraded-запись (decision=allow, reason=degraded:<err>) в decision-log —
    fail-open (safe-allow дефолты) больше не молчалив. best-effort, никогда не кидает."""
    try:
        from shared.gate_policy import log_decision

        log_decision(decision(where, True, f"degraded:{type(err).__name__}: {err}"))
    except Exception:
        pass


def _load(modname, filename):
    spec = importlib.util.spec_from_file_location(modname, str(_HOOKS_DIR / filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def build_context(sid, transcript_path):
    """ОДИН проход: вычислить все сигналы для политик. Никогда не кидает.

    Safe-allow дефолты (had_edits=False, pipeline_used=True, is_1c=False, петли=True) →
    при любом сбое сбора политики разрешают завершение (анти-deadlock).
    """
    ctx = {
        "sid": sid,
        "transcript_path": transcript_path,
        "had_edits": False,
        "pipeline_used": True,
        "is_1c": False,
        "config_edit": False,
        "recall": True,
        "capture": True,
        "research": True,
        "skill": True,
    }
    try:
        pp = _load("_pp_stop", "pipeline-protocol-stop.py")
        oc = _load("_oc_stop", "onec-task-completion-stop.py")
    except Exception as e:
        # P1.8 (2.E.2): полный сбой загрузки glue → оркестратор глохнет в safe-allow. Раньше молча;
        # теперь пишем degraded-запись в decision-log, чтобы fail-open был виден в аудите.
        _log_degraded("build_context:load", e)
        return ctx

    # Сигнал пайплайн-протокола (ADR-018): были ли правки без пайплайна
    try:
        if sid:
            had_write, start = pp._session_writes_and_start(sid)
        else:
            had_write, start = False, None
        if not had_write:
            had_write = pp._git_session_edit(start)
        ctx["had_edits"] = bool(had_write)
        ctx["pipeline_used"] = pp._pipeline_used_since(start) if had_write else True
    except Exception:
        pass

    # Сигнал 1С-task-completion — ЕДИНЫЙ источник: oc.evaluate_completion (P0.1, инцидент G-1).
    # До P0.1 build_context дублировал _collect_signals и НЕ учитывал Sonar/side-effects (LOOPS.md,
    # advisory-event) → при GATE_ORCHESTRATOR_ENABLE=1 Sonar-энфорсмент/окно ADR-035 были мертвы.
    # Теперь оркестратор зовёт ту же функцию, что и живой хук → block-решения совпадают (parity).
    try:
        ostart = oc._session_start(sid)
        # apply_side_effects=True: оркестратор — активный путь завершения при ENABLE=1
        # (живой onec-хук уступает early-return'ом) → LOOPS.md + advisory-event пишутся здесь.
        res = oc.evaluate_completion(
            oc.PROJECT_ROOT, ostart, transcript_path, apply_side_effects=True
        )
        if res is None:
            ctx["is_1c"] = False
        else:
            sig = res.get("sig", {})
            ctx["is_1c"] = True
            ctx["onec_result"] = res  # несёт hard_ok + rich reason + sonar-вердикт
            ctx["config_edit"] = sig.get("config_edit", False)
            ctx["recall"] = sig.get("recall", False)
            ctx["capture"] = sig.get("capture", False)
            ctx["research"] = sig.get("research", False)
            ctx["skill"] = sig.get("skill", False)
    except Exception as e:
        _log_degraded(
            "build_context:onec-eval", e
        )  # P1.8: сбой 1С-оценки → safe-allow виден в аудите
    return ctx


def pipeline_policy(ctx):
    """ADR-018: правки кода без использования пайплайна → deny."""
    if os.environ.get("PIPELINE_PROTOCOL_DISABLE") == "1":
        return decision("pipeline-protocol", True, "opt-out")
    if not ctx.get("sid"):
        return decision("pipeline-protocol", True, "нет session_id")
    if not ctx.get("had_edits"):
        return decision("pipeline-protocol", True, "нет правок за сессию (carve-out)")
    if ctx.get("pipeline_used"):
        return decision("pipeline-protocol", True, "пайплайн использован")
    return decision("pipeline-protocol", False, "правки кода без пайплайна (ADR-018)")


def onec_completion_policy(ctx):
    """1С-задача с незакрытыми обязательными петлями → deny. ЕДИНЫЙ вердикт из
    ``oc.evaluate_completion`` (ctx['onec_result']) — вкл. Sonar/toolgate-hard (P0.1);
    legacy-fallback на recall/capture/research, если контекст без onec_result (старые тесты)."""
    if os.environ.get("ONEC_TASK_GATE_DISABLE") == "1":
        return decision("onec-task-completion", True, "opt-out")
    if not ctx.get("is_1c"):
        return decision("onec-task-completion", True, "1С-задачи нет")
    # Основной путь: вердикт single-source (тот же, что у живого хука) — parity by construction.
    res = ctx.get("onec_result")
    if res is not None:
        sig = res.get("sig", {})
        if res.get("hard_ok"):
            return decision("onec-task-completion", True, "обязательные петли закрыты")
        return decision(
            "onec-task-completion",
            False,
            res.get("reason") or "незакрыты обязательные петли",
            recall=sig.get("recall"),
            capture=sig.get("capture"),
            research=sig.get("research"),
            sonar_rescan=sig.get("sonar_rescan"),
            skill=sig.get("skill"),
        )
    # Legacy-fallback (плоский ctx без onec_result): прежняя логика recall/capture/research.
    if ctx.get("recall") and ctx.get("capture") and ctx.get("research"):
        return decision("onec-task-completion", True, "обязательные петли закрыты")
    miss = [k for k in ("recall", "capture", "research") if not ctx.get(k)]
    return decision(
        "onec-task-completion",
        False,
        "незакрыты обязательные петли: " + ", ".join(miss),
        recall=ctx.get("recall"),
        capture=ctx.get("capture"),
        research=ctx.get("research"),
        skill=ctx.get("skill"),
    )


# Реестр политик оркестратора (порядок = порядок в консолидированном блоке)
DEFAULT_POLICIES = [pipeline_policy, onec_completion_policy]
