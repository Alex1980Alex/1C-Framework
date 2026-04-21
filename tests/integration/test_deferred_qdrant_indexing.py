"""Tests for scripts/deferred_qdrant_indexing.py — P5.3 deferred Qdrant indexing.

Source: scripts/deferred_qdrant_indexing.py — function signatures
Source: [own] — importlib.util for script load, MagicMock for Qdrant/ST isolation
"""

import importlib.util
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
spec = importlib.util.spec_from_file_location(
    "deferred_qdrant_indexing", str(SCRIPT_DIR / "deferred_qdrant_indexing.py")
)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE important_messages (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            category TEXT DEFAULT 'general',
            tags TEXT,
            created_at TEXT,
            updated_at TEXT,
            metadata TEXT
        )
        """
    )
    rows = [
        ("a", "alpha content", 0.9, "cat1", "[]", "2026-01-01", None, None),
        ("b", "beta content", 0.7, "cat2", "[]", "2026-01-02", None, None),
        ("c", "gamma content", 0.5, "cat3", "[]", "2026-01-03", None, None),
    ]
    conn.executemany(
        "INSERT INTO important_messages "
        "(id, content, importance, category, tags, created_at, updated_at, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    yield conn
    conn.close()


def test_ensure_schema_adds_column(tmp_db):
    mod.ensure_schema(tmp_db)
    cursor = tmp_db.execute("PRAGMA table_info(important_messages)")
    columns = [row[1] for row in cursor.fetchall()]
    assert "indexed_in_qdrant" in columns


def test_ensure_schema_idempotent(tmp_db):
    mod.ensure_schema(tmp_db)
    cursor = tmp_db.execute("PRAGMA table_info(important_messages)")
    col_count = len(cursor.fetchall())
    mod.ensure_schema(tmp_db)
    cursor = tmp_db.execute("PRAGMA table_info(important_messages)")
    assert len(cursor.fetchall()) == col_count


def test_fetch_unindexed_returns_all_initially(tmp_db):
    mod.ensure_schema(tmp_db)
    rows = mod.fetch_unindexed(tmp_db, 10)
    assert len(rows) == 3
    assert rows[0]["id"] == "a"
    assert rows[1]["id"] == "b"
    assert rows[2]["id"] == "c"


def test_mark_indexed_flag_and_fetch_skips(tmp_db):
    mod.ensure_schema(tmp_db)
    mod.mark_indexed(tmp_db, ["a", "b"])
    rows = mod.fetch_unindexed(tmp_db, 10)
    assert len(rows) == 1
    assert rows[0]["id"] == "c"


def test_embed_texts_calls_model_with_prefix():
    class FakeVec:
        def tolist(self):
            return [[0.1, 0.2], [0.3, 0.4]]

    model = MagicMock()
    model.encode.return_value = FakeVec()

    result = mod.embed_texts(model, ["hello", "world"])

    model.encode.assert_called_once_with(
        ["passage: hello", "passage: world"],
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_upsert_to_qdrant_builds_points_and_idempotent_id():
    client = MagicMock()
    rows = [
        {
            "id": "a",
            "content": "x",
            "category": "c1",
            "importance": 0.5,
            "tags": "[]",
            "created_at": "2026-01-01",
        }
    ]
    vectors = [[0.1] * 1024]

    mod.upsert_to_qdrant(client, rows, vectors)

    client.upsert.assert_called_once()
    call_kwargs = client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == mod.COLLECTION

    point = call_kwargs["points"][0]
    assert point.payload["original_id"] == "a"
    assert point.payload["source"] == "memory_ai_session"
    expected_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "session:a"))
    assert str(point.id) == expected_id
