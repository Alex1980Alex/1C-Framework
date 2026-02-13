"""Tests for ParentChildSplitter (Phase 7.1).

Tests two-level document chunking without LLM calls.
"""

import pytest

from src.pdf_framework.processing.splitters.parent_child import ParentChildSplitter
from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument


def _make_document(text: str, doc_id: str = "doc_1") -> ProcessedDocument:
    return ProcessedDocument(
        id=doc_id,
        source_path="/test/doc.pdf",
        metadata=DocumentMetadata(title="Test Doc"),
        raw_text=text,
    )


@pytest.fixture
def splitter():
    return ParentChildSplitter(
        parent_chunk_size=200,
        parent_chunk_overlap=20,
        child_chunk_size=50,
        child_chunk_overlap=10,
    )


@pytest.fixture
def long_text():
    """Generate text long enough for multiple parent chunks."""
    paragraph = "This is a test paragraph with enough content to create meaningful chunks. "
    return paragraph * 30  # ~2250 chars


class TestParentChildSplit:
    def test_empty_document(self, splitter):
        doc = _make_document("")
        parents, children = splitter.split(doc)
        assert parents == []
        assert children == []

    def test_whitespace_only(self, splitter):
        doc = _make_document("   \n\n   ")
        parents, children = splitter.split(doc)
        assert parents == []
        assert children == []

    def test_short_document_single_parent(self, splitter):
        doc = _make_document("A short text that fits in one parent.")
        parents, children = splitter.split(doc)
        assert len(parents) == 1
        assert len(children) >= 1

    def test_long_document_multiple_parents(self, splitter, long_text):
        doc = _make_document(long_text)
        parents, children = splitter.split(doc)
        assert len(parents) > 1
        assert len(children) > len(parents)

    def test_parent_has_correct_metadata(self, splitter, long_text):
        doc = _make_document(long_text)
        parents, _ = splitter.split(doc)

        for parent in parents:
            assert parent.metadata["chunk_type"] == "parent"
            assert parent.document_id == "doc_1"
            assert "child_ids" in parent.metadata
            assert "child_count" in parent.metadata
            assert parent.metadata["child_count"] > 0

    def test_child_has_correct_metadata(self, splitter, long_text):
        doc = _make_document(long_text)
        _, children = splitter.split(doc)

        for child in children:
            assert child.metadata["chunk_type"] == "child"
            assert "parent_id" in child.metadata
            assert "parent_index" in child.metadata
            assert child.document_id == "doc_1"

    def test_parent_child_links_consistent(self, splitter, long_text):
        doc = _make_document(long_text)
        parents, children = splitter.split(doc)

        # All child IDs in parent metadata should actually exist
        all_child_ids = {c.id for c in children}
        for parent in parents:
            for cid in parent.metadata["child_ids"]:
                assert cid in all_child_ids

        # All parent IDs in child metadata should exist
        all_parent_ids = {p.id for p in parents}
        for child in children:
            assert child.metadata["parent_id"] in all_parent_ids

    def test_unique_ids(self, splitter, long_text):
        doc = _make_document(long_text)
        parents, children = splitter.split(doc)

        parent_ids = [p.id for p in parents]
        child_ids = [c.id for c in children]

        assert len(parent_ids) == len(set(parent_ids))  # No duplicate parent IDs
        assert len(child_ids) == len(set(child_ids))  # No duplicate child IDs
        assert not set(parent_ids) & set(child_ids)  # No overlap

    def test_children_smaller_than_parents(self, splitter, long_text):
        doc = _make_document(long_text)
        parents, children = splitter.split(doc)

        avg_parent_size = sum(len(p.content) for p in parents) / len(parents)
        avg_child_size = sum(len(c.content) for c in children) / len(children)

        assert avg_child_size < avg_parent_size


class TestSplitToParentsOnly:
    def test_returns_only_parents(self, splitter, long_text):
        doc = _make_document(long_text)
        parents = splitter.split_to_parents_only(doc)
        assert len(parents) > 0
        for p in parents:
            assert p.metadata["chunk_type"] == "parent"


class TestSplitToChildrenOnly:
    def test_returns_clean_children(self, splitter, long_text):
        doc = _make_document(long_text)
        children = splitter.split_to_children_only(doc)
        assert len(children) > 0
        for c in children:
            assert "parent_id" not in c.metadata
            assert "parent_index" not in c.metadata


class TestGetStats:
    def test_stats_empty(self, splitter):
        stats = splitter.get_stats([], [])
        assert stats["parent_count"] == 0
        assert stats["child_count"] == 0

    def test_stats_with_data(self, splitter, long_text):
        doc = _make_document(long_text)
        parents, children = splitter.split(doc)
        stats = splitter.get_stats(parents, children)

        assert stats["parent_count"] == len(parents)
        assert stats["child_count"] == len(children)
        assert stats["avg_parent_size"] > 0
        assert stats["avg_child_size"] > 0
        assert stats["avg_children_per_parent"] > 0
        assert stats["max_children_per_parent"] >= stats["min_children_per_parent"]
