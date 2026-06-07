"""Unit tests for the content_hash backfill planner (§26 P0, D0.4).

Pure planner only — Qdrant-independent. Verifies idempotency (re-run = no-op)
and that the derived key matches the canonical content_key.
"""

from __future__ import annotations

import pytest

from scripts.backfill_content_hash import build_plan
from src.memory.orchestrator.content_hash import content_key

pytestmark = pytest.mark.unit


def _point(pid: str, payload: dict) -> dict:
    return {"id": pid, "payload": payload}


class TestBuildPlan:
    def test_stamps_missing_hash(self):
        pts = [_point("p1", {"content": "alpha"}), _point("p2", {"description": "beta"})]
        plan = build_plan(pts)
        assert len(plan["to_update"]) == 2
        assert plan["already_ok"] == 0
        by_id = {u["id"]: u["content_hash"] for u in plan["to_update"]}
        assert by_id["p1"] == content_key({"content": "alpha"})
        assert by_id["p2"] == content_key({"description": "beta"})

    def test_idempotent_when_already_stamped(self):
        payload = {"content": "gamma"}
        payload["content_hash"] = content_key(payload)
        plan = build_plan([_point("p1", payload)])
        assert plan["to_update"] == []
        assert plan["already_ok"] == 1

    def test_corrects_stale_hash(self):
        plan = build_plan([_point("p1", {"content": "delta", "content_hash": "0000000000000000"})])
        assert len(plan["to_update"]) == 1
        assert plan["to_update"][0]["content_hash"] == content_key({"content": "delta"})

    def test_counts_empty_content(self):
        plan = build_plan([_point("p1", {"content": ""}), _point("p2", {"content": "x"})])
        assert plan["empty_content"] == 1
        assert plan["total"] == 2

    def test_rerun_after_apply_is_noop(self):
        """Simulate apply by stamping, then re-plan → no updates."""
        pts = [_point("p1", {"content": "eps"}), _point("p2", {"content": "zeta"})]
        plan1 = build_plan(pts)
        for u in plan1["to_update"]:
            next(p for p in pts if p["id"] == u["id"])["payload"]["content_hash"] = u[
                "content_hash"
            ]
        plan2 = build_plan(pts)
        assert plan2["to_update"] == []
        assert plan2["already_ok"] == 2
