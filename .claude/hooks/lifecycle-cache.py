#!/usr/bin/env python3
"""
Hook: lifecycle-cache
Event: Stop
Purpose: auto-cache dev-lifecycle stages per §23 Auto-Cache Pipeline Pass 2.

Reads the session transcript, extracts lifecycle stage data via
shared.lifecycle_extract, and writes a dated markdown record to
data/lifecycle/<YYYY-MM-DD>_<session_id[:8]>.md plus an index line to
data/lifecycle/_index.jsonl.

Opt-out: LIFECYCLE_CACHE_DISABLE=1
Timeout: 8s
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Ensure shared/ and base/ are importable from this file's directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402
from shared.lifecycle_extract import extract_stages, render_record  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = PROJECT_ROOT / ".claude" / "cache"
INVOCATIONS_LOG = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
LIFECYCLE_DIR = PROJECT_ROOT / "data" / "lifecycle"
STATE_FILE = CACHE_DIR / "lifecycle-cache-state.json"
SESSION_LOG_TAIL_BYTES = 2 * 1024 * 1024  # 2 MB
SESSION_FALLBACK_WINDOW = "6 hours ago"
STATE_CAP = 500


# ---------------------------------------------------------------------------
# Sentinel helpers
# ---------------------------------------------------------------------------


def _read_sentinel() -> dict:
    """Read the state sentinel; fail-soft → empty."""
    if not STATE_FILE.exists():
        return {"sessions": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"sessions": []}


def _write_sentinel(data: dict) -> None:
    """Atomically write the sentinel file; fail-soft."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        sessions: list = data.get("sessions", [])
        # FIFO cap
        if len(sessions) > STATE_CAP:
            sessions = sessions[len(sessions) - STATE_CAP :]
        data["sessions"] = sessions
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(STATE_FILE))
    except Exception:
        pass


def _already_processed(session_id: str) -> bool:
    data = _read_sentinel()
    return session_id in data.get("sessions", [])


def _mark_processed(session_id: str) -> None:
    data = _read_sentinel()
    sessions: list = data.get("sessions", [])
    if session_id not in sessions:
        sessions.append(session_id)
    data["sessions"] = sessions
    _write_sentinel(data)


# ---------------------------------------------------------------------------
# Session start helper (mirrors roadmap-progress-enforcer pattern)
# ---------------------------------------------------------------------------


def _session_start(session_id: str) -> datetime | None:
    """Return earliest hook-invocations.jsonl timestamp for this session."""
    if not session_id or not INVOCATIONS_LOG.exists():
        return None
    try:
        with open(INVOCATIONS_LOG, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - SESSION_LOG_TAIL_BYTES))
            blob = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None

    earliest: datetime | None = None
    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        if obj.get("session") != session_id:
            continue
        ts_str = obj.get("ts", "")
        if not ts_str:
            continue
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if earliest is None or ts < earliest:
            earliest = ts
    return earliest


# ---------------------------------------------------------------------------
# git_ctx builder
# ---------------------------------------------------------------------------


def _run_git(args: list[str], timeout: int = 4) -> str:
    """Run a git command and return stdout; fail-soft → empty string."""
    try:
        r = subprocess.run(
            ["git"] + args,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if r.returncode == 0:
            return r.stdout
    except Exception:
        pass
    return ""


def _git_ctx(session_id: str) -> dict:
    """Build git context dict for extract_stages."""
    start = _session_start(session_id)
    since: str = start.isoformat() if start else SESSION_FALLBACK_WINDOW

    # commits: subject lines, cap 20
    commits_raw = _run_git(["log", f"--since={since}", "--format=%s"])
    commits = [c.strip() for c in commits_raw.splitlines() if c.strip()][:20]

    # files: unique changed files, cap 50
    files_raw = _run_git(["log", f"--since={since}", "--name-only", "--pretty="])
    files_seen: set[str] = set()
    files: list[str] = []
    for line in files_raw.splitlines():
        fp = line.strip()
        if fp and fp not in files_seen:
            files_seen.add(fp)
            files.append(fp)
            if len(files) >= 50:
                break

    # completed_tasks from hook-todos.json (cap 20)
    completed_tasks: list[str] = []
    try:
        todos_path = CACHE_DIR / "hook-todos.json"
        if todos_path.exists():
            data = json.loads(todos_path.read_text(encoding="utf-8"))
            for t in data.get("todos", []):
                if t.get("status") == "completed":
                    title = t.get("content", "")
                    if title:
                        completed_tasks.append(title)
            completed_tasks = completed_tasks[:20]
    except Exception:
        pass

    # activated skills from session-state.json
    skills: list[str] = []
    try:
        ss_path = CACHE_DIR / "session-state.json"
        if ss_path.exists():
            ss = json.loads(ss_path.read_text(encoding="utf-8"))
            skills = ss.get("activated_skills", []) or []
    except Exception:
        pass

    return {
        "commits": commits,
        "files": files,
        "completed_tasks": completed_tasks,
        "skills": skills,
    }


# ---------------------------------------------------------------------------
# Hook class
# ---------------------------------------------------------------------------


class LifecycleCache(BaseHook):
    """Stop hook: auto-cache dev-lifecycle stages to data/lifecycle/."""

    def execute(self, inp: HookInput) -> HookOutput | None:  # type: ignore[override]
        # 1. Opt-out
        if os.getenv("LIFECYCLE_CACHE_DISABLE") == "1":
            return None

        # 2. Require session_id
        session_id: str = getattr(inp, "session_id", "") or ""
        if not session_id:
            return None

        # 3. Idempotency check
        if _already_processed(session_id):
            return None

        # 4. transcript_path
        transcript_path: str = getattr(inp, "transcript", "") or ""

        # 5. Build git context
        try:
            git_ctx = _git_ctx(session_id)
        except Exception:
            git_ctx = {"commits": [], "files": [], "completed_tasks": [], "skills": []}

        # 6. Extract stages
        try:
            stages = extract_stages(transcript_path, git_ctx)
        except Exception:
            _mark_processed(session_id)
            return None

        # 7. Substantive gate
        if not stages.get("substantive"):
            _mark_processed(session_id)
            return None

        # 8. Write record
        now = datetime.now()
        now_iso = now.isoformat()
        date_str = now.strftime("%Y-%m-%d")
        sid_short = session_id[:8]
        record_name = f"{date_str}_{sid_short}.md"

        try:
            LIFECYCLE_DIR.mkdir(parents=True, exist_ok=True)
            record_path = LIFECYCLE_DIR / record_name
            content = render_record(stages, session_id, now_iso)
            record_path.write_text(content, encoding="utf-8")
        except Exception:
            _mark_processed(session_id)
            return None

        # Append to _index.jsonl
        try:
            stage_keys = ["research", "design", "impl", "review", "verify", "lessons"]
            stages_present = []
            for k in stage_keys:
                val = stages.get(k)
                if isinstance(val, list) and val:
                    stages_present.append(k)
                elif isinstance(val, dict) and any(bool(v) for v in val.values()):
                    stages_present.append(k)

            index_entry = json.dumps(
                {
                    "session_id": session_id,
                    "created": now_iso,
                    "file": record_name,
                    "stages_present": stages_present,
                },
                ensure_ascii=False,
            )
            index_path = LIFECYCLE_DIR / "_index.jsonl"
            with open(str(index_path), "a", encoding="utf-8") as fh:
                fh.write(index_entry + "\n")
        except Exception:
            pass  # index failure is non-fatal

        # 9. Mark processed
        _mark_processed(session_id)
        return None


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    LifecycleCache().run()
