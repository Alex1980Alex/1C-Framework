"""Unit tests for HybridLoader cascade helpers (T.4 of 260430_AUDIT_TESTS_COVERAGE.md)."""

import pytest

from src.pdf_framework.loaders.providers.hybrid_loader import HybridLoader
from src.pdf_framework.loaders.table_extractor import TableInfo


@pytest.mark.unit
class TestIsVisionRefusal:
    def test_clean_text_returns_false(self):
        assert HybridLoader._is_vision_refusal("Some normal extracted text") is False

    def test_russian_не_могу_обработать(self):
        assert HybridLoader._is_vision_refusal("Извините, не могу обработать это.") is True

    def test_russian_не_могу_просмотреть(self):
        assert HybridLoader._is_vision_refusal("Я не могу просмотреть документ") is True
