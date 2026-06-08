"""Unit tests for Processing splitters and pipeline (F2.6).

Tests:
- F2.6.1: RecursiveTextSplitter chunk sizes and content
- F2.6.2: SemanticTextSplitter breakpoint detection (mocked embeddings)
- F2.6.3: Pipeline._assign_page_numbers via page_offsets
- F2.6.4: deterministic ID generation (generate_document_id / generate_chunk_id)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(raw_text: str, doc_id: str = "testdoc001") -> object:
    """Build a minimal ProcessedDocument for splitter tests (no I/O)."""
    from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument

    return ProcessedDocument(
        id=doc_id,
        source_path="/tmp/test.pdf",
        metadata=DocumentMetadata(title="Test Doc", source="/tmp/test.pdf"),
        raw_text=raw_text,
    )


# ---------------------------------------------------------------------------
# F2.6.1 RecursiveTextSplitter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRecursiveSplitter:
    """Test RecursiveTextSplitter chunk size control and output structure."""

    def test_chunk_size_respected(self):
        """F2.6.1: No chunk content should exceed chunk_size by a large margin."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter

        splitter = RecursiveTextSplitter(chunk_size=300, chunk_overlap=30)
        # ~1500 chars, well over chunk_size=300
        long_text = ("The quick brown fox jumps over the lazy dog. " * 35).strip()
        doc = _make_doc(long_text)

        chunks = splitter.split(doc)

        assert len(chunks) > 1, "Long text must be split into multiple chunks"
        for chunk in chunks:
            # LangChain may slightly exceed due to separators, allow 2× headroom
            assert len(chunk.content) <= 600, (
                f"Chunk too large: {len(chunk.content)} chars"
            )

    def test_chunk_overlap_produces_shared_content(self):
        """F2.6.1: Consecutive chunks should share text due to overlap."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter

        splitter = RecursiveTextSplitter(chunk_size=200, chunk_overlap=50)
        text = ("alpha beta gamma delta epsilon zeta eta theta iota kappa " * 12).strip()
        doc = _make_doc(text)

        chunks = splitter.split(doc)

        assert len(chunks) >= 2, "Need at least 2 chunks to test overlap"
        # The end of chunk[0] content should have some words that appear in chunk[1]
        words_end = set(chunks[0].content.split()[-10:])
        words_start = set(chunks[1].content.split()[:30])
        overlap = words_end & words_start
        assert len(overlap) > 0, "Consecutive chunks should share overlapping words"

    def test_empty_text_returns_empty_list(self):
        """F2.6.1: Empty raw_text must produce no chunks."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter

        splitter = RecursiveTextSplitter()
        doc = _make_doc("")

        chunks = splitter.split(doc)

        assert chunks == []

    def test_short_text_returns_single_chunk(self):
        """F2.6.1: Text shorter than chunk_size must produce exactly one chunk."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter

        splitter = RecursiveTextSplitter(chunk_size=1000, chunk_overlap=100)
        doc = _make_doc("Short text that fits in one chunk.")

        chunks = splitter.split(doc)

        assert len(chunks) == 1
        assert "Short text that fits in one chunk." in chunks[0].content

    def test_returns_document_chunks_with_correct_fields(self):
        """F2.6.1: Each returned item must be a DocumentChunk with expected fields."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter
        from src.pdf_framework.schemas.documents import DocumentChunk

        splitter = RecursiveTextSplitter(chunk_size=500, chunk_overlap=50)
        doc = _make_doc(("word " * 200).strip(), doc_id="myDoc42")

        chunks = splitter.split(doc)

        assert len(chunks) >= 1
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, DocumentChunk)
            assert chunk.document_id == "myDoc42"
            assert chunk.chunk_index == i
            assert isinstance(chunk.id, str) and len(chunk.id) == 16
            assert chunk.content  # non-empty

    def test_heading_propagation_adds_section_prefix(self):
        """F2.6.1: Chunks following a markdown heading inherit a section prefix."""
        from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter

        splitter = RecursiveTextSplitter(chunk_size=500, chunk_overlap=0)
        text = "## 1. Introduction\n\n" + ("This is intro content. " * 30)
        doc = _make_doc(text)

        chunks = splitter.split(doc)

        assert len(chunks) >= 1
        # At least one chunk should carry the section header in metadata
        sections = [c.metadata.get("section_title", "") for c in chunks]
        assert any("Introduction" in s or "1." in s for s in sections), (
            f"No chunk has section_title with heading info; got: {sections}"
        )


