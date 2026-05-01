"""Tests for .claude/hooks/memory-first-hook.py — 4-layer federated memory recall hook (P5.2).

Source: [pytest fixtures] — monkeypatch.setattr for module-level paths
Source: [own] — importlib.util load for hyphenated hook filename
"""

import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks"
spec = importlib.util.spec_from_file_location(
    "memory_first_hook", str(HOOKS_DIR / "memory-first-hook.py")
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE important_messages "
        "(id TEXT PRIMARY KEY, content TEXT NOT NULL, importance REAL DEFAULT 0.5, "
        "category TEXT DEFAULT 'general', tags TEXT, created_at TEXT, updated_at TEXT, metadata TEXT)"
    )
    rows = [
        ("id1", "Python testing best practices with pytest", 0.8, "dev", "[]", None, None, None),
        ("id2", "Russian language processing and NLP techniques", 0.7, "nlp", "[]", None, None, None),
        ("id3", "Database optimization and query performance", 0.6, "db", "[]", None, None, None),
    ]
    conn.executemany("INSERT INTO important_messages VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()
    monkeypatch.setattr(mod, "SQLITE_DB", db_path, raising=False)
    return db_path


@pytest.fixture
def tmp_memory(tmp_path, monkeypatch):
    md1 = tmp_path / "note1.md"
    md1.write_text(
        "---\nname: test-note\ntype: feedback\n---\nPython testing strategies",
        encoding="utf-8",
    )
    md2 = tmp_path / "note2.md"
    md2.write_text(
        "---\nname: other-note\ntype: general\n---\nCooking recipes and kitchen tips",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "MEMORY_DIR", tmp_path, raising=False)
    return tmp_path


class TestShouldSkip:
    def test_short_prompt(self):
        assert mod.should_skip("short") is True

    def test_slash_command(self):
        assert mod.should_skip("/help something else long enough") is True

    def test_single_word_long(self):
        assert mod.should_skip("internationalization") is True

    def test_normal_sentence(self):
        assert mod.should_skip("How do I write a good test for this module?") is False


class TestStemToken:
    def test_russian_suffix_stripped(self):
        result = mod.stem_token("агентов")
        assert len(result) < len("агентов")
        assert result == "агент"

    def test_english_unchanged(self):
        assert mod.stem_token("english") == "english"

    def test_too_short_unchanged(self):
        assert mod.stem_token("аб") == "аб"


class TestTokenize:
    def test_mixed_ru_en(self):
        tokens = mod.tokenize("Hello мир агенты")
        assert "hello" in tokens
        assert any(t.startswith("агент") for t in tokens)


class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        content = "---\nname: X\ntype: feedback\n---\nBody"
        result = mod.parse_frontmatter(content)
        assert result["name"] == "X"
        assert result["type"] == "feedback"
        assert result["body"] == "Body"

    def test_no_frontmatter(self):
        content = "Just plain text here"
        result = mod.parse_frontmatter(content)
        assert result["body"] == content
        assert result["name"] == ""
        assert result["type"] == ""


class TestSearchSqlite:
    def test_query_matches_one_row(self, tmp_db):
        tokens = {"python", "testing"}
        results = mod.search_sqlite(tokens)
        assert len(results) >= 1
        assert results[0]["source"] == "sqlite"
        assert results[0]["score"] >= 0.3

    def test_query_matches_nothing(self, tmp_db):
        results = mod.search_sqlite({"zzzznonexistent"})
        assert results == []

    def test_missing_db_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "SQLITE_DB", tmp_path / "nope.db", raising=False)
        results = mod.search_sqlite({"python"})
        assert results == []


class TestSearchMd:
    def test_query_hits_body(self, tmp_memory):
        results = mod.search_md({"python", "testing"})
        assert len(results) >= 1
        assert results[0]["source"] == "md"


class TestSearchQdrantDisabled:
    def test_returns_empty_when_disabled(self, monkeypatch):
        monkeypatch.setenv("MEMORY_HOOK_NO_SEMANTIC", "1")
        results = mod.search_qdrant({"token"}, prompt="hi")
        assert results == []


