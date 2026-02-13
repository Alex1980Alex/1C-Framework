"""Hybrid PDF loader — 4-level cascade for 100% page coverage.

Phase 28: Combines PyMuPDF4LLM (fast text) + fitz find_tables() +
Docling TableFormer (ML tables) + Claude Vision OCR (scanned pages).

Cascade:
    Level 1: PyMuPDF4LLM (page_chunks=True) — text + page_offsets
    Level 2: fitz find_tables() — rule-based table extraction
    Level 3: Docling TableFormer — ML-based complex tables (Ralph Wiggum retry)
    Level 4: Claude Vision OCR — auto-detect scanned pages, render → OCR

Author: Claude Code
Version: 0.2.0 - Phase 28: Level 4 Vision OCR
"""

import asyncio
import base64
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz

from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.loaders.coverage_verifier import PageCoverageVerifier
from src.pdf_framework.loaders.table_extractor import SmartTableExtractor, TableInfo
from src.pdf_framework.schemas.documents import DocumentMetadata, ProcessedDocument
from src.pdf_framework.utils.id_generator import generate_document_id

logger = logging.getLogger(__name__)


# Vision OCR system prompt — focused on page text extraction
_VISION_OCR_SYSTEM = (
    "Ты — OCR-транскриптор для технической документации 1С:Предприятие. "
    "Твоя задача — извлечь ВЕСЬ текст со сканированной страницы документа.\n\n"
    "ПРАВИЛА:\n"
    "- Транскрибируй ВСЁ: заголовки, абзацы, списки, примечания, подписи\n"
    "- Таблицы оформляй как markdown-таблицы с | и ---\n"
    "- Сохраняй структуру: заголовки как ## или ###, списки как - или 1.\n"
    "- НЕ описывай страницу — транскрибируй текст дословно\n"
    "- НЕ добавляй комментарии или пояснения\n"
    "- Отвечай ТОЛЬКО на русском языке"
)

_VISION_OCR_PROMPT = (
    "Это скан страницы из технической документации 1С:Предприятие. "
    "Транскрибируй ВЕСЬ текст с этой страницы. "
    "Сохрани структуру: заголовки, абзацы, таблицы (в формате markdown), "
    "списки, примечания. Не пропускай ни одного слова."
)


