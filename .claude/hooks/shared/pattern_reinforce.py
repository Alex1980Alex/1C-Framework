"""pattern_reinforce — §22 P1 reinforcement orchestration module.

Records which learned-patterns were surfaced during a session and, on
session end, reinforces them in Qdrant based on a session-success
heuristic.  Designed to be imported by Stop-hooks (Pass 2b) without
any side effects at import time.

Public API
----------
record_surfaced(session_id, items)     — call from prework/search hooks
load_surfaced(session_id)              — read surfaced map for a session
detect_session_success(ctx)            — heuristic: commit OR task done
reinforce_session(session_id, success) — orchestrate cooldown + call reinforce_pattern

All public functions are fail-soft: they never raise into a hook caller.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Resolve project root: this file lives at <root>/.claude/hooks/shared/
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[3]  # shared/ -> hooks/ -> .claude/ -> root


# Allow env override (used by tests via monkeypatch or CLAUDE_CACHE_DIR)
def _resolve_cache_dir() -> Path:
    override = os.environ.get("CLAUDE_CACHE_DIR")
    if override:
        return Path(override).resolve()
    return _PROJECT_ROOT / ".claude" / "cache"


CACHE_DIR: Path = _resolve_cache_dir()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCORE_THRESHOLD: float = 0.3
DEFAULT_COOLDOWN_HOURS: float = 6.0
DEFAULT_CAP: int = 50
SENTINEL_CAP: int = 500


def _log_lifecycle(event: str, **fields: Any) -> None:
    """Fail-soft §22 lifecycle trace (shared log with reinforce.py via src import).

    The reinforce_session result dict (applied/skipped/errors/status) is otherwise
    discarded by the Stop-hook caller; this persists it so the reinforcement loop
    is observable. Never raises into the hook.
    """
    try:
        src_path = str(_PROJECT_ROOT / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        from memory.vector_memory.lifecycle_log import log_event

        log_event(event, **fields)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    """Write *data* as JSON to *path* atomically via temp-file + rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix="pr-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        if sys.platform == "win32" and path.exists():
            path.unlink()
        os.replace(tmp, str(path))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _surfaced_path(session_id: str) -> Path:
    return CACHE_DIR / f"surfaced-patterns-{session_id}.json"


def _sentinel_path() -> Path:
    return CACHE_DIR / "p1-reinforcement-state.json"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_surfaced(session_id: str, items: list[tuple[str, float]]) -> None:
    """Record that *items* (pattern_id, score) were surfaced in *session_id*.

    Keeps the *maximum* score seen per pattern_id across multiple calls.
    No-op if *session_id* is empty or *items* is empty.
    Fail-soft: swallows all exceptions.
    """
    if not session_id or not items:
        return
    try:
        path = _surfaced_path(session_id)
        existing: dict[str, float] = {}
        if path.exists():
            try:
                with open(path, encoding="utf-8") as fh:
                    raw = json.load(fh)
                existing = raw.get("patterns", {})
            except Exception:
                existing = {}

        for pid, score in items:
            existing[pid] = max(existing.get(pid, 0.0), score)

        payload: dict[str, Any] = {
            "session_id": session_id,
            "patterns": existing,
            "updated": datetime.now().isoformat(),
        }
        _atomic_write(path, payload)
    except Exception:
        pass


def load_surfaced(session_id: str) -> dict[str, float]:
    """Return ``{pattern_id: score}`` for *session_id*, or ``{}`` on any error."""
    if not session_id:
        return {}
    try:
        path = _surfaced_path(session_id)
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        return dict(raw.get("patterns", {}))
    except Exception:
        return {}


def detect_session_success(ctx: dict[str, Any]) -> bool:
    """Heuristic: session was successful if a commit happened or a task completed.

    *ctx* is the dict produced by ``session-memory-save.collect_context()``
    (keys: ``commits``, ``completed_tasks``, ``files_changed``, …).

    Returns True when *commits* or *completed_tasks* is non-empty.

    # TODO P1.x: transcript-based no-error gate — requires reading the
    # transcript JSON to check that the last Bash exit code was 0.  That
    # path is out of scope for §22 P1 Pass 2a (no transcript access here).
    """
    return bool(ctx.get("commits")) or bool(ctx.get("completed_tasks"))


