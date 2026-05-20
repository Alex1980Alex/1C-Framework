#!/usr/bin/env python3
"""
Hook: opsx-apply-postvalidate
Event: Stop
Matcher: -
Purpose: после успешного `/opsx:apply` напоминает запустить brownfield-validate.
Timeout: 5s

Логика:
  1. Читаем tail data/hook-invocations.jsonl (~512 KB, ~24h окно).
  2. Ищем slash_run start для `slash:opsx-apply` или `slash:opsx:apply` (forward-compat).
  3. Если в окне нет последующего sysmsg «brownfield-validate запущен» — эмитим
     informational systemMessage с инструкцией.
  4. Per-session cooldown через .claude/cache/opsx-apply-postvalidate-sessions.json
     (так же как у implement-1c-task-smoke-stop-alert.py).

Не блокирует. Pattern: Enforcer informational variant.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

LOG_PATH = Path("data/hook-invocations.jsonl")
COOKIE_PATH = Path(".claude/cache/opsx-apply-postvalidate-sessions.json")
TAIL_BYTES = 512 * 1024
WINDOW_HOURS = 24
COOKIE_BOOT = 50
APPLY_SLASH_TOKENS = ("slash:opsx-apply", "slash:opsx:apply", "slash:openspec-apply")
BROWNFIELD_TOKEN = "brownfield-validate"


def _read_tail(path: Path, max_bytes: int) -> list[dict]:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            start = max(0, size - max_bytes)
            f.seek(start)
            data = f.read().decode("utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return []
    rows = []
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _find_latest_apply(rows: list[dict], cutoff: datetime) -> dict | None:
    """Самый свежий start slash:opsx-apply в окне."""
    latest = None
    for row in rows:
        if row.get("category") != "slash_run":
            continue
        if row.get("event") not in ("start", "begin"):
            continue
        target = row.get("target") or ""
        if not any(tok in target for tok in APPLY_SLASH_TOKENS):
            continue
        ts_str = row.get("ts") or ""
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        if ts < cutoff:
            continue
        if latest is None or ts > latest["_ts"]:
            row["_ts"] = ts
            latest = row
    return latest


def _has_brownfield_after(rows: list[dict], after: datetime) -> bool:
    for row in rows:
        ts_str = row.get("ts") or ""
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        if ts < after:
            continue
        blob = json.dumps(row, ensure_ascii=False).lower()
        if BROWNFIELD_TOKEN in blob:
            return True
    return False


def _load_cookie() -> dict:
    try:
        return json.loads(COOKIE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sessions": []}


def _save_cookie(state: dict) -> None:
    try:
        COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


class OpsxApplyPostvalidate(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "Stop":
            return None

        rows = _read_tail(LOG_PATH, TAIL_BYTES)
        if not rows:
            return None

        cutoff = datetime.utcnow() - timedelta(hours=WINDOW_HOURS)
        latest = _find_latest_apply(rows, cutoff)
        if not latest:
            return None

        already_run = _has_brownfield_after(rows, latest["_ts"])
        if already_run:
            return None

        # Per-session cooldown
        sid = inp.session_id or "unknown"
        state = _load_cookie()
        sessions = state.get("sessions", [])
        if sid in sessions:
            return None
        sessions.append(sid)
        state["sessions"] = sessions[-COOKIE_BOOT:]
        _save_cookie(state)

        change_id = latest.get("change_id") or latest.get("args") or "<change>"
        msg = (
            "[OPSX-POSTVALIDATE] Обнаружен завершённый /opsx:apply без последующего "
            "brownfield-validate. Рекомендуется запустить:\n"
            f"  Skill('brownfield-validate') с change_id={change_id}\n"
            "Validators: Gap (полнота tasks vs реализованные точки) + Design "
            "(архитектура соответствует design.md) + Impl (BSL стиль, RFC 2119 reqs)."
        )
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    OpsxApplyPostvalidate().run()
