"""§27 P3+P4 — event envelope reader-adapter + unified observability report.

Covers:
  - event_envelope.normalize() projection per sink + known_sinks registry
  - event_envelope.make_envelope() CloudEvents shape
  - observability report aggregators (ingestion/maintenance/routing/read/
    propagation/circuit/audit) + freshness/regression detection

All offline / Qdrant-independent. Marker: unit.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# D3.1 — event envelope
# --------------------------------------------------------------------------- #
class TestEventEnvelope:
    def test_normalize_ingestion(self):
        from src.memory.infrastructure.event_envelope import normalize

        raw = {
            "ts": "2026-06-05T01:00:00.000",
            "event": "ingest",
            "store": "learned_patterns",
            "action": "saved",
            "content_hash": "abc123",
            "harvester": "patterns",
        }
        env = normalize("ingestion", raw)
        assert env["source"] == "ingestion"
        assert env["type"] == "ingest"
        assert env["content_hash"] == "abc123"
        assert env["store"] == "learned_patterns" and env["action"] == "saved"

    def test_normalize_surfacing_uses_outcome_as_type(self):
        from src.memory.infrastructure.event_envelope import normalize

        raw = {
            "ts": "2026-06-05T01:00:00.000",
            "hook": "memory-first-hook",
            "outcome": "injected",
            "duration_ms": 1234.5,
            "cache": "miss",
            "tei": "down",
        }
        env = normalize("surfacing", raw)
        assert env["type"] == "injected"
        assert env["latency_ms"] == 1234.5
        assert env["content_hash"] == ""  # surfacing carries no fact key

    def test_normalize_audit_maps_action_and_metadata_hash(self):
        from src.memory.infrastructure.event_envelope import normalize

        raw = {
            "timestamp": "2026-06-05T01:00:00",
            "action": "create",
            "resource_type": "pattern",
            "resource_id": "p1",
            "session_id": "sess9",
            "success": True,
            "metadata": {"content_hash": "deadbeef"},
        }
        env = normalize("audit", raw)
        assert env["type"] == "create"
        assert env["ts"] == "2026-06-05T01:00:00"
        assert env["correlation_id"] == "sess9"
        assert env["content_hash"] == "deadbeef"
        assert env["success"] is True

    def test_normalize_non_dict_is_failsoft(self):
        from src.memory.infrastructure.event_envelope import normalize

        env = normalize("ingestion", ["not", "a", "dict"])  # type: ignore[arg-type]
        assert env["source"] == "ingestion" and env["type"] == ""

    def test_known_sinks_covers_all_labels(self):
        from src.memory.infrastructure.event_envelope import SOURCE_LABELS, known_sinks

        sinks = known_sinks(PROJECT_ROOT)
        labels = {label for label, _ in sinks}
        assert labels == set(SOURCE_LABELS)
        # audit lives under data/services, the rest under .claude/cache
        audit = dict(sinks)["audit"]
        assert audit.parts[-2:] == ("services", "audit.jsonl")

    def test_make_envelope_cloudevents_shape(self):
        from src.memory.infrastructure.event_envelope import make_envelope

        env = make_envelope(
            "ingestion",
            "ingest",
            ts="2026-06-05T01:00:00.000",
            content_hash="h1",
            correlation_id="c1",
            store="lp",
        )
        assert env["specversion"] == "1.0"
        assert env["source"] == "ingestion" and env["type"] == "ingest"
        assert env["content_hash"] == "h1" and env["correlation_id"] == "c1"
        assert env["store"] == "lp" and "id" in env


# --------------------------------------------------------------------------- #
# D4.1 — report aggregators
# --------------------------------------------------------------------------- #
class TestReportAggregators:
    def test_analyze_ingestion_dup_rate_and_growth(self):
        from scripts.memory_observability_report import analyze_ingestion

        rows = [
            {"event": "store_size", "store": "lp", "size": 10},
            {"event": "ingest", "action": "saved", "harvester": "patterns"},
            {"event": "ingest", "action": "dup", "harvester": "patterns"},
            {"event": "ingest", "action": "saved", "harvester": "skills"},
            {"event": "store_size", "store": "lp", "size": 13},
        ]
        out = analyze_ingestion(rows)
        assert out["saved"] == 2
        assert out["dup_rate"] == round(1 / 3, 4)
        assert out["store_growth"]["lp"] == 3
        assert out["by_harvester"] == {"patterns": 2, "skills": 1}

    def test_analyze_maintenance_forget_rate(self):
        from scripts.memory_observability_report import analyze_maintenance

        rows = [
            {
                "event": "run",
                "applied": True,
                "forget": {"archive": 2, "keep": 8},
                "cross_store_dup_rate": 0.2,
                "store_sizes": {"lp": 25},
            },
        ]
        out = analyze_maintenance(rows)
        assert out["forget_volume"] == 2
        assert out["forget_rate"] == 0.2
        assert out["applied_runs"] == 1
        assert out["store_sizes_latest"] == {"lp": 25}

    def test_analyze_read_hit_rate_and_source(self):
        from scripts.memory_observability_report import analyze_read

        rows = [
            {
                "event": "search",
                "final": 3,
                "latency_ms": 100,
                "arm_hits": {"skill": 2, "pattern_dense": 0},
            },
            {
                "event": "search",
                "final": 0,
                "latency_ms": 50,
                "arm_hits": {"skill": 0, "pattern_dense": 1},
            },
        ]
        out = analyze_read(rows)
        assert out["searches"] == 2
        assert out["hit_rate"] == 0.5
        assert out["source_hit_rate"]["skill"] == 0.5
        assert out["source_hit_rate"]["pattern_dense"] == 0.5

    def test_analyze_propagation_reach(self):
        from scripts.memory_observability_report import analyze_propagation

        rows = [
            {
                "event": "propagate",
                "entities_updated": 4,
                "final_depth": 2,
                "cascades_prevented": 1,
            },
            {
                "event": "propagate",
                "entities_updated": 0,
                "final_depth": 0,
                "cascades_prevented": 3,
            },
        ]
        out = analyze_propagation(rows)
        assert out["events"] == 2 and out["max_reach"] == 4
        assert out["cascades_prevented"] == 4 and out["avg_reach"] == 2.0

    def test_analyze_circuit_opens(self):
        from scripts.memory_observability_report import analyze_circuit

        rows = [
            {"event": "transition", "circuit": "qdrant", "old": "closed", "new": "open"},
            {"event": "transition", "circuit": "qdrant", "old": "open", "new": "half_open"},
        ]
        out = analyze_circuit(rows)
        assert out["transitions"] == 2 and out["opens"] == 1
        assert out["by_circuit"] == {"qdrant": 2}

    def test_analyze_audit_coverage(self):
        from scripts.memory_observability_report import analyze_audit

        rows = [
            {"action": "create", "success": True},
            {"action": "link", "success": True},
            {"action": "rollback", "success": False},
        ]
        out = analyze_audit(rows)
        assert out["total"] == 3
        assert out["error_rate"] == round(1 / 3, 4)
        assert out["by_action"]["create"] == 1


# --------------------------------------------------------------------------- #
# D4.2 — freshness / regression detection
# --------------------------------------------------------------------------- #
class TestFreshnessRegression:
    def test_stale_sink_flagged_as_regression(self, tmp_path, monkeypatch):
        import scripts.memory_observability_report as rep

        # Point the sink registry at a temp project root with one stale + one fresh sink.
        cache = tmp_path / ".claude" / "cache"
        cache.mkdir(parents=True)
        now = datetime(2026, 6, 5, 12, 0, 0)
        old_ts = (now - timedelta(hours=200)).isoformat(timespec="milliseconds")
        fresh_ts = (now - timedelta(hours=1)).isoformat(timespec="milliseconds")
        (cache / "memory-ingestion.log").write_text(
            json.dumps({"ts": old_ts, "event": "ingest", "action": "saved"}) + "\n",
            encoding="utf-8",
        )
        (cache / "confidence-lifecycle.log").write_text(
            json.dumps({"ts": fresh_ts, "event": "save"}) + "\n", encoding="utf-8"
        )
        monkeypatch.setattr(rep, "PROJECT_ROOT", tmp_path)

        fresh = rep.analyze_freshness(now, stale_hours=168)
        by_src = {f["source"]: f for f in fresh}
        assert by_src["ingestion"]["status"] == "stale"  # 200h > 168h
        assert by_src["lifecycle"]["status"] == "fresh"  # 1h
        assert by_src["routing"]["status"] == "missing"  # never written (cold, not regression)

    def test_build_report_smoke_collects_regressions(self, tmp_path, monkeypatch):
        import scripts.memory_observability_report as rep

        cache = tmp_path / ".claude" / "cache"
        cache.mkdir(parents=True)
        now = datetime(2026, 6, 5, 12, 0, 0)
        old_ts = (now - timedelta(hours=300)).isoformat(timespec="milliseconds")
        (cache / "memory-ingestion.log").write_text(
            json.dumps({"ts": old_ts, "event": "ingest", "action": "saved"}) + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(rep, "PROJECT_ROOT", tmp_path)

        report = rep.build_report(since=None, now=now, stale_hours=168)
        md = rep.render_markdown(report)
        assert "Memory Observability Report" in md
        assert any(r["source"] == "ingestion" for r in report["regressions"])
        assert "observability regression" in md.lower()

    def test_event_driven_sinks_are_quiet_not_regressions(self, tmp_path, monkeypatch):
        """САБОТАЖ-ИНВАРИАНТ: у propagation/circuit/links нет планового писателя —
        они пишут только по событию, поэтому молчание НЕ регрессия (у circuit оно
        прямо означает «ни один breaker не сработал»). Замер 2026-07-25: все три
        висели в алерте, а их последние записи совпадали с сессиями собственной
        реализации — органического трафика у них не было никогда.
        """
        import scripts.memory_observability_report as rep

        cache = tmp_path / ".claude" / "cache"
        cache.mkdir(parents=True)
        now = datetime(2026, 6, 5, 12, 0, 0)
        old_ts = (now - timedelta(hours=1000)).isoformat(timespec="milliseconds")
        for fname in ("memory-propagation.log", "memory-circuit.log", "memory-links.log"):
            (cache / fname).write_text(
                json.dumps({"ts": old_ts, "event": "x"}) + "\n", encoding="utf-8"
            )
        monkeypatch.setattr(rep, "PROJECT_ROOT", tmp_path)

        report = rep.build_report(since=None, now=now, stale_hours=168)
        by_src = {f["source"]: f for f in report["freshness"]}
        assert by_src["propagation"]["status"] == "quiet"
        assert by_src["circuit"]["status"] == "quiet"
        assert by_src["links"]["status"] == "quiet"
        assert report["regressions"] == []  # маркер [REGRESSION] не выстрелит

    def test_scheduled_sink_still_flagged(self, tmp_path, monkeypatch):
        """Исключение адресное: у синка с плановым писателем staleness работает."""
        import scripts.memory_observability_report as rep

        cache = tmp_path / ".claude" / "cache"
        cache.mkdir(parents=True)
        now = datetime(2026, 6, 5, 12, 0, 0)
        old_ts = (now - timedelta(hours=1000)).isoformat(timespec="milliseconds")
        (cache / "memory-first-surfacing.log").write_text(
            json.dumps({"ts": old_ts, "event": "surface"}) + "\n", encoding="utf-8"
        )
        monkeypatch.setattr(rep, "PROJECT_ROOT", tmp_path)

        report = rep.build_report(since=None, now=now, stale_hours=168)
        by_src = {f["source"]: f for f in report["freshness"]}
        assert by_src["surfacing"]["status"] == "stale"
        assert [r["source"] for r in report["regressions"]] == ["surfacing"]


# --------------------------------------------------------------------------- #
# D3.2 — cross-sink fact trace (DuckDB; skipped when duckdb absent)
# --------------------------------------------------------------------------- #
class TestFactTraceDuckDB:
    def test_pattern_id_threads_ingestion_and_lifecycle(self, tmp_path, monkeypatch):
        duckdb = pytest.importorskip("duckdb")
        import scripts.memory_observability_query as q

        cache = tmp_path / ".claude" / "cache"
        cache.mkdir(parents=True)
        (tmp_path / "data" / "services").mkdir(parents=True)
        pid = "9b2c1e44-0000-5000-8000-aaaaaaaaaaaa"
        (cache / "memory-ingestion.log").write_text(
            json.dumps(
                {
                    "ts": "2026-06-05T10:00:00",
                    "event": "ingest",
                    "action": "saved",
                    "content_hash": "H",
                    "pattern_id": pid,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (cache / "confidence-lifecycle.log").write_text(
            json.dumps({"ts": "2026-06-05T10:05:00", "event": "reinforce", "pattern_id": pid})
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(q, "SINK_ROOT", tmp_path)
        con = duckdb.connect(":memory:")
        q._build_relation(con)
        # CAST guards the UUID-inference conversion bug (content_hash 'H' vs UUID col).
        rows = con.execute(
            "SELECT source, type FROM events "
            "WHERE CAST(content_hash AS VARCHAR) = ? OR CAST(pattern_id AS VARCHAR) = ? "
            "ORDER BY ts",
            [pid, pid],
        ).fetchall()
        assert len(rows) == 2
        assert {r[0] for r in rows} == {"ingestion", "lifecycle"}
