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

# MEMORY_AI_DB_PATH override — test isolation (roadmap 260612 P0.3)
SQLITE_DB = Path(os.environ.get("MEMORY_AI_DB_PATH") or PROJECT_ROOT / "data" / "memory_ai.db")
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
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode != 0:
            return []
        return [ln for ln in result.stdout.strip().splitlines() if ln.strip()]
    except Exception:
        return []


def _read_json_file(path):
    """Read JSON file, return dict or empty dict on error."""
    try:
        with open(path, encoding="utf-8") as f:
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
    log_lines = _run_git(
        [
            "log",
            "--oneline",
            "--since=8 hours ago",
            "--format=%s",
        ]
    )
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
                "SELECT 1 FROM important_messages WHERE category = ? AND metadata LIKE ?",
                (CATEGORY, f'%"session_id": "{session_id}"%'),
            ).fetchone()
        else:
            # Fallback dedup: by today's date (max 1 session summary per day)
            today = date.today().isoformat()
            row = conn.execute(
                "SELECT 1 FROM important_messages WHERE category = ? AND metadata LIKE ?",
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


def _content_hash(content):
    """Fail-soft canonical content_hash (§26 write-contract, roadmap 260612 P1).

    ``append`` (not ``insert(0)``) keeps hooks-local ``shared.*`` ahead of
    ``src/shared`` — see feedback-hook-src-shared-collision.
    """
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.append(src)
        from memory.orchestrator.content_hash import hash_content

        return hash_content(content)
    except Exception:
        return ""


def _record_ingest(action, content_hash=""):
    """Fail-soft §26 ingestion-metrics emit (W2 was invisible to fact-trace)."""
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.append(src)
        from memory.orchestrator.ingest_metrics import record_ingest

        record_ingest(
            "memory_ai", action, content_hash=content_hash, harvester="session-memory-save"
        )
    except Exception:
        pass


def save_to_sqlite(ctx):
    """Write session summary to SQLite memory_ai.db."""
    if not SQLITE_DB.exists():
        return False

    content = format_summary(ctx)
    importance = calculate_importance(ctx)
    tags = extract_tags(ctx)
    now = datetime.now().isoformat()
    content_hash = _content_hash(content)
    metadata = {
        "session_id": ctx["session_id"],
        "session_date": date.today().isoformat(),
        "files_count": len(ctx["files_changed"]),
        "commits_count": len(ctx["commits"]),
        "skills_count": len(ctx["skills"]),
        "skills": ctx["skills"][:10],
        "top_files": ctx["files_changed"][:20],
        "content_hash": content_hash,
    }

    conn = sqlite3.connect(str(SQLITE_DB), timeout=2)
    try:
        conn.execute("PRAGMA busy_timeout=5000")
    except sqlite3.Error:
        pass
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
    _record_ingest("saved", content_hash)
    return True


def save_to_wiki_log(ctx):
    """Append brief session summary to docs/wiki/log.md (Hermes Phase 2).

    Restored from the pre-PR#2 implementation (roadmap 260609 P2.2). Writes
    UTF-8, trims the file to WIKI_LOG_MAX_LINES, fully fail-soft.
    """
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
                kept = lines[:30] + lines[-(WIKI_LOG_MAX_LINES - 30) :]
                WIKI_LOG.write_text("".join(kept), encoding="utf-8")
        except Exception:
            pass

        return True
    except Exception:
        return False


def try_promote_patterns() -> None:
    """L2→L5 promotion: scan learned_patterns, write drafts. Best-effort, non-blocking.

    Restored (roadmap 260609 P2.2). Delegates to the canonical promote path
    (``export_graph_to_wiki promote-patterns``), the same job the §26 P4
    maintenance cadence runs — this is an opportunistic per-session trigger, not
    a second implementation. Uses CLI defaults (confidence>=0.8, application_count>=5).
    Failures are swallowed — drafts/ is advisory state; a missed run is acceptable.
    Disable with SESSION_MEMORY_NO_PROMOTE=1 (e.g. CI, dev with no Qdrant).
    """
    if os.environ.get("SESSION_MEMORY_NO_PROMOTE") == "1":
        return
    # Detached fire-and-forget (post-indexing-analyzer pattern): the hook's
    # Stop budget must not pay for a Qdrant scroll (~1.6s typical, unbounded
    # when Qdrant is slow). The CLI logs promotions itself (WikiPromoter), so
    # there is nothing to collect here; output goes to a log for diagnostics.
    creationflags = 0
    if sys.platform == "win32":
        # DETACHED_PROCESS (0x00000008) | CREATE_NO_WINDOW (0x08000000)
        creationflags = 0x00000008 | 0x08000000
    try:
        log_path = PROJECT_ROOT / ".claude" / "cache" / "session-promote.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = log_path.open("a", encoding="utf-8")
        try:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "scripts.export_graph_to_wiki",
                    "promote-patterns",
                ],
                stdout=log_fh,
                stderr=log_fh,
                cwd=str(PROJECT_ROOT),
                creationflags=creationflags,
                close_fds=True,
            )
        finally:
            # Child inherits its own duplicated FD; release the parent's copy.
            log_fh.close()
    except OSError:
        pass


