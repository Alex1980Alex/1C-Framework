"""Behavioral unit tests for orphan / bug-prone ``processing/`` classes.

This closes the gap that the import-smoke suite (``test_import_smoke.py``) cannot:
import-only checks never *execute* methods, so a runtime ``AttributeError`` inside a
method body — exactly the ``self._format`` bug in ``PageRenderer.save_pages`` — slips
through. Here we actually instantiate each class and exercise its public methods on
the happy path.

Side-effects are contained, not avoided:
* all filesystem writes go to pytest ``tmp_path`` (no cwd pollution),
* external services (Anthropic client, embedding engine, LLM) are mocked,
* PDF-consuming classes get a real but tiny PDF generated in-memory via PyMuPDF.

Every test asserts the method runs and returns a sane result — which means a
re-introduced ``self._format`` / missing-``await`` / stale-import regression fails loudly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """A real 2-page PDF generated with PyMuPDF (skips if PyMuPDF absent)."""
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i} — sample text")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """A real file on disk (cache/versioning hash the file contents)."""
    f = tmp_path / "doc.txt"
    f.write_text("hello world", encoding="utf-8")
    return f


# --------------------------------------------------------------------------- #
# cache.py — DocumentProcessingCache
# --------------------------------------------------------------------------- #
def test_document_cache_roundtrip(tmp_path: Path, sample_file: Path) -> None:
    from src.pdf_framework.processing.cache import CachedDocument, DocumentProcessingCache

    cache = DocumentProcessingCache(cache_dir=tmp_path / "cache")
    assert cache.get(sample_file) is None  # miss

    cache.set(
        sample_file,
        chunks=[{"text": "a"}],
        embeddings=[[0.1, 0.2]],
        metadata={"k": "v"},
    )
    got = cache.get(sample_file)
    assert isinstance(got, CachedDocument)
    assert got.chunks == [{"text": "a"}]
    assert got.metadata == {"k": "v"}
    assert not got.is_stale(sample_file)

    stats = cache.get_stats()
    assert stats["hits"] >= 1 and stats["misses"] >= 1

    assert cache.clear() >= 1
    assert cache.get(sample_file) is None


def test_document_cache_detects_stale(tmp_path: Path, sample_file: Path) -> None:
    from src.pdf_framework.processing.cache import DocumentProcessingCache

    cache = DocumentProcessingCache(cache_dir=tmp_path / "cache")
    cache.set(sample_file, chunks=[], embeddings=[], metadata={})
    sample_file.write_text("changed", encoding="utf-8")  # invalidates hash
    assert cache.get(sample_file) is None  # stale → evicted


# --------------------------------------------------------------------------- #
# versioning.py — DocumentVersionManager  (async, real SQLite in tmp)
# --------------------------------------------------------------------------- #
async def test_version_manager_create_get_rollback(tmp_path: Path) -> None:
    from src.pdf_framework.processing.versioning import DocumentVersionManager, VersionInfo

    mgr = DocumentVersionManager(db_path=tmp_path / "v.db", cache_dir=tmp_path / "chunks")

    v1 = await mgr.create_version("doc1", chunks=[{"c": "one"}], metadata={"n": 1})
    v2 = await mgr.create_version("doc1", chunks=[{"c": "two"}], metadata={"n": 2})
    assert isinstance(v1, VersionInfo) and v2.previous_version_id == v1.version_id

    versions = await mgr.get_versions("doc1")
    assert len(versions) == 2
    assert (await mgr.get_latest_version("doc1")).version_id == v2.version_id
    assert (await mgr.get_version(v1.version_id)).version_id == v1.version_id

    chunks_blob = await mgr.get_version_chunks(v1.version_id)
    assert chunks_blob is not None and chunks_blob["chunks"] == [{"c": "one"}]

    rolled_chunks, _emb, _meta = await mgr.rollback("doc1")  # to previous (v1)
    assert rolled_chunks == [{"c": "one"}]

    assert await mgr.delete_document("doc1") == 2
    assert await mgr.get_versions("doc1") == []


async def test_version_manager_incremental_and_checkpoints(
    tmp_path: Path, sample_file: Path
) -> None:
    from src.pdf_framework.processing.versioning import ChunkDelta, DocumentVersionManager
    from src.pdf_framework.schemas.documents import DocumentChunk

    mgr = DocumentVersionManager(db_path=tmp_path / "v.db", cache_dir=tmp_path / "chunks")
    path = str(sample_file)

    assert await mgr.check_status(path) == "new"
    chunks = [DocumentChunk(id="c1", content="alpha", document_id="d")]
    await mgr.save_version(path, "d", chunks)
    assert await mgr.check_status(path) == "unchanged"

    delta = await mgr.compute_delta(path, [DocumentChunk(id="c2", content="beta", document_id="d")])
    assert isinstance(delta, ChunkDelta)
    assert "c2" in delta.added and "c1" in delta.removed

    # Checkpoint lifecycle (exercises the bool()/row-index code paths)
    assert await mgr.start_indexing(path, "d", total_batches=1, total_chunks=1) is None
    assert await mgr.is_indexing_in_progress() is True
    await mgr.save_checkpoint(path, batch_index=0, batch_chunks=chunks)
    cp = await mgr.get_checkpoint(path)
    assert cp is not None and cp.last_completed_batch == 0
    await mgr.complete_indexing(path, "d", total_chunks=1)
    assert await mgr.is_indexing_in_progress() is False


async def test_version_manager_concurrency_guard(tmp_path: Path) -> None:
    """A second, different file cannot start indexing while another is in progress."""
    from src.pdf_framework.processing.versioning import DocumentVersionManager

    mgr = DocumentVersionManager(db_path=tmp_path / "v.db", cache_dir=tmp_path / "chunks")
    file_a = tmp_path / "a.txt"
    file_a.write_text("aaa", encoding="utf-8")
    file_b = tmp_path / "b.txt"
    file_b.write_text("bbb", encoding="utf-8")

    await mgr.start_indexing(str(file_a), "da", total_batches=1, total_chunks=1)
    with pytest.raises(RuntimeError, match="already in progress"):
        await mgr.start_indexing(str(file_b), "db", total_batches=1, total_chunks=1)


# --------------------------------------------------------------------------- #
# page_renderer.py — PageRenderer.save_pages  (the self._format regression site)
# --------------------------------------------------------------------------- #
def test_page_renderer_save_pages(tmp_path: Path, sample_pdf: Path) -> None:
    from src.pdf_framework.processing.page_renderer import PageRenderer

    renderer = PageRenderer(dpi=72)  # low DPI = fast
    assert renderer.get_page_count(sample_pdf) == 2

    rendered = renderer.render_pages(sample_pdf, pages=[0])
    assert len(rendered) == 1 and rendered[0][0] == 0

    out = tmp_path / "imgs"
    # This path dereferences self._config.format twice — would AttributeError
    # if the historical `self._format` bug were reintroduced.
    saved = renderer.save_pages(sample_pdf, out, prefix="pg")
    assert len(saved) == 2
    assert all(p.exists() and p.suffix.lower() == ".png" for p in saved)


# --------------------------------------------------------------------------- #
# splitters/proposition.py — PropositionSplitter (mocked LLM)
# --------------------------------------------------------------------------- #
def test_proposition_splitter_parses_str_content() -> None:
    from src.pdf_framework.processing.splitters.proposition import PropositionSplitter

    llm = MagicMock()
    llm.invoke = MagicMock(
        return_value=MagicMock(content="1. First fact\n2. Second fact\n3. Third")
    )
    splitter = PropositionSplitter(llm=llm, min_propositions=2)

    props = splitter.split_text("This is a sufficiently long input sentence to trigger splitting.")
    assert props == ["First fact", "Second fact", "Third"]


def test_proposition_splitter_survives_list_content() -> None:
    """response.content may be ``list`` (tool blocks); str() guard must not crash."""
    from src.pdf_framework.processing.splitters.proposition import PropositionSplitter

    llm = MagicMock()
    llm.invoke = MagicMock(return_value=MagicMock(content=[{"type": "text", "text": "x"}]))
    splitter = PropositionSplitter(llm=llm)
    # Long text → goes through _extract_propositions → str(list).strip(); must not raise.
    result = splitter.split_text(
        "A long enough sentence to exceed the fifty character threshold here."
    )
    assert result and isinstance(result[0], str)


def test_proposition_split_documents() -> None:
    from src.pdf_framework.processing.splitters.proposition import PropositionSplitter
    from src.pdf_framework.schemas.documents import DocumentChunk

    llm = MagicMock()
    llm.invoke = MagicMock(return_value=MagicMock(content="1. one\n2. two\n3. three"))
    splitter = PropositionSplitter(llm=llm, min_propositions=2)

    doc = DocumentChunk(id="d1", content="x" * 80, document_id="doc")
    out = splitter.split_documents([doc])
    assert out and all(isinstance(c, DocumentChunk) for c in out)


# --------------------------------------------------------------------------- #
# image_processor.py — ImageProcessor.process_from_chunks (the missing-await fix)
# --------------------------------------------------------------------------- #
async def test_image_processor_awaits_embedding() -> None:
    from src.pdf_framework.processing.image_processor import ImageProcessor
    from src.pdf_framework.schemas.images import ImageChunk

    embedder = MagicMock()
    embedder.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])
    proc = ImageProcessor(
        describer=None, embedder=embedder, enable_description=False, enable_embedding=True
    )

    chunk = ImageChunk(id="i1", document_id="d1", page_number=1, image_index=0)
    result = await proc.process_from_chunks([chunk])

    assert len(result) == 1
    # If the `await` regressed, embedding would be a coroutine, not a list.
    assert result[0].chunk.embedding == [0.1, 0.2, 0.3]
    embedder.embed_text.assert_awaited_once()

    chunk_dicts = proc.to_document_chunks(result, document_id="d1")
    assert chunk_dicts and chunk_dicts[0]["section"] == "image"


# --------------------------------------------------------------------------- #
# section_summary.py & image_extractor.py — None-client guards (the added guards)
# --------------------------------------------------------------------------- #
async def test_section_summary_crud_and_guard(tmp_path: Path) -> None:
    from src.pdf_framework.processing.section_summary import SectionSummaryService

    svc = SectionSummaryService(api_key="", db_path=tmp_path / "s.db")
    await svc.initialize()
    assert await svc.count() == 0
    assert await svc.get_summary("doc", "1.1") is None
    assert await svc.get_all("doc") == []
    assert await svc.delete_by_document("doc") == 0

    # No api_key → no client → the guard must raise a clear error, not AttributeError.
    with pytest.raises(RuntimeError, match="client not configured"):
        svc._call_summary_api("title", "content")


def test_image_extractor_guard_and_helpers() -> None:
    from src.pdf_framework.processing.image_extractor import ImageDescription, ImageExtractor

    extractor = ImageExtractor(api_key="")  # client is None
    with pytest.raises(RuntimeError, match="client not configured"):
        extractor._call_vision_api("base64data", "image/png")

    assert extractor._guess_media_type(b"\x89PNG\r\n") == "image/png"

    desc = ImageDescription(
        image_bytes=b"x",
        description="d",
        page_number=1,
        image_format="png",
        size=(10, 20),
        description_model="m",
    )
    assert desc.to_dict()["page_number"] == 1


# --------------------------------------------------------------------------- #
# table_extractor.py & splitters/parent_child.py — pure dict/stats methods
# --------------------------------------------------------------------------- #
def test_table_data_to_json() -> None:
    from src.pdf_framework.processing.table_extractor import TableData

    table = TableData(headers=["A", "B"], rows=[["1", "2"]], page_number=3)
    payload = table.to_json()
    assert payload["headers"] == ["A", "B"] and payload["page_number"] == 3


def test_parent_child_get_stats() -> None:
    from src.pdf_framework.processing.splitters.parent_child import ParentChildSplitter
    from src.pdf_framework.schemas.documents import DocumentChunk

    splitter = ParentChildSplitter()
    parents = [
        DocumentChunk(id="p1", content="parent body", document_id="d", metadata={"child_count": 2})
    ]
    children = [
        DocumentChunk(id="c1", content="child a", document_id="d"),
        DocumentChunk(id="c2", content="child b", document_id="d"),
    ]
    stats = splitter.get_stats(parents, children)
    assert stats["parent_count"] == 1 and stats["child_count"] == 2

    empty = splitter.get_stats([], [])
    assert empty["parent_count"] == 0