# ---------------------------------------------------------------------------
# F2.6.2 SemanticTextSplitter (mocked SentenceTransformer)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSemanticSplitter:
    """Test SemanticTextSplitter using mocked SentenceTransformer."""

    @staticmethod
    def _make_splitter(threshold: float = 0.75):
        """Build a SemanticTextSplitter with mocked SentenceTransformer."""
        from src.pdf_framework.processing.splitters.semantic_splitter import SemanticTextSplitter

        with patch(
            "src.pdf_framework.processing.splitters.semantic_splitter.SentenceTransformer"
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            splitter = SemanticTextSplitter(
                chunk_size=500,
                chunk_overlap=50,
                semantic_threshold=threshold,
                min_chunk_size=10,
                max_chunk_size=2000,
            )
        return splitter

    def test_empty_text_returns_empty(self):
        """F2.6.2: Empty document produces no chunks."""
        splitter = self._make_splitter()
        doc = _make_doc("")

        result = splitter.split(doc)

        assert result == []

    def test_short_text_returns_single_chunk(self):
        """F2.6.2: <=2 sentences → single chunk without embedding call."""
        splitter = self._make_splitter()
        doc = _make_doc("First sentence. Second sentence.")

        result = splitter.split(doc)

        assert len(result) == 1
        assert "First sentence" in result[0].content

    def test_breakpoints_split_at_low_similarity(self):
        """F2.6.2: Low-similarity transition causes a split into multiple chunks."""
        splitter = self._make_splitter(threshold=0.75)

        # 6 sentences → 5 similarity values; inject a low-similarity gap at index 2
        # embeddings: 3 orthogonal groups
        sentences_text = (
            "Alpha one sentence. Alpha two sentence. Alpha three sentence. "
            "Beta one sentence. Beta two sentence. Beta three sentence."
        )
        doc = _make_doc(sentences_text)

        # Build controlled embeddings: sentences 0-2 cluster A, 3-5 cluster B
        dim = 8
        cluster_a = np.zeros(dim)
        cluster_a[0] = 1.0
        cluster_b = np.zeros(dim)
        cluster_b[4] = 1.0

        embeddings = np.array([
            cluster_a, cluster_a, cluster_a,  # high similarity within group
            cluster_b, cluster_b, cluster_b,  # high similarity within group
        ])
        # similarity between index 2→3 will be 0.0 (orthogonal) → below 0.75

        splitter._model.encode.return_value = embeddings

        result = splitter.split(doc)

        assert len(result) >= 2, (
            f"Expected split at semantic boundary, got {len(result)} chunk(s)"
        )

    def test_find_breakpoints_returns_correct_indices(self):
        """F2.6.2: _find_breakpoints returns indices where similarity < threshold."""
        splitter = self._make_splitter(threshold=0.5)

        # similarities: high, low, high, low, high
        sims = [0.9, 0.2, 0.8, 0.1, 0.95]
        breakpoints = splitter._find_breakpoints(sims)

        # _find_breakpoints stores i+1 (the sentence index to break before).
        # sim[1]=0.2 → break at sentence 2; sim[3]=0.1 → break at sentence 4.
        assert 2 in breakpoints  # break before sentence 2 (after low sim at index 1)
        assert 4 in breakpoints  # break before sentence 4 (after low sim at index 3)

    def test_compute_consecutive_similarities_shape(self):
        """F2.6.2: _compute_consecutive_similarities returns N-1 values for N embeddings."""
        splitter = self._make_splitter()

        n = 5
        embs = np.random.rand(n, 16).astype(np.float32)
        sims = splitter._compute_consecutive_similarities(embs)

        assert len(sims) == n - 1
        for s in sims:
            assert -1.0 <= s <= 1.0 + 1e-6

    def test_output_chunks_are_document_chunks(self):
        """F2.6.2: Returned items are DocumentChunk instances with splitter metadata."""
        from src.pdf_framework.schemas.documents import DocumentChunk

        splitter = self._make_splitter()
        doc = _make_doc("Only one sentence here.", doc_id="semDoc1")

        result = splitter.split(doc)

        assert len(result) == 1
        chunk = result[0]
        assert isinstance(chunk, DocumentChunk)
        assert chunk.document_id == "semDoc1"
        assert chunk.metadata.get("splitter") == "semantic"


# ---------------------------------------------------------------------------
# F2.6.3 ProcessingPipeline._assign_page_numbers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPipeline:
    """Test ProcessingPipeline._assign_page_numbers page-offset mapping."""

    @staticmethod
    def _make_pipeline():
        """Build a ProcessingPipeline without loading heavy splitter deps."""
        from unittest.mock import MagicMock

        from src.pdf_framework.config import PDFSettings
        from src.pdf_framework.processing.pipeline import ProcessingPipeline

        settings = PDFSettings()
        # Bypass splitter construction to avoid SentenceTransformer download
        with patch.object(ProcessingPipeline, "_create_splitter", return_value=MagicMock()):
            pipeline = ProcessingPipeline(settings=settings)
        return pipeline

    @staticmethod
    def _make_doc_with_offsets(raw_text: str, page_offsets: list[tuple[int, int]]):
        """Build a ProcessedDocument with page_offsets in metadata.extra."""
        from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument

        return ProcessedDocument(
            id="pipe_doc",
            source_path="/tmp/pipe.pdf",
            metadata=DocumentMetadata(
                title="Pipeline Test",
                extra={"page_offsets": page_offsets},
            ),
            raw_text=raw_text,
        )

    @staticmethod
    def _make_chunk(content: str, doc_id: str = "pipe_doc", text_offset: int | None = None):
        """Build a DocumentChunk positioned at text_offset."""
        from src.pdf_framework.schemas.documents import DocumentChunk
        from src.pdf_framework.utils.id_generator import generate_chunk_id

        meta = {}
        if text_offset is not None:
            meta["text_offset"] = text_offset
        return DocumentChunk(
            id=generate_chunk_id(doc_id, 0, content),
            content=content,
            document_id=doc_id,
            chunk_index=0,
            metadata=meta,
        )

    def test_no_page_offsets_returns_chunks_unchanged(self):
        """F2.6.3: Without page_offsets, chunks are returned as-is (no page assigned)."""
        from src.pdf_framework.processing.pipeline import ProcessingPipeline
        from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument

        doc = ProcessedDocument(
            id="x",
            source_path="/tmp/x.pdf",
            metadata=DocumentMetadata(),
            raw_text="hello world",
        )
        chunk = self._make_chunk("hello world")
        result = ProcessingPipeline._assign_page_numbers([chunk], doc)

        assert result == [chunk]
        assert chunk.page_number is None

    def test_single_page_document_assigns_page_1(self):
        """F2.6.3: All chunks in a single-page doc get page 1."""
        raw = "First chunk text. Second chunk text."
        doc = self._make_doc_with_offsets(raw, [(0, 1)])

        chunks = [
            self._make_chunk("First chunk text.", text_offset=0),
            self._make_chunk("Second chunk text.", text_offset=18),
        ]

        from src.pdf_framework.processing.pipeline import ProcessingPipeline
        result = ProcessingPipeline._assign_page_numbers(chunks, doc)

        assert result[0].page_number == 1
        assert result[1].page_number == 1

    def test_multi_page_assigns_correct_pages(self):
        """F2.6.3: Chunks on different pages get correct page numbers via binary search."""
        # Build a text where page 1 starts at 0, page 2 starts at 50, page 3 at 100
        raw = "A" * 50 + "B" * 50 + "C" * 50
        page_offsets = [(0, 1), (50, 2), (100, 3)]
        doc = self._make_doc_with_offsets(raw, page_offsets)

        chunks = [
            self._make_chunk("A" * 20, text_offset=10),   # page 1
            self._make_chunk("B" * 20, text_offset=60),   # page 2
            self._make_chunk("C" * 20, text_offset=110),  # page 3
        ]

        from src.pdf_framework.processing.pipeline import ProcessingPipeline
        result = ProcessingPipeline._assign_page_numbers(chunks, doc)

        assert result[0].page_number == 1
        assert result[1].page_number == 2
        assert result[2].page_number == 3

    def test_already_assigned_page_not_overwritten(self):
        """F2.6.3: Chunk with existing page_number > 0 is left untouched."""
        raw = "Some text here."
        doc = self._make_doc_with_offsets(raw, [(0, 1)])

        from src.pdf_framework.schemas.documents import DocumentChunk
        from src.pdf_framework.utils.id_generator import generate_chunk_id

        chunk = DocumentChunk(
            id=generate_chunk_id("pipe_doc", 0, "Some text"),
            content="Some text here.",
            document_id="pipe_doc",
            chunk_index=0,
            page_number=99,  # pre-assigned (e.g. image chunk)
            metadata={"text_offset": 0},
        )

        from src.pdf_framework.processing.pipeline import ProcessingPipeline
        result = ProcessingPipeline._assign_page_numbers([chunk], doc)

        assert result[0].page_number == 99  # not overwritten


# ---------------------------------------------------------------------------
# F2.6.4 Deterministic ID generation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIDGeneration:
    """Test deterministic ID generation (generate_document_id / generate_chunk_id)."""

    def test_document_id_deterministic(self):
        """F2.6.4: Same file path produces the same document ID."""
        from src.pdf_framework.utils.id_generator import generate_document_id

        id1 = generate_document_id("/some/path/document.pdf")
        id2 = generate_document_id("/some/path/document.pdf")

        assert id1 == id2

    def test_document_id_different_paths_differ(self):
        """F2.6.4: Different file paths produce different document IDs."""
        from src.pdf_framework.utils.id_generator import generate_document_id

        id1 = generate_document_id("/path/doc1.pdf")
        id2 = generate_document_id("/path/doc2.pdf")

        assert id1 != id2

    def test_document_id_is_16char_hex(self):
        """F2.6.4: Document ID is a 16-char lowercase hex string."""
        from src.pdf_framework.utils.id_generator import generate_document_id

        doc_id = generate_document_id("/any/path/file.pdf")

        assert isinstance(doc_id, str)
        assert len(doc_id) == 16
        assert all(c in "0123456789abcdef" for c in doc_id)

    def test_chunk_id_deterministic(self):
        """F2.6.4: Same (doc_id, index, prefix) always yields the same chunk ID."""
        from src.pdf_framework.utils.id_generator import generate_chunk_id

        id1 = generate_chunk_id("abc123def456abcd", 0, "Hello world content")
        id2 = generate_chunk_id("abc123def456abcd", 0, "Hello world content")

        assert id1 == id2

    def test_chunk_id_unique_across_indices(self):
        """F2.6.4: 100 consecutive chunk indices produce 100 unique IDs."""
        from src.pdf_framework.utils.id_generator import generate_chunk_id

        ids = [generate_chunk_id("docId000docId000", i, f"chunk content {i}") for i in range(100)]

        assert len(set(ids)) == 100

    def test_chunk_id_differs_by_document(self):
        """F2.6.4: Same index/content but different doc IDs → different chunk IDs."""
        from src.pdf_framework.utils.id_generator import generate_chunk_id

        id1 = generate_chunk_id("doc1doc1doc1doc1", 0, "same content")
        id2 = generate_chunk_id("doc2doc2doc2doc2", 0, "same content")

        assert id1 != id2

    def test_chunk_id_differs_by_content_prefix(self):
        """F2.6.4: Same doc/index but different content → different chunk IDs."""
        from src.pdf_framework.utils.id_generator import generate_chunk_id

        id1 = generate_chunk_id("docXdocXdocXdocX", 5, "content A")
        id2 = generate_chunk_id("docXdocXdocXdocX", 5, "content B")

        assert id1 != id2

    def test_chunk_id_is_16char_hex(self):
        """F2.6.4: Chunk ID is a 16-char lowercase hex string."""
        from src.pdf_framework.utils.id_generator import generate_chunk_id

        cid = generate_chunk_id("docIdAbcdEfgh012", 3, "some content here")

        assert isinstance(cid, str)
        assert len(cid) == 16
        assert all(c in "0123456789abcdef" for c in cid)
