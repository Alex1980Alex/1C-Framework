#!/usr/bin/env python3
"""
Hook: implement-1c-task-smoke-stop-alert
Event: Stop
Matcher: (none)
Purpose: Phase 5.4 of 260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md.
         When the user is about to stop, surface a warning if:
           1) implement-1c-task preflight smoke-test came back degraded (exit=1)
              or unusable (exit=2) within the last 24h, AND
           2) the user actually ran /implement-1c-task at any point recently
              (slash-command-tracker logged a slash_run start for it).
         Both conditions must hold — without (2) the alert is noise; without
         (1) the smoke-test is healthy and there's nothing to surface.

         The alert is informational, never blocks. Fires at most once per
         (session_id), tracked via a tiny cookie file under .claude/cache/.

Timeout: 5s
Exit codes: always 0 (informational)
Pattern: Enforcer (informational variant — system_message only, no block).

Source signals (from data/hook-invocations.jsonl, written by
shared/invocation_logger.py via universal MCP/preflight logging):
  category="preflight"  → tool="slash:implement-1c-task",
                          outcome="mode=<Mode>;exit=<0|1|2>"
                          emitter: implement-1c-task-preflight.py
  category="slash_run"  → tool="slash:implement-1c-task",
                          outcome="start"|"end"
                          emitter: slash-command-tracker.py

Format spec for both is documented in CLAUDE.md → "Universal MCP &
slash-command logging (2026-05-04)" block.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INVOCATIONS_LOG = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
COOKIE_FILE = PROJECT_ROOT / ".claude" / "cache" / "smoke-stop-alert-sessions.json"
WINDOW_HOURS = 24
TAIL_BYTES = 512 * 1024  # 512 KB tail is enough for 24h of preflight+slash entries


def _read_log_tail(path: Path, max_bytes: int) -> list[dict]:
    """Read trailing window of jsonl and return parsed entries (tolerant of partial first line)."""
    if not path.exists():
        return []
    try:
        size = path.stat().st_size
        with open(path, "rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                # discard partial first line
                fh.readline()
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    entries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _parse_exit_code(outcome: str) -> int | None:
    """outcome format: 'mode=<Mode>;exit=<int>' (per implement-1c-task-preflight.py)."""
    if not outcome or "exit=" not in outcome:
        return None
    try:
        return int(outcome.split("exit=", 1)[1].split(";", 1)[0].strip())
    except (ValueError, IndexError):
        return None


def _already_alerted(session_id: str) -> bool:
    if not session_id or not COOKIE_FILE.exists():
        return False
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return session_id in data.get("sessions", {})
    except (OSError, json.JSONDecodeError):
        return False


def _mark_alerted(session_id: str) -> None:
    if not session_id:
        return
    try:
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if COOKIE_FILE.exists():
            with open(COOKIE_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        else:
            data = {"sessions": {}}
        sessions = data.setdefault("sessions", {})
        sessions[session_id] = datetime.now().isoformat()
        # Trim to last 50 sessions to keep file bounded
        if len(sessions) > 50:
            keep = dict(sorted(sessions.items(), key=lambda kv: kv[1], reverse=True)[:50])
            data["sessions"] = keep
        with open(COOKIE_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


class ImplementOneCTaskSmokeStopAlert(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "Stop":
            return None

        session_id = inp.session_id or ""
        if _already_alerted(session_id):
            return None

        entries = _read_log_tail(INVOCATIONS_LOG, TAIL_BYTES)
        if not entries:
            return None

        cutoff = datetime.now() - timedelta(hours=WINDOW_HOURS)

        worst_preflight: dict | None = None  # entry with highest exit code in window
        user_ran_implement = False

        for entry in entries:
            ts = _parse_ts(entry.get("ts", ""))
            if ts is None or ts < cutoff:
                continue
            tool = entry.get("tool", "")
            if tool != "slash:implement-1c-task":
                continue
            category = entry.get("category", "")
            if category == "slash_run" and entry.get("outcome", "") == "start":
                user_ran_implement = True
            elif category == "preflight":
                exit_code = _parse_exit_code(entry.get("outcome", ""))
                if exit_code and exit_code >= 1:
                    if worst_preflight is None:
                        worst_preflight = entry
                    else:
                        prev = _parse_exit_code(worst_preflight.get("outcome", "")) or 0
                        # Prefer higher severity; tie-break on most recent.
                        if exit_code > prev or (
                            exit_code == prev
                            and (ts > _parse_ts(worst_preflight.get("ts", "")) or datetime.min)
                        ):
                            worst_preflight = entry

        if not (user_ran_implement and worst_preflight):
            return None

        outcome = worst_preflight.get("outcome", "")
        ts_str = worst_preflight.get("ts", "")
        exit_code = _parse_exit_code(outcome) or 0
        severity = "FAIL (unusable)" if exit_code >= 2 else "WARN (degraded)"

        msg = (
            f"[IMPLEMENT-1C-SMOKE] {severity} в последние {WINDOW_HOURS}ч: {outcome} ({ts_str}). "
            f"Пользователь запускал /implement-1c-task в этом окне. "
            f"Перед следующим прогоном проверь: "
            f"`python scripts/smoke_test_implement_1c_task.py` и "
            f"docs/framework documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md."
        )
        _mark_alerted(session_id)
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    ImplementOneCTaskSmokeStopAlert().run()
