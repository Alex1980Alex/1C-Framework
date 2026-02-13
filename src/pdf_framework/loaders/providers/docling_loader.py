"""Docling PDF loader — layout-aware parsing with OCR and table extraction.

Uses IBM Docling for advanced document understanding:
- Layout detection (DocLayNet model)
- Table structure recognition (TableFormer, 97.9% accuracy)
- OCR for scanned documents (EasyOCR/Tesseract)
- Multi-format support (PDF, DOCX, PPTX, XLSX)

Author: Claude Code
Version: 0.1.0 - Phase 15.1: Docling Integration
"""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pdf_framework.config import DoclingSettings
from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument
from src.pdf_framework.utils.id_generator import generate_document_id

logger = logging.getLogger(__name__)


class DoclingLoader(BaseLoader):
    """Load documents using IBM Docling with layout detection and OCR."""

    def __init__(self, settings: DoclingSettings | None = None):
        self._settings = settings or DoclingSettings()
        self._converter = None  # Lazy init

    def _get_converter(self):
        """Lazy-initialize Docling converter (heavy import)."""
        if self._converter is not None:
            return self._converter

        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            TableFormerMode,
            TableStructureOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        pipeline_options = PdfPipelineOptions()

        # OCR
        pipeline_options.do_ocr = self._settings.ocr_enabled
        if self._settings.ocr_enabled:
            pipeline_options.ocr_options = self._create_ocr_options()
        pipeline_options.ocr_batch_size = self._settings.ocr_batch_size

        # Tables
        pipeline_options.do_table_structure = self._settings.table_structure_enabled
        if self._settings.table_structure_enabled:
            mode = (
                TableFormerMode.ACCURATE
                if self._settings.table_mode == "accurate"
                else TableFormerMode.FAST
            )
            pipeline_options.table_structure_options = TableStructureOptions(
                mode=mode,
                do_cell_matching=True,
            )
        pipeline_options.table_batch_size = self._settings.table_batch_size

        # Images
        pipeline_options.generate_picture_images = self._settings.generate_picture_images

        # Performance
        pipeline_options.layout_batch_size = self._settings.layout_batch_size
        pipeline_options.document_timeout = self._settings.document_timeout

        # Select PDF backend: docling_parse (fast) or pypdfium2 (fallback)
        backend = self._select_pdf_backend()
        format_opts = PdfFormatOption(pipeline_options=pipeline_options)
        if backend is not None:
            format_opts = PdfFormatOption(
                pipeline_options=pipeline_options,
                backend=backend,
            )

        self._converter = DocumentConverter(
            format_options={InputFormat.PDF: format_opts}
        )

        backend_name = backend.__name__ if backend else "docling_parse"
        logger.info(
            f"[DOCLING] Initialized: backend={backend_name}, "
            f"ocr={self._settings.ocr_engine}, "
            f"table_mode={self._settings.table_mode}, "
            f"languages={self._settings.ocr_languages}"
        )
        return self._converter

    @staticmethod
    def _select_pdf_backend():
        """Select PDF backend, falling back to pypdfium2 if docling_parse fails.

        docling_parse (C++ backend) crashes on Windows when the venv path
        contains non-ASCII characters (e.g. Cyrillic). Detect this and
        fall back to pypdfium2 automatically.
        """
        try:
            from docling_parse.pdf_parser import pdf_parser_v2
            pdf_parser_v2(level="fatal")
            return None  # Use default docling_parse backend
        except (RuntimeError, OSError, ImportError) as e:
            logger.warning(
                f"[DOCLING] docling_parse unavailable ({e}), "
                "falling back to pypdfium2 backend"
            )
            from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
            return PyPdfiumDocumentBackend

    def _create_ocr_options(self):
        """Create OCR options based on configured engine."""
        engine = self._settings.ocr_engine
        langs = self._settings.ocr_languages
        force_full = self._settings.force_full_page_ocr

        if engine == "easyocr":
            from docling.datamodel.pipeline_options import EasyOcrOptions

            return EasyOcrOptions(
                lang=langs,
                use_gpu=False,
                force_full_page_ocr=force_full,
                download_enabled=True,
            )
        elif engine == "tesseract":
            from docling.datamodel.pipeline_options import TesseractCliOcrOptions

            # Tesseract uses code "rus" for Russian
            tess_lang = "+".join(
                "rus" if l == "ru" else l for l in langs
            )
            return TesseractCliOcrOptions(
                lang=tess_lang,
                force_full_page_ocr=force_full,
            )
        else:
            from docling.datamodel.pipeline_options import RapidOcrOptions

            return RapidOcrOptions(
                force_full_page_ocr=force_full,
            )

    def _export_with_page_offsets(
        self, doc: Any,
    ) -> tuple[str, list[tuple[int, int]]]:
        """Export markdown page-by-page, building page_offsets for chunk mapping.

        Returns (raw_text, page_offsets) where page_offsets is
        a list of (char_offset, page_number) for binary search.
        """
        page_offsets: list[tuple[int, int]] = []
        sorted_pages = sorted(doc.pages.keys()) if hasattr(doc, "pages") else []

        if not sorted_pages:
            try:
                raw_text = doc.export_to_markdown()
            except TypeError:
                raw_text = self._fallback_text(doc)
            return raw_text, []

        # Try per-page markdown export
        page_markdowns: list[str] = []
        try:
            for page_no in sorted_pages:
                page_md = doc.export_to_markdown(page_no=page_no)
                page_markdowns.append(page_md)
        except TypeError:
            # Older docling without page_no parameter — use item-based fallback
            logger.info("[DOCLING] Per-page export unavailable, using item fallback")
            return self._fallback_page_offsets(doc, sorted_pages)

        # Build page_offsets (same pattern as PyMuPDFLoader)
        offset = 0
        for page_no, md in zip(sorted_pages, page_markdowns):
            page_offsets.append((offset, page_no))
            offset += len(md) + 2  # +2 for "\n\n" separator

        raw_text = "\n\n".join(page_markdowns)
        logger.info(
            "[DOCLING] Page offsets: %d pages, %d chars",
            len(page_offsets), len(raw_text),
        )
        return raw_text, page_offsets

    @staticmethod
    def _fallback_text(doc: Any) -> str:
        """Fallback text extraction when export_to_markdown fails."""
        parts = []
        for item, _ in doc.iterate_items():
            if hasattr(item, "text") and item.text:
                parts.append(item.text)
        return "\n\n".join(parts)

    @staticmethod
    def _fallback_page_offsets(
        doc: Any, sorted_pages: list[int],
    ) -> tuple[str, list[tuple[int, int]]]:
        """Build page_offsets from item provenance when per-page export unavailable."""
        page_texts: dict[int, list[str]] = {p: [] for p in sorted_pages}
        page_texts[0] = []  # items without page info

        for item, _ in doc.iterate_items():
            text = ""
            if hasattr(item, "text") and item.text:
                text = item.text
            elif hasattr(item, "export_to_markdown"):
                try:
                    text = item.export_to_markdown()
                except TypeError:
                    continue
            if not text.strip():
                continue

            page_no = 0
            if hasattr(item, "prov") and item.prov:
                page_no = getattr(item.prov[0], "page_no", 0)
            page_texts.setdefault(page_no, []).append(text)

        # Concatenate per page and build offsets
        page_offsets: list[tuple[int, int]] = []
        parts: list[str] = []
        offset = 0
        for page_no in sorted_pages:
            page_content = "\n\n".join(page_texts.get(page_no, []))
            if not page_content and page_no not in page_texts:
                continue
            page_offsets.append((offset, page_no))
            parts.append(page_content)
            offset += len(page_content) + 2

        # Prepend items without page info
        if page_texts.get(0):
            unassigned = "\n\n".join(page_texts[0])
            parts.insert(0, unassigned)
            # Shift all offsets
            shift = len(unassigned) + 2
            page_offsets = [(o + shift, p) for o, p in page_offsets]

        raw_text = "\n\n".join(parts)
        logger.info(
            "[DOCLING] Page offsets (fallback): %d pages, %d chars",
            len(page_offsets), len(raw_text),
        )
        return raw_text, page_offsets

    def _load_sync(self, source: str | Path) -> ProcessedDocument:
        """Synchronous document loading via Docling."""
        from docling.datamodel.base_models import ConversionStatus

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        converter = self._get_converter()

        logger.info(f"[DOCLING] Loading: {path.name}")
        result = converter.convert(str(path), raises_on_error=False)

        if result.status == ConversionStatus.FAILURE:
            raise RuntimeError(
                f"Docling failed to convert {path.name}: "
                + "; ".join(str(e) for e in (result.errors or []))
            )

        if result.status == ConversionStatus.PARTIAL_SUCCESS:
            for err in result.errors or []:
                logger.warning(f"[DOCLING] Partial error: {err}")

        doc = result.document

        # Extract text with page offset mapping
        raw_text, page_offsets = self._export_with_page_offsets(doc)

        # Extract layout elements
        layout_elements = self._extract_layout_elements(doc)

        # Extract tables separately
        tables_info = self._extract_tables_info(doc)

        # Metadata
        page_count = len(doc.pages) if hasattr(doc, "pages") else 0
        file_size = path.stat().st_size

        metadata = DocumentMetadata(
            source=str(path.resolve()),
            title=getattr(doc, "name", "") or path.stem,
            page_count=page_count,
            file_size_bytes=file_size,
            extra={
                "layout_elements": layout_elements,
                "layout_detection_method": "docling",
                "tables": tables_info,
                "element_counts": self._count_elements(layout_elements),
                "loaded_at": datetime.now(timezone.utc).isoformat(),
                "page_offsets": page_offsets,
            },
        )

        document_id = generate_document_id(str(path))

        logger.info(
            f"[DOCLING] Done: {path.name} — "
            f"{page_count} pages, "
            f"{len(layout_elements)} elements, "
            f"{len(tables_info)} tables, "
            f"{len(page_offsets)} page offsets"
        )

        return ProcessedDocument(
            id=document_id,
            source_path=str(path),
            metadata=metadata,
            raw_text=raw_text,
        )

    def _extract_layout_elements(self, doc: Any) -> list[dict]:
        """Convert Docling document structure to framework layout elements."""
        elements = []

        type_mapping = {
            "title": "title",
            "section_header": "section_header",
            "text": "paragraph",
            "paragraph": "paragraph",
            "table": "table",
            "picture": "image",
            "list_item": "list",
            "caption": "paragraph",
            "code": "paragraph",
            "formula": "paragraph",
            "footnote": "paragraph",
            "page_header": "header",
            "page_footer": "footer",
        }

        for item, level in doc.iterate_items():
            label = str(getattr(item, "label", "text")).lower()
            content = ""

            # Extract text
            if hasattr(item, "text"):
                content = item.text or ""
            elif hasattr(item, "export_to_markdown"):
                try:
                    content = item.export_to_markdown()
                except TypeError:
                    content = ""

            if not content.strip():
                continue

            # Extract position
            page_number = 0
            bbox = None
            if hasattr(item, "prov") and item.prov:
                prov = item.prov[0]
                page_number = getattr(prov, "page_no", 0)
                if hasattr(prov, "bbox"):
                    try:
                        bbox = prov.bbox.as_tuple()
                    except Exception:
                        pass

            element_type = type_mapping.get(label, "paragraph")

            elements.append({
                "type": element_type,
                "content": content.strip(),
                "page_number": page_number,
                "bbox": bbox,
                "element_id": f"{element_type}_{len(elements)}",
                "metadata": {
                    "docling_label": label,
                    "level": level,
                },
            })

        return elements

    def _extract_tables_info(self, doc: Any) -> list[dict]:
        """Extract structured table information."""
        tables = []

        if not hasattr(doc, "tables"):
            return tables

        for i, table in enumerate(doc.tables):
            table_info = {
                "index": i,
                "page_number": 0,
                "markdown": "",
                "rows": 0,
                "cols": 0,
            }

            # Position
            if hasattr(table, "prov") and table.prov:
                table_info["page_number"] = getattr(table.prov[0], "page_no", 0)

            # Table data
            try:
                if hasattr(table, "export_to_dataframe"):
                    df = table.export_to_dataframe()
                    table_info["rows"] = len(df)
                    table_info["cols"] = len(df.columns)
                    table_info["headers"] = list(df.columns)
                if hasattr(table, "export_to_markdown"):
                    table_info["markdown"] = table.export_to_markdown()
            except Exception as e:
                logger.warning(f"[DOCLING] Table {i} export error: {e}")

            tables.append(table_info)

        return tables

    @staticmethod
    def _count_elements(elements: list[dict]) -> dict[str, int]:
        """Count elements by type."""
        counts: dict[str, int] = {}
        for el in elements:
            t = el.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts

    async def load(self, source: str | Path) -> ProcessedDocument:
        """Load a document asynchronously."""
        return await asyncio.to_thread(self._load_sync, source)

    async def load_batch(self, sources: list[str | Path]) -> list[ProcessedDocument]:
        """Load multiple documents in parallel."""
        tasks = [self.load(s) for s in sources]
        return await asyncio.gather(*tasks)

    def supported_extensions(self) -> list[str]:
        """Supported file formats."""
        return [".pdf", ".docx", ".pptx", ".xlsx", ".html"]
