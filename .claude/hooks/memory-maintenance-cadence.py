#!/usr/bin/env python3
"""
Hook: memory-maintenance-cadence
Event: Stop
Matcher: (none)
Purpose: §26 P4 D4.1 — run the memory maintenance cadence
         (``scripts/memory_maintenance.py``) once every N distinct sessions, as a
         detached subprocess. Sequences reflect → cross_store_sync → promote →
         ForgetGate and writes the D4.3 dashboard.

Safety: **DRY-RUN by default** (the cadence only plans/reports). Set
        ``MEMORY_MAINTENANCE_APPLY=1`` to let it write (reflect/sync apply,
        promote drafts, ForgetGate archival). Never blocks Stop (exit 0).

State: .claude/cache/memory-maintenance-cadence-state.json
  {"pending_sessions": [...], "first_seen": "<iso>", "last_fire": "<iso>|null"}

Cold start: seed on first invocation (no state), do NOT fire — avoids a cadence
run on the very first Stop after install.

Env:
  MEMORY_MAINTENANCE_DISABLE=1   opt-out entirely
  MEMORY_MAINTENANCE_EVERY=N     cadence period in distinct sessions (default 10)
  MEMORY_MAINTENANCE_APPLY=1     run with --apply (default dry-run)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "memory-maintenance-cadence-state.json"
SCRIPT = PROJECT_ROOT / "scripts" / "memory_maintenance.py"
# P1.4 (B8, roadmap 260713): observability-отчёт с freshness/regression-детектором —
# «замолчавший sink» (писал и перестал). Раньше запускался ТОЛЬКО вручную. Read-only и
# быстрый (<1с), поэтому дёргаем синхронно при фаере каденса и сюрфейсим regressions в баннер.
OBS_SCRIPT = PROJECT_ROOT / "scripts" / "memory_observability_report.py"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
LOG = PROJECT_ROOT / "data" / "reports" / "memory" / "_maintenance.log"

DEFAULT_EVERY = 10
MAX_PENDING = 200


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def _every() -> int:
    try:
        n = int(os.environ.get("MEMORY_MAINTENANCE_EVERY", DEFAULT_EVERY))
        return n if n > 0 else DEFAULT_EVERY
    except ValueError:
        return DEFAULT_EVERY


def _launch(apply: bool) -> bool:
    """Detached fire-and-forget cadence run. Returns True on launch success."""
    if not PYTHON_EXE.exists() or not SCRIPT.exists():
        return False
    cmd = [str(PYTHON_EXE), str(SCRIPT)]
    if apply:
        cmd.append("--apply")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        fh = LOG.open("a", encoding="utf-8")
        try:
            subprocess.Popen(
                cmd,
                stdout=fh,
                stderr=fh,
                cwd=str(PROJECT_ROOT),
                creationflags=creationflags,
                close_fds=True,
            )
        finally:
            fh.close()
        return True
    except OSError:
        return False


def _check_regressions(timeout: float = 8.0) -> str | None:
    """P1.4 (B8): синхронно прогнать observability-отчёт (read-only, <1с) и вернуть
    строку `[REGRESSION] N stale sink(s): [...]` при замолчавших синках, иначе None.
    best-effort — таймаут/ошибка/нет скрипта → None (каденс не ломается)."""
    if not PYTHON_EXE.exists() or not OBS_SCRIPT.exists():
        return None
    try:
        r = subprocess.run(
            [str(PYTHON_EXE), str(OBS_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    for line in (r.stdout or "").splitlines():
        if line.startswith("[REGRESSION]"):
            return line.strip()
    return None


class MemoryMaintenanceCadence(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "Stop":
            return None
        if os.environ.get("MEMORY_MAINTENANCE_DISABLE") == "1":
            return None

        sid = inp.session_id or ""
        state = _load_state()

        # Cold-start: seed without firing (no cadence run on first Stop).
        if not state:
            _save_state(
                {
                    "pending_sessions": [sid] if sid else [],
                    "first_seen": _now(),
                    "last_fire": None,
                }
            )
            return None

        pending: list[str] = list(state.get("pending_sessions") or [])
        if sid and sid not in pending:
            pending.append(sid)

        every = _every()
        if len(pending) >= every:
            apply = os.environ.get("MEMORY_MAINTENANCE_APPLY") == "1"
            ok = _launch(apply)
            state["pending_sessions"] = []
            state["last_fire"] = _now()
            _save_state(state)
            # P1.4 (B8): freshness/regression-детектор синхронно (read-only, <1с) —
            # замолчавшие memory-sinks сюрфейсим сразу в баннере каденса.
            regr = _check_regressions()
            if ok:
                mode = "APPLY" if apply else "dry-run"
                msg = (
                    f"[MEMORY-MAINTENANCE] Cadence fired ({mode}; every {every} sessions). "
                    f"Dashboard → data/reports/memory/memory_maintenance_*.md в ~10-60с."
                )
                if regr:
                    msg += (
                        f"\n⚠ {regr}\n  → sink(s) перестали писать (>7д, observability-регрессия). "
                        f"Проверь writer'ы; отчёт: data/reports/memory/observability-*.md."
                    )
                return HookOutput().system_message(msg)
            # launch не удался, но регрессию всё равно стоит показать
            if regr:
                return HookOutput().system_message(
                    f"[MEMORY-MAINTENANCE] ⚠ {regr} — sink(s) перестали писать (>7д). "
                    f"Отчёт: data/reports/memory/observability-*.md."
                )
            return None

        state["pending_sessions"] = pending[-MAX_PENDING:]
        _save_state(state)
        return None


if __name__ == "__main__":
    MemoryMaintenanceCadence().run()
