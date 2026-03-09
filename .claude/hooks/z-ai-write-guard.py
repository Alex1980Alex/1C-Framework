#!/usr/bin/env python3
"""
Hook: z-ai-write-guard
Event: PreToolUse
Matcher: Write
Purpose: Block Write of >30 lines of code if Z.AI (llm_complete) was not
         used in this session. Enforces Token Economy protocol.
Timeout: 3s

Pattern: Enforcer (blocks until condition met).

Flow:
  1. Write fires → extract file_path and content from tool_input
  2. Skip non-code files (.md, .json, .yml, .env, .toml, .txt, .csv, .html)
  3. Skip exempt paths (.claude/, docs/, data/, tests/)
  4. Count lines in content
  5. If lines > 30 AND no llm_delegation in session → block with Z.AI instructions
  6. Otherwise → allow
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# Code file extensions that trigger the guard
_CODE_EXTENSIONS = {
    ".py", ".ts", ".js", ".tsx", ".jsx", ".bsl", ".os",
    ".java", ".go", ".rs", ".rb", ".php", ".cs", ".swift",
}

# Non-code extensions — always skip
_SKIP_EXTENSIONS = {
    ".md", ".json", ".yml", ".yaml", ".toml", ".env", ".txt",
    ".csv", ".html", ".css", ".xml", ".ini", ".cfg", ".lock",
    ".gitignore", ".editorconfig", ".log", ".sql",
}

# Exempt directory prefixes — skip enforcement
_EXEMPT_PREFIXES = [
    ".claude/",
    "docs/",
    "data/",
]

# Line threshold for delegation
_LINE_THRESHOLD = 30


class ZAIWriteGuard(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_input = inp.tool_input or {}
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")

        if not file_path or not content:
            return None

        # Normalize path
        fp = file_path.replace("\\", "/").lower()

        # Extract extension
        _, ext = os.path.splitext(fp)

        # Skip non-code files
        if ext in _SKIP_EXTENSIONS or ext not in _CODE_EXTENSIONS:
            return None

        # Skip exempt directories
        for prefix in _EXEMPT_PREFIXES:
            if prefix in fp:
                return None

        # Count lines
        line_count = content.count("\n") + 1

        if line_count <= _LINE_THRESHOLD:
            return None

        # Check if Z.AI was used in this session
        try:
            from shared.session_state import SessionState
            if SessionState.has_llm_delegation():
                return None  # Z.AI was used — allow
        except Exception:
            return None  # Graceful degradation

        # Block: large code write without Z.AI delegation
        return HookOutput().block(
            f"[Z.AI WRITE GUARD] Запись {line_count} строк кода без делегирования на Z.AI.\n"
            f"Файл: {os.path.basename(file_path)}\n\n"
            "Token Economy protocol требует делегировать генерацию >30 строк:\n"
            "1. Подготовь промпт с задачей + контекстом + форматом\n"
            "2. mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)\n"
            "3. Отревьюй результат, исправь если нужно\n"
            "4. Write() финальный код\n\n"
            "Полный протокол: Skill('z-ai-delegation')\n"
            "Если Z.AI недоступен — вызови llm_complete с любым prompt чтобы разблокировать."
        )


if __name__ == "__main__":
    ZAIWriteGuard().run()
