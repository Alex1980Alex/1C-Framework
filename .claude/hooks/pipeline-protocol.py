#!/usr/bin/env python3
"""
Hook: pipeline-protocol
Event: UserPromptSubmit
Matcher: (none — fires on every prompt)
Purpose: ADR-018 — делает generic 4-этапный пайплайн (ADR-017) ОБЯЗАТЕЛЬНОЙ
  парадигмой работы. Для запросов, меняющих код/файлы, инъектит mandatory-инструкцию
  вести работу через `pipeline/<slug>/` с артефактом на каждый этап. Чистые вопросы/
  ответы без правок — exempt (иначе хук заблокировал бы даже обычный ответ).
  «Зубы» (hard-block завершения) — в pipeline-protocol-stop.py (Stop).
Timeout: 3s
Opt-out: PIPELINE_PROTOCOL_DISABLE=1
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

_MSG = (
    "[PIPELINE-PROTOCOL · ОБЯЗАТЕЛЬНО (ADR-018)] Если этот запрос меняет код/файлы — "
    "веди работу через пайплайн (Планирование→Дизайн→Кодирование→Тестирование), "
    "артефакт на каждый этап:\n"
    '1) init: `.venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py init <slug> --title "..."`\n'
    "2) trivial (<1 файла) → один компактный `pipeline/<slug>/pipeline.md` (4 секции), дизайн авто-одобрен;\n"
    "   medium/complex → `01-architecture` → `02-design` → ПАУЗА на approve пользователя "
    "(`pipeline_state.py approve <slug>`) → `03-implementation` → `04-testing`.\n"
    "3) Закрывай этапы: `pipeline_state.py done <slug> <N> <файл>`.\n"
    "Чистые вопросы/ответы без правок кода — пайплайн НЕ нужен. Stop-хук блокирует завершение "
    "задачи с правками без пайплайна. Аварийный обход: PIPELINE_PROTOCOL_DISABLE=1."
)


class PipelineProtocol(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("PIPELINE_PROTOCOL_DISABLE") == "1":
            return None
        if not (inp.prompt or "").strip():
            return None
        return HookOutput().system_message(_MSG)


if __name__ == "__main__":
    PipelineProtocol().run()
