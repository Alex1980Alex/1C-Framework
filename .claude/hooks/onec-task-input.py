#!/usr/bin/env python3
"""
Hook: onec-task-input
Event: UserPromptSubmit
Matcher: (none — content-based, fires on 1С-task chat prompts)
Purpose: input-ingestion (V.6/G20–G23, roadmap 260614). Когда 1С-задача приходит ИЗ ЧАТА
         (не слэш-команда), инъектит протокол V.6: тип (T1/T2/T3), ASK-если-неоднозначно,
         folder-rules, prior-load для T3. best-effort, НЕ блокирует.
Timeout: 5s
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.slash_detect import detect_slash_command

_TDESC = {"T1": "новое/доработка", "T2": "bugfix", "T3": "не учтено/found-in-testing (ДЕЛЬТА)"}


class OnecTaskInput(BaseHook):
    HOOK_NAME = "OnecTaskInput"

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt or ""
        if detect_slash_command(prompt):
            return None  # слэш-команды ведёт их preflight — не дублируем
        from shared.pipeline_1c_bridge import classify_1c_task

        c = classify_1c_task(prompt)
        if not c.get("is_1c"):
            return None
        ttype = c.get("ttype")
        parts = [f"[onec-task-input] 1С-задача из чата, тип ≈ {ttype} ({_TDESC.get(ttype, ttype)}). Протокол V.6:"]
        if c.get("ask"):
            parts.append(
                "• нет JIRA → УТОЧНИ у пользователя: новая отдельная задача ИЛИ доработка/багфикс существующего ТЗ? (не угадывай)"
            )
            parts.append(
                "• standalone → создай папку `configuration/260304…/docs/<YYMMDD_slug>/` (spec из чата + скриншоты) и веди по 4 этапам"
            )
        else:
            parts.append(
                f"• JIRA {c.get('jira')} — собери ВСЕ артефакты папки (spec + скриншоты + чат-диалог + история), не один *ТЗ*.md"
            )
        if ttype == "T2":
            parts.append("• T2: Планирование сжато (root-cause + точка фикса), Тестирование критично (регресс)")
        if ttype == "T3":
            parts.append(
                "• T3: загрузи prior ANALYSIS-REPORT + реализацию родителя как контекст (дельта, НЕ greenfield); "
                "проверь prior-PR (открыт → дельта на ту же ветку)"
            )
        return HookOutput().system_message("\n".join(parts))


if __name__ == "__main__":
    OnecTaskInput().run()
