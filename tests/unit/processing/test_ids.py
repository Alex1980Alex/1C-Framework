"""Unit tests for ID generation (F2.6.4)."""

from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestIDGenerator:
    """Test deterministic ID generation."""

    def test_generate_id_same_input_same_output(self):
        """F2.6.4: Same inputs produce same ID."""
        from src.pdf_framework.utils.id_generator import generate_id

        id1 = generate_id("test.pdf", 1, 0)
        id2 = generate_id("test.pdf", 1, 0)

        assert id1 == id2

    def test_generate_id_different_inputs_different_outputs(self):
        """F2.6.4: Different inputs produce different IDs."""
        from src.pdf_framework.utils.id_generator import generate_id

        ids = [
            generate_id("test.pdf", i, 0)
            for i in range(10)
        ]

        assert len(set(ids)) == 10

    def test_generate_id_document_variation(self):
        """F2.6.4: Different documents produce different IDs."""
        from src.pdf_framework.utils.id_generator import generate_id

        id1 = generate_id("doc1.pdf", 1, 0)
        id2 = generate_id("doc2.pdf", 1, 0)

        assert id1 != id2

    def test_generate_id_page_variation(self):
        """F2.6.4: Different pages produce different IDs."""
        from src.pdf_framework.utils.id_generator import generate_id

        id1 = generate_id("doc.pdf", 1, 0)
        id2 = generate_id("doc.pdf", 2, 0)

        assert id1 != id2

    def test_generate_id_chunk_variation(self):
        """F2.6.4: Different chunks produce different IDs."""
        from src.pdf_framework.utils.id_generator import generate_id

        id1 = generate_id("doc.pdf", 1, 0)
        id2 = generate_id("doc.pdf", 1, 1)

        assert id1 != id2

    def test_generate_id_format_is_string(self):
        """F2.6.4: Generated ID should be a string."""
        from src.pdf_framework.utils.id_generator import generate_id

        id_value = generate_id("test.pdf", 1, 0)

        assert isinstance(id_value, str)
        assert len(id_value) > 0

    def test_generate_id_no_special_chars(self):
        """F2.6.4: ID should be safe for filenames/URLs."""
        from src.pdf_framework.utils.id_generator import generate_id

        id_value = generate_id("test file with spaces.pdf", 1, 0)

        # Should not contain spaces or special chars (except maybe hyphens, underscores)
        assert " " not in id_value
        assert "/" not in id_value
        assert "\\" not in id_value
