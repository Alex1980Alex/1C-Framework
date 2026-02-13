"""Smart table extraction with deduplication.

Phase 28: Extracts tables from PDF pages using PyMuPDF find_tables(),
with content-based deduplication to avoid inserting tables already
present in the PyMuPDF4LLM text output.
"""

import logging
import re
from pathlib import Path
from typing import Literal

import fitz
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TableInfo(BaseModel):
    """Extracted table metadata and content."""

    page_number: int  # 1-based
    markdown: str
    source: Literal["fitz", "docling", "vision"] = "fitz"
    rows: int = 0
    cols: int = 0
    headers: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump()


class SmartTableExtractor:
    """Extract tables from PDF using PyMuPDF find_tables() with dedup."""

    def __init__(self, dedup_threshold: float = 0.6):
        self._dedup_threshold = dedup_threshold

    def extract_fitz_tables(
        self,
        pdf_path: Path,
        page_texts: dict[int, str],
        dedup: bool = True,
    ) -> list[TableInfo]:
        """Extract tables using PyMuPDF find_tables() per page.

        Args:
            pdf_path: Path to PDF file.
            page_texts: Dict of {page_number(1-based): page_text} for dedup.
            dedup: If True, skip tables whose content already appears in page text.

        Returns:
            List of TableInfo for newly-found tables.
        """
        result: list[TableInfo] = []
        doc = fitz.open(str(pdf_path))

        try:
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                page_num = page_idx + 1  # 1-based

                try:
                    finder = page.find_tables()  # type: ignore[attr-defined]  # PyMuPDF 1.23+
                except Exception as e:
                    logger.debug("[TABLE] find_tables() failed on page %d: %s", page_num, e)
                    continue

                for tab in finder.tables:
                    md = self._table_to_markdown(tab)
                    if not md or len(md) < 10:
                        continue

                    rows = len(tab.extract())
                    cols = len(tab.extract()[0]) if rows > 0 else 0

                    # Dedup: skip if table content already in PyMuPDF4LLM text
                    if dedup and self._is_in_text(md, page_texts.get(page_num, "")):
                        logger.debug(
                            "[TABLE] Skipping duplicate table on page %d (%d rows)",
                            page_num, rows,
                        )
                        continue

                    headers = []
                    if tab.header and tab.header.cells:
                        raw = tab.extract()
                        if raw:
                            headers = [str(c) if c else "" for c in raw[0]]

                    result.append(TableInfo(
                        page_number=page_num,
                        markdown=md,
                        source="fitz",
                        rows=rows,
                        cols=cols,
                        headers=headers,
                    ))

            logger.info(
                "[TABLE] fitz extracted %d new tables from %d pages",
                len(result), len(doc),
            )
        finally:
            doc.close()

        return result

    @staticmethod
    def _table_to_markdown(table) -> str:
        """Convert fitz table to markdown format."""
        try:
            data = table.extract()
        except Exception:
            return ""

        if not data or not data[0]:
            return ""

        lines: list[str] = []
        # Header row
        header = [str(c).strip() if c else "" for c in data[0]]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join("---" for _ in header) + " |")

        # Data rows
        for row in data[1:]:
            cells = [str(c).strip() if c else "" for c in row]
            # Pad if fewer cells than header
            while len(cells) < len(header):
                cells.append("")
            lines.append("| " + " | ".join(cells[:len(header)]) + " |")

        return "\n".join(lines)

    def _is_in_text(self, table_md: str, page_text: str) -> bool:
        """Check if table content already exists in page text.

        Extracts cell values from table markdown and checks
        what fraction appears in the page text.
        """
        if not page_text:
            return False

        # Extract meaningful cell values from markdown
        cells = re.findall(r"\|([^|]+)", table_md)
        words: list[str] = []
        for cell in cells:
            cell_text = cell.strip()
            if cell_text and cell_text != "---" and len(cell_text) > 1:
                words.extend(cell_text.split())

        if not words:
            return False

        # Check how many words appear in page text
        normalized_page = " ".join(page_text.split()).lower()
        matches = sum(1 for w in words if w.lower() in normalized_page)
        ratio = matches / len(words)

        return ratio >= self._dedup_threshold
