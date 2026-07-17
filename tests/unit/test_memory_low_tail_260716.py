"""260716 §3.3 LOW-tail regression — latent crashes/lies the audit flagged.

Each test pins one fix and is written to go RED if the fix is reverted (sabotage-check,
per the P0/P1 review lesson: a test that cannot fail pins nothing).

Covered:
  1. get_categories — round(None) on an all-NULL-importance group (AVG → NULL) must not crash.
  2. delete_message — a post-commit link-cleanup failure must not turn a done delete into an error.
  3. compute_docs_freshness — naive-dt vs aware-now must not drift by the tz offset.
  5. MemoryCube converters — an untrusted metadata pattern_type is coerced on the boundary.
  6. from_string (MemoryType/SourceServer/LinkType) — ValueError lists the valid values.

(Item 4, RRF cross-store-dup summing, is a measured DEFER — see roadmap 260716 §3.3 —
so there is no behavioural change to pin here.)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- item 1
class TestGetCategoriesNullAvg:
    def _db(self, ai, tmp_path, rows):
        db = tmp_path / "m.db"
        with ai._connect(db) as conn:
            conn.execute(
                "CREATE TABLE important_messages (id TEXT PRIMARY KEY, content TEXT NOT NULL, "
                "importance REAL, category TEXT, tags TEXT, created_at TEXT, updated_at TEXT, "
                "metadata TEXT)"
            )
            for rid, content, imp, cat in rows:
                conn.execute(
                    "INSERT INTO important_messages (id, content, importance, category) "
                    "VALUES (?,?,?,?)",
                    (rid, content, imp, cat),
                )
            conn.commit()
        return db

    async def test_null_avg_importance_returns_none_not_crash(self, tmp_path, monkeypatch):
        from src.memory.ai_memory import server as ai

        db = self._db(
            ai,
            tmp_path,
            [
                ("1", "c1", None, "nullcat"),
                ("2", "c2", None, "nullcat"),
                ("3", "c3", 0.8, "realcat"),
            ],
        )
        monkeypatch.setattr(ai, "DB_PATH", db)

        out = await ai.get_categories({})  # would TypeError on round(None, 2) before the fix
        data = json.loads(out[0].text)
        cats = {c["category"]: c["avg_importance"] for c in data["categories"]}
        assert cats["nullcat"] is None
        assert cats["realcat"] == 0.8


# --------------------------------------------------------------------------- item 2
class TestDeleteMessageBestEffort:
    async def test_delete_succeeds_when_link_cleanup_raises(self, tmp_path, monkeypatch):
        from src.memory.ai_memory import server as ai

        db = tmp_path / "m.db"
        monkeypatch.setattr(ai, "DB_PATH", db)
        ai.ensure_db()
        with ai._connect(db) as conn:
            conn.execute(
                "INSERT INTO important_messages (id, content, importance, category) VALUES (?,?,?,?)",
                ("x1", "hello", 0.7, "g"),
            )
            conn.commit()

        def boom(_msg_id):
            raise RuntimeError("link registry locked")

        monkeypatch.setattr(ai, "_cleanup_links", boom)

        out = await ai.delete_message({"message_id": "x1"})
        data = json.loads(out[0].text)
        # The row IS committed-deleted; a cleanup failure must not mask that success.
        assert data["success"] is True
        assert data["deleted"] == 1
        assert data["links_removed"] == 0
        with ai._connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM important_messages").fetchone()[0] == 0

    async def test_delete_succeeds_when_metadata_is_non_dict(self, tmp_path, monkeypatch):
        """metadata is untrusted: valid JSON can be a non-dict (list/scalar). (x or {}).get
        raises AttributeError on it → would leak past the narrow except and turn a
        committed delete into an error (same class as the link-cleanup fix)."""
        from src.memory.ai_memory import server as ai

        db = tmp_path / "m.db"
        monkeypatch.setattr(ai, "DB_PATH", db)
        ai.ensure_db()
        with ai._connect(db) as conn:
            conn.execute(
                "INSERT INTO important_messages (id, content, importance, category, metadata) "
                "VALUES (?,?,?,?,?)",
                ("x2", "hi", 0.5, "g", "[1, 2, 3]"),  # valid JSON, but NOT a dict
            )
            conn.commit()

        out = await ai.delete_message({"message_id": "x2"})
        data = json.loads(out[0].text)
        assert data["success"] is True
        assert data["deleted"] == 1


# --------------------------------------------------------------------------- item 3
class TestDocsFreshnessTz:
    def test_both_naive_age_is_exact(self):
        from src.memory.maintenance.dashboard import compute_docs_freshness

        r = compute_docs_freshness(
            {"c": "2026-07-01T00:00:00"}, {}, now=datetime(2026, 7, 11, 0, 0, 0)
        )
        assert r["c"]["age_days"] == 10.0
        assert r["c"]["stale"] is False

    def test_naive_dt_aware_now_agrees_with_naive_now(self):
        """A naive dt compared against the SAME instant expressed aware vs naive-local
        must yield the same age. Old code stripped now's tzinfo without converting frames,
        so an aware-UTC now drifted by the machine's tz offset. Skips on a UTC machine
        where the offset (and thus the bug) is invisible."""
        from src.memory.maintenance.dashboard import compute_docs_freshness

        utc_now = datetime(2026, 7, 11, 0, 0, 0, tzinfo=UTC)
        if utc_now.astimezone().utcoffset() == timedelta(0):
            pytest.skip("local tz is UTC; naive/aware offset is invisible")
        local_naive = utc_now.astimezone().replace(tzinfo=None)  # same instant, local naive

        r_aware = compute_docs_freshness({"c": "2026-07-01T00:00:00"}, {}, now=utc_now)
        r_naive = compute_docs_freshness({"c": "2026-07-01T00:00:00"}, {}, now=local_naive)
        assert r_aware["c"]["age_days"] == r_naive["c"]["age_days"]

    def test_aware_dt_aware_now_offset_correct(self):
        """+03 wall-clock and its UTC equivalent are the same instant → age must match."""
        from src.memory.maintenance.dashboard import compute_docs_freshness

        dt = "2026-07-01T03:00:00+03:00"  # == 2026-07-01T00:00:00Z
        now = datetime(2026, 7, 11, 0, 0, 0, tzinfo=UTC)
        r = compute_docs_freshness({"c": dt}, {}, now=now)
        assert r["c"]["age_days"] == 10.0


# --------------------------------------------------------------------------- item 5
class TestMemCubeCoerce:
    def _cube(self, meta):
        from src.memory.orchestrator.memcube import MemoryCube

        return MemoryCube.from_dict({"content": "x", "metadata": meta})

    def test_garbage_metadata_pattern_type_is_coerced_via_alias(self):
        cube = self._cube({"pattern_type": "error-fix"})  # known alias
        assert cube.to_vector_memory_payload()["pattern_type"] == "debugging-heuristic"
        assert cube.to_skill_learning_record()["pattern_type"] == "debugging-heuristic"

    def test_unknown_pattern_type_defaults_to_canonical(self):
        cube = self._cube({"pattern_type": "totally-made-up"})
        assert cube.to_vector_memory_payload()["pattern_type"] == "workflow-pattern"

    def test_missing_pattern_type_defaults_to_canonical(self):
        cube = self._cube({})
        # Old to_vector_memory_payload defaulted to "code-convention" (inconsistent).
        assert cube.to_vector_memory_payload()["pattern_type"] == "workflow-pattern"
        assert cube.to_skill_learning_record()["pattern_type"] == "workflow-pattern"


# --------------------------------------------------------------------------- item 6
class TestFromStringEnriched:
    def test_all_from_string_list_valid_values(self):
        from src.memory.orchestrator.link_registry import LinkType
        from src.memory.orchestrator.unified_id import MemoryType, SourceServer

        cases = [(MemoryType, "episodic"), (SourceServer, "memory-ai"), (LinkType, "mirrors")]
        for cls, a_valid in cases:
            with pytest.raises(ValueError) as ei:
                cls.from_string("__nope__")
            msg = str(ei.value)
            assert "Valid:" in msg, f"{cls.__name__}: no valid list in {msg!r}"
            assert a_valid in msg, f"{cls.__name__}: {a_valid!r} not in {msg!r}"

    def test_from_string_still_raises_valueerror(self):
        """Enrichment must NOT change the exception type — callers catch ValueError."""
        from src.memory.orchestrator.link_registry import LinkType

        with pytest.raises(ValueError):
            LinkType.from_string("nonsense")