class HybridLoader(BaseLoader):
    """4-level cascade loader for 100% page coverage.

    Level 1: PyMuPDF4LLM text extraction (page_chunks=True)
    Level 2: PyMuPDF find_tables() for rule-based tables
    Level 3: Docling TableFormer for complex tables (optional)
    Level 4: Claude Vision OCR for scanned pages (auto-detect)
    """

    def __init__(self, settings=None, api_key: str = "", base_url: str = ""):
        from src.pdf_framework.config import HybridLoaderSettings

        self._settings = settings or HybridLoaderSettings()
        self._table_extractor = SmartTableExtractor(
            dedup_threshold=self._settings.table_dedup_threshold,
        )
        self._stats: dict[str, int] = {}

        # Vision OCR credentials — read from args or global settings
        self._api_key = api_key
        self._base_url = base_url
        if not self._api_key and self._settings.enable_vision_ocr:
            try:
                from src.pdf_framework.config import get_settings
                s = get_settings()
                self._api_key = s.anthropic_api_key
                self._base_url = self._base_url or s.agent.base_url
            except Exception:
                pass

        self._vision_client = None  # Lazy init

    def _get_vision_client(self):
        """Lazy-init Anthropic client for Vision OCR."""
        if self._vision_client is not None:
            return self._vision_client

        if not self._api_key:
            return None

        from anthropic import Anthropic

        kwargs: dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        self._vision_client = Anthropic(**kwargs)
        return self._vision_client

    def _load_sync(self, source: str | Path) -> ProcessedDocument:
        """Synchronous loading with 4-level cascade."""
        import pymupdf4llm

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Unsupported file type: {path.suffix}")

        self._stats = {
            "text_pages": 0,
            "fitz_tables": 0,
            "docling_tables": 0,
            "vision_ocr_pages": 0,
            "empty_pages": 0,
        }

        logger.info("[HYBRID] Loading: %s", path.name)

        # === Level 1: PyMuPDF4LLM text extraction ===
        logger.info("[HYBRID] Level 1: PyMuPDF4LLM text extraction")
        page_chunks: list[dict[str, Any]] = pymupdf4llm.to_markdown(
            str(path), page_chunks=True,
        )  # type: ignore[assignment]  # page_chunks=True returns list[dict]

        page_texts: dict[int, str] = {}  # {page_num(1-based): text}
        page_offsets: list[tuple[int, int]] = []
        page_list: list[str] = []  # ordered page texts
        page_nums: list[int] = []  # ordered page numbers
        offset = 0

        for chunk in page_chunks:
            meta: Any = chunk["metadata"]
            page_num: int = int(meta["page"])  # already 1-based
            text: str = chunk.get("text", "") or ""
            page_texts[page_num] = text
            page_list.append(text)
            page_nums.append(page_num)
            page_offsets.append((offset, page_num))
            offset += len(text) + 2  # +2 for "\n\n" separator

        raw_text = "\n\n".join(page_list)
        self._stats["text_pages"] = len(page_texts)

        # PDF metadata
        doc = fitz.open(str(path))
        try:
            pdf_meta = doc.metadata or {}
            page_count = len(doc)
        finally:
            doc.close()

        logger.info(
            "[HYBRID] Level 1 done: %d pages, %d chars",
            len(page_texts), len(raw_text),
        )

        # === Level 2: fitz table extraction ===
        tables: list[TableInfo] = []
        if self._settings.enable_fitz_tables:
            logger.info("[HYBRID] Level 2: fitz find_tables()")
            fitz_tables = self._table_extractor.extract_fitz_tables(
                pdf_path=path,
                page_texts=page_texts,
                dedup=self._settings.table_dedup_enabled,
            )
            tables.extend(fitz_tables)
            self._stats["fitz_tables"] = len(fitz_tables)
            logger.info("[HYBRID] Level 2 done: %d new tables", len(fitz_tables))

        # === Level 3: Docling table extraction is async, handled in load() ===

        # === Merge tables into text ===
        if tables:
            raw_text, page_offsets = self._merge_tables(
                page_list, page_nums, tables,
            )

        # === Coverage verification ===
        coverage: dict = {}
        if self._settings.verify_coverage:
            coverage = PageCoverageVerifier.verify(page_offsets, page_count)
            if not coverage["complete"]:
                # Diagnose gaps
                diagnostics = PageCoverageVerifier.diagnose_gaps(
                    coverage["missing_pages"], path,
                )
                coverage["diagnostics"] = diagnostics
                # Count truly empty pages
                empty = sum(1 for d in diagnostics if d["type"] in ("blank", "near_blank"))
                self._stats["empty_pages"] = empty
                if coverage["coverage_ratio"] < self._settings.coverage_threshold:
                    non_blank_missing = len(coverage["missing_pages"]) - empty
                    if non_blank_missing > 0:
                        logger.warning(
                            "[HYBRID] Coverage %.1f%% below threshold %.1f%% "
                            "(%d non-blank pages missing)",
                            coverage["coverage_ratio"] * 100,
                            self._settings.coverage_threshold * 100,
                            non_blank_missing,
                        )

        file_size = path.stat().st_size

        all_tables_dicts = [t.to_dict() for t in tables]

        metadata = DocumentMetadata(
            source=str(path.resolve()),
            title=pdf_meta.get("title", "") or path.stem,
            author=pdf_meta.get("author", ""),
            page_count=page_count,
            file_size_bytes=file_size,
            extra={
                "layout_detection_method": "hybrid_cascade",
                "producer": pdf_meta.get("producer", ""),
                "page_offsets": page_offsets,
                "tables": all_tables_dicts,
                "coverage": coverage,
                "loader_stats": dict(self._stats),
                "loaded_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        document_id = generate_document_id(str(path))

        logger.info(
            "[HYBRID] Done: %s — %d pages, %d chars, %d tables, coverage=%.1f%%",
            path.name,
            page_count,
            len(raw_text),
            len(tables),
            coverage.get("coverage_ratio", 1.0) * 100,
        )

        return ProcessedDocument(
            id=document_id,
            source_path=str(path),
            metadata=metadata,
            raw_text=raw_text,
        )

    async def load(self, source: str | Path) -> ProcessedDocument:
        """Load PDF with hybrid cascade (async)."""
        # Level 1 + 2 are sync (fast)
        doc = await asyncio.to_thread(self._load_sync, source)

        # Level 3: Docling tables (async, may be slow)
        if self._settings.enable_docling_tables:
            existing_tables = [
                TableInfo(**t) for t in doc.metadata.extra.get("tables", [])
            ]
            docling_tables = await self._extract_docling_tables(
                Path(source), existing_tables,
            )
            if docling_tables:
                # Re-merge with new tables
                all_tables = existing_tables + docling_tables
                self._stats["docling_tables"] = len(docling_tables)

                # Rebuild raw_text with docling tables
                page_offsets = doc.metadata.extra.get("page_offsets", [])
                # Parse page_list from raw_text using offsets
                page_list, page_nums = self._split_by_offsets(
                    doc.raw_text, page_offsets,
                )
                new_raw, new_offsets = self._merge_tables(
                    page_list, page_nums, docling_tables,
                )
                doc.raw_text = new_raw
                doc.metadata.extra["page_offsets"] = new_offsets
                doc.metadata.extra["tables"] = [t.to_dict() for t in all_tables]
                doc.metadata.extra["loader_stats"] = dict(self._stats)

                logger.info(
                    "[HYBRID] Level 3 done: %d Docling tables added",
                    len(docling_tables),
                )

        # Level 4: Vision OCR for scanned pages (auto-detect)
        if self._settings.enable_vision_ocr and self._api_key:
            ocr_pages = await self._level4_vision_ocr(Path(source), doc)
            if ocr_pages:
                self._stats["vision_ocr_pages"] = len(ocr_pages)
                doc.metadata.extra["loader_stats"] = dict(self._stats)
                logger.info(
                    "[HYBRID] Level 4 done: %d pages OCR'd via Vision",
                    len(ocr_pages),
                )

        return doc

    # ------------------------------------------------------------------ #
    # Level 4: Claude Vision OCR for scanned pages
    # ------------------------------------------------------------------ #

    async def _level4_vision_ocr(
        self,
        pdf_path: Path,
        doc: ProcessedDocument,
    ) -> list[int]:
        """Level 4: Auto-detect scanned/sparse pages and OCR via Claude Vision.

        Finds pages with very little text (< vision_min_text_chars) that have
        images, renders them at vision_dpi, sends to Claude Vision for OCR,
        and replaces the sparse text with the OCR result.

        Returns:
            List of page numbers that were OCR'd.
        """
        # Identify scanned pages: sparse text + has images
        page_offsets = doc.metadata.extra.get("page_offsets", [])
        if not page_offsets:
            return []

        page_list, page_nums = self._split_by_offsets(doc.raw_text, page_offsets)
        min_chars = self._settings.vision_min_text_chars

        # Find pages needing OCR
        sparse_pages: list[int] = []
        page_idx_map: dict[int, int] = {}  # page_num → index in page_list

        for idx, (text, page_num) in enumerate(zip(page_list, page_nums)):
            stripped = text.strip()
            if len(stripped) < min_chars:
                sparse_pages.append(page_num)
                page_idx_map[page_num] = idx

        if not sparse_pages:
            return []

        # Check which sparse pages actually have images (are scanned)
        scanned_pages: list[int] = []
        fitz_doc = fitz.open(str(pdf_path))
        try:
            for page_num in sparse_pages:
                if page_num < 1 or page_num > len(fitz_doc):
                    continue
                page = fitz_doc[page_num - 1]
                images = page.get_images()
                if images:
                    scanned_pages.append(page_num)
                # Also include pages with no text AND no images (might be blank but
                # we don't OCR truly blank pages)
        finally:
            fitz_doc.close()

        if not scanned_pages:
            return []

        logger.info(
            "[HYBRID] Level 4: %d scanned pages detected for Vision OCR: %s",
            len(scanned_pages),
            scanned_pages[:20] if len(scanned_pages) > 20 else scanned_pages,
        )

        # OCR each scanned page via Claude Vision
        ocr_results: dict[int, str] = {}
        for page_num in scanned_pages:
            try:
                ocr_text = await self._ocr_page_via_vision(pdf_path, page_num)
                if ocr_text and len(ocr_text.strip()) > min_chars:
                    ocr_results[page_num] = ocr_text
                    logger.info(
                        "[HYBRID] Level 4: page %d OCR'd — %d chars",
                        page_num, len(ocr_text),
                    )
                else:
                    logger.debug(
                        "[HYBRID] Level 4: page %d OCR returned insufficient text (%d chars)",
                        page_num, len(ocr_text) if ocr_text else 0,
                    )
            except Exception as e:
                logger.warning(
                    "[HYBRID] Level 4: Vision OCR failed on page %d: %s",
                    page_num, e,
                )

        if not ocr_results:
            return []

        # Replace sparse page texts with OCR results
        for page_num, ocr_text in ocr_results.items():
            idx = page_idx_map.get(page_num)
            if idx is not None:
                page_list[idx] = ocr_text

        # Rebuild raw_text and offsets
        new_offsets: list[tuple[int, int]] = []
        offset = 0
        for idx, page_text in enumerate(page_list):
            new_offsets.append((offset, page_nums[idx]))
            offset += len(page_text) + 2

        doc.raw_text = "\n\n".join(page_list)
        doc.metadata.extra["page_offsets"] = new_offsets

        # Update coverage (previously missing scanned pages now have text)
        if doc.metadata.extra.get("coverage"):
            coverage = PageCoverageVerifier.verify(
                new_offsets, doc.metadata.page_count,
            )
            doc.metadata.extra["coverage"] = coverage

        return list(ocr_results.keys())

    async def _ocr_page_via_vision(
        self,
        pdf_path: Path,
        page_num: int,
    ) -> str:
        """Render a single page and OCR via Claude Vision with Ralph Wiggum retry.

        Args:
            pdf_path: Path to the PDF file.
            page_num: 1-based page number.

        Returns:
            OCR'd text from the page.
        """
        # Render page to PNG
        image_bytes = await asyncio.to_thread(
            self._render_page, pdf_path, page_num,
        )
        if not image_bytes:
            return ""

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Detect media type
        media_type = "image/png"
        if image_bytes.startswith(b"\xff\xd8\xff"):
            media_type = "image/jpeg"

        feedback = ""
        last_result = ""

        for attempt in range(1, self._settings.vision_max_retries + 1):
            try:
                result = await asyncio.to_thread(
                    self._call_vision_ocr, image_base64, media_type, feedback,
                )
                last_result = result

                # Validate: too short → retry
                if len(result.strip()) < 30:
                    feedback = (
                        "Твой предыдущий ответ был слишком коротким. "
                        "На странице должен быть значительный текст. "
                        "Транскрибируй ВСЁ, что видишь на изображении."
                    )
                    logger.warning(
                        "[HYBRID] Level 4: page %d attempt %d — too short (%d chars), retrying",
                        page_num, attempt, len(result),
                    )
                    continue

                # Validate: refusal patterns
                if self._is_vision_refusal(result):
                    feedback = (
                        "Твой предыдущий ответ содержал отказ обработать изображение. "
                        "Изображение реальное — это скан страницы документации. "
                        "Транскрибируй ВЕСЬ текст."
                    )
                    logger.warning(
                        "[HYBRID] Level 4: page %d attempt %d — refusal, retrying",
                        page_num, attempt,
                    )
                    continue

                return result

            except Exception as e:
                logger.warning(
                    "[HYBRID] Level 4: Vision API error on page %d attempt %d: %s",
                    page_num, attempt, e,
                )
                feedback = f"Предыдущий вызов завершился ошибкой: {e}. Попробуй ещё раз."
                last_result = ""

        return last_result

    def _render_page(self, pdf_path: Path, page_num: int) -> bytes:
        """Render a PDF page as PNG image bytes (sync, runs in thread)."""
        doc = fitz.open(str(pdf_path))
        try:
            if page_num < 1 or page_num > len(doc):
                return b""
            page = doc[page_num - 1]
            # Render at configured DPI
            dpi = self._settings.vision_dpi
            zoom = dpi / 72.0  # fitz default is 72 DPI
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)  # type: ignore[arg-type]

            # Convert to PNG bytes
            png_bytes: bytes = pix.tobytes("png")
            return png_bytes
        finally:
            doc.close()

    def _call_vision_ocr(
        self,
        image_base64: str,
        media_type: str,
        feedback: str = "",
    ) -> str:
        """Synchronous Vision API call for page OCR (runs in thread)."""
        client = self._get_vision_client()
        if client is None:
            return ""

        prompt = _VISION_OCR_PROMPT
        if feedback:
            prompt += f"\n\n{feedback}"

        response = client.messages.create(
            model=self._settings.vision_model,
            max_tokens=4096,
            system=_VISION_OCR_SYSTEM,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }],
        )

        content = response.content[0]
        return getattr(content, "text", str(content)).strip()

    @staticmethod
    def _is_vision_refusal(text: str) -> bool:
        """Check if Vision model refused to process the page."""
        lower = text.lower()
        refusal_patterns = [
            "не могу просмотреть",
            "не могу обработать",
            "cannot transcribe",
            "cannot read",
            "i cannot",
            "i am unable",
            "не удалась",
        ]
        return any(p in lower for p in refusal_patterns)

    # ------------------------------------------------------------------ #
    # Level 3: Docling tables
    # ------------------------------------------------------------------ #

    async def _extract_docling_tables(
        self,
        pdf_path: Path,
        existing_tables: list[TableInfo],
    ) -> list[TableInfo]:
        """Level 3: Extract tables via Docling with Ralph Wiggum retry."""
        from src.pdf_framework.config import DoclingSettings
        from src.pdf_framework.loaders.providers.docling_loader import DoclingLoader

        # Configure Docling for table-only extraction (no OCR, no layout)
        settings = DoclingSettings(
            ocr_enabled=False,
            table_structure_enabled=True,
            table_mode=self._settings.docling_table_mode,
            extract_images=False,
            generate_picture_images=False,
        )

        new_tables: list[TableInfo] = []

        for attempt in range(1, self._settings.docling_max_retries + 1):
            try:
                loader = DoclingLoader(settings=settings)
                doc = await loader.load(pdf_path)

                raw_tables = doc.metadata.extra.get("tables", [])
                if not raw_tables:
                    if attempt < self._settings.docling_max_retries:
                        logger.warning(
                            "[HYBRID] Docling attempt %d/%d: no tables found, retrying",
                            attempt, self._settings.docling_max_retries,
                        )
                        continue
                    break

                # Convert to TableInfo and filter
                existing_pages = {
                    (t.page_number, t.markdown[:100]) for t in existing_tables
                }
                for raw_t in raw_tables:
                    md = raw_t.get("markdown", "")
                    page = raw_t.get("page_number", 0)

                    # Validate: Ralph Wiggum
                    if not self._is_valid_table(md):
                        logger.debug(
                            "[HYBRID] Docling table on page %d invalid (no markdown)",
                            page,
                        )
                        continue

                    # Dedup against existing
                    key = (page, md[:100])
                    if key in existing_pages:
                        continue

                    new_tables.append(TableInfo(
                        page_number=page,
                        markdown=md,
                        source="docling",
                        rows=raw_t.get("rows", 0),
                        cols=raw_t.get("cols", 0),
                        headers=raw_t.get("headers", []),
                    ))

                logger.info(
                    "[HYBRID] Docling: %d raw tables, %d new after dedup",
                    len(raw_tables), len(new_tables),
                )
                break  # Success

            except Exception as e:
                logger.warning(
                    "[HYBRID] Docling attempt %d failed: %s", attempt, e,
                )
                if attempt < self._settings.docling_max_retries:
                    await asyncio.sleep(1)

        return new_tables

    @staticmethod
    def _is_valid_table(md: str) -> bool:
        """Validate table markdown has proper structure."""
        if not md or len(md) < 10:
            return False
        return "|" in md and "---" in md

    @staticmethod
    def _merge_tables(
        page_list: list[str],
        page_nums: list[int],
        tables: list[TableInfo],
    ) -> tuple[str, list[tuple[int, int]]]:
        """Merge new tables into raw_text at page boundaries.

        Groups tables by page number, appends each table after
        the corresponding page text, then rebuilds raw_text and
        page_offsets.
        """
        # Group tables by page
        tables_by_page: dict[int, list[str]] = defaultdict(list)
        for t in tables:
            tables_by_page[t.page_number].append(t.markdown)

        # Rebuild pages with appended tables
        new_pages: list[str] = []
        for i, (text, page_num) in enumerate(zip(page_list, page_nums)):
            if page_num in tables_by_page:
                table_block = "\n\n".join(tables_by_page[page_num])
                new_pages.append(f"{text}\n\n{table_block}")
            else:
                new_pages.append(text)

        # Rebuild raw_text and offsets
        new_offsets: list[tuple[int, int]] = []
        offset = 0
        for i, page_text in enumerate(new_pages):
            new_offsets.append((offset, page_nums[i]))
            offset += len(page_text) + 2  # +2 for "\n\n"

        new_raw = "\n\n".join(new_pages)
        return new_raw, new_offsets

    @staticmethod
    def _split_by_offsets(
        raw_text: str,
        page_offsets: list[tuple[int, int]],
    ) -> tuple[list[str], list[int]]:
        """Split raw_text back into page texts using offsets."""
        page_list: list[str] = []
        page_nums: list[int] = []

        for i, (start, page_num) in enumerate(page_offsets):
            if i + 1 < len(page_offsets):
                end = page_offsets[i + 1][0] - 2  # -2 for "\n\n"
            else:
                end = len(raw_text)
            page_list.append(raw_text[start:end])
            page_nums.append(page_num)

        return page_list, page_nums

    async def load_batch(self, sources: list[str | Path]) -> list[ProcessedDocument]:
        tasks = [self.load(s) for s in sources]
        return await asyncio.gather(*tasks)

    def supported_extensions(self) -> list[str]:
        return [".pdf"]
