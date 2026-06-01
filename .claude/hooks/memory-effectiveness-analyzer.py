#!/usr/bin/env python3
"""
Hook: memory-effectiveness-analyzer
Event: Stop
Matcher: (none)
Purpose: Periodically generate a memory-effectiveness report (roadmap section 25
         Part A) from the two memory JSONL trace logs. Detached spawn of
         scripts/analyze_memory_effectiveness.py -> report in
         data/reports/memory/. Throttled: at most once per MIN_INTERVAL_HOURS.

Timeout: 15s
Exit codes: always 0 (informational; never blocks Stop)
Pattern: Enforcer (informational variant -- system_message only, no block).

Opt-out: MEMORY_EFFECTIVENESS_ANALYZER_DISABLE=1
State: .claude/cache/memory-effectiveness-analyzer-state.json { "last_fire": "<iso>" }
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "memory-effectiveness-analyzer-state.json"
ANALYZER_SCRIPT = PROJECT_ROOT / "scripts" / "analyze_memory_effectiveness.py"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "memory"
SURFACING_LOG = PROJECT_ROOT / ".claude" / "cache" / "memory-first-surfacing.log"

MIN_INTERVAL_HOURS = 6.0


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def _within_cooldown(state: dict[str, Any], now: datetime) -> bool:
    last = state.get("last_fire")
    if not last:
        return False
    try:
        return (now - datetime.fromisoformat(last)) < timedelta(hours=MIN_INTERVAL_HOURS)
    except (ValueError, TypeError):
        return False


def _spawn_analyzer() -> bool:
    """Fire-and-forget detached subprocess. Returns True on launch success."""
    if not PYTHON_EXE.exists() or not ANALYZER_SCRIPT.exists():
        return False
    cmd = [str(PYTHON_EXE), str(ANALYZER_SCRIPT), "--since", "7d"]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        log_fh = (REPORTS_DIR / "_analyzer.log").open("a", encoding="utf-8")
        try:
            subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=log_fh,
                cwd=str(PROJECT_ROOT),
                creationflags=creationflags,
                close_fds=True,
            )
        finally:
            log_fh.close()
        return True
    except OSError:
        return False


class MemoryEffectivenessAnalyzer(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("MEMORY_EFFECTIVENESS_ANALYZER_DISABLE") == "1":
            return None
        if inp.detected_event != "Stop":
            return None
        if not SURFACING_LOG.exists():
            return None

        now = datetime.now()
        state = _load_state()
        if _within_cooldown(state, now):
            return None

        ok = _spawn_analyzer()
        if not ok:
            # Spawn failed (e.g. venv/script missing) — do NOT stamp cooldown, so a
            # transient failure doesn't suppress retries for the next 6h.
            return None
        state["last_fire"] = now.isoformat(timespec="seconds")
        _save_state(state)
        return HookOutput().system_message(  # type: ignore[no-untyped-call]
            "[MEMORY-EFFECTIVENESS] Запущен анализ эффективности памяти (section 25 A). "
            "Отчёт появится в data/reports/memory/_latest.md через ~5-10с."
        )


if __name__ == "__main__":
    MemoryEffectivenessAnalyzer().run()  # type: ignore[no-untyped-call]
