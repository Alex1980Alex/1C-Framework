#!/usr/bin/env python3
"""
Hook: tdd-guard
Event: PreToolUse
Matcher: Write|Edit
Purpose: 260613 Этап 4.2 (ADR-015) — opt-in red-first nudge для Python.
  При TDD_GUARD_ENABLE=1 и правке production `src/**.py`, добавляющей def/class БЕЗ
  соответствующего теста → ADVISORY system_message (НЕ блок). Default (env unset) =
  чистый no-op → поведение не меняется (non-breaking, инвариант N3).
Timeout: 3s
Opt-in:  TDD_GUARD_ENABLE=1 включает advisory.
Opt-out: env unset / != "1" → no-op.

MVP-ограничение: это **test-presence** guard (есть ли тест для модуля), НЕ полный
run-tracked «red-first» (как community tdd-guard, что парсит вывод тестов). Полный
run-tracking — будущее усиление (ADR-015). **Advisory-only: НИКОГДА не блокирует
Write/Edit** — минимизирует риск; hard-block рассматривается только после недели
валидации (4.3).
"""

import glob
import json
import os
import re
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HOOK_DIR))  # .claude/hooks -> repo root
_EVENTS_LOG = os.path.join(PROJECT_ROOT, ".claude", "cache", "tdd-guard-events.jsonl")

# Сигнатура «новой логики, достойной теста» — добавление функции/класса.
_DEF_RE = re.compile(r"^\s*(?:async\s+def|def|class)\s+\w", re.MULTILINE)


def _log_event(file_rel: str, module: str) -> None:
    """260613 4.3: кеш advisory-событий для авто-валидации (tdd_guard_validation.py).
    Fail-soft, UTF-8 байты (cp1251-pipe safe)."""
    try:
        os.makedirs(os.path.dirname(_EVENTS_LOG), exist_ok=True)
        rec = {
            "ts": datetime.now(UTC).isoformat(),
            "file": file_rel,
            "module": module,
            "event": "advisory_no_test",
        }
        with open(_EVENTS_LOG, "ab") as f:
            f.write((json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8"))
    except Exception:
        pass


class TddGuard(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        # 1. opt-in gate: default OFF → no-op (non-breaking)
        if os.environ.get("TDD_GUARD_ENABLE") != "1":
            return None
        if inp.tool_name not in ("Write", "Edit"):
            return None

        fp = (inp.tool_input.get("file_path") or "").replace("\\", "/")
        if not fp.endswith(".py"):
            return None
        low = fp.lower()

        # 2. только production python под src/ (не тесты/conftest/__init__)
        if "/src/" not in low and not low.startswith("src/"):
            return None
        stem = fp.rsplit("/", 1)[-1]
        if (
            stem.startswith("test_")
            or stem == "conftest.py"
            or stem == "__init__.py"
            or "/tests/" in low
        ):
            return None

        # 3. правка добавляет def/class? (иначе — не «новая логика»)
        content = inp.tool_input.get("content") or inp.tool_input.get("new_string") or ""
        if not _DEF_RE.search(content):
            return None

        # 4. есть ли тест для модуля? (test_<stem>.py / <stem>_test.py в tests/**)
        modstem = stem[:-3]  # без .py
        patterns = [
            f"{PROJECT_ROOT}/tests/**/test_{modstem}.py",
            f"{PROJECT_ROOT}/tests/**/{modstem}_test.py",
        ]
        for pat in patterns:
            if glob.glob(pat, recursive=True):
                return None  # тест есть — ок

        # 5. ADVISORY (НЕ блок) + кеш события для авто-валидации (4.3)
        _log_event(fp, modstem)
        return HookOutput().system_message(
            f"[TDD-GUARD] Нет теста для модуля '{stem}' "
            f"(искал tests/**/test_{modstem}.py). TDD: напиши failing-тест ПЕРЕД "
            f"реализацией (Skill('evaluation-benchmark')). Это advisory — правка НЕ "
            f"заблокирована. Opt-out: TDD_GUARD_ENABLE=0."
        )


if __name__ == "__main__":
    TddGuard().run()
