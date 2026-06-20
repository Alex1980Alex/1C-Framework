#!/usr/bin/env python3
"""
Hook: onec-state-first-guard
Event: PreToolUse
Matcher: Write|Edit|MultiEdit
Purpose: ADR-026 — state-first enforcement пайплайна 1С. При правке 1С-файла
  (.bsl/.mdo/.form под configuration/ или ИБTransport) БЕЗ активного 1С-pipeline-state
  → ADVISORY-нудж «войди через /run-1c-task или заведи pipeline-state» (43.5 §0.9).
  Закрывает пробел: pipeline-protocol-stop ловит «правки без пайплайна» только на Stop
  (поздно) — этот хук напоминает на ПЕРВОЙ 1С-правке (gate-at-creation, паттерн Kiro/Spec-Kit).
  НИКОГДА не блокирует (advisory; анти-deadlock; §0.6 «сомнение → спросить, не запрещать»).
Timeout: 3s
Opt-out: ONEC_STATE_FIRST_DISABLE=1 → no-op.
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HOOK_DIR))  # .claude/hooks -> repo root

_1C_EXT = (".bsl", ".mdo", ".form")
_1C_TITLE_PREFIX = (
    "1С-задача ("  # единый маркер реальной 1С-задачи (pipeline_1c_bridge.is_1c_task_title)
)
# Деревья конфигураций заказчика (НЕ reference-дампы external/1c-reference-src — это не задачи).
_TASK_TREES = ("configuration/", "transportmanagement", "/конфигурация/")


def _is_1c_file(fp: str) -> bool:
    """1С-файл задачи: расширение EDT (.bsl/.mdo/.form) под деревом конфигурации заказчика."""
    low = (fp or "").replace("\\", "/").lower()
    if not low.endswith(_1C_EXT):
        return False
    return any(t in low for t in _TASK_TREES)


def _has_active_1c_pipeline() -> bool:
    """True, если есть НЕЗАВЕРШЁННЫЙ 1С-pipeline-state (title '1С-задача (', current_stage<5).

    Best-effort: любая ошибка чтения → пропуск записи; не нашли → False (нудж не опаснее
    ложного молчания). Источники state: generic-слот pipeline/<slug>/ + папки задач из
    реестра pipeline/_1c_index.json (relocate-on-artifact, 43.5 §0.9).
    """
    states: set[str] = set(
        glob.glob(os.path.join(PROJECT_ROOT, "pipeline", "*", ".pipeline-state.json"))
    )
    idx = os.path.join(PROJECT_ROOT, "pipeline", "_1c_index.json")
    try:
        if os.path.exists(idx):
            with open(idx, encoding="utf-8") as f:
                reg = json.load(f)
            for v in (reg or {}).values():
                folder = (
                    v if isinstance(v, str) else (v.get("folder") if isinstance(v, dict) else None)
                )
                if folder:
                    states.add(os.path.join(folder, ".pipeline-state.json"))
    except Exception:
        pass

    for sp in states:
        try:
            with open(sp, encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            continue
        if (
            str(st.get("title", "")).startswith(_1C_TITLE_PREFIX)
            and int(st.get("current_stage", 5)) < 5
        ):
            return True
    return False


class OnecStateFirstGuard(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("ONEC_STATE_FIRST_DISABLE") == "1":
            return None
        if inp.tool_name not in ("Write", "Edit", "MultiEdit"):
            return None

        fp = inp.tool_input.get("file_path") or ""
        if not _is_1c_file(fp):
            return None
        if _has_active_1c_pipeline():
            return None  # state-first соблюдён — молчим

        return HookOutput().system_message(
            "[1C-STATE-FIRST] Правка 1С-файла без активного pipeline-state. По парадигме "
            "пайплайна 1С (гл. 43.5 §0.9, ADR-026) веди задачу СОСТОЯНИЕМ-ПЕРВЫМ: войди через "
            "/run-1c-task (AUTO) или /analyze-1c-task (гейт) — preflight заведёт pipeline-state в "
            "папке задачи; либо подхвати существующую задачу configuration/<JIRA>/docs/. "
            "Сомнение (новая/продолжение) → спроси. Advisory — правка НЕ заблокирована. "
            "Opt-out: ONEC_STATE_FIRST_DISABLE=1."
        )


if __name__ == "__main__":
    OnecStateFirstGuard().run()
