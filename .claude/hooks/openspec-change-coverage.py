#!/usr/bin/env python3
"""
Hook: openspec-change-coverage
Event: PostToolUse
Matcher: Write|Edit
Purpose: при правке файла в ИБTransportManagementDevelop/Конфигурация/src/** без
         соответствующего active change в openspec/changes/ — выдаёт информационный
         systemMessage с предложением создать change через /opsx:propose.
Timeout: 5s

Логика:
  1. Detect Edit/Write на путь под `ИБTransportManagementDevelop/Конфигурация/src/**`
     либо под `configuration/<gkstcplk-XXXX>/...`.
  2. Извлечь jira_token (GKSTCPLK-XXXX) из пути если есть.
  3. Прочитать openspec/changes/*/.openspec.yaml (без archive). Если ни в одном
     `title`/`scope`/`jira_task_id` нет совпадения с jira_token (или вообще нет
     active change'ей) — эмитим systemMessage.
  4. Per-session cooldown (15-minute window) через
     .claude/cache/openspec-change-coverage-sessions.json — чтобы не флудить на
     серии правок одного файла.

Не блокирует. Pattern: Enforcer informational variant.

SKIP cases:
  - правки в openspec/** (это сам спек-каталог, не code)
  - правки в configuration/**/docs/** (docs не code)
  - правки в .claude/hooks/, .claude/skills/, .github/, scripts/ (фреймворк-инфра)
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

COOKIE_PATH = Path(".claude/cache/openspec-change-coverage-sessions.json")
COOLDOWN_MIN = 15
COOKIE_BOOT = 100

JIRA_RE = re.compile(r"(GKSTCPLK-\d{3,5})", re.IGNORECASE)

CODE_PATTERNS = (
    "ИБTransportManagementDevelop/Конфигурация/src/",
    "configuration/",
)

SKIP_PATTERNS = (
    "openspec/",
    ".claude/",
    ".github/",
    "scripts/",
    "/docs/",
    "tests/",
    "tools/",
)


def _is_code_path(path: str) -> bool:
    p = path.replace("\\", "/")
    if any(skip in p for skip in SKIP_PATTERNS):
        return False
    return any(pat in p for pat in CODE_PATTERNS)


def _extract_jira(path: str) -> str | None:
    m = JIRA_RE.search(path)
    return m.group(1).upper() if m else None


def _list_active_changes() -> list[Path]:
    root = Path("openspec/changes")
    if not root.exists():
        return []
    return [p for p in root.iterdir() if p.is_dir() and p.name != "archive"]


def _change_matches_jira(change_dir: Path, jira: str) -> bool:
    """Проверяем .openspec.yaml + proposal.md + tasks.md на упоминание jira-токена."""
    targets = (
        change_dir / ".openspec.yaml",
        change_dir / "proposal.md",
        change_dir / "tasks.md",
    )
    for t in targets:
        try:
            text = t.read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, OSError):
            continue
        if jira.lower() in text.lower():
            return True
    return False


def _load_cookie() -> dict:
    try:
        return json.loads(COOKIE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sessions": {}}


def _save_cookie(state: dict) -> None:
    try:
        COOKIE_PATH.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_PATH.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _cooldown_active(state: dict, key: str) -> bool:
    sessions = state.get("sessions", {})
    last = sessions.get(key)
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return False
    return datetime.utcnow() - last_dt < timedelta(minutes=COOLDOWN_MIN)


def _record_cooldown(state: dict, key: str) -> None:
    sessions = state.setdefault("sessions", {})
    sessions[key] = datetime.utcnow().isoformat()
    if len(sessions) > COOKIE_BOOT:
        oldest = sorted(sessions.items(), key=lambda kv: kv[1])[:-COOKIE_BOOT]
        for k, _ in oldest:
            sessions.pop(k, None)


class OpenspecChangeCoverage(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "PostToolUse":
            return None
        if inp.tool_name not in ("Edit", "Write", "NotebookEdit"):
            return None

        target = inp.tool_input.get("file_path") or ""
        if not _is_code_path(target):
            return None

        jira = _extract_jira(target)
        active = _list_active_changes()

        # Если в пути нет JIRA-токена — связь определить нельзя, не шумим.
        # Warning эмитим только когда JIRA в пути есть, но соответствующий
        # change в openspec/changes/ отсутствует.
        if not jira:
            return None

        if active:
            for ch in active:
                if _change_matches_jira(ch, jira):
                    return None  # покрытие есть, всё ок

        # Cooldown — чтобы не флудить на серии правок одного файла
        sid = inp.session_id or "unknown"
        key = f"{sid}::{jira or 'no-jira'}::{Path(target).name}"
        state = _load_cookie()
        if _cooldown_active(state, key):
            return None
        _record_cooldown(state, key)
        _save_cookie(state)

        active_names = ", ".join(p.name for p in active) if active else "<none>"
        jira_part = f" для задачи {jira}" if jira else ""
        msg = (
            "[OPENSPEC-COVERAGE] Правка кода в submodule"
            f" Конфигурация{jira_part} без соответствующего active change. "
            f"Active changes: {active_names}. Рекомендуется создать "
            "`/opsx:propose <change-id>` ДО изменения кода (SDD-маршрут "
            "обязателен для ADDED метаданных, желателен для MODIFIED). "
            "Если правка тривиальна — можно проигнорировать."
        )
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    OpenspecChangeCoverage().run()
