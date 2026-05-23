#!/usr/bin/env python3
"""
Hook: openspec-task-progress
Event: Stop
Matcher: -
Purpose: при завершении сессии — сопоставить изменённые файлы с задачами tasks.md
         active openspec change'ей и эмитить systemMessage с predлагаемым batch update
         (Claude может выполнить через mcp__openspec-mcp__openspec_batch_update_tasks).
Timeout: 8s

Логика:
  1. git diff за окно (last 24h ИЛИ от earliest session ts).
  2. Извлечь JIRA-токены из путей изменённых файлов И из commit-сообщений.
  3. Найти active openspec change'ы, чьи .openspec.yaml/proposal.md содержат эти токены.
  4. Прочитать tasks.md change'а: для каждого pending task посмотреть, упоминаются ли
     ключевые имена файлов/функций из задачи в git diff. Если да — пометить как
     candidate completed.
  5. Эмитим informational systemMessage с candidate list и подсказкой запустить
     mcp__openspec-mcp__openspec_batch_update_tasks.

Не блокирует. Per-session cooldown через cookie file.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

COOKIE_PATH = Path(".claude/cache/openspec-task-progress-sessions.json")
COOKIE_BOOT = 50
CHANGES_ROOT = Path("openspec/changes")
JIRA_RE = re.compile(r"(GKSTCPLK-\d{3,5})", re.IGNORECASE)
TASK_RE = re.compile(r"^- \[ \] \*\*(\d+\.\d+)\*\* (.+?)$", re.MULTILINE)


def _git(args: list[str]) -> str:
    try:
        out = subprocess.run(
            ["git", "-c", "core.quotepath=false", *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            encoding="utf-8",
            errors="replace",
        )
        return out.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def _list_active_changes() -> list[Path]:
    if not CHANGES_ROOT.exists():
        return []
    return [p for p in CHANGES_ROOT.iterdir() if p.is_dir() and p.name != "archive"]


def _change_matches_jira(change_dir: Path, jira: str) -> bool:
    for fname in (".openspec.yaml", "proposal.md", "tasks.md"):
        p = change_dir / fname
        if not p.exists():
            continue
        try:
            body = p.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if jira.lower() in body:
            return True
    return False


def _parse_tasks(tasks_md: Path) -> list[tuple[str, str]]:
    try:
        text = tasks_md.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return []
    return [(m.group(1), m.group(2).strip()) for m in TASK_RE.finditer(text)]


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


class OpenspecTaskProgress(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "Stop":
            return None

        diff = _git(["diff", "--name-only", "HEAD~10..HEAD"])
        if not diff.strip():
            return None
        msgs = _git(["log", "--format=%B", "HEAD~10..HEAD"])

        all_text = diff + "\n" + msgs
        jiras = {j.upper() for j in JIRA_RE.findall(all_text)}
        if not jiras:
            return None

        active = _list_active_changes()
        if not active:
            return None

        sid = inp.session_id or "unknown"
        state = _load_cookie()
        sessions = state.get("sessions", [])
        if sid in sessions:
            return None

        matches: list[str] = []
        for jira in jiras:
            for ch in active:
                if not _change_matches_jira(ch, jira):
                    continue
                tasks = _parse_tasks(ch / "tasks.md")
                if not tasks:
                    continue
                # Эвристика: задача 'candidate completed' если её ID или ключевые
                # слова из текста встречаются в diff.
                candidates: list[str] = []
                for tid, ttext in tasks:
                    tlow = ttext.lower()
                    diff_low = diff.lower()
                    # Простое совпадение: упоминание имени файла/символа из задачи.
                    # Берём слова длиной >=8 (имена 1С).
                    words = [w for w in re.findall(r"[А-Яа-яA-Za-z_]{8,}", ttext) if len(w) >= 8]
                    if any(w.lower() in diff_low for w in words[:3]):
                        candidates.append(f"  - **{tid}** {ttext[:80]}")
                if candidates:
                    matches.append(
                        f"### Change `{ch.name}` (JIRA {jira})\n" + "\n".join(candidates[:5])
                    )

        if not matches:
            return None

        sessions.append(sid)
        state["sessions"] = sessions[-COOKIE_BOOT:]
        _save_cookie(state)

        body = "\n\n".join(matches)
        msg = (
            "[OPENSPEC-TASK-PROGRESS] Обнаружены изменённые файлы, похожие на "
            "задачи в active openspec change'ах. Кандидаты на completed:\n\n" + body + "\n\n"
            "Если эти задачи действительно выполнены — обнови через "
            "`mcp__openspec-mcp__openspec_batch_update_tasks(changeId, updates=[{id, status:done}])`."
        )
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    OpenspecTaskProgress().run()