def _langfuse_configured() -> bool:
    """Cheap pre-gate: is a Langfuse public key plausibly configured?

    ``emit_observation`` self-disables when unconfigured, but its gate goes
    through pydantic ``get_settings()`` — ~2s per fresh hook process for a
    no-op, which the 5-15s Stop budget cannot afford on every path. Probe the
    env and the .env file directly instead; only on a hit do we pay the real
    import + settings load.
    """
    if os.environ.get("MEMORY_HOOK_NO_LANGFUSE") == "1":
        return False
    if os.environ.get("LANGFUSE_PUBLIC_KEY"):
        return True
    try:
        env_file = PROJECT_ROOT / ".env"
        return env_file.exists() and "LANGFUSE_PUBLIC_KEY" in env_file.read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError:
        return False


def _emit_langfuse_span(ctx: dict, status: str) -> None:
    """Emit a standalone Langfuse observation (roadmap §5c.4). Never blocks the hook.

    Restored (roadmap 260609 P2.2). ``emit_observation`` self-disables when
    Langfuse is not configured/installed, so this degrades to a silent no-op
    rather than forcing a dependency.
    """
    if not _langfuse_configured():
        return
    try:
        if str(PROJECT_ROOT) not in sys.path:
            # append, not insert(0): repo root must not shadow hooks-local
            # modules ([[feedback-hook-src-shared-collision]]).
            sys.path.append(str(PROJECT_ROOT))
        from src.pdf_framework.observability.langfuse_setup import emit_observation

        emit_observation(
            name="session-memory-save",
            input={
                "session_id": ctx.get("session_id"),
                "files_changed": len(ctx.get("files_changed", [])),
                "commits": len(ctx.get("commits", [])),
                "skills": len(ctx.get("skills", [])),
            },
            output={"status": status, "category": CATEGORY},
            session_id=str(ctx.get("session_id", "")) or None,
            metadata={"hook": "session-memory-save", "event": "Stop"},
        )
    except Exception:
        pass


class SessionMemorySave(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        ctx = collect_context()

        if not is_meaningful(ctx):
            _emit_langfuse_span(ctx, status="skipped-trivial")
            return None

        if already_saved(ctx["session_id"]):
            _emit_langfuse_span(ctx, status="skipped-duplicate")
            return None

        save_to_sqlite(ctx)
        save_to_wiki_log(ctx)
        try_promote_patterns()
        # §22 reinforce moved to dedicated Stop-hook pattern-reinforce-stop.py
        # (roadmap 260609 P0.1): here it sat behind the already_saved early-return
        # and the 5s budget, so it never ran in production.
        _emit_langfuse_span(ctx, status="saved")

        return None


if __name__ == "__main__":
    SessionMemorySave().run()
