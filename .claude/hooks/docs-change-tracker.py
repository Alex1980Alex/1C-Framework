#!/usr/bin/env python3
"""
Hook: docs-change-tracker
Event: PostToolUse
Matcher: Write
Purpose: When files in key directories change, remind to update
         the corresponding documentation in docs/architecture/.
         Creates mandatory task in hook-todos.json.
Timeout: 3s
"""

import sys
import os

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput
from shared.task_master import add_task, has_recent_completion, get_pending_tasks

HOOK_ID = "docs-change-tracker-hook"

# (path_pattern, doc_file, area_label, update_hints)
_PATH_TO_DOC = [
    (
        ".claude/hooks/",
        "docs/architecture/hooks-reference.md",
        "hooks",
        "- Проверь что hook описан в таблице\n"
        "- Обнови event/matcher/назначение если изменились\n"
        "- Обнови счётчик hooks в overview.md",
    ),
    (
        ".claude/skills/",
        "docs/architecture/skills-reference.md",
        "skills",
        "- Проверь что skill описан в таблице\n"
        "- Обнови trigger/тип/описание если изменились\n"
        "- Обнови счётчик skills в overview.md",
    ),
    (
        ".claude/settings",
        "docs/architecture/core-framework-separation.md",
        "settings",
        "- Проверь что регистрация hooks актуальна\n"
        "- Обнови структуру .claude/ если добавлены файлы",
    ),
    (
        "src/pdf_framework/search/",
        "docs/architecture/overview.md",
        "search",
        "- Обнови секцию Search Strategies/Pipelines\n"
        "- Обнови секцию Search в Data Flows",
    ),
    (
        "src/pdf_framework/agents/",
        "docs/architecture/overview.md",
        "agents",
        "- Обнови секцию RAG Agent\n"
        "- Обнови Components если добавлен agent",
    ),
    (
        "src/pdf_framework/config/",
        "docs/architecture/overview.md",
        "config",
        "- Обнови секцию Configuration\n"
        "- Обнови env variables если добавлены",
    ),
    (
        "src/pdf_framework/loaders/",
        "docs/architecture/overview.md",
        "loaders",
        "- Обнови секцию Indexing в Data Flows\n"
        "- Обнови Components если изменён loader",
    ),
    (
        "src/api/routes/",
        "docs/architecture/overview.md",
        "api routes",
        "- Обнови Project Structure\n"
        "- Обнови API docs если новый endpoint",
    ),
]

# Skip patterns — not real code changes
_SKIP_PATTERNS = [
    "/cache/",
    "/__pycache__/",
    "_index.json",
    "_topic_template.md",
    "/docs/architecture/",
    "/docs/roadmap/",
    "/memory/",
]


class DocsChangeTracker(BaseHook):
    """Remind to update docs when key files change."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name != "Write":
            return None

        tool_input = inp.tool_input
        file_path = ""
        if isinstance(tool_input, dict):
            file_path = tool_input.get("file_path", "")
        elif isinstance(tool_input, str):
            file_path = tool_input

        if not file_path:
            return None

        path_norm = file_path.replace("\\", "/").lower()

        # Skip docs themselves (avoid recursion)
        for skip in _SKIP_PATTERNS:
            if skip in path_norm:
                return None

        # Find matching doc
        for pattern, doc_file, area, hints in _PATH_TO_DOC:
            if pattern.replace("\\", "/").lower() in path_norm:
                return self._remind(file_path, doc_file, area, hints)

        return None

    def _remind(self, changed_file, doc_file, area, hints):
        """Create task and return systemMessage."""
        if has_recent_completion(HOOK_ID, cooldown_minutes=5):
            return None

        pending = get_pending_tasks(created_by=HOOK_ID)
        if len(pending) >= 3:
            return None

        basename = os.path.basename(changed_file)
        add_task(
            title=f"Обновить {doc_file} (изменён {area})",
            description=(
                f"Файл {basename} изменён.\n"
                f"Обнови документацию: {doc_file}\n"
                f"{hints}"
            ),
            priority="normal",
            created_by=HOOK_ID,
        )

        return HookOutput().system_message(
            f"[DOCS-TRACKER] Изменён файл в {area}: {basename}\n"
            f"ОБЯЗАТЕЛЬНО обнови {doc_file}:\n"
            f"{hints}"
        )


if __name__ == "__main__":
    DocsChangeTracker().run()
