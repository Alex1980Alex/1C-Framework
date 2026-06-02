"""Unit tests for the §26 P0 ingestion-metrics emitter (D0.3).

Verifies JSONL records are written (metadata only), opt-out is honored, and the
emitter is fail-soft. Uses CLAUDE_CACHE_DIR to redirect the log to a tmp dir.
"""

from __future__ import annotations

import importlib
import json

import pytest

pytestmark = pytest.mark.unit


def _fresh_module(monkeypatch, tmp_path):
    """Import ingest_metrics with CLAUDE_CACHE_DIR pointed at tmp + log enabled."""
    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("MEMORY_INGEST_LOG_DISABLE", raising=False)
    import src.memory.orchestrator.ingest_metrics as im

    return importlib.reload(im)


def _read_log(tmp_path):
    log = tmp_path / "memory-ingestion.log"
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


class TestRecordIngest:
    def test_writes_record(self, monkeypatch, tmp_path):
        im = _fresh_module(monkeypatch, tmp_path)
        im.record_ingest("learned_patterns", "saved", content_hash="abc123", harvester="h1")
        rows = _read_log(tmp_path)
        assert len(rows) == 1
        r = rows[0]
        assert r["event"] == "ingest"
        assert r["store"] == "learned_patterns"
        assert r["action"] == "saved"
        assert r["content_hash"] == "abc123"
        assert r["harvester"] == "h1"
        assert "ts" in r

    def test_dup_with_reason(self, monkeypatch, tmp_path):
        im = _fresh_module(monkeypatch, tmp_path)
        im.record_ingest("memory-ai", "dup", content_hash="dead", reason="content_hash_exists")
        r = _read_log(tmp_path)[0]
        assert r["action"] == "dup"
        assert r["reason"] == "content_hash_exists"

    def test_no_content_body_leaked(self, monkeypatch, tmp_path):
        im = _fresh_module(monkeypatch, tmp_path)
        im.record_ingest("learned_patterns", "saved", content_hash="h", count=3)
        r = _read_log(tmp_path)[0]
        assert "content" not in r  # metadata only
        assert r["count"] == 3

    def test_store_size(self, monkeypatch, tmp_path):
        im = _fresh_module(monkeypatch, tmp_path)
        im.record_store_size("learned_patterns", 23)
        r = _read_log(tmp_path)[0]
        assert r["event"] == "store_size"
        assert r["size"] == 23

    def test_opt_out(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        monkeypatch.setenv("MEMORY_INGEST_LOG_DISABLE", "1")
        import src.memory.orchestrator.ingest_metrics as im

        im = importlib.reload(im)
        im.record_ingest("learned_patterns", "saved", content_hash="x")
        assert _read_log(tmp_path) == []

    def test_fail_soft_on_bad_field(self, monkeypatch, tmp_path):
        im = _fresh_module(monkeypatch, tmp_path)
        # Non-serializable extra must not raise (json.dumps inside try/except).
        im.record_ingest("s", "saved", weird=object())
        # No exception == pass; log may or may not contain the line.
