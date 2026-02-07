"""Table extraction from PDF documents (Phase 10).

Extracts tables as structured data (Markdown for embedding, JSON for metadata).

Author: Claude Code
Version: 1.1.0 - Phase 10.3: Table Extraction
"""

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TableData(BaseModel):
    """Structured table data extracted from PDF."""

    headers: list[str] = Field(description="Column headers")
    rows: list[list[str]] = Field(description="Table rows (cell values)")
    caption: str | None = Field(default=None, description="Table caption if available")
    page_number: int = Field(description="Page number where table was found")
    bbox: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Bounding box of table on page"
    )

    def to_markdown(self) -> str:
        """
        Convert table to Markdown format.

        Returns:
            Markdown table string
        """
        if not self.headers or not self.rows:
            return ""

        lines = []

        # Header row
        header = "| " + " | ".join(self.headers) + " |"
        lines.append(header)

        # Separator
        separator = "| " + " | ".join(["---"] * len(self.headers)) + " |"
        lines.append(separator)

        # Data rows
        for row in self.rows:
            # Ensure row has same number of columns as headers
            while len(row) < len(self.headers):
                row.append("")
            row_text = "| " + " | ".join(row[:len(self.headers)]) + " |"
            lines.append(row_text)

        return "\n".join(lines)

    def to_json(self) -> dict:
        """
        Convert table to JSON-serializable dict.

        Returns:
            Dictionary with table data
        """
        return {
            "headers": self.headers,
            "rows": self.rows,
            "caption": self.caption,
            "page_number": self.page_number,
            "bbox": self.bbox,
        }


class TableExtractor:
    """
    Extracts tables from PDF documents using pdfplumber.

    Provides both Markdown (for embeddings) and JSON (for metadata)
    representations of extracted tables.
    """

    def __init__(
        self,
        min_rows: int = 2,
        min_cols: int = 2,
        handle_merged_cells: bool = True,
    ):
        """
        Initialize table extractor.

        Args:
            min_rows: Minimum rows to consider as valid table
            min_cols: Minimum columns to consider as valid table
            handle_merged_cells: Whether to attempt merged cell handling
        """
        self._min_rows = min_rows
        self._min_cols = min_cols
        self._handle_merged_cells = handle_merged_cells

        # Check if pdfplumber is available
        self._pdfplumber_available = self._check_pdfplumber()

        if not self._pdfplumber_available:
            logger.warning("[TABLE] pdfplumber not available")

    @staticmethod
    def _check_pdfplumber() -> bool:
        """Check if pdfplumber library is available."""
        try:
            import pdfplumber  # noqa: F401
            return True
        except ImportError:
            return False

    def extract_from_page(
        self,
        pdf_path: str | Path,
        page_number: int,
    ) -> list[TableData]:
        """
        Extract all tables from a specific page.

        Args:
            pdf_path: Path to PDF file
            page_number: Page number (1-based)

        Returns:
            List of TableData objects
        """
        if not self._pdfplumber_available:
            return []

        import pdfplumber

        tables = []

        with pdfplumber.open(str(pdf_path)) as pdf:
            if page_number < 1 or page_number > len(pdf.pages):
                logger.warning(f"[TABLE] Invalid page number: {page_number}")
                return []

            page = pdf.pages[page_number - 1]

            # Extract tables
            extracted_tables = page.extract_tables()

            for i, table in enumerate(extracted_tables):
                if self._is_valid_table(table):
                    table_data = self._convert_to_table_data(
                        table,
                        page_number,
                        table_index=i,
                    )
                    if table_data:
                        tables.append(table_data)

        logger.info(f"[TABLE] Extracted {len(tables)} tables from page {page_number}")

        return tables

    def extract_all(
        self,
        pdf_path: str | Path,
    ) -> list[TableData]:
        """
        Extract all tables from entire PDF document.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of all TableData objects
        """
        if not self._pdfplumber_available:
            return []

        import pdfplumber

        all_tables = []

        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                extracted_tables = page.extract_tables()

                for i, table in enumerate(extracted_tables):
                    if self._is_valid_table(table):
                        table_data = self._convert_to_table_data(
                            table,
                            page_num,
                            table_index=i,
                        )
                        if table_data:
                            all_tables.append(table_data)

        logger.info(f"[TABLE] Extracted {len(all_tables)} total tables from PDF")

        return all_tables

    def _is_valid_table(self, table: list[list[Any]]) -> bool:
        """
        Check if extracted table meets minimum criteria.

        Args:
            table: Raw table data from pdfplumber

        Returns:
            True if table is valid
        """
        if not table:
            return False

        rows = len(table)
        if rows < self._min_rows:
            return False

        # Check column count
        cols = max(len(row) for row in table) if table else 0
        if cols < self._min_cols:
            return False

        return True

    def _convert_to_table_data(
        self,
        table: list[list[Any]],
        page_number: int,
        table_index: int,
    ) -> TableData | None:
        """
        Convert raw pdfplumber table to TableData.

        Args:
            table: Raw table data
            page_number: Page number
            table_index: Table index on page

        Returns:
            TableData object or None
        """
        if not table:
            return None

        # First row as headers
        headers = []
        if table[0]:
            headers = [str(cell or "") for cell in table[0]]

        # Remaining rows as data
        rows = []
        for row in table[1:]:
            row_str = [str(cell or "") for cell in row]
            rows.append(row_str)

        return TableData(
            headers=headers,
            rows=rows,
            page_number=page_number,
            bbox=None,  # pdfplumber doesn't provide bbox easily
        )

    def tables_to_markdown_chunks(
        self,
        tables: list[TableData],
        document_id: str = "unknown",
    ) -> list[dict]:
        """
        Convert tables to chunks ready for embedding.

        Args:
            tables: List of TableData objects
            document_id: Document identifier

        Returns:
            List of chunk dicts with content and metadata
        """
        chunks = []

        for table in tables:
            markdown = table.to_markdown()

            chunks.append({
                "content": markdown,
                "metadata": {
                    "element_type": "table",
                    "page_number": table.page_number,
                    "table_data": table.to_json(),
                    "chunk_type": "table",
                    "document_id": document_id,
                },
            })

        return chunks

    def extract_with_bbox(
        self,
        pdf_path: str | Path,
        page_number: int,
        bbox: tuple[float, float, float, float],
    ) -> TableData | None:
        """
        Extract table from specific bounding box area.

        Args:
            pdf_path: Path to PDF file
            page_number: Page number (1-based)
            bbox: Bounding box (x0, y0, x1, y1)

        Returns:
            TableData object or None
        """
        if not self._pdfplumber_available:
            return None

        import pdfplumber

        with pdfplumber.open(str(pdf_path)) as pdf:
            if page_number < 1 or page_number > len(pdf.pages):
                return None

            page = pdf.pages[page_number - 1]

            # Crop to bbox
            cropped = page.crop(bbox)

            # Extract table from cropped area
            tables = cropped.extract_tables()

            if tables and self._is_valid_table(tables[0]):
                return self._convert_to_table_data(
                    tables[0],
                    page_number,
                    table_index=0,
                )

        return None
