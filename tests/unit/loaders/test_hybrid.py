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

    def test_english_i_cannot_case_insensitive(self):
        assert HybridLoader._is_vision_refusal("I Cannot help with this image") is True

    def test_english_cannot_transcribe(self):
        assert HybridLoader._is_vision_refusal("Cannot transcribe page contents") is True

    def test_empty_string_returns_false(self):
        assert HybridLoader._is_vision_refusal("") is False


@pytest.mark.unit
class TestIsValidTable:
    def test_valid_md_table(self):
        md = "| col_a | col_b |\n| --- | --- |\n| 1 | 2 |"
        assert HybridLoader._is_valid_table(md) is True

    def test_no_pipe_returns_false(self):
        assert HybridLoader._is_valid_table("plain text without table marks ---") is False

    def test_no_separator_returns_false(self):
        assert HybridLoader._is_valid_table("| a | b |\n| 1 | 2 |") is False

    def test_too_short_returns_false(self):
        assert HybridLoader._is_valid_table("|abc") is False

    def test_empty_string_returns_false(self):
        assert HybridLoader._is_valid_table("") is False


@pytest.mark.unit
class TestMergeTables:
    def test_single_page_single_table(self):
        tables = [TableInfo(page_number=1, markdown="| a |\n| --- |\n| 1 |")]
        raw, offsets = HybridLoader._merge_tables(["page one"], [1], tables)
        assert "page one" in raw and "| a |" in raw
        assert offsets == [(0, 1)]

    def test_table_on_missing_page_silently_skipped(self):
        tables = [TableInfo(page_number=5, markdown="| x |\n| --- |\n| 9 |")]
        raw, offsets = HybridLoader._merge_tables(["only"], [1], tables)
        assert raw == "only"
        assert offsets == [(0, 1)]

    def test_multiple_tables_on_same_page_joined(self):
        t1 = TableInfo(page_number=2, markdown="| a |\n| --- |\n| 1 |")
        t2 = TableInfo(page_number=2, markdown="| b |\n| --- |\n| 2 |")
        raw, offsets = HybridLoader._merge_tables(["A", "B"], [1, 2], [t1, t2])
        page2_block = raw.split("\n\n", 1)[1]
        assert "| a |" in page2_block and "| b |" in page2_block
        assert offsets[0] == (0, 1)
        assert offsets[1][0] > 0 and offsets[1][1] == 2


@pytest.mark.unit
class TestSplitByOffsets:
    def test_round_trip_three_pages(self):
        raw = "alpha\n\nbeta\n\ngamma"
        offsets = [(0, 1), (7, 2), (13, 3)]
        pages, nums = HybridLoader._split_by_offsets(raw, offsets)
        assert pages == ["alpha", "beta", "gamma"]
        assert nums == [1, 2, 3]

    def test_single_page(self):
        pages, nums = HybridLoader._split_by_offsets("solo", [(0, 1)])
        assert pages == ["solo"] and nums == [1]

    def test_empty_offsets(self):
        pages, nums = HybridLoader._split_by_offsets("", [])
        assert pages == [] and nums == []
