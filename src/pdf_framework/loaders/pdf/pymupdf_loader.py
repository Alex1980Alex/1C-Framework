"""PDF loader using PyMuPDF (fitz) library.

Extracts text, metadata, and page-level information from PDF files.
"""

import asyncio
import logging
import time
from pathlib import Path

import fitz  # PyMuPDF

from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.schemas.documents import (
    DocumentMetadata,
    ProcessedDocument,
)
from src.pdf_framework.utils.id_generator import generate_document_id

logger = logging.getLogger(__name__)


class PyMuPDFLoader(BaseLoader):
    """Load PDF documents using PyMuPDF."""

    def _load_sync(self, source: str | Path) -> ProcessedDocument:
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Unsupported file type: {path.suffix}")

        t0 = time.time()
        doc = fitz.open(str(path))
        total_pages = len(doc)
        logger.info(
            "[LOADER] Opening '%s' (%d pages, %.1f MB)",
            path.name, total_pages, path.stat().st_size / 1048576,
        )

        try:
            pages_text: list[str] = []
            total_chars = 0
            for page_idx, page in enumerate(doc):
                page_text = page.get_text()
                pages_text.append(page_text)
                total_chars += len(page_text)

                # Log progress every 50 pages or on the last page
                if (page_idx + 1) % 50 == 0 or page_idx + 1 == total_pages:
                    logger.info(
                        "[LOADER] Страница %d/%d — %d символов (всего %d)",
                        page_idx + 1, total_pages, len(page_text), total_chars,
                    )

            # Build page_offsets: list of (char_offset, page_number)
            # so chunks can be mapped back to source pages after splitting
            page_offsets: list[tuple[int, int]] = []
            offset = 0
            for page_num, text in enumerate(pages_text, start=1):
                page_offsets.append((offset, page_num))
                offset += len(text) + 2  # +2 for "\n\n" separator

            raw_text = "\n\n".join(pages_text)
            pdf_meta = doc.metadata or {}
            file_size = path.stat().st_size

            metadata = DocumentMetadata(
                source=str(path.resolve()),
                title=pdf_meta.get("title", "") or path.stem,
                author=pdf_meta.get("author", ""),
                page_count=len(doc),
                file_size_bytes=file_size,
                extra={
                    "producer": pdf_meta.get("producer", ""),
                    "creator": pdf_meta.get("creator", ""),
                    "format": pdf_meta.get("format", ""),
                    "page_offsets": page_offsets,
                },
            )

            document_id = generate_document_id(str(path))
            elapsed = time.time() - t0
            logger.info(
                "[LOADER] Готово: '%s' — %d стр, %d символов за %.2f сек (%.0f стр/сек)",
                path.name, total_pages, len(raw_text), elapsed,
                total_pages / elapsed if elapsed > 0 else 0,
            )
            return ProcessedDocument(
                id=document_id,
                source_path=str(path),
                metadata=metadata,
                raw_text=raw_text,
            )
        finally:
            doc.close()

    async def load(self, source: str | Path) -> ProcessedDocument:
        """Load a single PDF document."""
        return await asyncio.to_thread(self._load_sync, source)

    async def load_batch(self, sources: list[str | Path]) -> list[ProcessedDocument]:
        """Load multiple PDF documents."""
        tasks = [self.load(s) for s in sources]
        return await asyncio.gather(*tasks)

    def supported_extensions(self) -> list[str]:
        return [".pdf"]
