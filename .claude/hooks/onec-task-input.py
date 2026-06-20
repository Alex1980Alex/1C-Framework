#!/usr/bin/env python3
"""
Hook: onec-task-input
Event: UserPromptSubmit
Matcher: (none — content-based, fires on 1С-task chat prompts)
Purpose: input-ingestion (V.6/G20–G23, roadmap 260614) + маршрутизация по сложности (2026-06-15).
         Когда 1С-задача приходит ИЗ ЧАТА (не слэш-команда):
           1) детект 1С + тип (T1/T2/T3) + оценка трудозатрат (простая/средняя/сложная);
           2) РЕКОМЕНДАЦИЯ потока: простая→`/run-1c-task` (AUTO), средняя→спросить,
              сложная→гейтованный `/analyze`+`/implement`; не-1С/сомнение → спросить;
           3) V.6: ASK-если-неоднозначно, folder-rules, prior-load для T3.
         best-effort, advisory (НЕ блокирует). Эвристика < правило пользователя «сомнение → спросить».
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
        from shared.pipeline_1c_bridge import route_1c_task

        r = route_1c_task(prompt)
        flow = r.get("flow")
        if flow == "none":
            return None  # не 1С-задача

        ttype = r.get("ttype")
        comp = r.get("complexity")
        pts = r.get("points")
        parts = [
            f"[onec-task-input] 1С-задача из чата (тип ≈ {ttype} {_TDESC.get(ttype, '')}, "
            f"сложность ≈ {comp}/{pts} трудозатрат)."
        ]

        if flow == "ask_1c":
            parts.append(
                "• 1С-сигнал слабый/без JIRA → ПОДТВЕРДИ у пользователя: это задача по 1С? Если да — "
                "новая отдельная ИЛИ доработка/багфикс существующего? (не угадывай)"
            )
            parts.append(
                "• standalone → создай папку `configuration/260304…/docs/<YYMMDD_slug>/` "
                "(spec из чата + скриншоты) и веди по 4 этапам"
            )
        elif flow == "auto":
            parts.append(
                "• МАРШРУТ: простая → запусти **`/run-1c-task`** (AUTO: analyze→approve→implement→test, без паузы на ревью)."
            )
        elif flow == "ask_action":
            parts.append(
                "• МАРШРУТ: 1С-контекст распознан, но ДЕЙСТВИЕ не названо (нет таск-глагола/scope) — "
                "НЕ запускай **`/run-1c-task`**; СПРОСИ у пользователя, что именно сделать."
            )
        elif flow == "ask_flow":
            parts.append(
                "• МАРШРУТ: средней сложности → СПРОСИ пользователя: **`/run-1c-task`** (AUTO) ИЛИ "
                "гейтованный **`/analyze-1c-task`** → ревью → **`/implement-1c-task`**?"
            )
        elif flow == "gated":
            parts.append(
                "• МАРШРУТ: сложная → гейтованный поток **`/analyze-1c-task`** → ревью ANALYSIS-REPORT → "
                "**`/implement-1c-task`** (контроль анализа перед кодом)."
            )

        if r.get("jira"):
            parts.append(
                f"• JIRA {r.get('jira')} — собери ВСЕ артефакты папки (spec + скриншоты + чат-диалог + история), не один *ТЗ*.md"
            )
        if ttype == "T2":
            parts.append(
                "• T2: Планирование сжато (root-cause + точка фикса), Тестирование критично (регресс)"
            )
        if ttype == "T3":
            parts.append(
                "• T3: загрузи prior ANALYSIS-REPORT + реализацию родителя как контекст (дельта, НЕ greenfield); "
                "проверь prior-PR (открыт → дельта на ту же ветку)"
            )
        parts.append(
            "• ⚠ Сложность — ЭВРИСТИКА: сомневаешься, 1С ли это / какой поток → СПРОСИ пользователя "
            "(его правило сильнее классификатора)."
        )
        return HookOutput().system_message("\n".join(parts))


if __name__ == "__main__":
    OnecTaskInput().run()
