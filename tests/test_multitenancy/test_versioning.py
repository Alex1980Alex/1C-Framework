"""Tests for document versioning (Phase 12.5)."""

import json
from pathlib import Path

import pytest

from src.pdf_framework.processing.versioning import (
    DocumentVersionManager,
    VersionInfo,
    get_version_manager,
)


@pytest.fixture
def vm(tmp_path):
    return DocumentVersionManager(
        db_path=tmp_path / "versions.db",
        cache_dir=tmp_path / "chunks",
    )


# ---------------------------------------------------------------------------
# VersionInfo model
# ---------------------------------------------------------------------------

class TestVersionInfo:
    def test_model_fields(self):
        v = VersionInfo(
            version_id="v1",
            document_id="doc1",
            file_hash="abc123",
            indexed_at="2024-01-01T00:00:00",
            chunk_count=10,
            previous_version_id=None,
            metadata={"key": "value"},
            file_size_bytes=4096,
        )
        assert v.version_id == "v1"
        assert v.chunk_count == 10
        assert v.previous_version_id is None

    def test_with_previous_version(self):
        v = VersionInfo(
            version_id="v2",
            document_id="doc1",
            file_hash="def456",
            indexed_at="2024-01-02T00:00:00",
            chunk_count=5,
            previous_version_id="v1",
            metadata={},
            file_size_bytes=2048,
        )
        assert v.previous_version_id == "v1"


# ---------------------------------------------------------------------------
# DocumentVersionManager init
# ---------------------------------------------------------------------------

class TestVersionManagerInit:
    def test_creates_directories(self, tmp_path):
        db_path = tmp_path / "sub" / "versions.db"
        cache_dir = tmp_path / "sub" / "chunks"
        vm = DocumentVersionManager(db_path=db_path, cache_dir=cache_dir)
        assert db_path.parent.exists()
        assert cache_dir.exists()


# ---------------------------------------------------------------------------
# create_version
# ---------------------------------------------------------------------------

class TestCreateVersion:
    @pytest.mark.asyncio
    async def test_creates_version(self, vm):
        chunks = [{"content": "hello", "id": "c1"}]
        version = await vm.create_version("doc1", chunks)
        assert isinstance(version, VersionInfo)
        assert version.document_id == "doc1"
        assert version.chunk_count == 1

    @pytest.mark.asyncio
    async def test_version_id_contains_document_id(self, vm):
        chunks = [{"content": "hello", "id": "c1"}]
        version = await vm.create_version("doc1", chunks)
        assert "doc1" in version.version_id

    @pytest.mark.asyncio
    async def test_file_hash_computed(self, vm):
        chunks = [{"content": "hello", "id": "c1"}]
        version = await vm.create_version("doc1", chunks)
        assert len(version.file_hash) == 64  # SHA-256 hex

    @pytest.mark.asyncio
    async def test_same_chunks_same_hash(self, vm):
        chunks = [{"content": "hello", "id": "c1"}]
        v1 = await vm.create_version("doc1", chunks)
        v2 = await vm.create_version("doc1", chunks)
        assert v1.file_hash == v2.file_hash

    @pytest.mark.asyncio
    async def test_different_chunks_different_hash(self, vm):
        v1 = await vm.create_version("doc1", [{"content": "a"}])
        v2 = await vm.create_version("doc1", [{"content": "b"}])
        assert v1.file_hash != v2.file_hash

    @pytest.mark.asyncio
    async def test_previous_version_linked(self, vm):
        v1 = await vm.create_version("doc1", [{"content": "a"}])
        v2 = await vm.create_version("doc1", [{"content": "b"}])
        assert v2.previous_version_id == v1.version_id

    @pytest.mark.asyncio
    async def test_first_version_no_previous(self, vm):
        v = await vm.create_version("doc1", [{"content": "a"}])
        assert v.previous_version_id is None

    @pytest.mark.asyncio
    async def test_metadata_stored(self, vm):
        chunks = [{"content": "hello"}]
        version = await vm.create_version("doc1", chunks, metadata={"author": "test"})
        assert version.metadata == {"author": "test"}

    @pytest.mark.asyncio
    async def test_cache_file_created(self, vm, tmp_path):
        chunks = [{"content": "hello"}]
        version = await vm.create_version("doc1", chunks)
        cache_file = tmp_path / "chunks" / f"{version.version_id}.json"
        assert cache_file.exists()

    @pytest.mark.asyncio
    async def test_embeddings_cached(self, vm, tmp_path):
        chunks = [{"content": "hello"}]
        embeddings = [[0.1, 0.2, 0.3]]
        version = await vm.create_version("doc1", chunks, embeddings=embeddings)

        cache_file = tmp_path / "chunks" / f"{version.version_id}.json"
        data = json.loads(cache_file.read_text())
        assert data["embeddings"] == embeddings


# ---------------------------------------------------------------------------
# get_versions / get_latest_version / get_version
# ---------------------------------------------------------------------------

