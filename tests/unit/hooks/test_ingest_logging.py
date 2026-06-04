"""Unit tests for §27 P0 D0.1 — ingestion logging in pattern_harvest.

`_emit_ingest_stats` turns ingest_items' outcome counts into per-action events in
`memory-ingestion.log` (the sink that previously had zero writers), so the §25
analyzer / P4 dashboard can derive ingest_rate / dup_rate.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
_MODULE_PATH = _HOOKS_DIR / "shared" / "pattern_harvest.py"


def _load() -> Any:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("pattern_harvest", _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


ph = _load()


def _read_log(tmp_path: Path) -> list[dict[str, Any]]:
    log = tmp_path / "memory-ingestion.log"
    if not log.exists():
        return []
    return [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines() if ln.strip()]


class TestEmitIngestStats:
    def test_emits_per_action_events(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        ph._emit_ingest_stats(
            {"created": 3, "skipped_dup": 2, "skipped_cap": 1, "errors": 1}, "patterns"
        )
        ingest = [e for e in _read_log(tmp_path) if e.get("event") == "ingest"]
        actions = [e.get("action") for e in ingest]
        assert actions.count("saved") == 3
        assert actions.count("dup") == 2
        assert actions.count("skipped") == 1
        assert actions.count("error") == 1
        assert all(e.get("store") == "learned_patterns" for e in ingest)
        assert all(e.get("harvester") == "patterns" for e in ingest)

    def test_cap_carries_reason(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        ph._emit_ingest_stats({"skipped_cap": 1}, "patterns")
        ingest = [e for e in _read_log(tmp_path) if e.get("event") == "ingest"]
        assert len(ingest) == 1
        assert ingest[0]["action"] == "skipped"
        assert ingest[0]["reason"] == "cap"

    def test_zero_stats_no_events(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        ph._emit_ingest_stats(
            {"created": 0, "skipped_dup": 0, "skipped_cap": 0, "errors": 0}, "patterns"
        )
        assert _read_log(tmp_path) == []

    def test_default_harvester_label(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        ph._emit_ingest_stats({"created": 1}, None)
        ingest = [e for e in _read_log(tmp_path) if e.get("event") == "ingest"]
        assert ingest and ingest[0].get("harvester") == "ingest_items"


class TestIngestItemsDryRunGuard:
    def test_dry_run_emits_nothing(self, tmp_path, monkeypatch):
        # dry_run is a planning mode — it must NOT pollute the ingestion log
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        item = ph.HarvestItem(
            name="t", content="x" * 60, content_hash="deadbeefdeadbeef", pattern_type="workflow"
        )
        stats = ph.ingest_items([item], dry_run=True)
        assert stats["created"] == 1  # planned
        assert _read_log(tmp_path) == []  # but not logged
