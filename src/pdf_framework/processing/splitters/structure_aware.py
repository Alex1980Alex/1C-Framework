"""Structure-aware text splitter for layout-parsed documents (Phase 10).

Splits documents based on detected structure elements, preserving
semantic units like tables, lists, and sections.

Author: Claude Code
Version: 1.1.0 - Phase 10.2: Structure-Aware Chunking
"""

import hashlib
import logging

from langchain_text_splitters import RecursiveCharacterTextSplitter

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
            max_chunk_size: Maximum characters per chunk
            chunk_overlap: Overlap between chunks
            min_chunk_size: Minimum characters per chunk
        """
        self._max_chunk_size = max_chunk_size
        self._chunk_overlap = chunk_overlap
        self._min_chunk_size = min_chunk_size

        # Fallback text splitter for oversized content
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def split(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """
        Split document based on layout elements.

        Args:
            document: ProcessedDocument with layout_elements in metadata.extra

        Returns:
            List of DocumentChunk objects
        """
        layout_elements = document.metadata.extra.get("layout_elements", [])

        if not layout_elements:
            # No layout info, use fallback text splitting
            logger.warning("[STRUCTURE] No layout elements, using fallback splitter")
            return self._fallback_split(document)

        logger.info(f"[STRUCTURE] Splitting {len(layout_elements)} layout elements...")

        doc_id = document.id
        chunks: list[DocumentChunk] = []
        current_section_title: str | None = None
        current_section_content: list[dict] = []
        last_page_number = 1

        for el_data in layout_elements:
            el_type = el_data["type"]
            content = el_data["content"]
            page_number = el_data["page_number"]
            bbox = el_data.get("bbox")
            last_page_number = page_number

            # Skip elements that shouldn't be indexed
            if el_type in ("header", "footer", "page_number"):
                continue

            # Handle titles and section headers
            if el_type in ("title", "section_header"):
                # Flush current section if any
                if current_section_content:
                    chunks.extend(self._create_section_chunks(
                        current_section_title,
                        current_section_content,
                        last_page_number,
                        doc_id,
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
                        doc_id,
                    ))
                    current_section_content = []

                chunks.append(self._create_chunk(
                    text=content,
                    element_type="table",
                    page_number=page_number,
                    doc_id=doc_id,
                    section_title=current_section_title,
                    bbox=bbox,
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
                        doc_id,
                    ))
                    current_section_content = []

                chunks.append(self._create_chunk(
                    text=content,
                    element_type="image",
                    page_number=page_number,
                    doc_id=doc_id,
                    section_title=current_section_title,
                    bbox=bbox,
                ))
                continue

            # Handle lists and paragraphs — accumulate in current section
            current_section_content.append({
                "type": el_type,
                "content": content,
            })

            # Check if section exceeds max size
            section_text = self._format_section_content(current_section_content)
            if len(section_text) > self._max_chunk_size:
                chunks.extend(self._create_section_chunks(
                    current_section_title,
                    current_section_content,
                    page_number,
                    doc_id,
                ))
                current_section_content = []

        # Flush remaining content
        if current_section_content:
            chunks.extend(self._create_section_chunks(
                current_section_title,
                current_section_content,
                last_page_number,
                doc_id,
            ))

        logger.info(f"[STRUCTURE] Created {len(chunks)} chunks from {len(layout_elements)} elements")

        return chunks

    def _fallback_split(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """Split using plain text splitter when no layout elements available."""
        if not document.raw_text.strip():
            return []

        texts = self._text_splitter.split_text(document.raw_text)
        return [
            DocumentChunk(
                id=f"{document.id}_chunk_{i}",
                content=text,
                document_id=document.id,
                chunk_index=i,
                metadata={
                    "element_type": "paragraph",
                    "source": document.source_path,
                },
            )
            for i, text in enumerate(texts)
        ]

    def _format_section_content(self, content_items: list[dict]) -> str:
        """Format section content items into text."""
        return "\n\n".join(item["content"] for item in content_items)

    def _create_section_chunks(
        self,
        title: str | None,
        content_items: list[dict],
        page_number: int,
        doc_id: str,
    ) -> list[DocumentChunk]:
        """Create chunks from a section (title + content)."""
        text = self._format_section_content(content_items)

        # If section is small enough, single chunk
        if len(text) <= self._max_chunk_size:
            return [self._create_chunk(
                text=text,
                element_type="section",
                page_number=page_number,
                doc_id=doc_id,
                section_title=title,
            )]

        # Split large section using text splitter
        sub_texts = self._text_splitter.split_text(text)

        chunks = []
        for i, sub_text in enumerate(sub_texts):
            chunk = self._create_chunk(
                text=sub_text,
                element_type="section",
                page_number=page_number,
                doc_id=doc_id,
                section_title=title,
            )
            if len(sub_texts) > 1:
                chunk.metadata["chunk_index"] = i
                chunk.metadata["total_chunks"] = len(sub_texts)
            chunks.append(chunk)

        return chunks

    def _create_chunk(
        self,
        text: str,
        element_type: str,
        page_number: int,
        doc_id: str,
        section_title: str | None = None,
        bbox: tuple | None = None,
    ) -> DocumentChunk:
        """Create a standard document chunk."""
        content_hash = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16) % 10000
        return DocumentChunk(
            id=f"{doc_id}_{element_type}_{page_number}_{content_hash:04d}",
            document_id=doc_id,
            content=text,
            page_number=page_number,
            section=section_title or "",
            metadata={
                "element_type": element_type,
                "page_number": page_number,
                "section_title": section_title,
                "bbox": bbox,
                "chunk_type": element_type,
            },
        )
