#!/usr/bin/env python3
"""
Hook: pipeline-1c-advance
Event: PostToolUse
Matcher: Write|Edit
Purpose: Двигает этапы 1С-пайплайна по записи 1С-артефактов (ADR-019 B′ F-1.5):
         ANALYSIS-REPORT → этапы 1,2 (Планирование+Дизайн); IMPLEMENTATION-PROGRESS
         → этап 3 (Кодирование). best-effort, НЕ блокирует. Guard в
         `pipeline_1c_bridge.advance_for_artifact` режет не-1С пайплайны.
Timeout: 5s
"""

import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput


def _completeness_note(path: str) -> str:
    """Advisory: полнота 1С-артефакта по конвенции (lint_1c_artifacts) — НЕ блок, нудж к шаблону.

    Корень пробела: run-1c-task давал тонкие ANALYSIS-REPORT/IMPLEMENTATION-PROGRESS, ничто не
    проверяло структуру. Здесь — мягкое предупреждение о недостающих core-секциях. best-effort → ''.
    opt-out ARTIFACT_LINT_DISABLE=1."""
    if os.environ.get("ARTIFACT_LINT_DISABLE") == "1":
        return ""
    name = os.path.basename(path).upper()
    if "ANALYSIS-REPORT" not in name and "IMPLEMENTATION-PROGRESS" not in name:
        return ""
    try:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        lint_path = os.path.join(root, "scripts", "lint_1c_artifacts.py")
        spec = importlib.util.spec_from_file_location("_lint_1c_for_advance", lint_path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        res = m.lint_file(path)
        # нудж только для «созревшего, но неполного» (score 30–69); stub (<30) = ещё пишется → молчим
        # (снижает дребезг на инкрементальной записи, code-verify ade29e8e Rec 2).
        if res.get("ok") or res.get("score", 0) < 30:
            return ""
        miss = ", ".join(res.get("missing", [])[:6])
        return (
            f"\n[artifact-lint] ⚠ {res['kind']} неполон (score {res['score']}/100). Отсутствуют секции: "
            f"{miss}. Дополни по шаблону analyze-1c-task-v2 §1-§11 / implement-1c-task "
            f"(advisory, продвижение НЕ блокируется; opt-out ARTIFACT_LINT_DISABLE=1)."
        )
    except Exception:
        return ""


class Pipeline1CAdvance(BaseHook):
    HOOK_NAME = "Pipeline1CAdvance"

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name not in ("Write", "Edit", "MultiEdit"):
            return None
        ti = inp.tool_input or {}
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        if not path:
            return None

        from shared.pipeline_1c_bridge import advance_for_artifact, advance_test_done

        # F-1.5 + F-1.6: звать ОБА (не `or`) — IMPLEMENTATION-PROGRESS с секцией live-данных PASS
        # двигает этап 3 (advance_for_artifact) И этап 4 (advance_test_done, ADR-050) ОДНОЙ записью;
        # `or` закорачивал бы этап-4-путь. Оба идемпотентны; сливаем реально продвинутые этапы.
        adv_artifact = advance_for_artifact(path)
        adv_test = advance_test_done(path)
        adv = tuple(sorted({*(adv_artifact or ()), *(adv_test or ())})) or None
        note = _completeness_note(path)  # D: advisory-валидатор секций (не блок)
        if adv or note:
            msg = (
                f"[pipeline-1c-advance] этап(ы) {adv} → done (1С-пайплайн, ADR-019 F-1.5/F-1.6)"
                if adv
                else ""
            )
            return HookOutput().system_message((msg + note).strip())
        return None


if __name__ == "__main__":
    Pipeline1CAdvance().run()
