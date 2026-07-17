#!/usr/bin/env python3
"""
Hook: z-ai-write-guard
Event: PreToolUse
Matcher: Write|Edit
Purpose: Block Write/Edit of >15 lines of code if Z.AI (llm_complete) was not
         used in this session. Enforces Token Economy protocol (strict mode).
Timeout: 3s

Pattern: Enforcer (blocks until condition met).

Scope: SHIPPED code only. Anything outside the repo root is skipped — the session
scratchpad holds throwaway one-shot tooling that is neither shipped nor worth a
delegation round-trip (2026-07-17).

Flow:
  1. Write/Edit fires → extract file_path and content/new_string from tool_input
  2. Skip paths outside the repo root (scratchpad / temp tooling)
  3. Skip non-code files (.md, .json, .yml, .env, .toml, .txt, .csv, .html)
  4. Skip exempt paths (.claude/, docs/, data/, tests/ — NOT pipeline/, see NB below)
  5. Count lines in content (Write) or new_string (Edit)
  6. If lines > 15 AND no llm_delegation in session → block with Z.AI instructions
  7. Otherwise → allow

Large .md (>50 lines) is enforced even under docs/ — long prose IS delegatable —
except under .claude/ and pipeline/ (_MD_EXEMPT_PREFIXES): ADR-018 makes pipeline
artefacts mandatory, so blocking them pitted this guard against pipeline-protocol-stop.

Tests: tests/unit/hooks/test_z_ai_write_guard_scope.py (both exemptions are narrow —
src/ and large docs/*.md must still block).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Code file extensions that trigger the guard
_CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".js",
    ".tsx",
    ".jsx",
    ".bsl",
    ".os",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cs",
    ".swift",
}

# Non-code extensions — always skip
_SKIP_EXTENSIONS = {
    ".md",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".env",
    ".txt",
    ".csv",
    ".html",
    ".css",
    ".xml",
    ".ini",
    ".cfg",
    ".lock",
    ".gitignore",
    ".editorconfig",
    ".log",
    ".sql",
}

# Exempt directory prefixes — skip enforcement
_EXEMPT_PREFIXES = [
    ".claude/",
    "docs/",
    "data/",
    "tests/",  # test code is precision work (exact signatures/fixtures), not delegatable generation
]
# NB: "pipeline/" deliberately NOT here. These prefixes are matched as substrings
# (`f"/{p}" in fp`), so it would also exempt infra/pipeline/**/*.py — 127 tracked
# product files — and it is unreachable for the ADR-018 motive anyway: .md is in
# _SKIP_EXTENSIONS and returns earlier. _MD_EXEMPT_PREFIXES alone closes that conflict.

# Prefixes where a large .md is NOT delegatable prose.
# pipeline/: ADR-018 makes these artefacts MANDATORY (pipeline-protocol-stop hard-blocks
# completion without them), so blocking the write here pitted two enforcers against each
# other — one demanding a file the other forbade. docs-change-enforcer already treats
# pipeline/ as process artefacts, not product (its own SKIP_PATTERNS).
_MD_EXEMPT_PREFIXES = [".claude/", "pipeline/"]

# Paths within data/ that ARE enforced for large .md files (not exempt)
_ENFORCED_DATA_PATHS = [
    "data/analyze-1c-research/",
]

# Line threshold for delegation (strict: 15 lines forces more through Z.AI)
_LINE_THRESHOLD = 15


class ZAIWriteGuard(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_input = inp.tool_input or {}
        tool_name = inp.tool_name or ""
        file_path = tool_input.get("file_path", "")

        # Write uses "content", Edit uses "new_string"
        if tool_name == "Edit":
            content = tool_input.get("new_string", "")
        else:
            content = tool_input.get("content", "")

        if not file_path or not content:
            return None

        # Outside the repo (session scratchpad, throwaway tooling) → not our business.
        # The guard keeps *shipped* generation off the expensive model; a one-shot script
        # under Temp/claude/**/scratchpad/ is neither shipped nor delegatable — same
        # rationale as the tests/ exemption below. It fired there because the scratchpad
        # lives outside the repo and matches no _EXEMPT_PREFIXES.
        #
        # ValueError from relative_to = "provably outside" → exempt.
        # OSError from resolve = "could not tell" → keep enforcing: for a guard, the
        # unknown must fail closed, or a flaky UNC path becomes a silent bypass.
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = _PROJECT_ROOT / candidate  # else resolve() would anchor on CWD
        try:
            candidate.resolve().relative_to(_PROJECT_ROOT)
        except ValueError:
            return None
        except OSError:
            pass

        # Normalize path
        fp = file_path.replace("\\", "/").lower()

        # Extract extension
        _, ext = os.path.splitext(fp)

        # Count lines early (needed for .md large file check)
        line_count = content.count("\n") + 1

        # Large .md is NOT exempt (long prose IS delegatable) — except under
        # _MD_EXEMPT_PREFIXES (.claude/, pipeline/) and data/.
        # Exception to the exception: specific data/ subdirs ARE enforced (_ENFORCED_DATA_PATHS)
        _LARGE_MD_THRESHOLD = 50
        is_large_md = (
            ext == ".md"
            and line_count > _LARGE_MD_THRESHOLD
            and not any(fp.startswith(p) or f"/{p}" in fp for p in _MD_EXEMPT_PREFIXES)
        )
        # data/ is generally exempt for .md, EXCEPT enforced paths
        if is_large_md and (fp.startswith("data/") or "/data/" in fp):
            is_large_md = any(p in fp for p in _ENFORCED_DATA_PATHS)

        if not is_large_md:
            # Skip non-code files
            if ext in _SKIP_EXTENSIONS or ext not in _CODE_EXTENSIONS:
                return None

            # Skip exempt directories
            for prefix in _EXEMPT_PREFIXES:
                if fp.startswith(prefix) or f"/{prefix}" in fp:
                    return None

        if line_count <= _LINE_THRESHOLD:
            return None

        # Graceful: провайдеры делегирования недоступны → не форсировать futile-вызов
        try:
            from shared.llm_health import is_provider_down

            if is_provider_down():
                return None
        except Exception:
            pass

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
            "Token Economy protocol требует делегировать генерацию >15 строк:\n"
            "1. Подготовь промпт с задачей + контекстом + форматом\n"
            "2. mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)\n"
            "3. Отревьюй результат, исправь если нужно\n"
            "4. Write() финальный код\n\n"
            "Полный протокол: Skill('z-ai-delegation')"
        )


if __name__ == "__main__":
    ZAIWriteGuard().run()
