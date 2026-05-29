#!/usr/bin/env python3
"""
Hook: roadmap-progress-enforcer
Event: Stop
Matcher: (none — all Stop events)
Purpose: SOFT reminder to update the active roadmap's §18 Progress Log when a
         milestone (PR merge) happened this session but no docs/roadmap/ file was
         touched. Implements §19.3 P1 "trigger-detection" item of roadmap
         260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md — closes the gap where §18
         updates relied only on memory anchor feedback_roadmap_progress_log_protocol.
Timeout: 5s
Opt-out: ROADMAP_PROGRESS_NO_ENFORCE=1

Why "soft": blocks Stop AT MOST ONCE per session (sentinel in
.claude/cache/roadmap-progress-enforcer-state.json). After reminding once, a
repeated Stop in the same session passes — so it never deadlocks if Claude
decides the milestone doesn't warrant a §18 entry.

Milestone detection (conservative, precision-first): scans the transcript JSONL
for Bash `tool_use` blocks whose command runs `gh pr merge` or `git merge`
(excluding `--abort`). Parsing tool_use inputs (not raw text) avoids
false-positives from merely READING a roadmap full of "MERGED" strings.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INVOCATIONS_LOG = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
STATE_FILE = Path(__file__).resolve().parent / "cache" / "roadmap-progress-enforcer-state.json"
SESSION_LOG_TAIL_BYTES = 2 * 1024 * 1024  # 2MB tail, matches docs-change-enforcer
SESSION_FALLBACK_WINDOW = "6 hours ago"
STATE_CAP = 200

# Bash commands that constitute a "PR merged" milestone (§19 trigger #1).
# Matches the two common, unambiguous merge forms: `gh pr merge ...` and a direct
# `git merge ...`. Precision over recall (false BLOCK annoys more than a rare miss):
#   - `\bgit\s+merge\b` also matches `git merge-base` (hyphen = word boundary) →
#     merge-base explicitly excluded.
#   - `merge\.` deliberately NOT excluded: `git config merge.tool` already fails
#     _MERGE_CMD_RE (git not immediately followed by merge), so it was redundant.
#   - Known uncovered edge: `-c`-prefixed merges like `git -c merge.ff=false merge X`
#     (git not directly followed by merge). Broadening to `git.*merge` would
#     false-positive on `git log --grep merge` etc., so left uncovered by design.
_MERGE_CMD_RE = re.compile(r"\bgh\s+pr\s+merge\b|\bgit\s+merge\b", re.IGNORECASE)
_MERGE_EXCLUDE_RE = re.compile(r"--abort|--quit|\bmerge-base\b", re.IGNORECASE)


def _read_stdin() -> dict:
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        return json.loads(raw)
    except Exception:
        return {}


def _iter_tool_uses(obj):
    """Recursively yield dicts that look like Claude Code tool_use blocks."""
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name"):
            yield obj
        for v in obj.values():
            yield from _iter_tool_uses(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_tool_uses(item)


def _detect_merge_milestone(transcript_path: str) -> str | None:
    """Return the first merge command found in transcript tool_use blocks, or None."""
    if not transcript_path:
        return None
    p = Path(transcript_path)
    if not p.exists():
        return None
    try:
        with open(p, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - SESSION_LOG_TAIL_BYTES))
            blob = f.read().decode("utf-8", errors="replace")
    except OSError:
        return None

    for line in blob.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        for tu in _iter_tool_uses(entry):
            if tu.get("name") != "Bash":
                continue
            cmd = (tu.get("input") or {}).get("command", "")
            if not isinstance(cmd, str):
                continue
            if _MERGE_CMD_RE.search(cmd) and not _MERGE_EXCLUDE_RE.search(cmd):
                return cmd.strip().splitlines()[0][:120]
    return None


def _session_start(session_id: str) -> datetime | None:
    """Earliest hook-invocations.jsonl ts for this session (practical session start)."""
    if not session_id or not INVOCATIONS_LOG.exists():
        return None
    try:
        with open(INVOCATIONS_LOG, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - SESSION_LOG_TAIL_BYTES))
            blob = f.read().decode("utf-8", errors="replace")
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


def _roadmap_touched_this_session(session_id: str) -> bool:
    """True if any docs/roadmap/ file changed this session (working tree OR commits).

    Includes auto-save commits intentionally: auto-git-save may have committed the
    §18 edit (known preempt pattern), and that still counts as "roadmap updated".
    """
    # 1. Working tree (always current session)
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", timeout=3,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                fp = line[2:].lstrip().strip('"').replace("\\", "/") if len(line) > 2 else ""
                if fp.lower().startswith("docs/roadmap/"):
                    return True
    except Exception:
        pass

    # 2. Commits since session start (session-bounded if possible)
    start = _session_start(session_id)
    since = start.isoformat() if start else SESSION_FALLBACK_WINDOW
    try:
        r = subprocess.run(
            ["git", "log", f"--since={since}", "--name-only", "--pretty=format:"],
            capture_output=True, text=True, encoding="utf-8", timeout=4,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if line.strip().replace("\\", "/").lower().startswith("docs/roadmap/"):
                    return True
    except Exception:
        pass
    return False


def _already_reminded(session_id: str) -> bool:
    if not session_id or not STATE_FILE.exists():
        return False
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return session_id in data
    except Exception:
        return False


def _mark_reminded(session_id: str) -> None:
    if not session_id:
        return
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        data[session_id] = datetime.now().isoformat()
        # FIFO cap
        if len(data) > STATE_CAP:
            for k in list(data.keys())[: len(data) - STATE_CAP]:
                data.pop(k, None)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(STATE_FILE))
    except Exception:
        pass


def main() -> None:
    try:
        from shared.invocation_logger import InvocationTimer

        timer = InvocationTimer("roadmap-progress-enforcer", event="Stop").start()
    except Exception:
        timer = None

    if os.environ.get("ROADMAP_PROGRESS_NO_ENFORCE") == "1":
        if timer:
            timer.log(outcome="allow")
        sys.exit(0)

    inp = _read_stdin()
    session_id = inp.get("session_id", "")
    transcript = inp.get("transcript_path", inp.get("transcript", ""))
    if timer:
        timer.session_id = session_id

    try:
        merge_cmd = _detect_merge_milestone(transcript)
        if not merge_cmd:
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)  # No milestone → nothing to enforce

        if _roadmap_touched_this_session(session_id):
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)  # §18 already updated (or roadmap edited) this session

        if _already_reminded(session_id):
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)  # Soft: remind only once per session

        _mark_reminded(session_id)

        reason = (
            "[ROADMAP-PROGRESS-ENFORCER] Обнаружен milestone этой сессии "
            "(merge-команда), но ни один файл в docs/roadmap/ не обновлён.\n\n"
            f"Триггер: `{merge_cmd}`\n\n"
            "Протокол §19 (roadmap 260523) требует после PR merge / phase DONE "
            "обновить §18 Implementation Progress Log активной дорожной карты:\n"
            "1. Добавить dated-запись `YYYY-MM-DD` на top §18 (reverse-chrono)\n"
            "2. Обновить phase table + PRs table + Next priorities\n"
            "3. Commit `docs(roadmap): progress log YYYY-MM-DD <summary>`\n\n"
            "Если milestone НЕ roadmap-worthy (routine merge, no deliverable) — "
            "просто заверши снова: напоминание повторно не сработает в этой сессии.\n"
            "Отключить навсегда: ROADMAP_PROGRESS_NO_ENFORCE=1"
        )
        out = {"decision": "block", "reason": reason}
        sys.stdout.buffer.write(json.dumps(out, ensure_ascii=False).encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()
        if timer:
            timer.log(outcome="block")
        sys.exit(2)  # Block stop (once)
    except SystemExit:
        raise  # exit codes are control flow, not errors — don't swallow
    except Exception as e:
        # Graceful degradation: never block on internal error
        if timer:
            timer.log(outcome="error", error=f"{type(e).__name__}: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
