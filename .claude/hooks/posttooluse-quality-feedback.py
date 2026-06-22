#!/usr/bin/env python3
"""
Hook: posttooluse-quality-feedback
Event: PostToolUse
Matcher: Write|Edit
Purpose: Run ruff check on *.py files after Write/Edit and report errors
         back to Claude via hookSpecificOutput. Only fires for Python files.
Timeout: 5s
"""

import json
import os
import subprocess
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


def _run_ruff(file_path: str) -> list[dict] | None:
    """Run ruff check on a file. Returns list of issues or None on error."""
    project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
    venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    venv_ruff = os.path.join(project_dir, ".venv", "Scripts", "ruff.exe")

    # Prefer ruff executable, fallback to python -m ruff
    if os.path.isfile(venv_ruff):
        cmd = [venv_ruff, "check", "--output-format=json", file_path]
    elif os.path.isfile(venv_python):
        cmd = [venv_python, "-m", "ruff", "check", "--output-format=json", file_path]
    else:
        return None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            cwd=project_dir,
        )
        # ruff exits 0 if no issues, 1 if issues found, 2 on error
        if result.returncode == 2:
            return None
        if result.stdout.strip():
            issues = json.loads(result.stdout)
            return issues if isinstance(issues, list) else None
        return []
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return None


def _spawn_bsl_format(file_path: str) -> bool:
    """ADR-036: авто-форматирование BSL — bsl_lint.py --format (in-place, идемпотентно).

    Запускается ДЕТАЧЕНО (Popen без wait): bsl-ls = JVM, cold-start легко >5s timeout хука,
    поэтому форматируем в фоне — хук возвращается мгновенно, формат завершается сам. Best-effort:
    нет venv/скрипта/ошибка spawn → False, никогда не роняет хук. Делает bsl_lint «обязательным
    по построению» (auto), без блокировки (вариант A промоута high-leverage инструментов)."""
    project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
    venv_python = os.path.join(project_dir, ".venv", "Scripts", "python.exe")
    script = os.path.join(project_dir, "scripts", "bsl_lint.py")
    if not (os.path.isfile(venv_python) and os.path.isfile(script)):
        return False
    try:
        kwargs = {
            "cwd": project_dir,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if os.name == "nt":
            # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP — переживает возврат хука
            kwargs["creationflags"] = 0x00000008 | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([venv_python, script, file_path, "--format"], **kwargs)
        return True
    except OSError:
        return False


class PostToolUseQualityFeedback(BaseHook):
    """PostToolUse hook for Write|Edit: run ruff on *.py files."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        tool_input = inp.tool_input
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, AttributeError):
                return None

        if not isinstance(tool_input, dict):
            return None

        file_path = tool_input.get("file_path", "")
        if not file_path:
            return None

        normalized = file_path.replace("\\", "/")

        # ADR-036: BSL-файлы → авто-формат (bsl_lint --format, детачено). Вендорные деревья
        # (reference-конфиги ERP/УТ, tools/) НЕ форматируем. Конфигурация/гкс_-код — да.
        if normalized.endswith(".bsl"):
            if not os.path.isfile(file_path):
                return None
            if any(s in normalized for s in ("/external/", "/tools/")):
                return None
            if _spawn_bsl_format(file_path):
                return HookOutput().hook_context(
                    "[bsl-format] авто-форматирование (bsl_lint --format) запущено фоном — "
                    "идемпотентно, форматированная версия попадёт в коммит (ADR-036)"
                )
            return None

        # Only Python files
        if not file_path.replace("\\", "/").endswith(".py"):
            return None

        # Skip non-project files (normalized уже вычислен выше)
        skip = (
            ".claude/cache/",
            ".claude/hooks/",
            "__pycache__",
            ".venv/",
            "node_modules/",
            "build/",
            "dist/",
        )
        if any(s in normalized for s in skip):
            return None

        # File must exist (Write creates it, Edit modifies)
        if not os.path.isfile(file_path):
            return None

        issues = _run_ruff(file_path)
        if issues is None:
            return None  # ruff unavailable or errored

        if not issues:
            return None  # No issues found

        # Build feedback message
        error_count = 0
        warning_count = 0
        lines = []
        for issue in issues[:10]:  # Max 10 issues to avoid feedback bloat
            loc = f"{issue.get('location', {}).get('row', '?')}"
            code = issue.get("code", "")
            msg = issue.get("message", "")
            severity = "E" if code.startswith("E") or code.startswith("F") else "W"
            if severity == "E":
                error_count += 1
            else:
                warning_count += 1
            lines.append(f"  L{loc} [{code}] {msg}")

        fname = os.path.basename(file_path)
        summary = (
            f"[quality-feedback] ruff found "
            f"{error_count} errors, {warning_count} "
            f"warnings in {fname}:\n"
        )
        summary += "\n".join(lines)
        if len(issues) > 10:
            summary += f"\n  ... and {len(issues) - 10} more issues"

        return HookOutput().hook_context(summary)


if __name__ == "__main__":
    PostToolUseQualityFeedback().run()
