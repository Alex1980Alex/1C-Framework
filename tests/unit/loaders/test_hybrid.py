"""Unit tests for HybridLoader (F2.5).

Tests:
- F2.5.1: HybridLoader level selection
- F2.5.2: page_offsets correctness
- F2.5.3: coverage verification
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestHybridLoader:
    """Test HybridLoader level selection and page offsets."""

    def test_level_selection_basic(self):
        """F2.5.1: HybridLoader should select appropriate loader level."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # Level 0: Basic loader
        assert loader._select_level(needs_ocr=False, has_tables=False) == 0

        # Level 1: Tables only
        assert loader._select_level(needs_ocr=False, has_tables=True) == 1

        # Level 2: OCR only
        assert loader._select_level(needs_ocr=True, has_tables=False) == 2

        # Level 3: OCR + Tables
        assert loader._select_level(needs_ocr=True, has_tables=True) == 3

    def test_page_offsets_calculation(self):
        """F2.5.2: page_offsets should be correctly calculated."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # Simulate chunks with page numbers
        chunks = [
            MagicMock(page_number=1, chunk_index=0),
            MagicMock(page_number=1, chunk_index=1),
            MagicMock(page_number=2, chunk_index=2),
            MagicMock(page_number=3, chunk_index=3),
        ]

        offsets = loader._calculate_page_offsets(chunks)

        assert offsets == {1: 0, 2: 2, 3: 3}

    def test_page_offsets_empty(self):
        """F2.5.2: Empty chunks should return empty offsets."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()
        offsets = loader._calculate_page_offsets([])

        assert offsets == {}

    def test_coverage_verification_full(self):
        """F2.5.3: Coverage should be 100% for complete document."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # 3 pages, all covered
        chunks = [
            MagicMock(page_number=1, content="page1"),
            MagicMock(page_number=2, content="page2"),
            MagicMock(page_number=3, content="page3"),
        ]

        coverage = loader._verify_coverage(chunks, total_pages=3)

        assert coverage == 1.0

    def test_coverage_verification_partial(self):
        """F2.5.3: Partial coverage should be calculated correctly."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # 3 pages, only 2 covered
        chunks = [
            MagicMock(page_number=1, content="page1"),
            MagicMock(page_number=3, content="page3"),
        ]

        coverage = loader._verify_coverage(chunks, total_pages=3)

        assert coverage == 2/3

    def test_coverage_threshold_warning(self):
        """F2.5.3: Coverage below threshold should warn."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader(min_coverage=0.8)

        # Only 50% coverage
        chunks = [
            MagicMock(page_number=1, content="page1"),
            MagicMock(page_number=2, content="page2"),
        ]

        with pytest.warns(UserWarning, match="Coverage below threshold"):
            loader._verify_coverage(chunks, total_pages=4)


@pytest.mark.unit
class TestLoaderFallback:
    """Test loader fallback mechanism."""

    def test_fallback_to_basic_on_error(self):
        """HybridLoader should fallback to basic loader on error."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        # Mock primary loader to fail
        loader._level1_loader = AsyncMock(side_effect=Exception("Loader failed"))

        # Should use fallback
        assert loader._get_fallback_loader() is not None

    def test_loader_priority(self):
        """Loader priority should be: level3 > level2 > level1 > level0."""
        from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader

        loader = HybridLoader()

        priorities = [
            ("level3", 3),
            ("level2", 2),
            ("level1", 1),
            ("level0", 0),
        ]

        for level_name, expected_priority in priorities:
            loader._loaders[level_name] = MagicMock(priority=expected_priority)

        # Verify priority order
        assert loader._get_highest_priority_loader() == "level3"
