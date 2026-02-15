#!/usr/bin/env python3
"""
Hook: document-persistence
Event: UserPromptSubmit
Purpose: When user asks for a roadmap, plan, analysis, or decomposition,
         inject systemMessage telling Claude to ALWAYS save the result
         to an appropriate file, not just display in chat.

Pattern: "Auto-Save Structured Documents"
- Roadmaps -> docs/roadmap/<name>.md
- Analysis -> docs/analysis/<name>.md
- Plans (implementation) -> docs/plans/<name>.md
- Decomposition -> docs/roadmap/<name>.md

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


class DocumentPersistence(BaseHook):
    """Ensure structured documents (roadmaps, plans, analysis) are saved to files."""

    # Document type detection: keywords -> (type_label, save_path, file_prefix)
    DOCUMENT_TYPES = {
        "roadmap": {
            "keywords": [
                "дорожная карта", "дорожную карту", "roadmap",
                "план развития", "план улучшений",
            ],
            "path": "docs/roadmap/",
            "label": "дорожная карта",
        },
        "plan": {
            "keywords": [
                "план реализации", "план внедрения",
                "implementation plan", "план работ",
                "план миграции",
            ],
            "path": "docs/plans/",
            "label": "план реализации",
        },
        "analysis": {
            "keywords": [
                "глубокий анализ", "детальный анализ",
                "deep analysis", "gap analysis",
                "сравнительный анализ", "аудит",
            ],
            "path": "docs/analysis/",
            "label": "анализ",
        },
        "decomposition": {
            "keywords": [
                "декомпозиция", "decomposition",
                "максимальная декомпозиция",
                "разбей на задачи", "разбить на шаги",
            ],
            "path": "docs/roadmap/",
            "label": "декомпозиция",
        },
    }

    # Amplifiers: if these appear with document keywords, increase confidence
    AMPLIFIERS = [
        "создай", "сделай", "подготовь", "составь",
        "напиши", "сформируй", "разработай",
        "create", "make", "prepare", "write",
    ]

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt) < 10:
            return None

        prompt_lower = prompt.lower()

        # Detect document type
        matched_types = []
        for doc_type, config in self.DOCUMENT_TYPES.items():
            for kw in config["keywords"]:
                if kw in prompt_lower:
                    matched_types.append((doc_type, config))
                    break

        if not matched_types:
            return None

        # Check for amplifiers (optional, increases confidence)
        has_amplifier = any(a in prompt_lower for a in self.AMPLIFIERS)

        # Build save instructions
        save_instructions = []
        for doc_type, config in matched_types:
            save_instructions.append(
                f"- {config['label']} → `{config['path']}<имя>.md`"
            )

        paths = " или ".join(
            f"`{c['path']}`" for _, c in matched_types
        )

        msg = (
            f"[DOC-PERSISTENCE] Обнаружен запрос на создание структурированного документа.\n"
            f"ОБЯЗАТЕЛЬНО сохрани результат в файл:\n"
            + "\n".join(save_instructions)
            + "\n\n"
            "Правила:\n"
            "1. НЕ только отображай в чате — ВСЕГДА сохраняй в файл\n"
            "2. Имя файла: SCREAMING_SNAKE_CASE (например SKILL_ROUTER_ROADMAP.md)\n"
            "3. Включи заголовок с датой и статусом\n"
            "4. Файл должен быть самодостаточным (без ссылок на \"см. чат выше\")"
        )

        return HookOutput().system_message(msg)


if __name__ == "__main__":
    DocumentPersistence().run()
