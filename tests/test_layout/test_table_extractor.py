"""Tests for TableExtractor and TableData (Phase 10.3).

Tests table data model and extraction with mocked pdfplumber.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.pdf_framework.processing.table_extractor import TableData, TableExtractor


class TestTableData:
    """Test TableData model."""

    def test_basic_creation(self):
        td = TableData(
            headers=["A", "B"],
            rows=[["1", "2"], ["3", "4"]],
            page_number=1,
        )
        assert td.headers == ["A", "B"]
        assert len(td.rows) == 2
        assert td.caption is None
        assert td.bbox is None

    def test_with_caption_and_bbox(self):
        td = TableData(
            headers=["X"],
            rows=[["1"]],
            caption="Table 1: Results",
            page_number=5,
            bbox=(10.0, 20.0, 300.0, 400.0),
        )
        assert td.caption == "Table 1: Results"
        assert td.bbox == (10.0, 20.0, 300.0, 400.0)


class TestTableDataMarkdown:
    """Test Markdown conversion."""

    def test_basic_markdown(self):
        td = TableData(
            headers=["Name", "Age"],
            rows=[["Alice", "30"], ["Bob", "25"]],
            page_number=1,
        )
        md = td.to_markdown()
        assert "| Name | Age |" in md
        assert "| --- | --- |" in md
        assert "| Alice | 30 |" in md
        assert "| Bob | 25 |" in md

    def test_empty_table_returns_empty_string(self):
        td = TableData(headers=[], rows=[], page_number=1)
        assert td.to_markdown() == ""

    def test_empty_headers_returns_empty(self):
        td = TableData(headers=[], rows=[["1"]], page_number=1)
        assert td.to_markdown() == ""

    def test_empty_rows_returns_empty(self):
        td = TableData(headers=["A"], rows=[], page_number=1)
        assert td.to_markdown() == ""

    def test_short_row_padded(self):
        """Rows shorter than headers should be padded."""
        td = TableData(
            headers=["A", "B", "C"],
            rows=[["1"]],
            page_number=1,
        )
        md = td.to_markdown()
        # Row should be padded
        lines = md.strip().split("\n")
        data_row = lines[2]  # skip header and separator
        assert data_row.count("|") == 4  # | A | B | C |

    def test_long_row_truncated(self):
        """Rows longer than headers should be truncated."""
        td = TableData(
            headers=["A", "B"],
            rows=[["1", "2", "3", "4"]],
            page_number=1,
        )
        md = td.to_markdown()
        lines = md.strip().split("\n")
        data_row = lines[2]
        # Should only have 2 data columns + borders
        assert "3" not in data_row

    def test_single_column_table(self):
        td = TableData(
            headers=["Value"],
            rows=[["100"], ["200"]],
            page_number=1,
        )
        md = td.to_markdown()
        assert "| Value |" in md
        assert "| 100 |" in md


class TestTableDataJSON:
    """Test JSON conversion."""

    def test_to_json(self):
        td = TableData(
            headers=["A", "B"],
            rows=[["1", "2"]],
            caption="Test",
            page_number=3,
            bbox=(0.0, 0.0, 100.0, 50.0),
        )
        j = td.to_json()
        assert j["headers"] == ["A", "B"]
        assert j["rows"] == [["1", "2"]]
        assert j["caption"] == "Test"
        assert j["page_number"] == 3
        assert j["bbox"] == (0.0, 0.0, 100.0, 50.0)


class TestTableExtractorInit:
    """Test TableExtractor initialization."""

    def test_default_init(self):
        te = TableExtractor()
        assert te._min_rows == 2
        assert te._min_cols == 2
        assert te._handle_merged_cells is True

    def test_custom_init(self):
        te = TableExtractor(min_rows=3, min_cols=3, handle_merged_cells=False)
        assert te._min_rows == 3
        assert te._min_cols == 3
        assert te._handle_merged_cells is False


class TestTableValidation:
    """Test _is_valid_table method."""

    def test_valid_table(self):
        te = TableExtractor(min_rows=2, min_cols=2)
        table = [["A", "B"], ["1", "2"]]
        assert te._is_valid_table(table) is True

    def test_empty_table(self):
        te = TableExtractor()
        assert te._is_valid_table([]) is False
        assert te._is_valid_table(None) is False

    def test_too_few_rows(self):
        te = TableExtractor(min_rows=2)
        assert te._is_valid_table([["A", "B"]]) is False

    def test_too_few_cols(self):
        te = TableExtractor(min_cols=2)
        assert te._is_valid_table([["A"], ["B"]]) is False

    def test_exact_minimum(self):
        te = TableExtractor(min_rows=2, min_cols=2)
        table = [["A", "B"], ["1", "2"]]
        assert te._is_valid_table(table) is True


class TestTableConversion:
    """Test _convert_to_table_data method."""

    def test_basic_conversion(self):
        te = TableExtractor()
        raw = [["Name", "Age"], ["Alice", "30"], ["Bob", "25"]]
        td = te._convert_to_table_data(raw, page_number=1, table_index=0)

        assert td is not None
        assert td.headers == ["Name", "Age"]
        assert len(td.rows) == 2
        assert td.rows[0] == ["Alice", "30"]
        assert td.page_number == 1

    def test_none_cells_converted_to_empty_string(self):
        te = TableExtractor()
        raw = [["A", None], [None, "2"]]
        td = te._convert_to_table_data(raw, page_number=1, table_index=0)
        assert td.headers == ["A", ""]
        assert td.rows[0] == ["", "2"]

    def test_empty_table_returns_none(self):
        te = TableExtractor()
        assert te._convert_to_table_data([], page_number=1, table_index=0) is None
        assert te._convert_to_table_data(None, page_number=1, table_index=0) is None


class TestTableExtractFromPage:
    """Test extract_from_page with mocked pdfplumber."""

    def test_extract_valid_tables(self):
        te = TableExtractor()

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [["A", "B"], ["1", "2"], ["3", "4"]],
        ]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            tables = te.extract_from_page("test.pdf", page_number=1)

        assert len(tables) == 1
        assert tables[0].headers == ["A", "B"]

    def test_extract_invalid_page_number(self):
        te = TableExtractor()

        mock_pdf = MagicMock()
        mock_pdf.pages = []
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            tables = te.extract_from_page("test.pdf", page_number=99)
        assert tables == []

    def test_extract_filters_small_tables(self):
        te = TableExtractor(min_rows=3)

        mock_page = MagicMock()
        mock_page.extract_tables.return_value = [
            [["A", "B"], ["1", "2"]],  # Only 2 rows, below min_rows=3
        ]

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf):
            tables = te.extract_from_page("test.pdf", page_number=1)
        assert tables == []


class TestTablesToMarkdownChunks:
    """Test conversion to embedding-ready chunks."""

    def test_tables_to_chunks(self):
        te = TableExtractor()
        tables = [
            TableData(
                headers=["A", "B"],
                rows=[["1", "2"]],
                page_number=1,
            ),
            TableData(
                headers=["X"],
                rows=[["Y"]],
                page_number=2,
            ),
        ]
        chunks = te.tables_to_markdown_chunks(tables, document_id="doc1")
        assert len(chunks) == 2
        assert "| A | B |" in chunks[0]["content"]
        assert chunks[0]["metadata"]["element_type"] == "table"
        assert chunks[0]["metadata"]["document_id"] == "doc1"
        assert chunks[0]["metadata"]["page_number"] == 1
        assert "table_data" in chunks[0]["metadata"]
