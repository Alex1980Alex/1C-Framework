"""Structure-aware text splitter for layout-parsed documents (Phase 10).

Splits documents based on detected structure elements, preserving
semantic units like tables, lists, and sections.

Author: Claude Code
Version: 1.1.0 - Phase 10.2: Structure-Aware Chunking
"""

import logging
from typing import Any

from src.pdf_framework.processing.splitters.recursive import RecursiveTextSplitter
from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument

logger = logging.getLogger(__name__)


class StructureAwareSplitter:
    """
    Splits documents based on layout structure.

    Rules:
    - title + following paragraphs → one chunk (up to max_size)
    - table → separate chunk (never split)
    - list → preserve as unit
    - image → separate chunk with description
    - header/footer/page_number → skip
    """

    def __init__(
        self,
        max_chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100,
    ):
        """
        Initialize structure-aware splitter.

        Args:
            max_chunk_size: Maximum tokens per chunk
            chunk_overlap: Overlap between chunks
            min_chunk_size: Minimum tokens per chunk
        """
        self._max_chunk_size = max_chunk_size
        self._chunk_overlap = chunk_overlap
        self._min_chunk_size = min_chunk_size

        # Fallback splitter for oversized content
        self._fallback_splitter = RecursiveTextSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """
        Split document based on layout elements.

        Args:
            document: ProcessedDocument with layout_elements in metadata

        Returns:
            List of DocumentChunk objects
        """
        layout_elements = document.metadata.get("layout_elements", [])

        if not layout_elements:
            # No layout info, use fallback
            logger.warning("[STRUCTURE] No layout elements, using fallback splitter")
            return self._fallback_splitter.split(document)

        logger.info(f"[STRUCTURE] Splitting {len(layout_elements)} layout elements...")

        chunks = []
        current_section_title = None
        current_section_content = []

        for i, el_data in enumerate(layout_elements):
            el_type = el_data["type"]
            content = el_data["content"]
            page_number = el_data["page_number"]
            bbox = el_data.get("bbox")

            # Skip elements that shouldn't be indexed
            if el_type in ("header", "footer", "page_number"):
                continue

            # Handle titles
            if el_type == "title":
                # Flush current section if any
                if current_section_content:
                    chunks.extend(self._create_section_chunks(
                        current_section_title,
                        current_section_content,
                        page_number,
                    ))
                    current_section_content = []

                current_section_title = content
                continue

            # Handle tables (never split)
            if el_type == "table":
                # Flush current section first
                if current_section_content:
                    chunks.extend(self._create_section_chunks(
                        current_section_title,
                        current_section_content,
                        page_number,
                    ))
                    current_section_content = []

                # Table as separate chunk
                chunks.append(self._create_table_chunk(
                    content,
                    page_number,
                    bbox,
                    current_section_title,
                ))
                continue

            # Handle images
            if el_type == "image":
                # Flush current section first
                if current_section_content:
                    chunks.extend(self._create_section_chunks(
                        current_section_title,
                        current_section_content,
                        page_number,
                    ))
                    current_section_content = []

                # Image as separate chunk
                chunks.append(self._create_image_chunk(
                    content,
                    page_number,
                    bbox,
                    current_section_title,
                ))
                continue

            # Handle lists (preserve as unit)
            if el_type == "list":
                current_section_content.append({
                    "type": "list",
                    "content": content,
                })

                # Check if list makes section too large
                section_text = self._format_section_content(current_section_content)
                if len(section_text.split()) > self._max_chunk_size:
                    chunks.extend(self._create_section_chunks(
                        current_section_title,
                        current_section_content,
                        page_number,
                    ))
                    current_section_content = []
                continue

            # Handle paragraphs
            if el_type == "paragraph":
                current_section_content.append({
                    "type": "paragraph",
                    "content": content,
                })

                # Check if section exceeds max size
                section_text = self._format_section_content(current_section_content)
                if len(section_text.split()) > self._max_chunk_size:
                    chunks.extend(self._create_section_chunks(
                        current_section_title,
                        current_section_content,
                        page_number,
                    ))
                    current_section_content = []
                continue

            # Handle section headers
            if el_type == "section_header":
                # Flush current section
                if current_section_content:
                    chunks.extend(self._create_section_chunks(
                        current_section_title,
                        current_section_content,
                        page_number,
                    ))
                    current_section_content = []

                current_section_title = content
                continue

        # Flush remaining content
        if current_section_content:
            chunks.extend(self._create_section_chunks(
                current_section_title,
                current_section_content,
                page_number,
            ))

        logger.info(f"[STRUCTURE] Created {len(chunks)} chunks from {len(layout_elements)} elements")

        return chunks

    def _format_section_content(self, content_items: list[dict]) -> str:
        """Format section content items into text."""
        parts = []
        for item in content_items:
            parts.append(item["content"])
        return "\n\n".join(parts)

    def _create_section_chunks(
        self,
        title: str | None,
        content_items: list[dict],
        page_number: int,
    ) -> list[DocumentChunk]:
        """Create chunks from a section (title + content)."""
        text = self._format_section_content(content_items)

        # If section is small enough, single chunk
        if len(text.split()) <= self._max_chunk_size:
            return [self._create_chunk(
                text=text,
                element_type="section",
                page_number=page_number,
                section_title=title,
            )]

        # Split large section using fallback
        sub_chunks = self._fallback_splitter._split_text(text)

        chunks = []
        for i, sub_text in enumerate(sub_chunks):
            chunk = self._create_chunk(
                text=sub_text,
                element_type="section",
                page_number=page_number,
                section_title=title,
            )
            # Add chunk index for large sections
            if len(sub_chunks) > 1:
                chunk.metadata["chunk_index"] = i
                chunk.metadata["total_chunks"] = len(sub_chunks)
            chunks.append(chunk)

        return chunks

    def _create_table_chunk(
        self,
        content: str,
        page_number: int,
        bbox: tuple | None,
        section_title: str | None,
    ) -> DocumentChunk:
        """Create a chunk for a table element."""
        chunk = DocumentChunk(
            id=f"table_{page_number}_{hash(content) % 10000:04d}",
            document_id="unknown",
            content=content,
            metadata={
                "element_type": "table",
                "page_number": page_number,
                "bbox": bbox,
                "section_title": section_title,
                "chunk_type": "table",
            },
        )
        return chunk

    def _create_image_chunk(
        self,
        content: str,
        page_number: int,
        bbox: tuple | None,
        section_title: str | None,
    ) -> DocumentChunk:
        """Create a chunk for an image element."""
        chunk = DocumentChunk(
            id=f"image_{page_number}_{hash(content) % 10000:04d}",
            document_id="unknown",
            content=content,
            metadata={
                "element_type": "image",
                "page_number": page_number,
                "bbox": bbox,
                "section_title": section_title,
                "chunk_type": "image",
            },
        )
        return chunk

    def _create_chunk(
        self,
        text: str,
        element_type: str,
        page_number: int,
        section_title: str | None = None,
        **extra_metadata,
    ) -> DocumentChunk:
        """Create a standard document chunk."""
        chunk = DocumentChunk(
            id=f"chunk_{page_number}_{hash(text) % 10000:04d}",
            document_id="unknown",
            content=text,
            metadata={
                "element_type": element_type,
                "page_number": page_number,
                "section_title": section_title,
                "chunk_type": element_type,
                **extra_metadata,
            },
        )
        return chunk
