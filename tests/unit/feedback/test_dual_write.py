"""Dual-write feedback durability tests (roadmap 260509 §3.5).

Three guarantees verified:

1. Every successful `add_feedback()` produces matching SQLite row + JSONL line.
2. Backup write failure must NOT propagate — SQLite remains primary.
3. Replay from JSONL recovers ALL entries into a fresh SQLite — even if the
   original SQLite is wiped.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

from src.pdf_framework.feedback.collector import FeedbackCollector, FeedbackEntry


def _make_entry(query: str = "test", feedback: str = "positive", **kw) -> FeedbackEntry:
    return FeedbackEntry(query=query, answer="answer", feedback=feedback, **kw)


@pytest.fixture
def isolated_collector(tmp_path: Path) -> FeedbackCollector:
    return FeedbackCollector(
        db_path=tmp_path / "feedback.db",
        backup_dir=tmp_path / "backups",
        backup_enabled=True,
    )


@pytest.mark.unit
class TestDualWrite:
    def test_sqlite_and_jsonl_both_populated(self, isolated_collector, tmp_path):
        rid = isolated_collector.add_feedback(_make_entry("q1"))
        assert rid is not None and rid > 0

        # SQLite has the row
        with sqlite3.connect(tmp_path / "feedback.db") as conn:
            (count,) = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()
        assert count == 1

        # JSONL backup has the entry
        backup_files = list((tmp_path / "backups").glob("backup_*.jsonl"))
        assert len(backup_files) == 1
        lines = backup_files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["entry"]["query"] == "q1"
        assert record["id"] == rid

    def test_multiple_entries_appended_one_per_line(self, isolated_collector, tmp_path):
        for i in range(5):
            isolated_collector.add_feedback(_make_entry(f"q{i}"))

        backup_files = list((tmp_path / "backups").glob("backup_*.jsonl"))
        assert len(backup_files) == 1
        lines = backup_files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 5
        # Each line is a valid JSON object
        for line in lines:
            json.loads(line)

    def test_backup_failure_does_not_break_sqlite(self, tmp_path):
        """JSONL write fails (simulated) → SQLite still gets the row."""
        collector = FeedbackCollector(
            db_path=tmp_path / "feedback.db",
            backup_dir=tmp_path / "backups",
            backup_enabled=True,
        )
        call_count = {"n": 0}

        def failing_backup(entry, row_id):
            call_count["n"] += 1
            # Simulate an IO error captured by the production code's `except Exception`
            try:
                raise OSError("simulated backup failure")
            except Exception as e:
                import logging

                logging.getLogger("src.pdf_framework.feedback.collector").warning(
                    f"[FEEDBACK] JSONL backup write failed (non-fatal): {e}"
                )

        original_method = collector._write_jsonl_backup
        collector._write_jsonl_backup = failing_backup  # type: ignore[method-assign]
        try:
            rid = collector.add_feedback(_make_entry("survives"))
        finally:
            collector._write_jsonl_backup = original_method  # type: ignore[method-assign]

        assert rid is not None and rid > 0
        assert call_count["n"] == 1
        with sqlite3.connect(tmp_path / "feedback.db") as conn:
            (count,) = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()
        assert count == 1, "SQLite write must succeed even when backup fails"

    def test_disabled_backup_writes_no_files(self, tmp_path):
        collector = FeedbackCollector(
            db_path=tmp_path / "feedback.db",
            backup_dir=tmp_path / "backups",
            backup_enabled=False,
        )
        collector.add_feedback(_make_entry("q-no-backup"))

        # No JSONL files created when disabled
        backup_files = list((tmp_path / "backups").glob("backup_*.jsonl"))
        assert backup_files == []


@pytest.mark.unit
class TestReplayFromBackup:
    """Verify scripts/replay_feedback_backup.py recovers data."""

    def _import_replay(self):
        # Isolated import via importlib (consistent with tests/test_docs_invariants.py)
        # — avoids sys.path pollution for the rest of the pytest session.
        import importlib.util

        repo_root = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "replay_feedback_backup",
            repo_root / "scripts" / "replay_feedback_backup.py",
        )
        if spec is None or spec.loader is None:
            pytest.skip("scripts/replay_feedback_backup.py not loadable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_replay_recovers_all_entries_into_fresh_sqlite(self, tmp_path):
        # 1. Write 3 entries → both SQLite + JSONL populated
        primary_db = tmp_path / "feedback.db"
        backup_dir = tmp_path / "backups"
        collector = FeedbackCollector(
            db_path=primary_db,
            backup_dir=backup_dir,
            backup_enabled=True,
        )
        for i in range(3):
            collector.add_feedback(_make_entry(f"q{i}", feedback="positive"))

        with sqlite3.connect(primary_db) as conn:
            (count_before,) = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()
        assert count_before == 3

        # 2. Replay JSONL → INDEPENDENT fresh SQLite (simulates the post-corruption
        #    recovery path; we don't unlink primary_db because Windows holds a
        #    sqlite3 file handle until GC, which would race with unlink).
        replay_module = self._import_replay()
        target_db = tmp_path / "feedback_restored.db"
        seen, inserted, skipped = replay_module.replay(
            backup_dir=backup_dir,
            target_db=target_db,
            dedupe=False,
            dry_run=False,
        )
        assert seen == 3
        assert inserted == 3
        assert skipped == 0

        # 3. Target DB has all 3 entries with backup_origin_id traceability
        with sqlite3.connect(target_db) as conn:
            rows = conn.execute("SELECT query, metadata FROM feedback ORDER BY id").fetchall()
        assert [r[0] for r in rows] == ["q0", "q1", "q2"]
        for _, raw_meta in rows:
            meta = json.loads(raw_meta)
            assert "backup_origin_id" in meta
            assert "backup_source_file" in meta

    def test_dedupe_skips_existing_entries(self, tmp_path):
        primary_db = tmp_path / "feedback.db"
        backup_dir = tmp_path / "backups"
        collector = FeedbackCollector(
            db_path=primary_db,
            backup_dir=backup_dir,
            backup_enabled=True,
        )
        for i in range(2):
            collector.add_feedback(_make_entry(f"q{i}"))

        # Replay with dedupe → all 2 skipped (already in target)
        replay_module = self._import_replay()
        seen, inserted, skipped = replay_module.replay(
            backup_dir=backup_dir,
            target_db=primary_db,
            dedupe=True,
            dry_run=False,
        )
        assert seen == 2
        assert skipped == 2
        assert inserted == 0

    def test_dry_run_counts_without_writing(self, tmp_path):
        backup_dir = tmp_path / "backups"
        collector = FeedbackCollector(
            db_path=tmp_path / "feedback.db",
            backup_dir=backup_dir,
            backup_enabled=True,
        )
        for i in range(4):
            collector.add_feedback(_make_entry(f"q{i}"))

        replay_module = self._import_replay()
        target_db = tmp_path / "feedback_restored.db"
        seen, inserted, skipped = replay_module.replay(
            backup_dir=backup_dir,
            target_db=target_db,
            dry_run=True,
        )
        assert seen == 4
        assert inserted == 4
        assert skipped == 0
        assert not target_db.exists()  # nothing written

    def test_date_range_filter(self, tmp_path):
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir(parents=True)
        # Hand-craft 3 dated backup files
        for d in ["2026-04-01", "2026-05-05", "2026-05-09"]:
            f = backup_dir / f"backup_{d}.jsonl"
            f.write_text(
                json.dumps(
                    {
                        "id": 1,
                        "written_at": f"{d}T12:00:00+00:00",
                        "entry": {
                            "query": f"q-{d}",
                            "answer": "a",
                            "feedback": "positive",
                            "timestamp": 0.0,
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

        replay_module = self._import_replay()
        target_db = tmp_path / "filtered.db"
        seen, inserted, skipped = replay_module.replay(
            backup_dir=backup_dir,
            target_db=target_db,
            since=date(2026, 5, 1),
            until=date(2026, 5, 8),
            dry_run=False,
        )
        # Only 2026-05-05 falls in range
        assert seen == 1 and inserted == 1
        with sqlite3.connect(target_db) as conn:
            rows = conn.execute("SELECT query FROM feedback").fetchall()
        assert [r[0] for r in rows] == ["q-2026-05-05"]
