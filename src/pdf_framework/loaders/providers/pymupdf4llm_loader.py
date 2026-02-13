"""PyMuPDF4LLM loader — fast PDF→Markdown for native (non-scanned) PDFs.

Extremely fast (<0.1 sec/page), no ML models required.
Best for digital PDFs with embedded text.

Phase 28: Added page_chunks=True for per-page extraction with page_offsets.

Author: Claude Code
Version: 0.2.0 - Phase 28: page_offsets support
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF — for metadata extraction

from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument
from src.pdf_framework.utils.id_generator import generate_document_id

logger = logging.getLogger(__name__)


class PyMuPDF4LLMLoader(BaseLoader):
    """Fast PDF→Markdown loader using pymupdf4llm."""

    def _load_sync(self, source: str | Path) -> ProcessedDocument:
        """Synchronous loading with per-page extraction."""
        import pymupdf4llm

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Unsupported file type: {path.suffix}")

        logger.info("[PYMUPDF4LLM] Loading: %s", path.name)

        # Extract markdown per page (page_chunks=True)
        page_chunks: list[dict[str, Any]] = pymupdf4llm.to_markdown(
            str(path), page_chunks=True,
        )  # type: ignore[assignment]  # page_chunks=True returns list[dict]

        # Build page_offsets and raw_text
        page_texts: list[str] = []
        page_offsets: list[tuple[int, int]] = []
        offset = 0
        for chunk in page_chunks:
            meta: Any = chunk["metadata"]
            page_num = int(meta["page"])  # already 1-based
            text: str = chunk.get("text", "") or ""
            page_texts.append(text)
            page_offsets.append((offset, page_num))
            offset += len(text) + 2  # +2 for "\n\n" separator

        raw_text = "\n\n".join(page_texts)

        # Metadata via PyMuPDF
        doc = fitz.open(str(path))
        try:
            pdf_meta = doc.metadata or {}
            page_count = len(doc)
        finally:
            doc.close()

        file_size = path.stat().st_size

        metadata = DocumentMetadata(
            source=str(path.resolve()),
            title=pdf_meta.get("title", "") or path.stem,
            author=pdf_meta.get("author", ""),
            page_count=page_count,
            file_size_bytes=file_size,
            extra={
                "layout_detection_method": "pymupdf4llm",
                "producer": pdf_meta.get("producer", ""),
                "page_offsets": page_offsets,
            },
        )

        document_id = generate_document_id(str(path))

        logger.info(
            "[PYMUPDF4LLM] Done: %s — %d pages, %d chars, %d page_offsets",
            path.name, page_count, len(raw_text), len(page_offsets),
        )

        return ProcessedDocument(
            id=document_id,
            source_path=str(path),
            metadata=metadata,
            raw_text=raw_text,
        )

    async def load(self, source: str | Path) -> ProcessedDocument:
        return await asyncio.to_thread(self._load_sync, source)

    async def load_batch(self, sources: list[str | Path]) -> list[ProcessedDocument]:
        tasks = [self.load(s) for s in sources]
        return await asyncio.gather(*tasks)

    def supported_extensions(self) -> list[str]:
        return [".pdf"]