class TestGetVersions:
    @pytest.mark.asyncio
    async def test_get_versions_empty(self, vm):
        versions = await vm.get_versions("doc1")
        assert versions == []

    @pytest.mark.asyncio
    async def test_get_versions_ordered_newest_first(self, vm):
        v1 = await vm.create_version("doc1", [{"a": 1}])
        v2 = await vm.create_version("doc1", [{"b": 2}])
        versions = await vm.get_versions("doc1")
        assert len(versions) == 2
        assert versions[0].version_id == v2.version_id
        assert versions[1].version_id == v1.version_id

    @pytest.mark.asyncio
    async def test_get_latest_version(self, vm):
        await vm.create_version("doc1", [{"a": 1}])
        v2 = await vm.create_version("doc1", [{"b": 2}])
        latest = await vm.get_latest_version("doc1")
        assert latest.version_id == v2.version_id

    @pytest.mark.asyncio
    async def test_get_latest_version_empty(self, vm):
        latest = await vm.get_latest_version("doc1")
        assert latest is None

    @pytest.mark.asyncio
    async def test_get_version_by_id(self, vm):
        v = await vm.create_version("doc1", [{"a": 1}])
        retrieved = await vm.get_version(v.version_id)
        assert retrieved is not None
        assert retrieved.version_id == v.version_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_version(self, vm):
        result = await vm.get_version("nonexistent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_versions_isolated_by_document(self, vm):
        await vm.create_version("doc1", [{"a": 1}])
        await vm.create_version("doc2", [{"b": 2}])
        v1 = await vm.get_versions("doc1")
        v2 = await vm.get_versions("doc2")
        assert len(v1) == 1
        assert len(v2) == 1


# ---------------------------------------------------------------------------
# get_version_chunks
# ---------------------------------------------------------------------------

class TestGetVersionChunks:
    @pytest.mark.asyncio
    async def test_retrieves_cached_chunks(self, vm):
        chunks = [{"content": "hello", "id": "c1"}]
        version = await vm.create_version("doc1", chunks)
        data = await vm.get_version_chunks(version.version_id)
        assert data is not None
        assert data["chunks"] == chunks

    @pytest.mark.asyncio
    async def test_nonexistent_returns_none(self, vm):
        result = await vm.get_version_chunks("no_such_version")
        assert result is None


# ---------------------------------------------------------------------------
# rollback
# ---------------------------------------------------------------------------

class TestRollback:
    @pytest.mark.asyncio
    async def test_rollback_to_previous(self, vm):
        v1_chunks = [{"content": "version 1"}]
        v2_chunks = [{"content": "version 2"}]
        v1 = await vm.create_version("doc1", v1_chunks)
        await vm.create_version("doc1", v2_chunks)

        chunks, embeddings, metadata = await vm.rollback("doc1")
        assert chunks == v1_chunks

    @pytest.mark.asyncio
    async def test_rollback_to_specific_version(self, vm):
        v1_chunks = [{"content": "version 1"}]
        v2_chunks = [{"content": "version 2"}]
        v1 = await vm.create_version("doc1", v1_chunks)
        await vm.create_version("doc1", v2_chunks)

        chunks, embeddings, metadata = await vm.rollback("doc1", version_id=v1.version_id)
        assert chunks == v1_chunks

    @pytest.mark.asyncio
    async def test_rollback_no_previous_raises(self, vm):
        await vm.create_version("doc1", [{"content": "v1"}])
        with pytest.raises(ValueError, match="No previous version"):
            await vm.rollback("doc1")

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_version_raises(self, vm):
        with pytest.raises(ValueError, match="not found"):
            await vm.rollback("doc1", version_id="bad_id")


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------

class TestDeleteDocument:
    @pytest.mark.asyncio
    async def test_deletes_all_versions(self, vm):
        await vm.create_version("doc1", [{"a": 1}])
        await vm.create_version("doc1", [{"b": 2}])
        count = await vm.delete_document("doc1")
        assert count == 2

        versions = await vm.get_versions("doc1")
        assert versions == []

    @pytest.mark.asyncio
    async def test_deletes_cache_files(self, vm, tmp_path):
        v = await vm.create_version("doc1", [{"a": 1}])
        cache_file = tmp_path / "chunks" / f"{v.version_id}.json"
        assert cache_file.exists()

        await vm.delete_document("doc1")
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_zero(self, vm):
        count = await vm.delete_document("nonexistent")
        assert count == 0


# ---------------------------------------------------------------------------
# get_version_manager singleton
# ---------------------------------------------------------------------------

class TestGetVersionManager:
    def test_returns_instance(self):
        import src.pdf_framework.processing.versioning as mod
        mod._version_manager = None

        mgr = get_version_manager()
        assert isinstance(mgr, DocumentVersionManager)

        mod._version_manager = None

    def test_returns_same_instance(self):
        import src.pdf_framework.processing.versioning as mod
        mod._version_manager = None

        m1 = get_version_manager()
        m2 = get_version_manager()
        assert m1 is m2

        mod._version_manager = None
