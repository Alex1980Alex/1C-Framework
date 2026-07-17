"""
Tests for P5.1: session-memory-save Stop hook.
28 tests: meaningfulness, formatting, importance, tags, dedup, SQLite, collection, graceful degradation.
"""

import importlib.util
import json
import sqlite3
import subprocess
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

# CI collects strictly by marker (`-m "unit and not slow"` / `-m "integration or e2e"`),
# so an unmarked file runs in neither job. This one silently stopped being a gate: the
# already_saved contract change (2026-07-17) left 5 tests red and every CI run stayed
# green. 27 further files under tests/integration/ still carry no marker.
pytestmark = pytest.mark.integration

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks"
spec = importlib.util.spec_from_file_location(
    "session_memory_save", str(HOOKS_DIR / "session-memory-save.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

collect_context = mod.collect_context
is_meaningful = mod.is_meaningful
already_saved = mod.already_saved
format_summary = mod.format_summary
calculate_importance = mod.calculate_importance
extract_tags = mod.extract_tags
save_to_sqlite = mod.save_to_sqlite

SCHEMA = """
CREATE TABLE important_messages (
    id TEXT PRIMARY KEY, content TEXT NOT NULL, importance REAL DEFAULT 0.5,
    category TEXT DEFAULT 'general', tags TEXT, created_at TEXT, updated_at TEXT, metadata TEXT
)
"""


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "memory_ai.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(SCHEMA)
    conn.commit()
    conn.close()
    return db_path


def _ctx(**overrides):
    base = {
        "session_id": "abc12345",
        "created_at": "2026-04-04T10:00:00",
        "skills": ["memory-unified", "create-hook"],
        "files_changed": [
            "src/memory/orchestrator/memory_orchestrator.py",
            ".claude/hooks/session-memory-save.py",
            "tests/test.py",
            "docs/roadmap.md",
            "src/bsl/parser.py",
        ],
        "commits": ["feat: add hook", "docs: refresh audit"],
        "completed_tasks": ["Create hook"],
    }
    base.update(overrides)
    return base


class TestIsMeaningful:
    def test_files_gte_2(self):
        assert is_meaningful(_ctx(files_changed=["a.py", "b.py"], commits=[], skills=[])) is True

    def test_commits_gte_1(self):
        assert is_meaningful(_ctx(files_changed=[], commits=["fix"], skills=[])) is True

    def test_skills_gte_1(self):
        assert is_meaningful(_ctx(files_changed=[], commits=[], skills=["s"])) is True

    def test_empty_false(self):
        assert is_meaningful(_ctx(files_changed=[], commits=[], skills=[])) is False

    def test_one_file_false(self):
        assert is_meaningful(_ctx(files_changed=["a.py"], commits=[], skills=[])) is False


class TestFormatSummary:
    def test_full_summary(self):
        result = format_summary(_ctx())
        assert "Session" in result
        assert "Skills:" in result
        assert "Changed 5 files" in result
        assert "Commit:" in result
        assert "Done:" in result

    def test_minimal_no_extras(self):
        result = format_summary(_ctx(skills=[], commits=[], completed_tasks=[]))
        assert "Changed" in result
        assert "Skills:" not in result
        assert "Commit:" not in result

    def test_caps_commits_at_3(self):
        result = format_summary(_ctx(commits=[f"c{i}" for i in range(5)]))
        assert result.count("Commit:") == 3


class TestCalculateImportance:
    def test_base(self):
        assert (
            calculate_importance(_ctx(files_changed=[], commits=[], skills=[], completed_tasks=[]))
            == 0.5
        )

    def test_10_files(self):
        ctx = _ctx(
            files_changed=[f"f{i}" for i in range(10)], commits=[], skills=[], completed_tasks=[]
        )
        assert calculate_importance(ctx) == pytest.approx(0.7)

    def test_capped(self):
        ctx = _ctx(
            files_changed=[f"f{i}" for i in range(50)],
            commits=[f"c{i}" for i in range(20)],
            skills=[f"s{i}" for i in range(20)],
            completed_tasks=[f"t{i}" for i in range(20)],
        )
        assert calculate_importance(ctx) <= 0.95

    def test_sample(self):
        assert 0.75 <= calculate_importance(_ctx()) <= 0.85


class TestExtractTags:
    def test_always_session_and_date(self):
        tags = extract_tags(_ctx(skills=[], files_changed=[]))
        assert "session" in tags
        assert date.today().isoformat() in tags

    def test_includes_skills(self):
        tags = extract_tags(_ctx(files_changed=[]))
        assert "memory-unified" in tags
        assert "create-hook" in tags

    def test_includes_path_tags(self):
        tags = extract_tags(_ctx(skills=[]))
        for expected in ("memory", "bsl", "hooks", "tests", "docs"):
            assert expected in tags

    def test_max_10(self):
        tags = extract_tags(_ctx(skills=[f"s{i}" for i in range(20)]))
        assert len(tags) <= 10


class TestAlreadySaved:
    """Contract since 2026-07-17: the incumbent ``{content_hash, reason}``, or None.

    Was a bare bool. The dup ingest event must carry the STORED row's hash: ctx is
    rebuilt from live git state and drifts between Stops, so a freshly computed hash
    would name content that exists in no store and orphan fact-trace.
    """

    @staticmethod
    def _stored_hash(db):
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute("SELECT metadata FROM important_messages LIMIT 1").fetchone()
        finally:
            conn.close()
        return json.loads(row[0])["content_hash"]

    def test_not_saved_empty_db(self, tmp_db):
        with patch.object(mod, "SQLITE_DB", tmp_db):
            assert already_saved("abc12345") is None

    def test_saved_after_insert_returns_incumbent(self, tmp_db):
        with patch.object(mod, "SQLITE_DB", tmp_db):
            save_to_sqlite(_ctx())
            incumbent = already_saved("abc12345")
            assert incumbent is not None
            assert incumbent["reason"] == "session_already_saved"
            assert incumbent["content_hash"] == self._stored_hash(tmp_db)

    def test_different_session(self, tmp_db):
        with patch.object(mod, "SQLITE_DB", tmp_db):
            save_to_sqlite(_ctx())
            assert already_saved("other_id") is None

    def test_empty_session_dedup_by_date(self, tmp_db):
        """The two branches key on different things — reason must name the real one.

        Empty session_id is not hypothetical: ~19 UPS hooks race on
        session-skills.json, and a garbled read yields "".
        """
        with patch.object(mod, "SQLITE_DB", tmp_db):
            save_to_sqlite(_ctx(session_id=""))
            incumbent = already_saved("")
            assert incumbent is not None
            assert incumbent["reason"] == "date_already_saved"
            assert incumbent["content_hash"] == self._stored_hash(tmp_db)

    def test_db_missing(self, tmp_path):
        with patch.object(mod, "SQLITE_DB", tmp_path / "nope.db"):
            assert already_saved("abc") is None


class TestSaveToSqlite:
    def test_creates_record(self, tmp_db):
        with patch.object(mod, "SQLITE_DB", tmp_db):
            assert save_to_sqlite(_ctx()) is True
            conn = sqlite3.connect(str(tmp_db))
            count = conn.execute(
                "SELECT COUNT(*) FROM important_messages WHERE category='session_summary'"
            ).fetchone()[0]
            conn.close()
            assert count == 1

    def test_correct_fields(self, tmp_db):
        with patch.object(mod, "SQLITE_DB", tmp_db):
            save_to_sqlite(_ctx())
            conn = sqlite3.connect(str(tmp_db))
            row = conn.execute(
                "SELECT content, importance, category, tags, metadata FROM important_messages"
            ).fetchone()
            conn.close()
            content, importance, category, tags_str, meta_str = row
            assert "Session" in content
            assert importance >= 0.5
            assert category == "session_summary"
            assert "session" in json.loads(tags_str)
            assert json.loads(meta_str)["session_id"] == "abc12345"

    def test_no_db(self, tmp_path):
        with patch.object(mod, "SQLITE_DB", tmp_path / "missing.db"):
            assert save_to_sqlite(_ctx()) is False


class TestCollectContext:
    @patch.object(mod, "_run_git", return_value=[])
    @patch.object(mod, "_read_json_file", return_value={})
    def test_empty_sources(self, mock_json, mock_git):
        ctx = collect_context()
        assert ctx["session_id"] == ""
        assert ctx["skills"] == []
        assert ctx["files_changed"] == []
        assert ctx["commits"] == []

    @patch.object(mod, "_run_git", return_value=[])
    @patch.object(mod, "_read_json_file")
    def test_reads_session_state(self, mock_json, mock_git):
        mock_json.return_value = {
            "session_id": "test123",
            "activated_skills": ["memory-unified"],
            "created_at": "2026-04-04T10:00:00",
        }
        ctx = collect_context()
        assert ctx["session_id"] == "test123"
        assert ctx["skills"] == ["memory-unified"]


class TestGracefulDegradation:
    def test_bad_stdin_exit_0(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "session-memory-save.py")],
            input=b"invalid json",
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_empty_stdin_exit_0(self):
        result = subprocess.run(
            [sys.executable, str(HOOKS_DIR / "session-memory-save.py")],
            input=b"",
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0
