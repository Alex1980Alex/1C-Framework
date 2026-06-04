"""Unit tests for §27 P0 D0.3 — audit write-path persistence.

The orchestrator's `_audit` helper revives the dead audit write-path by calling
`AuditService.log()` on route_and_save / create_link / propagate_update / rollback.
These tests pin the persistence semantics the wiring relies on: non-destructive
actions buffer (flushed on orchestrator stop), destructive actions persist
immediately, and entries are metadata-only (no content bodies).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from src.memory.ai_memory.services.audit_service import AuditAction, AuditService

pytestmark = pytest.mark.unit


def _entries(log: Path) -> list[dict]:
    if not log.exists():
        return []
    return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_create_buffers_then_flush_persists(tmp_path):
    log = tmp_path / "audit.jsonl"
    svc = AuditService(storage_path=log)

    async def run():
        await svc.log(AuditAction.CREATE, "memory", resource_id="e1", metadata={"targets": ["a"]})
        before = log.exists()  # CREATE buffers — not on disk yet
        n = await svc.flush()
        return before, n

    before, n = asyncio.run(run())
    assert before is False
    assert n == 1
    entries = _entries(log)
    assert any(e["action"] == "create" and e["resource_id"] == "e1" for e in entries)


def test_delete_persists_immediately(tmp_path):
    log = tmp_path / "audit.jsonl"
    svc = AuditService(storage_path=log)
    asyncio.run(svc.log(AuditAction.DELETE, "memory", resource_id="e2"))
    # destructive action → immediate persist, no flush needed
    assert any(e["action"] == "delete" for e in _entries(log))


def test_rollback_metadata_only_no_body(tmp_path):
    log = tmp_path / "audit.jsonl"
    svc = AuditService(storage_path=log)
    asyncio.run(
        svc.log(AuditAction.ROLLBACK, "memory", resource_id="e3", metadata={"target_version": 2})
    )
    e = next(x for x in _entries(log) if x["action"] == "rollback")
    assert e["metadata"] == {"target_version": 2}
    assert e.get("new_value") is None and e.get("old_value") is None


def test_auto_flush_at_capacity_no_deadlock(tmp_path):
    # Regression: log() holds the lock and auto-flushes at max_buffer_size; the flush
    # must NOT re-acquire the non-reentrant lock (would deadlock). wait_for guards it.
    log = tmp_path / "audit.jsonl"
    svc = AuditService(storage_path=log, max_buffer_size=3)

    async def run():
        for i in range(3):  # 3rd write hits capacity -> auto-flush
            await svc.log(AuditAction.CREATE, "memory", resource_id=f"e{i}")

    asyncio.run(asyncio.wait_for(run(), timeout=5))
    assert len(_entries(log)) == 3  # auto-flush wrote the buffer to disk
