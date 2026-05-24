"""Integration tests for scripts/migrate_memory_md_to_db.py (P5.4 migration).

Source: scripts/migrate_memory_md_to_db.py — function signatures and schema
Source: [own] — importlib.util for script load
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
spec = importlib.util.spec_from_file_location(
    "migrate_memory_md_to_db", str(SCRIPT_DIR / "migrate_memory_md_to_db.py")
)
assert spec is not None and spec.loader is not None
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "memory_ai.db"
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
    conn.commit()
    yield conn
    conn.close()


def test_parse_frontmatter_valid():
    content = "---\nname: My Note\ntype: feedback\ndescription: hello\n---\nBody text here"
    result = mod.parse_frontmatter(content)
    assert result["name"] == "My Note"
    assert result["type"] == "feedback"
    assert result["description"] == "hello"
    assert result["body"] == "Body text here"


def test_parse_frontmatter_plain_text():
    content = "Just plain content no frontmatter"
    result = mod.parse_frontmatter(content)
    assert result["body"] == content
    assert result["name"] == ""
    assert result["type"] == ""
    assert result["description"] == ""


def test_compute_importance_by_type():
    assert mod.compute_importance("feedback") == 0.8
    assert mod.compute_importance("USER") == 0.7
    assert mod.compute_importance("unknown") == mod.DEFAULT_IMPORTANCE


def test_content_hash_stable_and_different():
    assert mod.content_hash("abc") == mod.content_hash("abc")
    assert mod.content_hash("abc") != mod.content_hash("xyz")
    assert mod.content_hash("  abc  ") == mod.content_hash("abc")


def test_extract_tags_from_body_and_filename():
    tags = mod.extract_tags("feedback", "my_memory_hook.md", "This has qdrant and skill references")
    assert "feedback" in tags
    assert "memory" in tags
    assert "hooks" in tags or "hook" in tags
    assert "qdrant" in tags
    assert "skills" in tags
    assert len(tags) <= 10


def test_extract_tags_capped_at_10():
    tags = mod.extract_tags(
        "feedback", "a_b_c_d_e_f_g_h_i_j_k_l_m.md", "bsl qdrant hook skill memory"
    )
    assert len(tags) <= 10


def test_insert_row_dry_run_no_write():
    conn = sqlite3.connect(":memory:")
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
    conn.commit()
    fm = {"name": "X", "type": "feedback", "description": ""}
    result = mod.insert_row(conn, "x.md", fm, "body", "h1", dry_run=True)
    assert result is not None
    row_count = conn.execute("SELECT COUNT(*) FROM important_messages").fetchone()[0]
    assert row_count == 0
    conn.close()


def test_insert_row_writes_and_already_migrated_detects(tmp_db):
    fm = {"name": "X", "type": "feedback", "description": "d"}
    mod.insert_row(tmp_db, "x.md", fm, "body", "hABC", dry_run=False)
    row_count = tmp_db.execute("SELECT COUNT(*) FROM important_messages").fetchone()[0]
    assert row_count == 1
    assert mod.already_migrated(tmp_db, "hABC") is True
    assert mod.already_migrated(tmp_db, "hXYZ") is False
