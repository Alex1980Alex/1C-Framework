"""Unit tests for scripts/retention_policy.py (§15 P3 item 14).

Pure-function coverage of the adaptive 3-tier retention orchestrator:
config parsing, timestamp parsing, JSONL/parquet/key tier stats, and the
hot→warm / cold-shred decision plan. No external services required.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import pytest

# scripts/ is not a package — put it on sys.path then import the module by name
# (mirrors tests/integration/test_analyze_run.py convention).
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import retention_policy as rp

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# RetentionConfig.from_env
# ---------------------------------------------------------------------------


class TestRetentionConfig:
    def test_defaults(self, monkeypatch):
        for k in ("RETENTION_HOT_DAYS", "RETENTION_WARM_DAYS", "RETENTION_HOT_MAX_MB"):
            monkeypatch.delenv(k, raising=False)
        cfg = rp.RetentionConfig.from_env()
        assert cfg.hot_days == rp.DEFAULT_HOT_DAYS
        assert cfg.warm_days == rp.DEFAULT_WARM_DAYS
        assert cfg.hot_max_mb == rp.DEFAULT_HOT_MAX_MB

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("RETENTION_HOT_DAYS", "3")
        monkeypatch.setenv("RETENTION_WARM_DAYS", "30")
        monkeypatch.setenv("RETENTION_HOT_MAX_MB", "12.5")
        cfg = rp.RetentionConfig.from_env()
        assert cfg.hot_days == 3
        assert cfg.warm_days == 30
        assert cfg.hot_max_mb == 12.5

    def test_garbage_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("RETENTION_HOT_DAYS", "not-a-number")
        monkeypatch.setenv("RETENTION_HOT_MAX_MB", "")
        cfg = rp.RetentionConfig.from_env()
        assert cfg.hot_days == rp.DEFAULT_HOT_DAYS
        assert cfg.hot_max_mb == rp.DEFAULT_HOT_MAX_MB


# ---------------------------------------------------------------------------
# _parse_ts
# ---------------------------------------------------------------------------


class TestParseTs:
    def test_iso_with_z(self):
        got = rp._parse_ts("2026-05-28T10:00:00Z")
        assert got is not None
        assert got.tzinfo is None  # normalised to naive local

    def test_iso_naive(self):
        got = rp._parse_ts("2026-05-28T10:00:00")
        assert got == dt.datetime(2026, 5, 28, 10, 0, 0)

    def test_epoch_float(self):
        ts = 1_700_000_000.0
        got = rp._parse_ts(ts)
        assert got == dt.datetime.fromtimestamp(ts)

    def test_garbage_returns_none(self):
        assert rp._parse_ts("definitely not a date") is None
        assert rp._parse_ts("") is None
        assert rp._parse_ts(None) is None
        assert rp._parse_ts({"x": 1}) is None


# ---------------------------------------------------------------------------
# _oldest_entry_age_days
# ---------------------------------------------------------------------------


class TestOldestEntryAge:
    def test_parses_first_line_timestamp(self, tmp_path):
        p = tmp_path / "log.jsonl"
        old = dt.datetime(2026, 5, 18, 12, 0, 0)
        now = dt.datetime(2026, 5, 28, 12, 0, 0)
        p.write_text(
            json.dumps({"time": old.isoformat(), "hook": "a"})
            + "\n"
            + json.dumps({"time": now.isoformat(), "hook": "b"})
            + "\n",
            encoding="utf-8",
        )
        age = rp._oldest_entry_age_days(p, now=now)
        assert age == pytest.approx(10.0, abs=0.01)

    def test_skips_malformed_first_line(self, tmp_path):
        p = tmp_path / "log.jsonl"
        old = dt.datetime(2026, 5, 25, 12, 0, 0)
        now = dt.datetime(2026, 5, 28, 12, 0, 0)
        p.write_text(
            "{ not json\n" + json.dumps({"timestamp": old.isoformat()}) + "\n",
            encoding="utf-8",
        )
        age = rp._oldest_entry_age_days(p, now=now)
        assert age == pytest.approx(3.0, abs=0.01)

    def test_mtime_fallback_when_no_ts_field(self, tmp_path):
        p = tmp_path / "log.jsonl"
        p.write_text(json.dumps({"hook": "x", "no": "timestamp"}) + "\n", encoding="utf-8")
        # set mtime to 5 days ago
        five_days_ago = dt.datetime.now().timestamp() - 5 * 86400
        os.utime(p, (five_days_ago, five_days_ago))
        age = rp._oldest_entry_age_days(p)
        assert age == pytest.approx(5.0, abs=0.1)

    def test_missing_file(self, tmp_path):
        assert rp._oldest_entry_age_days(tmp_path / "nope.jsonl") is None


# ---------------------------------------------------------------------------
# jsonl_stats
# ---------------------------------------------------------------------------


class TestJsonlStats:
    def test_missing_file(self, tmp_path):
        s = rp.jsonl_stats(tmp_path / "absent.jsonl")
        assert s["exists"] is False
        assert s["lines"] == 0
        assert s["oldest_age_days"] is None

    def test_counts_nonblank_lines(self, tmp_path):
        p = tmp_path / "log.jsonl"
        now = dt.datetime(2026, 5, 28, 12, 0, 0)
        p.write_text(
            json.dumps({"time": now.isoformat()})
            + "\n"
            + "\n"  # blank line ignored
            + json.dumps({"time": now.isoformat()})
            + "\n",
            encoding="utf-8",
        )
        s = rp.jsonl_stats(p, now=now)
        assert s["exists"] is True
        assert s["lines"] == 2
        assert s["size_bytes"] > 0
        assert s["oldest_age_days"] == pytest.approx(0.0, abs=0.01)


# ---------------------------------------------------------------------------
# parquet_stats
# ---------------------------------------------------------------------------


class TestParquetStats:
    def test_empty_or_missing_dir(self, tmp_path):
        s = rp.parquet_stats(tmp_path / "no_archive")
        assert s["count"] == 0
        assert s["max_age_days"] is None

    def test_counts_parquet_only(self, tmp_path):
        (tmp_path / "a.parquet").write_bytes(b"x" * 100)
        (tmp_path / "b.parquet").write_bytes(b"y" * 200)
        (tmp_path / "ignore.txt").write_bytes(b"z")
        now = dt.datetime.now()
        s = rp.parquet_stats(tmp_path, now=now)
        assert s["count"] == 2
        assert s["total_bytes"] == 300
        assert s["min_age_days"] is not None


# ---------------------------------------------------------------------------
# key_stats
# ---------------------------------------------------------------------------


class TestKeyStats:
    def test_counts_shred_candidates(self):
        cfg = rp.RetentionConfig(warm_days=90)
        fake = [
            {"session_id": "a", "age_days": 120},
            {"session_id": "b", "age_days": 91},
            {"session_id": "c", "age_days": 10},
        ]
        s = rp.key_stats(cfg, list_keys_fn=lambda: fake)
        assert s["available"] is True
        assert s["total"] == 3
        assert s["shred_candidates"] == 2

    def test_boundary_counts_at_warm_days(self):
        # `>=` semantics: a key whose truncated age_days equals warm_days must
        # count as a shred candidate (gc deletes on sub-day resolution, so the
        # preview must not under-report — see key_stats docstring).
        cfg = rp.RetentionConfig(warm_days=90)
        fake = [{"session_id": "edge", "age_days": 90}, {"session_id": "young", "age_days": 89}]
        s = rp.key_stats(cfg, list_keys_fn=lambda: fake)
        assert s["shred_candidates"] == 1

    def test_degrades_on_error(self):
        cfg = rp.RetentionConfig()

        def boom():
            raise RuntimeError("keys backend down")

        s = rp.key_stats(cfg, list_keys_fn=boom)
        assert s["available"] is False
        assert s["shred_candidates"] == 0


# ---------------------------------------------------------------------------
# build_plan
# ---------------------------------------------------------------------------


class TestBuildPlan:
    def test_size_trigger(self):
        cfg = rp.RetentionConfig(hot_days=7, hot_max_mb=10)
        jstats = {"exists": True, "size_mb": 12.0, "oldest_age_days": 1.0}
        plan = rp.build_plan(jstats, {"shred_candidates": 0}, cfg)
        assert plan["hot_to_warm"] is True
        assert any("size" in r for r in plan["hot_to_warm_reasons"])

    def test_age_trigger(self):
        cfg = rp.RetentionConfig(hot_days=7, hot_max_mb=100)
        jstats = {"exists": True, "size_mb": 1.0, "oldest_age_days": 9.0}
        plan = rp.build_plan(jstats, {"shred_candidates": 0}, cfg)
        assert plan["hot_to_warm"] is True
        assert any("oldest" in r for r in plan["hot_to_warm_reasons"])

    def test_no_trigger_within_hot_tier(self):
        cfg = rp.RetentionConfig(hot_days=7, hot_max_mb=50)
        jstats = {"exists": True, "size_mb": 2.0, "oldest_age_days": 1.0}
        plan = rp.build_plan(jstats, {"shred_candidates": 0}, cfg)
        assert plan["hot_to_warm"] is False
        assert plan["hot_to_warm_reasons"] == []

    def test_boundary_exactly_at_threshold_triggers(self):
        # `>=` semantics: size or age exactly at the limit must trigger.
        cfg = rp.RetentionConfig(hot_days=7, hot_max_mb=50)
        size_at = rp.build_plan({"exists": True, "size_mb": 50.0, "oldest_age_days": 0.0}, {}, cfg)
        age_at = rp.build_plan({"exists": True, "size_mb": 0.0, "oldest_age_days": 7.0}, {}, cfg)
        assert size_at["hot_to_warm"] is True
        assert age_at["hot_to_warm"] is True

    def test_none_age_does_not_crash_or_trigger(self):
        # Undeterminable oldest age (None) must not raise and must not trigger
        # on the age axis (guarded `age is not None`).
        cfg = rp.RetentionConfig(hot_days=7, hot_max_mb=50)
        plan = rp.build_plan(
            {"exists": True, "size_mb": 1.0, "oldest_age_days": None},
            {"shred_candidates": 0},
            cfg,
        )
        assert plan["hot_to_warm"] is False

    def test_missing_jsonl_never_triggers(self):
        cfg = rp.RetentionConfig()
        plan = rp.build_plan({"exists": False}, {"shred_candidates": 0}, cfg)
        assert plan["hot_to_warm"] is False

    def test_cold_shred_passthrough(self):
        cfg = rp.RetentionConfig()
        plan = rp.build_plan({"exists": False}, {"shred_candidates": 7}, cfg)
        assert plan["cold_shred_keys"] == 7


# ---------------------------------------------------------------------------
# cmd_run apply-path (delegation wiring)
# ---------------------------------------------------------------------------


class TestApplyPath:
    """Verify --apply delegates correctly and that archive failure does not
    block the (independent) cold-shred step."""

    def _wire(self, monkeypatch, *, archive_rc: int, shred_candidates: int):
        """Patch tier stats + both delegates; return call recorders."""
        import types

        monkeypatch.setattr(
            rp,
            "jsonl_stats",
            lambda: {
                "exists": True,
                "size_bytes": 1,
                "size_mb": 100.0,  # forces hot→warm
                "lines": 1,
                "oldest_age_days": 1.0,
            },
        )
        monkeypatch.setattr(
            rp,
            "parquet_stats",
            lambda: {"count": 0, "total_bytes": 0, "min_age_days": None, "max_age_days": None},
        )
        monkeypatch.setattr(
            rp,
            "key_stats",
            lambda cfg: {"available": True, "total": 3, "shred_candidates": shred_candidates},
        )

        archive_calls: list[tuple[bool, bool]] = []

        def fake_archive(rotate: bool, dry_run: bool) -> int:
            archive_calls.append((rotate, dry_run))
            return archive_rc

        fake_mod = types.ModuleType("archive_jsonl_to_parquet")
        fake_mod.cmd_archive = fake_archive  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "archive_jsonl_to_parquet", fake_mod)

        gc_calls: list[int] = []
        monkeypatch.setattr(
            rp, "_import_gc_old_keys", lambda: lambda days: gc_calls.append(days) or 2
        )
        return archive_calls, gc_calls

    def test_apply_delegates_archive_and_shred(self, monkeypatch):
        archive_calls, gc_calls = self._wire(monkeypatch, archive_rc=0, shred_candidates=2)
        cfg = rp.RetentionConfig(hot_max_mb=50, warm_days=90)
        rc = rp.cmd_run(apply=True, status_only=False, cfg=cfg)
        assert rc == 0
        assert archive_calls == [(True, False)]  # rotate=True, dry_run=False
        assert gc_calls == [90]  # gc_old_keys(warm_days)

    def test_archive_failure_does_not_block_shred(self, monkeypatch):
        archive_calls, gc_calls = self._wire(monkeypatch, archive_rc=1, shred_candidates=2)
        cfg = rp.RetentionConfig(hot_max_mb=50, warm_days=90)
        rc = rp.cmd_run(apply=True, status_only=False, cfg=cfg)
        assert rc != 0  # archive failure surfaces in return code
        assert archive_calls == [(True, False)]
        assert gc_calls == [90]  # shred still ran despite archive failure

    def test_dry_run_mutates_nothing(self, monkeypatch):
        archive_calls, gc_calls = self._wire(monkeypatch, archive_rc=0, shred_candidates=2)
        cfg = rp.RetentionConfig(hot_max_mb=50, warm_days=90)
        rc = rp.cmd_run(apply=False, status_only=False, cfg=cfg)
        assert rc == 0
        assert archive_calls == []  # nothing executed in dry-run
        assert gc_calls == []
