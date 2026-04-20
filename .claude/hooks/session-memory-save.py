#!/usr/bin/env python3
"""
Hook: session-memory-save
Event: Stop
Matcher: (none — fires on every stop attempt)
Purpose: Auto-save session context (git diff, skills, commits, tasks)
         to SQLite (memory_ai.db) for cross-session recall.
Timeout: 5s

Exit codes:
  0 = always allow stop (advisory, non-blocking)

Pattern: Advisory (save + pass through). Part of P5.1 Session Memory Bridge.
"""

import json
import os
import sqlite3
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SQLITE_DB = PROJECT_ROOT / "data" / "memory_ai.db"
SESSION_STATE_FILE = PROJECT_ROOT / ".claude" / "data" / "session-skills.json"
HOOK_TODOS_FILE = PROJECT_ROOT / ".claude" / "cache" / "hook-todos.json"
WIKI_LOG = PROJECT_ROOT / "docs" / "wiki" / "log.md"
WIKI_LOG_MAX_LINES = 500

# Minimum thresholds — skip trivial sessions
MIN_FILES = 2
MIN_COMMITS = 1
MIN_SKILLS = 1

# Category for session summaries
CATEGORY = "session_summary"


def _run_git(args, timeout=2):
    """Run git command with timeout, return stdout lines."""
    try:
        result = subprocess.run(
            ["git", "-c", "core.quotepath=false"] + args,
            capture_output=True, text=True, encoding="utf-8",
            timeout=timeout, cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []
        return [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    except Exception:
        return []


def _read_json_file(path):
    """Read JSON file, return dict or empty dict on error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def collect_context():
    """Gather session context from multiple sources."""
    # 1. Session state (skills, session_id)
    state = _read_json_file(SESSION_STATE_FILE)
    session_id = state.get("session_id", "")
    skills = state.get("activated_skills", [])
    created_at = state.get("created_at", "")

    # 2. Git: uncommitted changes (modified + staged + untracked)
    diff_lines = _run_git(["diff", "--name-only"])
    staged_lines = _run_git(["diff", "--cached", "--name-only"])
    untracked_lines = _run_git(["status", "--porcelain"])
    untracked_files = []
    for line in untracked_lines:
        if len(line) >= 3 and line[0:2].strip() in ("??", "A", "M", "AM"):
            untracked_files.append(line[3:].strip().strip('"'))
    all_files = sorted(set(diff_lines + staged_lines + untracked_files))

    # 3. Git: recent commits (last 8 hours)
    log_lines = _run_git([
        "log", "--oneline", "--since=8 hours ago", "--format=%s",
    ])
    commits = log_lines[:5]

    # 4. Completed tasks from hook-todos
    todos = _read_json_file(HOOK_TODOS_FILE)
    completed_tasks = []
    task_list = todos if isinstance(todos, list) else todos.get("tasks", [])
    for t in task_list:
        if isinstance(t, dict) and t.get("status") == "completed":
            title = t.get("title", "")
            if title:
                completed_tasks.append(title)

    return {
        "session_id": session_id,
        "created_at": created_at,
        "skills": skills,
        "files_changed": all_files,
        "commits": commits,
        "completed_tasks": completed_tasks,
    }


def is_meaningful(ctx):
    """Check if session has enough activity to save."""
    return (
        len(ctx["files_changed"]) >= MIN_FILES
        or len(ctx["commits"]) >= MIN_COMMITS
        or len(ctx["skills"]) >= MIN_SKILLS
    )


def already_saved(session_id):
    """Check if this session was already saved (dedup by session_id or date)."""
    if not SQLITE_DB.exists():
        return False
    try:
        conn = sqlite3.connect(str(SQLITE_DB), timeout=1)
        # Primary dedup: by session_id (if available)
        if session_id:
            row = conn.execute(
                "SELECT 1 FROM important_messages "
                "WHERE category = ? AND metadata LIKE ?",
                (CATEGORY, f'%"session_id": "{session_id}"%'),
            ).fetchone()
        else:
            # Fallback dedup: by today's date (max 1 session summary per day)
            today = date.today().isoformat()
            row = conn.execute(
                "SELECT 1 FROM important_messages "
                "WHERE category = ? AND metadata LIKE ?",
                (CATEGORY, f'%"session_date": "{today}"%'),
            ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def format_summary(ctx):
    """Format session context into human-readable summary."""
    parts = []
    today = date.today().isoformat()
    parts.append(f"Session {today}")

    if ctx["skills"]:
        parts.append(f"Skills: {', '.join(ctx['skills'][:8])}")

    if ctx["files_changed"]:
        dirs = set()
        for f in ctx["files_changed"]:
            segments = f.replace("\\", "/").split("/")
            if len(segments) >= 2:
                dirs.add(f"{segments[0]}/{segments[1]}")
            else:
                dirs.add(segments[0])
        dir_list = ", ".join(sorted(dirs)[:5])
        parts.append(f"Changed {len(ctx['files_changed'])} files in {dir_list}")

    if ctx["commits"]:
        for msg in ctx["commits"][:3]:
            parts.append(f"Commit: {msg}")

    if ctx["completed_tasks"]:
        for task in ctx["completed_tasks"][:3]:
            parts.append(f"Done: {task}")

    return ". ".join(parts)


def calculate_importance(ctx):
    """Auto-calculate importance score (0.5-0.95)."""
    score = 0.5
    score += min(len(ctx["files_changed"]) * 0.02, 0.2)
    score += min(len(ctx["commits"]) * 0.05, 0.15)
    score += min(len(ctx["skills"]) * 0.03, 0.1)
    score += min(len(ctx["completed_tasks"]) * 0.03, 0.1)
    return min(round(score, 2), 0.95)


def extract_tags(ctx):
    """Auto-extract tags from files and skills."""
    tags = {"session", date.today().isoformat()}

    for skill in ctx["skills"][:5]:
        tags.add(skill)

    path_tag_map = {
        "src/memory/": "memory",
        "src/bsl/": "bsl",
        ".claude/hooks/": "hooks",
        ".claude/skills/": "skills",
        "src/pdf_framework/": "pdf-framework",
        "tests/": "tests",
        "docs/": "docs",
        "tools/": "tools",
    }
    for f in ctx["files_changed"]:
        normalized = f.replace("\\", "/")
        for prefix, tag in path_tag_map.items():
            if normalized.startswith(prefix):
                tags.add(tag)
                break

    return sorted(tags)[:10]


def save_to_sqlite(ctx):
    """Write session summary to SQLite memory_ai.db."""
    if not SQLITE_DB.exists():
        return False

    content = format_summary(ctx)
    importance = calculate_importance(ctx)
    tags = extract_tags(ctx)
    now = datetime.now().isoformat()
    metadata = {
        "session_id": ctx["session_id"],
        "session_date": date.today().isoformat(),
        "files_count": len(ctx["files_changed"]),
        "commits_count": len(ctx["commits"]),
        "skills_count": len(ctx["skills"]),
        "skills": ctx["skills"][:10],
        "top_files": ctx["files_changed"][:20],
    }

    conn = sqlite3.connect(str(SQLITE_DB), timeout=2)
    conn.execute(
        "INSERT INTO important_messages "
        "(id, content, importance, category, tags, created_at, updated_at, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid4()),
            content,
            importance,
            CATEGORY,
            json.dumps(tags, ensure_ascii=False),
            now,
            now,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
    return True


def save_to_wiki_log(ctx):
    """Append brief session summary to docs/wiki/log.md."""
    if not WIKI_LOG.exists():
        return False

    try:
        today = date.today().isoformat()
        summary = format_summary(ctx)
        skills_str = ", ".join(ctx["skills"][:5]) if ctx["skills"] else "none"
        files_count = len(ctx["files_changed"])

        entry = (
            f"\n## {today} — Session Summary\n\n"
            f"**Event:** Auto-saved session\n\n"
            f"- Skills: {skills_str}\n"
            f"- Files changed: {files_count}\n"
            f"- Summary: {summary}\n\n"
        )

        with open(WIKI_LOG, "a", encoding="utf-8") as f:
            f.write(entry)

        # Trim if over max lines
        try:
            lines = WIKI_LOG.read_text(encoding="utf-8").splitlines(keepends=True)
            if len(lines) > WIKI_LOG_MAX_LINES:
                # Keep frontmatter + first section + tail
                kept = lines[:30] + lines[-(WIKI_LOG_MAX_LINES - 30):]
                WIKI_LOG.write_text("".join(kept), encoding="utf-8")
        except Exception:
            pass

        return True
    except Exception:
        return False


class SessionMemorySave(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        ctx = collect_context()

        if not is_meaningful(ctx):
            return None

        if already_saved(ctx["session_id"]):
            return None

        save_to_sqlite(ctx)

        # Non-blocking: always allow stop
        return None


if __name__ == "__main__":
    SessionMemorySave().run()