class TestRrfMerge:
    def test_merge_two_layers_sorted_deduped(self):
        shared_content = "shared item content"
        layers = {
            "sqlite": [
                {"source": "sqlite", "content": shared_content, "score": 0.9, "category": "a"},
                {"source": "sqlite", "content": "sqlite only item", "score": 0.7, "category": "b"},
            ],
            "md": [
                {"source": "md", "content": shared_content, "score": 0.8, "category": "a"},
                {"source": "md", "content": "md only item", "score": 0.6, "category": "c"},
            ],
        }
        weights = {"sqlite": 2.0, "md": 1.0}
        merged = mod.rrf_merge(layers, weights)
        assert all("fused_score" in item for item in merged)
        scores = [item["fused_score"] for item in merged]
        assert scores == sorted(scores, reverse=True)
        contents = [item["content"] for item in merged]
        assert contents.count(shared_content) == 1


class TestFormatFederatedContext:
    def test_nonempty_output_format(self):
        merged = [
            {"source": "sqlite", "fused_score": 0.95, "category": "dev", "content": "test content alpha"},
            {"source": "md", "fused_score": 0.80, "category": "note", "content": "test content beta"},
        ]
        output = mod.format_federated_context(merged)
        assert output.startswith("[MEMORY CONTEXT] Top")
        assert "SQLite" in output
        assert ".md" in output

    def test_result_line_regex(self):
        merged = [
            {"source": "sqlite", "fused_score": 0.95, "category": "dev", "content": "alpha"},
        ]
        output = mod.format_federated_context(merged)
        lines = output.strip().split("\n")
        data_lines = [line for line in lines if re.match(r"^\d+\.", line.strip())]
        assert len(data_lines) >= 1
        assert re.match(r"^\d+\. \[\w+\|\d\.\d+\]", data_lines[0].strip())


class TestDimAlignment:
    """Regression for Phase 9.1 dim mismatch bug (hook used 768d Ollama nomic while
    Qdrant collections were 4096d Qwen3 — caused silent 0-result semantic recall)."""

    EXPECTED_DIM = 4096
    KNOWN_COLLECTIONS = {"skill_library", "experience_embeddings", "conversation_memory"}

    def test_hook_declares_expected_collections(self) -> None:
        declared = {name for name, _ in mod.SEMANTIC_COLLECTIONS}
        assert declared == self.KNOWN_COLLECTIONS

    def test_hook_comment_documents_4096d(self) -> None:
        hook_src = (HOOKS_DIR / "memory-first-hook.py").read_text(encoding="utf-8")
        assert "4096" in hook_src

    @pytest.mark.integration
    def test_qdrant_collection_dims_match_expected(self) -> None:
        import httpx
        try:
            httpx.get("http://127.0.0.1:6333/collections", timeout=2).raise_for_status()
        except Exception:
            pytest.skip("Qdrant not available at localhost:6333")
        mismatches = []
        for collection_name, _ in mod.SEMANTIC_COLLECTIONS:
            try:
                r = httpx.get(
                    f"http://127.0.0.1:6333/collections/{collection_name}", timeout=2
                )
                if r.status_code == 404:
                    continue
                vectors = r.json()["result"]["config"]["params"]["vectors"]
                actual_dim = (
                    vectors.get("size")
                    or next(iter(vectors.values()))["size"]
                )
                if actual_dim != self.EXPECTED_DIM:
                    mismatches.append(f"{collection_name}: actual={actual_dim}")
            except Exception:
                continue
        assert not mismatches, "Dim mismatch (Phase 9.1 regression):\n" + "\n".join(mismatches)


class TestHookIntegrationSubprocess:
    def test_subprocess_empty_dirs(self, tmp_path):
        hook_script = HOOKS_DIR / "memory-first-hook.py"
        if not hook_script.exists():
            pytest.skip("memory-first-hook.py not found")
        env = os.environ.copy()
        env["MEMORY_HOOK_NO_SEMANTIC"] = "1"
        empty_mem = tmp_path / "mem"
        empty_mem.mkdir()
        env["CLAUDE_MEMORY_DIR"] = str(empty_mem)
        payload = json.dumps({"prompt": "This is a normal test prompt for integration"})
        result = subprocess.run(
            [sys.executable, str(hook_script)],
            input=payload,
            capture_output=True,
            text=True,
            env=env,
            timeout=20,
        )
        assert result.returncode == 0
