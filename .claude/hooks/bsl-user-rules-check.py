#!/usr/bin/env python3
"""
Hook: bsl-user-rules-check
Event: PostToolUse
Matcher: Write|Edit|mcp__edt-mcp__write_module_source
Purpose: Advisory-линтер свода правил пользователя по добавленному BSL-коду
         (СтрШаблон вместо конкатенации, предопределённые вместо кодов-литералов,
         БСП вместо устаревших глобальных, ВТ вместо подзапроса в ИЗ и др.).
         Замечания возвращаются Claude в тот же ход - до Sonar и до пользователя.
         НИКОГДА не блокирует. Полный свод: bsl-development SKILL.md.
Timeout: 5s

Слой 1 механизма «фидбэк по 1С-коду → машинная проверка» (roadmap 260724 В-6;
корень рецидивов: память всплывает по семантике запроса, а не в момент
генерации кода - линтер срабатывает всегда).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.bsl_user_rules import _JIRA_MARKER, check_fragment, format_findings


class BslUserRulesCheck(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        tool = inp.tool_name or ""
        tool_input = inp.tool_input or {}

        if tool in ("Write", "Edit"):
            path = str(tool_input.get("file_path", ""))
            if not path.lower().endswith(".bsl"):
                return None
            if tool == "Write":
                text = str(tool_input.get("content", ""))
                is_fragment = False
            else:
                text = str(tool_input.get("new_string", ""))
                is_fragment = True
            label = os.path.basename(path)
        elif tool == "mcp__edt-mcp__write_module_source":
            path = str(tool_input.get("modulePath", "") or tool_input.get("objectName", ""))
            if path and not path.lower().endswith(".bsl") and "modulePath" in tool_input:
                return None
            text = str(tool_input.get("source", ""))
            is_fragment = str(tool_input.get("mode", "searchReplace")) != "replace"
            label = os.path.basename(path) if path else "write_module_source"
        else:
            return None

        if not text.strip():
            return None

        findings = check_fragment(text, is_fragment=is_fragment)

        # The replaced (old) fragment may already carry the JIRA marker just
        # outside the edited window - do not nag about it again (review rec.6).
        old_text = str(tool_input.get("old_string", "") or tool_input.get("oldSource", ""))
        if old_text and _JIRA_MARKER.search(old_text):
            findings = [f for f in findings if f["rule"] != "jira-task-markers"]

        if not findings:
            return None

        msg = format_findings(findings, label)
        # PostToolUse: модель видит hookSpecificOutput.additionalContext
        # (hook_context) - systemMessage здесь user-facing. Dual-emit: замечания
        # доходят и до Claude в тот же ход, и до пользователя (review fix 1).
        return HookOutput().hook_context(msg).system_message(msg)


if __name__ == "__main__":
    BslUserRulesCheck().run()
