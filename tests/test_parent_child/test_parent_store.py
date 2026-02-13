"""Tests for ParentDocumentStore (Phase 7.2).

Tests SQLite-based parent chunk storage.
"""

import pytest

from src.pdf_framework.schemas.documents import DocumentChunk
from src.pdf_framework.vector_store.parent_store import ParentDocumentStore


def _chunk(id: str, doc_id: str = "doc1", content: str = "test content", idx: int = 0) -> DocumentChunk:
    return DocumentChunk(
        id=id,
        document_id=doc_id,
        content=content,
        chunk_index=idx,
        metadata={"chunk_type": "parent", "source": "test.pdf"},
    )


@pytest.fixture
async def store(tmp_path):
    db_path = tmp_path / "test_parent.db"
    s = ParentDocumentStore(db_path=db_path)
    await s.initialize()
    return s


class TestParentStoreBasics:
    @pytest.mark.asyncio
    async def test_initialize_creates_db(self, tmp_path):
        db_path = tmp_path / "new.db"
        store = ParentDocumentStore(db_path=db_path)
        await store.initialize()
        assert db_path.exists()

    @pytest.mark.asyncio
    async def test_double_initialize_is_safe(self, store):
        await store.initialize()
        await store.initialize()  # Should not raise

    @pytest.mark.asyncio
    async def test_count_empty(self, store):
        count = await store.count()
        assert count == 0


class TestAddAndGet:
    @pytest.mark.asyncio
    async def test_add_single_parent(self, store):
        await store.add_parents([_chunk("p1")])
        count = await store.count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_add_multiple_parents(self, store):
        chunks = [_chunk(f"p{i}") for i in range(5)]
        await store.add_parents(chunks)
        count = await store.count()
        assert count == 5

    @pytest.mark.asyncio
    async def test_add_empty_list(self, store):
        await store.add_parents([])
        count = await store.count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_parent_found(self, store):
        await store.add_parents([_chunk("p1", content="Hello world")])
        result = await store.get_parent("p1")
        assert result is not None
        assert result.id == "p1"
        assert result.content == "Hello world"

    @pytest.mark.asyncio
    async def test_get_parent_not_found(self, store):
        result = await store.get_parent("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_parents_multiple(self, store):
        chunks = [_chunk(f"p{i}", content=f"Content {i}") for i in range(5)]
        await store.add_parents(chunks)

        results = await store.get_parents(["p0", "p2", "p4"])
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_parents_partial(self, store):
        await store.add_parents([_chunk("p1")])
        results = await store.get_parents(["p1", "missing"])
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_parents_empty_list(self, store):
        results = await store.get_parents([])
        assert results == []

    @pytest.mark.asyncio
    async def test_upsert_replaces(self, store):
        await store.add_parents([_chunk("p1", content="old")])
        await store.add_parents([_chunk("p1", content="new")])

        result = await store.get_parent("p1")
        assert result.content == "new"

        count = await store.count()
        assert count == 1


class TestGetByDocument:
    @pytest.mark.asyncio
    async def test_get_by_document(self, store):
        await store.add_parents([
            _chunk("p1", doc_id="docA", idx=0),
            _chunk("p2", doc_id="docA", idx=1),
            _chunk("p3", doc_id="docB", idx=0),
        ])

        results = await store.get_parents_by_document("docA")
        assert len(results) == 2
        assert all(r.document_id == "docA" for r in results)

    @pytest.mark.asyncio
    async def test_get_by_document_ordered(self, store):
        await store.add_parents([
            _chunk("p2", doc_id="docA", idx=2),
            _chunk("p0", doc_id="docA", idx=0),
            _chunk("p1", doc_id="docA", idx=1),
        ])

        results = await store.get_parents_by_document("docA")
        indices = [r.chunk_index for r in results]
        assert indices == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_get_by_document_empty(self, store):
        results = await store.get_parents_by_document("nonexistent")
        assert results == []


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_by_ids(self, store):
        await store.add_parents([_chunk("p1"), _chunk("p2"), _chunk("p3")])
        deleted = await store.delete(["p1", "p3"])
        assert deleted == 2

        count = await store.count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_delete_empty_list(self, store):
        deleted = await store.delete([])
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_delete_by_document(self, store):
        await store.add_parents([
            _chunk("p1", doc_id="docA"),
            _chunk("p2", doc_id="docA"),
            _chunk("p3", doc_id="docB"),
        ])

        deleted = await store.delete_by_document("docA")
        assert deleted == 2

        count = await store.count()
        assert count == 1

    @pytest.mark.asyncio
    async def test_clear(self, store):
        await store.add_parents([_chunk("p1"), _chunk("p2")])
        await store.clear()
        count = await store.count()
        assert count == 0


class TestStatistics:
    @pytest.mark.asyncio
    async def test_statistics_empty(self, store):
        stats = await store.get_statistics()
        assert stats["total_parents"] == 0
        assert stats["documents_count"] == 0

    @pytest.mark.asyncio
    async def test_statistics_with_data(self, store):
        await store.add_parents([
            _chunk("p1", doc_id="docA", content="short"),
            _chunk("p2", doc_id="docA", content="a longer content here"),
            _chunk("p3", doc_id="docB", content="medium text"),
        ])

        stats = await store.get_statistics()
        assert stats["total_parents"] == 3
        assert stats["documents_count"] == 2
        assert stats["avg_char_count"] > 0
        assert "parents_by_document" in stats


class TestMetadataPreservation:
    @pytest.mark.asyncio
    async def test_metadata_roundtrip(self, store):
        chunk = DocumentChunk(
            id="p1",
            document_id="doc1",
            content="test",
            metadata={
                "chunk_type": "parent",
                "child_ids": ["c1", "c2"],
                "nested": {"key": "value"},
            },
        )
        await store.add_parents([chunk])
        result = await store.get_parent("p1")

        assert result.metadata["chunk_type"] == "parent"
        assert result.metadata["child_ids"] == ["c1", "c2"]
        assert result.metadata["nested"]["key"] == "value"
