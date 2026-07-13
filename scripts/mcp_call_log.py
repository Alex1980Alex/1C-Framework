"""Per-call JSONL log for MCP servers (roadmap 260713 P2.3 / B9).

Self-contained helper modeled after ``src/memory/infrastructure/trace_log.py``
but with **zero internal dependencies** (stdlib only), so it can be imported
from path-isolated MCP server processes:

  - ``memory-orchestrator`` (``python -m src.memory...`` from project root)
  - ``1c-mcp-crud`` (launcher chdir's into the ``external/1c_mcp`` submodule)

Both reach it as ``scripts.mcp_call_log`` (namespace package on project root).

Gives a **second source of truth** for MCP tool invocations that survives when
the stdio transport crashes/times out *before* the Claude Code Post-hook logs
the call (B9): the server records ``{ts, tool, ok, ms, error_type}`` the moment
its own ``call_tool`` handler returns/raises.

Conventions (mirror trace_log, do not break):
  - **Fail-soft** — never raises into a caller (file/JSON errors swallowed).
  - **Metadata only** — tool name / ok / ms / truncated error type; NEVER
    argument or result bodies.
  - **Opt-out** — global ``MCP_CALL_LOG_DISABLE=1``.
  - **Atomic size-rotation** at ~2 MB (keep the newest half).

Target file: ``.claude/cache/mcp-<server>-calls.jsonl``.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

# scripts/ -> <project root>
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_CAP_BYTES = 2_000_000


def _cache_dir() -> Path:
    """Resolve the cache dir per call (honors CLAUDE_CACHE_DIR for tests/relocation)."""
    override = os.environ.get("CLAUDE_CACHE_DIR")
    return Path(override) if override else _PROJECT_ROOT / ".claude" / "cache"


def _rotate(path: Path) -> None:
    """Atomic size-rotation: keep the newest half when the file exceeds the cap."""
    try:
        if path.exists() and path.stat().st_size > _CAP_BYTES:
            data = path.read_bytes()[-(_CAP_BYTES // 2) :]
            idx = data.find(b"\n")
            if idx != -1:
                data = data[idx + 1 :]  # drop partial first line
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix="mcpcall-")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, str(path))
            except Exception:
                os.unlink(tmp)
                raise
    except Exception:
        pass  # rotation failure never blocks the append


def log_mcp_call(
    server: str,
    tool: str,
    *,
    ok: bool,
    ms: float,
    error_type: str | None = None,
    **extra: Any,
) -> None:
    """Append one MCP call record to ``.claude/cache/mcp-<server>-calls.jsonl``.

    Fully fail-soft. Metadata only — never pass argument/result bodies.

    Args:
        server: server slug, e.g. ``"memory-orchestrator"`` / ``"1c-mcp-crud"``.
        tool: tool name that was invoked.
        ok: True if the call returned without error.
        ms: wall-clock duration in milliseconds.
        error_type: low-cardinality error class (exception name / "tool_error"),
            None on success.
        **extra: additional metadata-only fields (counts/ids/floats).
    """
    if os.environ.get("MCP_CALL_LOG_DISABLE") == "1":  # global kill-switch
        return
    try:
        path = _cache_dir() / f"mcp-{server}-calls.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        _rotate(path)
        record: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "server": server,
            "tool": tool,
            "ok": bool(ok),
            "ms": round(float(ms), 1),
        }
        if error_type:
            record["error_type"] = str(error_type)[:120]
        if extra:
            record.update(extra)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass  # fully fail-soft: never raise


@contextmanager
def track_call(server: str, tool: str, **extra: Any) -> Iterator[dict[str, Any]]:
    """Time an MCP tool invocation and log it on exit (success or exception).

    Yields a mutable ``state`` dict; set ``state["ok"] = False`` and
    ``state["error_type"] = "..."`` inside the block to record a soft failure
    (e.g. a result flagged ``isError`` without raising). An escaping exception
    is recorded automatically (``ok=False``, ``error_type=<ExcName>``) and then
    re-raised.

    Example::

        with track_call("memory-orchestrator", name) as st:
            result = await handler(...)
            if getattr(result, "isError", False):
                st["ok"] = False
                st["error_type"] = "tool_error"
    """
    state: dict[str, Any] = {"ok": True, "error_type": None}
    start = time.perf_counter()
    try:
        yield state
    except BaseException as exc:  # log then re-raise (fail-soft logging only)
        ms = (time.perf_counter() - start) * 1000.0
        log_mcp_call(
            server,
            tool,
            ok=False,
            ms=ms,
            error_type=type(exc).__name__,
            **extra,
        )
        raise
    else:
        ms = (time.perf_counter() - start) * 1000.0
        log_mcp_call(
            server,
            tool,
            ok=bool(state.get("ok", True)),
            ms=ms,
            error_type=state.get("error_type"),
            **extra,
        )


__all__ = ["log_mcp_call", "track_call"]