def reinforce_session(
    session_id: str,
    success: bool,
    *,
    cooldown_hours: float = DEFAULT_COOLDOWN_HOURS,
    cap: int = DEFAULT_CAP,
    reinforce_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reinforce surfaced patterns for *session_id* with a success/failure signal.

    Flow
    ----
    1. Opt-out gate (``P1_REINFORCE_DISABLE=1``).
    2. Per-session idempotency: skip if already processed.
    3. Load surfaced patterns; filter by ``SCORE_THRESHOLD``; sort desc; cap.
    4. Per-pattern cooldown: skip patterns reinforced within *cooldown_hours*.
    5. Call *reinforce_fn* (defaults to lazy import of
       ``memory.vector_memory.reinforce.reinforce_pattern``).
    6. Persist updated sentinel; FIFO-trim to ``SENTINEL_CAP``.
    7. Optionally clean up the surfaced file.

    Returns a status dict — never raises.
    """
    if os.getenv("P1_REINFORCE_DISABLE") == "1":
        return {"status": "disabled"}

    if not session_id:
        return {"status": "no-session"}

    try:
        # --- Load sentinel state ---
        sentinel = _sentinel_path()
        state: dict[str, Any] = {"sessions": [], "patterns": {}}
        if sentinel.exists():
            try:
                with open(sentinel, encoding="utf-8") as fh:
                    loaded = json.load(fh)
                state = {
                    "sessions": list(loaded.get("sessions", [])),
                    "patterns": dict(loaded.get("patterns", {})),
                }
            except Exception:
                state = {"sessions": [], "patterns": {}}

        # --- Per-session idempotency ---
        if session_id in state["sessions"]:
            return {"status": "already-processed", "session_id": session_id}

        # --- Resolve reinforce_fn lazily ---
        if reinforce_fn is None:
            src_path = str(_PROJECT_ROOT / "src")
            if src_path not in sys.path:
                sys.path.insert(0, src_path)
            from memory.vector_memory.reinforce import reinforce_pattern

            reinforce_fn = reinforce_pattern

        # --- Filter + sort surfaced patterns ---
        surfaced = load_surfaced(session_id)
        candidates = sorted(
            [(pid, sc) for pid, sc in surfaced.items() if sc >= SCORE_THRESHOLD],
            key=lambda t: t[1],
            reverse=True,
        )[:cap]

        # --- Per-pattern cooldown + reinforce ---
        now = datetime.now()
        applied = 0
        skipped = 0
        errors = 0

        for pid, _score in candidates:
            last_str = state["patterns"].get(pid)
            if last_str:
                try:
                    last_dt = datetime.fromisoformat(last_str)
                    if (now - last_dt) < timedelta(hours=cooldown_hours):
                        skipped += 1
                        continue
                except (ValueError, TypeError):
                    pass  # Corrupt timestamp — proceed with reinforce

            try:
                result = reinforce_fn(pid, success)
                if result.get("success"):
                    state["patterns"][pid] = now.isoformat()
                    applied += 1
                else:
                    errors += 1
            except Exception:
                errors += 1

        # --- Update + FIFO-trim sentinel ---
        sessions_list: list[str] = state["sessions"]
        sessions_list.append(session_id)
        if len(sessions_list) > SENTINEL_CAP:
            sessions_list = sessions_list[-SENTINEL_CAP:]
        state["sessions"] = sessions_list

        patterns_dict: dict[str, str] = state["patterns"]
        if len(patterns_dict) > SENTINEL_CAP:
            # Drop oldest by parsed datetime (robust against string-order edge cases).
            # Unparseable timestamps are treated as oldest so they get evicted first.
            def _parse_ts(v: str) -> datetime:
                try:
                    return datetime.fromisoformat(v)
                except (ValueError, TypeError):
                    return datetime.min

            sorted_pids = sorted(patterns_dict.keys(), key=lambda k: _parse_ts(patterns_dict[k]))
            for old_pid in sorted_pids[: len(patterns_dict) - SENTINEL_CAP]:
                del patterns_dict[old_pid]
        state["patterns"] = patterns_dict

        _atomic_write(sentinel, state)

        # --- Cleanup surfaced file ---
        try:
            sp = _surfaced_path(session_id)
            if sp.exists():
                sp.unlink()
        except Exception:
            pass

        _log_lifecycle(
            "session",
            session_id=session_id[:8],
            success=success,
            applied=applied,
            skipped=skipped,
            errors=errors,
            candidates=len(candidates),
        )
        return {
            "status": "ok",
            "session_id": session_id,
            "success": success,
            "applied": applied,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as exc:
        _log_lifecycle(
            "session_error",
            session_id=session_id[:8],
            error=f"{type(exc).__name__}: {exc}"[:160],
        )
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
