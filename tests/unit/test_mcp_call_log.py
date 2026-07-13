"""Unit tests for the per-call MCP log helper (roadmap 260713 P2.3 / B9).

Covers ``scripts/mcp_call_log.py`` (shared JSONL writer + timing context) and
the launcher monkeypatch shape used to instrument ``OneCClient.call_tool``
without touching the vendored ``external/1c_mcp`` submodule.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from scripts import mcp_call_log

pytestmark = pytest.mark.unit


def _read(cache: Path, server: str) -> list[dict]:
    p = cache / f"mcp-{server}-calls.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture()
def cache(tmp_path, monkeypatch) -> Path:
    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("MCP_CALL_LOG_DISABLE", raising=False)
    return tmp_path


# --- log_mcp_call --------------------------------------------------------


def test_log_writes_record_with_required_fields(cache):
    mcp_call_log.log_mcp_call("memory-orchestrator", "unified_search", ok=True, ms=12.34)
    (rec,) = _read(cache, "memory-orchestrator")
    assert rec["server"] == "memory-orchestrator"
    assert rec["tool"] == "unified_search"
    assert rec["ok"] is True
    assert rec["ms"] == 12.3  # rounded to 0.1
    assert "error_type" not in rec  # omitted on success
    assert "ts" in rec


def test_log_records_error_type_truncated(cache):
    mcp_call_log.log_mcp_call("1c-mcp-crud", "execute_query", ok=False, ms=5, error_type="X" * 300)
    (rec,) = _read(cache, "1c-mcp-crud")
    assert rec["ok"] is False
    assert len(rec["error_type"]) == 120


def test_log_includes_extra_metadata(cache):
    mcp_call_log.log_mcp_call("srv", "t", ok=True, ms=1, count=7)
    (rec,) = _read(cache, "srv")
    assert rec["count"] == 7


def test_opt_out_env_suppresses_write(cache, monkeypatch):
    monkeypatch.setenv("MCP_CALL_LOG_DISABLE", "1")
    mcp_call_log.log_mcp_call("srv", "t", ok=True, ms=1)
    assert _read(cache, "srv") == []


def test_log_is_fail_soft_on_bad_cache_dir(monkeypatch, tmp_path):
    # Point cache at a path that cannot be a directory (a file) → must not raise.
    bad = tmp_path / "afile"
    bad.write_text("x")
    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(bad / "sub"))
    # Should swallow the error silently.
    mcp_call_log.log_mcp_call("srv", "t", ok=True, ms=1)


def test_rotation_keeps_newest_half(cache, monkeypatch):
    monkeypatch.setattr(mcp_call_log, "_CAP_BYTES", 2000)
    for i in range(400):
        mcp_call_log.log_mcp_call("srv", f"tool{i}", ok=True, ms=1)
    recs = _read(cache, "srv")
    # File was rotated (kept newest half) → far fewer than 400 rows remain,
    # and the very last write survives.
    assert 0 < len(recs) < 400
    assert recs[-1]["tool"] == "tool399"
    # Every surviving line is valid JSON (no partial first line).
    assert all("tool" in r for r in recs)


# --- track_call ----------------------------------------------------------


def test_track_call_success(cache):
    async def run():
        with mcp_call_log.track_call("memory-orchestrator", "route_and_save") as st:
            assert st["ok"] is True

    asyncio.run(run())
    (rec,) = _read(cache, "memory-orchestrator")
    assert rec["tool"] == "route_and_save"
    assert rec["ok"] is True
    assert rec["ms"] >= 0


def test_track_call_soft_error(cache):
    async def run():
        with mcp_call_log.track_call("1c-mcp-crud", "execute_query") as st:
            st["ok"] = False
            st["error_type"] = "tool_error"

    asyncio.run(run())
    (rec,) = _read(cache, "1c-mcp-crud")
    assert rec["ok"] is False
    assert rec["error_type"] == "tool_error"


def test_track_call_exception_reraises_and_logs(cache):
    async def run():
        with mcp_call_log.track_call("1c-mcp-crud", "post_document"):
            raise ValueError("boom")

    with pytest.raises(ValueError):
        asyncio.run(run())
    (rec,) = _read(cache, "1c-mcp-crud")
    assert rec["ok"] is False
    assert rec["error_type"] == "ValueError"


# --- launcher instrumentation shape --------------------------------------


def test_instrument_wrap_shape_success_and_error(cache):
    """The wrapper monkeypatch (mirrors launcher._instrument_call_tool) logs
    ok/isError from CallToolResult and re-dispatches to the original method."""

    class _Result:
        def __init__(self, is_error):
            self.isError = is_error

    class OneCClient:
        async def call_tool(self, name, arguments):
            return _Result(is_error=(name == "boom"))

    _orig = OneCClient.call_tool

    async def call_tool(self, name, arguments):
        with mcp_call_log.track_call("1c-mcp-crud", name) as st:
            result = await _orig(self, name, arguments)
            if getattr(result, "isError", False):
                st["ok"] = False
                st["error_type"] = "tool_error"
            return result

    call_tool._mcp_call_logged = True
    OneCClient.call_tool = call_tool

    c = OneCClient()
    asyncio.run(c.call_tool("execute_query", {}))
    asyncio.run(c.call_tool("boom", {}))

    recs = _read(cache, "1c-mcp-crud")
    assert [(r["tool"], r["ok"]) for r in recs] == [
        ("execute_query", True),
        ("boom", False),
    ]
    assert recs[1]["error_type"] == "tool_error"
    # idempotency guard flag is present on the wrapper
    assert getattr(OneCClient.call_tool, "_mcp_call_logged", False) is True


def test_instrument_is_idempotent():
    """Re-running the instrument logic must not double-wrap (mirrors the
    launcher's `_mcp_call_logged` guard)."""

    class OneCClient:
        async def call_tool(self, name, arguments):
            return None

    def instrument():
        if getattr(OneCClient.call_tool, "_mcp_call_logged", False):
            return  # already wrapped
        _orig = OneCClient.call_tool

        async def call_tool(self, name, arguments):
            with mcp_call_log.track_call("1c-mcp-crud", name):
                return await _orig(self, name, arguments)

        call_tool._mcp_call_logged = True
        OneCClient.call_tool = call_tool

    instrument()
    first = OneCClient.call_tool
    instrument()  # second run must be a no-op
    assert OneCClient.call_tool is first
