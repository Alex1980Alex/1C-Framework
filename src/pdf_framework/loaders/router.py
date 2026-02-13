"""Smart Loader Router — auto-selects best loader based on PDF characteristics.

Classification logic:
  - Native simple PDF → PyMuPDF4LLM (fast, <0.1 sec/page)
  - Native complex PDF (tables, columns) → Docling (full pipeline)
  - Scanned PDF (no text) → Docling with OCR

Author: Claude Code
Version: 0.1.0 - Phase 15.1: Smart Router
"""

import logging
from pathlib import Path

import fitz  # PyMuPDF for PDF classification

from src.pdf_framework.config import DoclingSettings, SmartRouterSettings
from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.schemas.documents import ProcessedDocument

logger = logging.getLogger(__name__)


class SmartLoaderRouter(BaseLoader):
    """Auto-selects the best loader based on PDF characteristics."""

    def __init__(
        self,
        settings: SmartRouterSettings | None = None,
        docling_settings: DoclingSettings | None = None,
    ):
        self._settings = settings or SmartRouterSettings()
        self._docling_settings = docling_settings
        self._fast_loader = None
        self._full_loader = None

    def _get_fast_loader(self) -> BaseLoader:
        if self._fast_loader is None:
            if self._settings.fast_loader == "pymupdf4llm":
                from src.pdf_framework.loaders.providers.pymupdf4llm_loader import (
                    PyMuPDF4LLMLoader,
                )
                self._fast_loader = PyMuPDF4LLMLoader()
            else:
                from src.pdf_framework.loaders.pdf.pymupdf_loader import PyMuPDFLoader
                self._fast_loader = PyMuPDFLoader()
        return self._fast_loader

    def _get_full_loader(self, *, force_ocr: bool | None = None) -> BaseLoader:
        """Get the full (heavy) loader.

        Args:
            force_ocr: If provided, override OCR setting.  None = use cached
                       loader, True/False = create new loader with that setting.
        """
        need_new = self._full_loader is None or force_ocr is not None
        if need_new:
            if self._settings.full_loader == "docling":
                from src.pdf_framework.loaders.providers.docling_loader import (
                    DoclingLoader,
                )
                ds = self._docling_settings or DoclingSettings()
                if force_ocr is not None:
                    ds = ds.model_copy(update={"ocr_enabled": force_ocr})
                self._full_loader = DoclingLoader(settings=ds)
            else:
                from src.pdf_framework.loaders.providers.layout_parser import (
                    LayoutAwareLoader,
                )
                self._full_loader = LayoutAwareLoader()
        return self._full_loader

    def _classify_pdf(self, path: Path) -> str:
        """Classify PDF type by analyzing its content.

        Returns:
            "native_simple" — digital PDF, simple layout
            "native_complex" — digital PDF, complex layout (tables, columns)
            "scanned" — image-based PDF, needs OCR
        """
        try:
            doc = fitz.open(str(path))
        except Exception as e:
            logger.warning(f"[ROUTER] Cannot open PDF for classification: {e}")
            return "native_complex"  # Fallback to full loader

        try:
            total_pages = len(doc)
            if total_pages == 0:
                return "native_simple"

            pages_with_text = 0
            pages_with_tables = 0
            pages_with_images = 0

            # Check up to 10 pages for fast classification
            sample_pages = min(total_pages, 10)

            for i in range(sample_pages):
                page = doc[i]
                text = page.get_text().strip()

                # Is there text?
                if len(text) > self._settings.min_text_chars_per_page:
                    pages_with_text += 1

                # Are there tables? (heuristic: many horizontal/vertical lines)
                drawings = page.get_drawings()
                if len(drawings) > 10:
                    pages_with_tables += 1

                # Are there images?
                images = page.get_images()
                if images:
                    pages_with_images += 1

            text_ratio = pages_with_text / sample_pages
            table_ratio = pages_with_tables / sample_pages
            image_ratio = pages_with_images / sample_pages

            # Decision
            if text_ratio < 0.5:
                pdf_type = "scanned"
            elif table_ratio > self._settings.table_heavy_threshold:
                pdf_type = "native_complex"
            elif image_ratio > 0.5:
                pdf_type = "native_complex"
            else:
                pdf_type = "native_simple"

            logger.info(
                f"[ROUTER] {path.name}: type={pdf_type} "
                f"(text={text_ratio:.0%}, tables={table_ratio:.0%}, images={image_ratio:.0%})"
            )
            return pdf_type

        except Exception as e:
            logger.warning(f"[ROUTER] Classification error: {e}")
            return "native_complex"
        finally:
            doc.close()

    async def load(self, source: str | Path) -> ProcessedDocument:
        """Load document with auto-selected best loader."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # For non-PDF files always use full loader
        if path.suffix.lower() != ".pdf":
            loader = self._get_full_loader()
            return await loader.load(source)

        pdf_type = self._classify_pdf(path)

        if pdf_type == "native_simple":
            loader = self._get_fast_loader()
            logger.info(f"[ROUTER] → Fast path ({self._settings.fast_loader})")
            return await loader.load(source)

        # For native_complex: use Docling but disable OCR (not needed)
        # For scanned: use Docling with OCR enabled
        need_ocr = pdf_type == "scanned"
        loader = self._get_full_loader(force_ocr=need_ocr)
        ocr_label = "OCR=on" if need_ocr else "OCR=off"
        logger.info(
            f"[ROUTER] → Full path ({self._settings.full_loader}, {ocr_label})"
        )
        try:
            return await loader.load(source)
        except Exception as e:
            logger.warning(
                f"[ROUTER] Full loader failed for {path.name}: {e}. "
                f"Falling back to {self._settings.fast_loader}"
            )
            return await self._get_fast_loader().load(source)

    async def load_batch(self, sources: list[str | Path]) -> list[ProcessedDocument]:
        """Load multiple documents (each routed individually)."""
        import asyncio
        tasks = [self.load(s) for s in sources]
        return await asyncio.gather(*tasks)

    def supported_extensions(self) -> list[str]:
        return [".pdf", ".docx", ".pptx", ".xlsx", ".html"]
