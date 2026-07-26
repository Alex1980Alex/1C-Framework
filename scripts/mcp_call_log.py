"""Per-call JSONL log for MCP servers (roadmap 260713 P2.3 / B9).

Self-contained helper modeled after ``src/memory/infrastructure/trace_log.py``
but with **zero internal dependencies** (stdlib only), so it can be imported
from path-isolated MCP server processes:

  - ``memory-orchestrator`` (``python -m src.memory...`` from project root) —
    imports it as ``scripts.mcp_call_log`` (namespace package on project root);
  - ``1c-mcp-crud`` (launcher chdir's into the ``external/1c_mcp`` submodule) —
    imports it bare (``import mcp_call_log``) with the ``scripts/`` DIR on
    sys.path: putting the project root on path would shadow the submodule's
    ``src`` namespace package with the parent's regular ``src`` package.

Concurrency note: appends of short (<1KB) lines from multiple processes are
effectively atomic (single buffered write, append mode); the size-rotation is
NOT concurrency-safe — a write landing between read_bytes() and os.replace()
may be lost (~once per cap overflow). Accepted for a metadata-only log; on
Windows a busy-handle PermissionError is swallowed and rotation retries on the
next call, so unbounded growth does not occur.

Gives a **second source of truth** for MCP tool invocations that survives when
the stdio transport crashes/times out *before* the Claude Code Post-hook logs
the call (B9): the server records ``{ts, tool, ok, ms, error_type}`` the moment
its own ``call_tool`` handler returns/raises.

Conventions (mirror trace_log, do not break):
  - **Fail-soft** — never raises into a caller (file/JSON errors swallowed).
  - **Metadata only BY DEFAULT** — tool name / ok / ms / truncated error type.
    Argument/result bodies are written **only** when the caller opts in *and*
    ``MCP_CALL_LOG_CONTENT=1`` is set (roadmap 260725 J-P0.1): the LLM-judge
    needs args/result — metadata alone carries no semantic signal. With the
    flag unset the emitted record is byte-identical to the pre-J-P0.1 format
    (pinned by ``tests/unit/test_mcp_call_log_content.py``). Secrets are
    redacted **fail-closed**: an unredactable value drops the field entirely.
  - **Opt-out** — global ``MCP_CALL_LOG_DISABLE=1``.
  - **Atomic size-rotation** at ~2 MB (keep the newest half).

Target file: ``.claude/cache/mcp-<server>-calls.jsonl``.
"""

from __future__ import annotations

import json
import os
import re
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


