"""Unit tests for deterministic ID generation (F2.6.4).

Rewritten 2026-06-08 (roadmap 260608): the old single ``generate_id(file, page,
chunk)`` helper was split into ``generate_document_id(file_path)`` and
``generate_chunk_id(document_id, chunk_index, content_prefix)`` in
``src.pdf_framework.utils.id_generator``. These behavior tests assert the public
contract (determinism, sensitivity to each input, hex-string format) rather than
the removed signature.
"""

import re

import pytest

from src.pdf_framework.utils.id_generator import (
    generate_chunk_id,
    generate_document_id,
)

_HEX16 = re.compile(r"^[0-9a-f]{16}$")


@pytest.mark.unit
class TestGenerateDocumentID:
    """Deterministic document IDs derived from the file path."""

    def test_same_path_same_id(self):
        """F2.6.4: same input path produces the same ID (idempotent upserts)."""
        assert generate_document_id("test.pdf") == generate_document_id("test.pdf")

    def test_different_paths_different_ids(self):
        """F2.6.4: distinct documents produce distinct IDs."""
        assert generate_document_id("doc1.pdf") != generate_document_id("doc2.pdf")

    def test_format_is_16_char_hex(self):
        """F2.6.4: ID is a 16-char lowercase hex string (filename/URL safe)."""
        doc_id = generate_document_id("test file with spaces.pdf")
        assert isinstance(doc_id, str)
        assert _HEX16.match(doc_id), doc_id
        assert " " not in doc_id
        assert "/" not in doc_id and "\\" not in doc_id


@pytest.mark.unit
class TestGenerateChunkID:
    """Deterministic chunk IDs derived from document ID, index, and content."""

    def test_same_inputs_same_id(self):
        """F2.6.4: same inputs produce the same chunk ID."""
        id1 = generate_chunk_id("abc123", 0, "Hello world")
        id2 = generate_chunk_id("abc123", 0, "Hello world")
        assert id1 == id2

    def test_index_variation_changes_id(self):
        """F2.6.4: different chunk indices produce different IDs."""
        ids = [generate_chunk_id("abc123", i, "same content") for i in range(10)]
        assert len(set(ids)) == 10

    def test_document_variation_changes_id(self):
        """F2.6.4: chunks under different documents produce different IDs."""
        id1 = generate_chunk_id("doc1", 0, "content")
        id2 = generate_chunk_id("doc2", 0, "content")
        assert id1 != id2

    def test_content_variation_changes_id(self):
        """F2.6.4: same index but different content yields a different ID."""
        id1 = generate_chunk_id("abc123", 0, "first text")
        id2 = generate_chunk_id("abc123", 0, "second text")
        assert id1 != id2

    def test_string_index_label_supported(self):
        """Hierarchical labels (e.g. ``parent_3``) are accepted and deterministic."""
        id1 = generate_chunk_id("abc123", "parent_3", "content")
        id2 = generate_chunk_id("abc123", "parent_3", "content")
        assert id1 == id2
        assert id1 != generate_chunk_id("abc123", "child_2_5", "content")

    def test_content_prefix_truncated_at_100_chars(self):
        """Only the first 100 content chars matter — tails beyond that don't change the ID."""
        base = "x" * 100
        id1 = generate_chunk_id("abc123", 0, base + "AAA")
        id2 = generate_chunk_id("abc123", 0, base + "BBB")
        assert id1 == id2

    def test_format_is_16_char_hex(self):
        """F2.6.4: chunk ID is a 16-char lowercase hex string."""
        chunk_id = generate_chunk_id("abc123", 0, "Hello world")
        assert isinstance(chunk_id, str)
        assert _HEX16.match(chunk_id), chunk_id
