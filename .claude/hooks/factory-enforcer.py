#!/usr/bin/env python3
"""
Hook: factory-enforcer
Event: PostToolUse
Matcher: Write
Purpose: After Claude writes files to .claude/hooks/ or .claude/skills/,
         create mandatory tasks for Factory Steps 4-5 (connect + verify).
         This closes the gap between entry (decision-to-triad) and exit
         (task-enforcer): without this hook, Claude can create artifacts
         but stop before updating registries and testing.

         Detects:
         - New hook files -> tasks: update settings.json, test with echo
         - New skill files -> tasks: update triad SKILL.md, test triggers
         - New cache files -> no tasks (handled by knowledge-cache-reminder)

Timeout: 5s
"""

import sys
import os

# Core path resolution: find base/ + shared/ in user-level or project-level
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput
from shared.task_master import add_task, has_recent_completion, get_pending_tasks

HOOK_ID = "factory-enforcer-hook"

# Paths that are part of cache workflow (skip — handled elsewhere)
SKIP_PATHS = ["/cache/", "\\cache\\", "_index.json", "_topic_template.md"]


class FactoryEnforcer(BaseHook):
    """Enforce Factory Steps 4-5 after artifact creation."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_name = inp.tool_name
        if tool_name != "Write":
            return None

        # Extract file_path from tool_input
        tool_input = inp.tool_input
        file_path = ""
        if isinstance(tool_input, dict):
            file_path = tool_input.get("file_path", "")
        elif isinstance(tool_input, str):
            file_path = tool_input

        if not file_path:
            return None

        # Normalize path separators for matching
        path_normalized = file_path.replace("\\", "/").lower()

        # Skip cache files (different workflow)
        for skip in SKIP_PATHS:
            if skip.replace("\\", "/").lower() in path_normalized:
                return None

        # --- Detect hook creation ---
        if "/.claude/hooks/" in path_normalized and path_normalized.endswith(".py"):
            return self._enforce_hook_creation(file_path)

        # --- Detect skill creation ---
        if "/.claude/skills/" in path_normalized and path_normalized.endswith(".md"):
            return self._enforce_skill_creation(file_path)

        return None

    def _enforce_hook_creation(self, file_path: str) -> HookOutput | None:
        """Create mandatory tasks for a new hook file."""
        # Cooldown: don't spam on rapid edits to same hook
        if has_recent_completion(HOOK_ID, cooldown_minutes=5):
            return None

        # Don't duplicate if tasks already pending
        pending = get_pending_tasks(created_by=HOOK_ID)
        if len(pending) >= 2:
            return None

        filename = os.path.basename(file_path)

        add_task(
            title=f"ШАГ 4: Зарегистрировать hook {filename}",
            description=(
                f"Артефакт создан: {file_path}\n"
                "Выполнить:\n"
                "1. Добавить в .claude/settings.json (event + matcher + timeout)\n"
                "2. Обновить MANDATORY_HOOKS в task_master.py (если mandatory)\n"
                "3. Обновить MANDATORY_HOOKS в task-enforcer.py (если mandatory)\n"
                "4. Обновить таблицу Hooks в hooks-skills-mcp-triad/SKILL.md\n"
                "5. Обновить MEMORY.md"
            ),
            priority="high",
            created_by=HOOK_ID,
        )

        add_task(
            title=f"ШАГ 5: Верифицировать hook {filename}",
            description=(
                f"Протестировать: echo '{{...}}' | python {file_path}\n"
                "Убедиться: нет ошибок, правильный JSON output"
            ),
            priority="high",
            created_by=HOOK_ID,
        )

        return HookOutput().system_message(
            f"[FACTORY-ENFORCER] Обнаружено создание hook: {filename}\n\n"
            "ОБЯЗАТЕЛЬНО выполни ШАГ 4 (Связывание):\n"
            "1. Зарегистрируй в .claude/settings.json\n"
            "2. Обнови таблицу Hooks в "
            ".claude/skills/hooks-skills-mcp-triad/SKILL.md\n"
            "3. Обнови MEMORY.md\n\n"
            "ОБЯЗАТЕЛЬНО выполни ШАГ 5 (Верификация):\n"
            f"  echo '{{\"tool_name\":\"Write\"}}' | python {filename}\n"
        )

    def _enforce_skill_creation(self, file_path: str) -> HookOutput | None:
        """Create mandatory tasks for a new skill file."""
        if has_recent_completion(HOOK_ID, cooldown_minutes=5):
            return None

        pending = get_pending_tasks(created_by=HOOK_ID)
        if len(pending) >= 2:
            return None

        # Extract skill directory name
        parts = file_path.replace("\\", "/").split("/")
        skill_name = "unknown"
        for i, part in enumerate(parts):
            if part == "skills" and i + 1 < len(parts):
                skill_name = parts[i + 1]
                break

        add_task(
            title=f"ШАГ 4: Зарегистрировать skill {skill_name}",
            description=(
                f"Артефакт создан: {file_path}\n"
                "Выполнить:\n"
                "1. Обновить таблицу Skills в hooks-skills-mcp-triad/SKILL.md\n"
                "2. Обновить MEMORY.md\n"
                "3. Проверить что description содержит триггеры"
            ),
            priority="high",
            created_by=HOOK_ID,
        )

        add_task(
            title=f"ШАГ 5: Верифицировать skill {skill_name}",
            description=(
                "Проверить:\n"
                "1. YAML frontmatter (name, description, triggers)\n"
                "2. Skill загружается Claude Code\n"
                "3. Триггеры из description срабатывают"
            ),
            priority="high",
            created_by=HOOK_ID,
        )

        return HookOutput().system_message(
            f"[FACTORY-ENFORCER] Обнаружено создание skill: {skill_name}\n\n"
            "ОБЯЗАТЕЛЬНО выполни ШАГ 4 (Связывание):\n"
            "1. Обнови таблицу Skills в "
            ".claude/skills/hooks-skills-mcp-triad/SKILL.md\n"
            "2. Обнови MEMORY.md\n"
            "3. Проверь что description содержит триггеры\n\n"
            "ОБЯЗАТЕЛЬНО выполни ШАГ 5 (Верификация):\n"
            f"  Убедись что skill '{skill_name}' появился в списке "
            "доступных skills."
        )


if __name__ == "__main__":
    FactoryEnforcer().run()