# ── редакция секретов: два эшелона ────────────────────────────────────────────
# 1) СТРУКТУРЫ (dict/list) чистятся рекурсивно ПО КЛЮЧАМ до сериализации.
#    Regex по сериализованному тексту принципиально не ловит вложенный объект как
#    значение (`"secret": {"k": "v"}`): ветка `\S+` обрывается на пробеле и хвост
#    `"v"}` утекал бы сырым (найдено code-verify, Р1).
# 2) СТРОКИ (и сериализованный остаток) — regex, как второй эшелон.
_SECRET_KEY_RE = re.compile(
    r"\b(?:token|password|passwd|pwd|api[_-]?key|secret|credentials?|passphrase|"
    r"private[_-]?key|cookie|session[_-]?key|signature|sig|authorization|auth)\b",
    re.IGNORECASE,
)
_SECRET_KV_RE = re.compile(
    r"""(["']?\b(?:token|password|passwd|pwd|api[_-]?key|secret|credentials?|passphrase|"""
    r"""private[_-]?key|cookie|session[_-]?key)\b["']?\s*[=:]\s*)"""
    r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\S+)""",
    re.IGNORECASE,
)
_AUTH_HEADER_RE = re.compile(r"(\bauthorization\s*[:=]\s*)(\S+)", re.IGNORECASE)
_BEARER_RE = re.compile(r"\b(Bearer|Basic|Digest)\s+(\S+)", re.IGNORECASE)
_CONTENT_CAP_DEFAULT = 800
_REDACT_MAX_DEPTH = 12  # страховка от самоссылающихся структур


def _content_enabled() -> bool:
    """Пишем ли тела аргументов/результата (по умолчанию — нет)."""
    return os.environ.get("MCP_CALL_LOG_CONTENT") == "1"


def _content_cap() -> int:
    """Потолок длины дайджеста в символах."""
    try:
        return max(1, int(os.environ.get("MCP_CALL_LOG_CONTENT_CAP", _CONTENT_CAP_DEFAULT)))
    except Exception:
        return _CONTENT_CAP_DEFAULT


def _redact_struct(value: object, depth: int = 0) -> object:
    """Рекурсивно заменить значения секретных КЛЮЧЕЙ в dict/list на «***».

    Первый эшелон (Р1): работает по структуре, поэтому закрывает случай, когда
    секрет — вложенный объект, а не скаляр (`{"secret": {"k": "v"}}`).
    """
    if depth >= _REDACT_MAX_DEPTH:
        return "***[depth]"
    if isinstance(value, dict):
        out: dict = {}
        for k, v in value.items():
            out[k] = (
                "***"
                if isinstance(k, str) and _SECRET_KEY_RE.search(k)
                else _redact_struct(v, depth + 1)
            )
        return out
    if isinstance(value, (list, tuple)):
        return [_redact_struct(v, depth + 1) for v in value]
    return value


def _redact(text: str) -> str | None:
    """Вычищает секреты из СТРОКИ (второй эшелон); fail-closed — ошибка → None."""
    try:
        out = _BEARER_RE.sub(lambda m: f"{m.group(1)} ***", text)
        out = _AUTH_HEADER_RE.sub(lambda m: f"{m.group(1)}***", out)
        return _SECRET_KV_RE.sub(lambda m: f"{m.group(1)}***", out)
    except Exception:
        return None


def _digest(value: object, cap: int) -> str | None:
    """Сериализует, редактирует и усекает значение; fail-closed — None."""
    try:
        if isinstance(value, str):
            text = value
        else:
            # структуру чистим ПО КЛЮЧАМ до сериализации (эшелон 1), затем строку — regex'ом
            text = json.dumps(_redact_struct(value), ensure_ascii=False, default=str)
        redacted = _redact(text)
        if redacted is None:
            return None
        return redacted if len(redacted) <= cap else redacted[:cap] + "…[truncated]"
    except Exception:
        return None


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
    args: object | None = None,
    result: object | None = None,
    **extra: Any,
) -> None:
    """Append one MCP call record to ``.claude/cache/mcp-<server>-calls.jsonl``.

    Fully fail-soft. Metadata only unless ``MCP_CALL_LOG_CONTENT=1`` **and** the
    caller passes ``args``/``result`` (J-P0.1) — see the module docstring.

    Args:
        server: server slug, e.g. ``"memory-orchestrator"`` / ``"1c-mcp-crud"``.
        tool: tool name that was invoked.
        ok: True if the call returned without error.
        ms: wall-clock duration in milliseconds.
        error_type: low-cardinality error class (exception name / "tool_error"),
            None on success.
        args: call arguments — written as redacted ``args_digest`` only when the
            content flag is on; ignored otherwise (no cost when disabled).
        result: call result — same contract, field ``result_digest``.
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
        # Контент — только по флагу И только если вызывающий его передал.
        # fail-closed: нередактируемое значение (None из _digest) поле не пишет.
        if _content_enabled():
            cap = _content_cap()
            for field, value in (("args_digest", args), ("result_digest", result)):
                if value is None:
                    continue
                digest = _digest(value, cap)
                if digest is not None:
                    record[field] = digest
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

    For the LLM-judge (J-P0.1) the caller may additionally set ``state["args"]``
    / ``state["result"]``. They are **ignored** unless ``MCP_CALL_LOG_CONTENT=1``,
    so wiring them costs nothing while the flag is off — the decision to capture
    bodies stays with the operator, the decision *what* is capturable stays with
    the call site (never wire a server whose arguments carry production data).

    Example::

        with track_call("memory-orchestrator", name) as st:
            st["args"] = arguments
            result = await handler(...)
            st["result"] = result
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
            args=state.get("args"),
            result=state.get("result"),
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
            args=state.get("args"),
            result=state.get("result"),
            **extra,
        )


__all__ = ["log_mcp_call", "track_call"]
