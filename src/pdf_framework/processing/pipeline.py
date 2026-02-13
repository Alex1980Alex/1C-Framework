"""Processing pipeline: orchestrates splitting by config."""

import bisect
import hashlib
import logging
import time

from src.pdf_framework.config import ParentChildSettings, PDFSettings
from src.pdf_framework.processing.metadata_enricher import MetadataEnricher
from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter
from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument

logger = logging.getLogger(__name__)


class ProcessingPipeline:
    """Orchestrate document processing: choose splitter by config, split documents.

    Phase 1.3: Automatically enriches chunks with structured metadata.
    Phase 7: Parent-Child two-level splitting.
    Phase 24.1: Page-aware chunk mapping.
    """

    def __init__(self, settings: PDFSettings | None = None, enable_metadata_enrichment: bool = True):
        self._settings = settings or PDFSettings()
        self._splitter = self._create_splitter()
        self._enable_metadata_enrichment = enable_metadata_enrichment

    def _create_splitter(self) -> RecursiveTextSplitter:
        if self._settings.splitter == "semantic":
            from src.pdf_framework.processing.splitters.semantic_splitter import SemanticTextSplitter

            return SemanticTextSplitter(  # type: ignore[return-value]
                chunk_size=self._settings.chunk_size,
                chunk_overlap=self._settings.chunk_overlap,
                semantic_threshold=self._settings.semantic_threshold,
                min_chunk_size=self._settings.min_chunk_size,
                max_chunk_size=self._settings.max_chunk_size,
            )
        # Default to recursive for all other modes (including parent_child fallback)
        return RecursiveTextSplitter(
            chunk_size=self._settings.chunk_size,
            chunk_overlap=self._settings.chunk_overlap,
        )

    @staticmethod
    def _assign_page_numbers(
        chunks: list[DocumentChunk],
        document: ProcessedDocument,
    ) -> list[DocumentChunk]:
        """Map each chunk back to its source page using page_offsets from loader.

        page_offsets is a list of (char_offset, page_number) stored by PyMuPDFLoader.
        For each chunk, find its position in raw_text and determine the page.
        """
        page_offsets: list[tuple[int, int]] = document.metadata.extra.get("page_offsets", [])
        if not page_offsets or not document.raw_text:
            return chunks

        # Build sorted offset list for binary search
        offsets = [o[0] for o in page_offsets]
        page_nums = [o[1] for o in page_offsets]

        for chunk in chunks:
            if chunk.page_number and chunk.page_number > 0:
                continue  # already has page (e.g. image chunks)

            # Use stored text_offset from splitter (handles header-prefixed content)
            pos = chunk.metadata.get("text_offset") if chunk.metadata else None
            if pos is None:
                # Fallback: find chunk content in raw_text
                search_text = chunk.content
                # Strip "Раздел: ..." header prefix if present
                if search_text.startswith("Раздел: "):
                    nl_pos = search_text.find("\n\n")
                    if nl_pos > 0:
                        search_text = search_text[nl_pos + 2:]
                pos = document.raw_text.find(search_text[:200])
            if pos is None or pos < 0:
                continue

            # Binary search: find the page this offset belongs to
            idx = bisect.bisect_right(offsets, pos) - 1
            if 0 <= idx < len(page_nums):
                chunk.page_number = page_nums[idx]

        return chunks

    @staticmethod
    def _deduplicate_chunks(chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        """Remove duplicate chunks by content hash (Phase 29)."""
        seen: set[str] = set()
        result: list[DocumentChunk] = []
        for chunk in chunks:
            h = hashlib.sha256(chunk.content.encode()).hexdigest()[:16]
            if h not in seen:
                seen.add(h)
                result.append(chunk)
        if len(result) < len(chunks):
            logger.info(
                "[PIPELINE] Дедупликация: %d → %d чанков (%d дубликатов удалено)",
                len(chunks), len(result), len(chunks) - len(result),
            )
        return result

    @staticmethod
    def _inherit_image_sections(
        text_chunks: list[DocumentChunk],
        image_chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        """Copy section/breadcrumb from nearest text chunk to image chunks (Phase 29).

        For each image chunk, finds text chunks on the same page (or adjacent pages)
        and copies their section metadata.
        """
        page_sections: dict[int, dict] = {}
        for c in text_chunks:
            if c.page_number and c.section and c.section != "image":
                page_sections[c.page_number] = {
                    "section": c.section,
                    "section_headers": c.metadata.get("section_headers", []),
                    "breadcrumb": c.metadata.get("breadcrumb", ""),
                    "section_number": c.metadata.get("section_number", ""),
                    "level": c.metadata.get("level", 0),
                }

        inherited = 0
        for img in image_chunks:
            page = img.page_number
            if not page:
                continue
            for offset in (0, -1, 1, -2, 2):
                info = page_sections.get(page + offset)
                if info:
                    img.section = info["section"]
                    img.metadata["section_headers"] = info["section_headers"]
                    img.metadata["breadcrumb"] = info["breadcrumb"]
                    img.metadata["section_number"] = info["section_number"]
                    img.metadata["section_title"] = info["section"]
                    img.metadata["level"] = info["level"]
                    inherited += 1
                    break

        if inherited:
            logger.info(
                "[PIPELINE] Image sections: %d/%d image chunks inherited section from text",
                inherited, len(image_chunks),
            )
        return image_chunks

    def process(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """Split a document into chunks.

        Phase 1.3: Enriches chunks with structured metadata fields.
        Phase 24.1: Assigns page numbers to chunks via page_offsets.
        """
        t0 = time.time()
        logger.info(
            "[PIPELINE] Разбиение '%s' (splitter=%s, chunk_size=%d, overlap=%d)",
            document.source_path, self._settings.splitter,
            self._settings.chunk_size, self._settings.chunk_overlap,
        )

        chunks = self._splitter.split(document)
        t_split = time.time() - t0
        logger.info(
            "[PIPELINE] Сплиттер создал %d чанков за %.2f сек (avg %d символов/чанк)",
            len(chunks), t_split,
            sum(len(c.content) for c in chunks) // max(len(chunks), 1),
        )

        # Assign page numbers from loader's page_offsets
        chunks = self._assign_page_numbers(chunks, document)
        pages_assigned = sum(1 for c in chunks if c.page_number and c.page_number > 0)
        unique_pages = len({c.page_number for c in chunks if c.page_number and c.page_number > 0})
        logger.info(
            "[PIPELINE] Страницы назначены: %d/%d чанков, %d уникальных страниц",
            pages_assigned, len(chunks), unique_pages,
        )

        # Deduplicate by content hash (Phase 29)
        chunks = self._deduplicate_chunks(chunks)

        # Enrich metadata if enabled (Phase 1.3)
        if self._enable_metadata_enrichment:
            chunks = MetadataEnricher.enrich_chunks(chunks, document)

        elapsed = time.time() - t0
        logger.info(
            "[PIPELINE] Готово: %d чанков за %.2f сек",
            len(chunks), elapsed,
        )

        document.chunks = chunks
        return chunks

    def process_parent_child(
        self,
        document: ProcessedDocument,
        pc_settings: ParentChildSettings | None = None,
    ) -> tuple[list[DocumentChunk], list[DocumentChunk]]:
        """Split document into parent and child chunks (Phase 7).

        Args:
            document: Processed document to split
            pc_settings: Parent-Child settings (uses defaults if None)

        Returns:
            Tuple of (parent_chunks, child_chunks)
        """
        from src.pdf_framework.processing.splitters.parent_child import ParentChildSplitter

        settings = pc_settings or ParentChildSettings()

        splitter = ParentChildSplitter(
            parent_chunk_size=settings.parent_chunk_size,
            parent_chunk_overlap=settings.parent_chunk_overlap,
            child_chunk_size=settings.child_chunk_size,
            child_chunk_overlap=settings.child_chunk_overlap,
        )

        parents, children = splitter.split(document)

        # Enrich metadata on children (they go to vector store)
        if self._enable_metadata_enrichment:
            children = MetadataEnricher.enrich_chunks(children, document)

        document.chunks = children
        return parents, children

    def process_batch(self, documents: list[ProcessedDocument]) -> list[DocumentChunk]:
        """Split multiple documents into chunks."""
        all_chunks: list[DocumentChunk] = []
        for doc in documents:
            all_chunks.extend(self.process(doc))
        return all_chunks
