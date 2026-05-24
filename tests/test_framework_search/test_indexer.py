"""Unit tests for src/framework_search/indexer.py.

Covers _read_file, _chunks_for, collect_chunks, ensure_collection,
upsert_chunks, delete_stale_paths, run_index (T.1.7.a/b/c).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("qdrant_client")

from src.framework_search.chunker_base import Chunk
from src.framework_search.indexer import (
    _chunks_for,
    _read_file,
    collect_chunks,
    delete_stale_paths,
    ensure_collection,
    run_index,
    upsert_chunks,
)

pytestmark = pytest.mark.unit

_FAKE_VEC: list[float] = [0.1] * 4096


def _make_chunk(rel: str = "src/foo.py", content: str = "x = 1") -> Chunk:
    return Chunk(
        relative_path=rel,
        content=content,
        language="python",
        chunk_type="module",
        line_start=1,
        line_end=1,
        mtime=0.0,
    )


def _make_client(exists: bool = False, collection_dim: int = 4096) -> MagicMock:
    c = MagicMock()
    c.collection_exists.return_value = exists
    c.upsert.return_value = MagicMock(status="completed")
    c.delete.return_value = MagicMock(status="completed")
    info = MagicMock()
    info.config.params.vectors = MagicMock(size=collection_dim)
    c.get_collection.return_value = info
    c.get_aliases.return_value = MagicMock(aliases=[])
    return c


def _make_embedder_mock() -> tuple[MagicMock, MagicMock]:
    """Return (embedder_class_mock, embedder_instance_mock).

    embed_batch returns a list of one _FAKE_VEC per call.
    For variable-length batches call side_effect instead.
    """
    inst = MagicMock()
    inst.__enter__ = MagicMock(return_value=inst)
    inst.__exit__ = MagicMock(return_value=False)
    inst.embed_batch.return_value = [_FAKE_VEC]
    cls = MagicMock(return_value=inst)
    return cls, inst


# ---------------------------------------------------------------------------
# _read_file
# ---------------------------------------------------------------------------


class TestReadFile:
    def test_valid_file_returns_content(self, tmp_path: Path) -> None:
        fp = tmp_path / "hello.py"
        fp.write_text("print('hi')", encoding="utf-8")
        assert _read_file(fp) == "print('hi')"

    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert _read_file(tmp_path / "ghost.py") is None


# ---------------------------------------------------------------------------
# _chunks_for
# ---------------------------------------------------------------------------


class TestChunksFor:
    def test_python_file_returns_chunks(self, tmp_path: Path) -> None:
        fp = tmp_path / "mod.py"
        fp.write_text("def foo():\n    return 1\n", encoding="utf-8")
        chunks = _chunks_for(fp, "mod.py", "python")
        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_markdown_file_returns_chunks(self, tmp_path: Path) -> None:
        fp = tmp_path / "doc.md"
        fp.write_text("# Title\n\nBody text.\n", encoding="utf-8")
        chunks = _chunks_for(fp, "doc.md", "markdown")
        assert len(chunks) > 0

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        fp = tmp_path / "empty.py"
        fp.write_text("", encoding="utf-8")
        assert _chunks_for(fp, "empty.py", "python") == []

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        fp = tmp_path / "nonexistent.py"
        assert _chunks_for(fp, "nonexistent.py", "python") == []

    def test_json_file_returns_chunks(self, tmp_path: Path) -> None:
        fp = tmp_path / "cfg.json"
        fp.write_text('{"key": "value"}\n', encoding="utf-8")
        chunks = _chunks_for(fp, "cfg.json", "json")
        assert len(chunks) > 0


# ---------------------------------------------------------------------------
# collect_chunks
# ---------------------------------------------------------------------------


class TestCollectChunks:
    def test_py_and_md_files_indexed(self, tmp_path: Path) -> None:
        d = tmp_path / "src"
        d.mkdir()
        (d / "a.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
        (d / "b.md").write_text("# Doc\n\nContent.\n", encoding="utf-8")
        chunks, stats = collect_chunks(roots=["src"], repo_root=tmp_path)
        assert stats["files_indexed"] >= 2
        assert len(chunks) > 0

    def test_only_paths_filter(self, tmp_path: Path) -> None:
        d = tmp_path / "src"
        d.mkdir()
        (d / "a.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
        (d / "b.py").write_text("def bar():\n    return 2\n", encoding="utf-8")
        chunks, _ = collect_chunks(roots=["src"], repo_root=tmp_path, only_paths={"src/a.py"})
        paths = {c.relative_path for c in chunks}
        assert "src/b.py" not in paths

    def test_empty_directory_returns_empty(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        chunks, stats = collect_chunks(roots=["empty"], repo_root=tmp_path)
        assert chunks == []
        assert stats["files_indexed"] == 0

    def test_stats_files_indexed(self, tmp_path: Path) -> None:
        d = tmp_path / "src"
        d.mkdir()
        (d / "x.py").write_text("x = 1\n", encoding="utf-8")
        _, stats = collect_chunks(roots=["src"], repo_root=tmp_path)
        assert stats["files_indexed"] >= 1
        assert "by_language" in stats

    def test_extra_files_included(self, tmp_path: Path) -> None:
        (tmp_path / "utils.py").write_text("def helper():\n    pass\n", encoding="utf-8")
        chunks, _ = collect_chunks(roots=[], extra_files=["utils.py"], repo_root=tmp_path)
        assert any(c.relative_path == "utils.py" for c in chunks)


# ---------------------------------------------------------------------------
# ensure_collection
# ---------------------------------------------------------------------------


class TestEnsureCollection:
    def test_creates_when_not_exists(self) -> None:
        client = _make_client(exists=False)
        ensure_collection(client, "my_col", dims=4096)
        client.create_collection.assert_called_once()
        kw = client.create_collection.call_args.kwargs
        assert kw.get("collection_name") == "my_col"

    def test_skips_create_when_exists(self) -> None:
        client = _make_client(exists=True)
        ensure_collection(client, "my_col", dims=4096)
        client.create_collection.assert_not_called()

    def test_drop_and_recreate(self) -> None:
        client = _make_client(exists=True)
        ensure_collection(client, "my_col", dims=4096, recreate=True)
        client.delete_collection.assert_called_once_with("my_col")
        client.create_collection.assert_called_once()


# ---------------------------------------------------------------------------
# upsert_chunks
# ---------------------------------------------------------------------------


class TestUpsertChunks:
    def test_single_batch_upsert(self) -> None:
        client = _make_client()
        chunks = [_make_chunk(content=f"x={i}") for i in range(3)]
        upsert_chunks(client, "col", chunks, [_FAKE_VEC] * 3, sub_batch=64)
        assert client.upsert.call_count == 1

    def test_splits_into_sub_batches(self) -> None:
        client = _make_client()
        chunks = [_make_chunk(content=f"x={i}") for i in range(5)]
        upsert_chunks(client, "col", chunks, [_FAKE_VEC] * 5, sub_batch=2)
        assert client.upsert.call_count == 3  # ceil(5/2)

    def test_collection_name_passed(self) -> None:
        client = _make_client()
        upsert_chunks(client, "special_col", [_make_chunk()], [_FAKE_VEC])
        kw = client.upsert.call_args.kwargs
        assert kw.get("collection_name") == "special_col"

    def test_size_mismatch_raises(self) -> None:
        client = _make_client()
        with pytest.raises(ValueError, match="mismatch"):
            upsert_chunks(client, "col", [_make_chunk()], [_FAKE_VEC, _FAKE_VEC])


# ---------------------------------------------------------------------------
# delete_stale_paths
# ---------------------------------------------------------------------------


class TestDeleteStalePaths:
    def test_empty_paths_returns_zero(self) -> None:
        client = _make_client()
        assert delete_stale_paths(client, "col", []) == 0
        client.delete.assert_not_called()

    def test_collection_name_used(self) -> None:
        client = _make_client()
        delete_stale_paths(client, "my_col", ["src/foo.py"])
        kw = client.delete.call_args.kwargs
        assert kw.get("collection_name") == "my_col"

    def test_returns_path_count(self) -> None:
        client = _make_client()
        assert delete_stale_paths(client, "col", ["a.py", "b.py", "c.py"]) == 3


# ---------------------------------------------------------------------------
# run_index — dry_run / no-chunks / limit
# ---------------------------------------------------------------------------


class TestRunIndexDryRun:
    def test_dry_run_no_embeddings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "src.framework_search.indexer.collect_chunks",
            lambda *a, **kw: ([_make_chunk()], {"files_indexed": 1, "chunks": 1}),
        )
        with patch("src.framework_search.indexer.QdrantClient") as mc:
            stats = run_index(dry_run=True)
        assert stats["embeddings_done"] == 0
        mc.assert_not_called()

    def test_no_chunks_skip_qdrant(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "src.framework_search.indexer.collect_chunks",
            lambda *a, **kw: ([], {"files_indexed": 0, "chunks": 0}),
        )
        with patch("src.framework_search.indexer.QdrantClient") as mc:
            stats = run_index()
        mc.assert_not_called()
        assert stats["embeddings_done"] == 0

    def test_limit_caps_chunks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        many = [_make_chunk(content=f"x={i}") for i in range(10)]
        monkeypatch.setattr(
            "src.framework_search.indexer.collect_chunks",
            lambda *a, **kw: (many, {"files_indexed": 1, "chunks": 10}),
        )
        emb_cls, emb_inst = _make_embedder_mock()
        emb_inst.embed_batch.side_effect = lambda texts: [_FAKE_VEC] * len(texts)
        with (
            patch("src.framework_search.indexer.QdrantClient", return_value=_make_client()),
            patch("src.framework_search.indexer.FrameworkTEIEmbedder", emb_cls),
        ):
            stats = run_index(limit=3)
        assert stats["chunks"] == 3


# ---------------------------------------------------------------------------
# run_index — end-to-end (T.1.7.a / T.1.7.b / T.1.7.c)
# ---------------------------------------------------------------------------


class TestRunIndexEndToEnd:
    def test_upsert_called_on_normal_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """T.1.7.a — upsert_chunks is invoked for a normal (non-dry) run."""
        chunk = _make_chunk()
        monkeypatch.setattr(
            "src.framework_search.indexer.collect_chunks",
            lambda *a, **kw: ([chunk], {"files_indexed": 1, "chunks": 1}),
        )
        client = _make_client()
        emb_cls, _ = _make_embedder_mock()
        with (
            patch("src.framework_search.indexer.QdrantClient", return_value=client),
            patch("src.framework_search.indexer.FrameworkTEIEmbedder", emb_cls),
        ):
            stats = run_index()
        assert client.upsert.call_count >= 1
        assert stats["embeddings_done"] == 1

    def test_chunk_ids_are_deterministic(self) -> None:
        """T.1.7.b — same path/content/line → same chunk_id on two instantiations."""
        a = _make_chunk(rel="src/foo.py", content="x = 1")
        b = _make_chunk(rel="src/foo.py", content="x = 1")
        assert a.chunk_id == b.chunk_id

    def test_modified_file_new_chunk_ids(self) -> None:
        """T.1.7.c — different content → different chunk_id (sha1 changes)."""
        a = _make_chunk(rel="src/foo.py", content="x = 1")
        b = _make_chunk(rel="src/foo.py", content="x = 2")
        assert a.chunk_id != b.chunk_id

    def test_delete_stale_called_on_incremental(self, monkeypatch: pytest.MonkeyPatch) -> None:
        chunk = _make_chunk()
        monkeypatch.setattr(
            "src.framework_search.indexer.collect_chunks",
            lambda *a, **kw: ([chunk], {"files_indexed": 1, "chunks": 1}),
        )
        client = _make_client()
        emb_cls, _ = _make_embedder_mock()
        with (
            patch("src.framework_search.indexer.QdrantClient", return_value=client),
            patch("src.framework_search.indexer.FrameworkTEIEmbedder", emb_cls),
        ):
            run_index(only_paths={"src/foo.py"})
        client.delete.assert_called_once()

    def test_no_delete_on_full_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        chunk = _make_chunk()
        monkeypatch.setattr(
            "src.framework_search.indexer.collect_chunks",
            lambda *a, **kw: ([chunk], {"files_indexed": 1, "chunks": 1}),
        )
        client = _make_client()
        emb_cls, _ = _make_embedder_mock()
        with (
            patch("src.framework_search.indexer.QdrantClient", return_value=client),
            patch("src.framework_search.indexer.FrameworkTEIEmbedder", emb_cls),
        ):
            run_index(only_paths=None)
        client.delete.assert_not_called()
