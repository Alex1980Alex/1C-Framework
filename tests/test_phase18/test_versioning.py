"""Phase 18: Incremental Indexing — Document Version Manager tests.

Tests for:
  - DocumentVersionManager: track file hashes and chunk versions
  - ChunkDelta: detect added/modified/removed chunks
  - PDFFileWatcher: directory monitoring for auto-indexing
"""

import pytest


class TestDocumentVersionManager:
    """Tests for DocumentVersionManager."""

    @pytest.mark.asyncio
    async def test_initialize_creates_db(self, tmp_path):
        from src.pdf_framework.processing.versioning import DocumentVersionManager

        mgr = DocumentVersionManager(db_path=tmp_path / "versions.db")
        await mgr.initialize()

    @pytest.mark.asyncio
    async def test_check_status_new_file(self, tmp_path):
        from src.pdf_framework.processing.versioning import DocumentVersionManager

        mgr = DocumentVersionManager(db_path=tmp_path / "versions.db")
        await mgr.initialize()
        status = await mgr.check_status("nonexistent.pdf")
        assert status == "new"

    @pytest.mark.asyncio
    async def test_check_status_unchanged(self, tmp_path):
        from src.pdf_framework.processing.versioning import DocumentVersionManager

        mgr = DocumentVersionManager(db_path=tmp_path / "versions.db")
        await mgr.initialize()

        # Create a test file
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content v1")

        # Save version
        await mgr.save_version(str(test_file), "doc1", [])
        status = await mgr.check_status(str(test_file))
        assert status == "unchanged"

    @pytest.mark.asyncio
    async def test_check_status_modified(self, tmp_path):
        from src.pdf_framework.processing.versioning import DocumentVersionManager

        mgr = DocumentVersionManager(db_path=tmp_path / "versions.db")
        await mgr.initialize()

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"PDF content v1")
        await mgr.save_version(str(test_file), "doc1", [])

        # Modify file
        test_file.write_bytes(b"PDF content v2 - modified")
        status = await mgr.check_status(str(test_file))
        assert status == "modified"

    @pytest.mark.asyncio
    async def test_remove_version(self, tmp_path):
        from src.pdf_framework.processing.versioning import DocumentVersionManager

        mgr = DocumentVersionManager(db_path=tmp_path / "versions.db")
        await mgr.initialize()

        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")
        await mgr.save_version(str(test_file), "doc1", [])
        await mgr.remove_version(str(test_file))

        status = await mgr.check_status(str(test_file))
        assert status == "new"


class TestChunkDelta:
    """Tests for ChunkDelta computation."""

    @pytest.mark.asyncio
    async def test_all_new_chunks(self, tmp_path):
        from src.pdf_framework.processing.versioning import DocumentVersionManager
        from src.pdf_framework.schemas.documents import DocumentChunk

        mgr = DocumentVersionManager(db_path=tmp_path / "versions.db")
        await mgr.initialize()

        new_chunks = [
            DocumentChunk(id="c1", content="Text 1", document_id="d1"),
            DocumentChunk(id="c2", content="Text 2", document_id="d1"),
        ]
        delta = await mgr.compute_delta("new_file.pdf", new_chunks)

        assert len(delta.added) == 2
        assert len(delta.modified) == 0
        assert len(delta.removed) == 0
        assert delta.unchanged == 0

    @pytest.mark.asyncio
    async def test_detect_modified_chunks(self, tmp_path):
        from src.pdf_framework.processing.versioning import DocumentVersionManager
        from src.pdf_framework.schemas.documents import DocumentChunk

        mgr = DocumentVersionManager(db_path=tmp_path / "versions.db")
        await mgr.initialize()

        old_chunks = [
            DocumentChunk(id="c1", content="Original text", document_id="d1"),
        ]
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")
        await mgr.save_version(str(test_file), "d1", old_chunks)

        new_chunks = [
            DocumentChunk(id="c1", content="Modified text", document_id="d1"),
        ]
        delta = await mgr.compute_delta(str(test_file), new_chunks)

        assert len(delta.modified) == 1
        assert len(delta.added) == 0
        assert len(delta.removed) == 0

    @pytest.mark.asyncio
    async def test_detect_removed_chunks(self, tmp_path):
        from src.pdf_framework.processing.versioning import DocumentVersionManager
        from src.pdf_framework.schemas.documents import DocumentChunk

        mgr = DocumentVersionManager(db_path=tmp_path / "versions.db")
        await mgr.initialize()

        old_chunks = [
            DocumentChunk(id="c1", content="Text 1", document_id="d1"),
            DocumentChunk(id="c2", content="Text 2", document_id="d1"),
        ]
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"content")
        await mgr.save_version(str(test_file), "d1", old_chunks)

        new_chunks = [
            DocumentChunk(id="c1", content="Text 1", document_id="d1"),
        ]
        delta = await mgr.compute_delta(str(test_file), new_chunks)

        assert len(delta.removed) == 1
        assert "c2" in delta.removed


class TestFileWatcher:
    """Tests for PDFFileWatcher."""

    @pytest.mark.asyncio
    async def test_watcher_detects_new_file(self, tmp_path):
        from src.pdf_framework.processing.watcher import PDFFileWatcher

        events = []

        async def callback(event_type, file_path):
            events.append((event_type, str(file_path)))

        watcher = PDFFileWatcher(watch_dir=tmp_path, indexing_callback=callback)
        await watcher.start()

        (tmp_path / "new_doc.pdf").write_bytes(b"PDF")
        import asyncio
        await asyncio.sleep(6)  # debounce_seconds = 5

        await watcher.stop()
        assert any(e[0] == "index" for e in events)

    @pytest.mark.asyncio
    async def test_watcher_ignores_non_pdf(self, tmp_path):
        from src.pdf_framework.processing.watcher import PDFFileWatcher

        events = []

        async def callback(event_type, file_path):
            events.append((event_type, str(file_path)))

        watcher = PDFFileWatcher(watch_dir=tmp_path, indexing_callback=callback)
        await watcher.start()

        (tmp_path / "readme.txt").write_text("text")
        import asyncio
        await asyncio.sleep(6)

        await watcher.stop()
        assert len(events) == 0
