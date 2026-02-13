"""Recursive text splitter with hierarchical heading propagation.

Splits documents into overlapping chunks, producing DocumentChunk objects.
Phase 27: Parses markdown headings and propagates the full section hierarchy
to each chunk's metadata and content prefix, enabling section-aware search.

Heading patterns supported:
- Docling format: ## 5 . 5 . 12 . 2 . Title
- Standard markdown: ## 5.5.12.2. Title
- Chapter headers: ## Глава 5. Title
"""

import re

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument
from src.pdf_framework.utils.id_generator import generate_chunk_id

# Match markdown headings: ## Title (any level 1-6)
_MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


class RecursiveTextSplitter:
    """Split document text into overlapping chunks with header propagation."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def split(self, document: ProcessedDocument) -> list[DocumentChunk]:
        """Split a processed document into chunks with header propagation."""
        if not document.raw_text.strip():
            return []

        raw = document.raw_text

        # Step 1: Parse all headings and their positions
        headings = self._parse_headings(raw)

        # Step 2: Split text into chunks
        texts = self._splitter.split_text(raw)
        chunks: list[DocumentChunk] = []

        # Cache for position lookups (avoid repeated raw.find)
        search_start = 0

        for i, text in enumerate(texts):
            # Step 3: Find chunk position in raw_text
            pos = raw.find(text[:200], search_start)
            if pos < 0:
                pos = raw.find(text[:200])  # fallback: search from start
            if pos >= 0:
                search_start = pos  # next search starts after this

            # Step 4: Get active heading hierarchy at this position
            section_headers = (
                self._get_headers_at_position(headings, pos) if pos >= 0 else []
            )

            # Step 5: Build section title (deepest heading)
            section_title = section_headers[-1] if section_headers else ""

            # Step 6: Prepend header path to content (P1.2)
            # Skip if the chunk already starts with a markdown heading
            content = text
            if section_headers and not text.lstrip().startswith("#"):
                header_path = " > ".join(section_headers)
                content = f"Раздел: {header_path}\n\n{text}"

            # Phase 29: hierarchy metadata
            section_number = self._extract_section_number(section_title)
            level = section_number.count(".") + 1 if section_number else 0
            breadcrumb = " > ".join(section_headers)
            parent_section = section_headers[-2] if len(section_headers) >= 2 else ""

            chunk = DocumentChunk(
                id=generate_chunk_id(document.id, i, text),
                content=content,
                document_id=document.id,
                chunk_index=i,
                section=section_title,
                metadata={
                    "source": document.source_path,
                    "title": document.metadata.title,
                    "section_headers": section_headers,
                    "section_title": section_title,
                    "text_offset": pos if pos >= 0 else None,
                    "level": level,
                    "breadcrumb": breadcrumb,
                    "section_number": section_number,
                    "parent_section": parent_section,
                },
            )
            chunks.append(chunk)

        return chunks

    @staticmethod
    def _parse_headings(text: str) -> list[tuple[int, int, str]]:
        """Parse markdown headings, returning (position, depth, clean_title).

        Handles Docling format with spaces: ## 5 . 5 . 12 . 2 . Title
        and standard markdown: ## 5.5.12.2. Title
        """
        headings: list[tuple[int, int, str]] = []

        for match in _MD_HEADING_RE.finditer(text):
            pos = match.start()
            heading_text = match.group(2).strip()

            # Normalize spaces around dots: "5 . 5 . 12" → "5.5.12"
            normalized = re.sub(r"\s*\.\s*", ".", heading_text)

            # Try to extract numbered section level
            num_match = re.match(r"^(\d+(?:\.\d+)*)", normalized)
            if num_match:
                num_part = num_match.group(1)
                depth = num_part.count(".") + 1
                rest = normalized[num_match.end():].lstrip(". ")
                clean_heading = f"{num_part}. {rest}" if rest else num_part
            elif normalized.lower().startswith("глава"):
                depth = 1
                clean_heading = normalized
            elif normalized.lower().startswith("рис."):
                continue  # Skip figures — they don't form hierarchy
            else:
                depth = 0  # Unknown level — treat as top-level
                clean_heading = normalized

            headings.append((pos, depth, clean_heading))

        return headings

    @staticmethod
    def _get_headers_at_position(
        headings: list[tuple[int, int, str]],
        pos: int,
    ) -> list[str]:
        """Get the active heading hierarchy at a given text position.

        Uses Docling's heading_by_level pattern: when a heading of the same
        or higher level appears, deeper headings are cleared.
        """
        heading_by_level: dict[int, str] = {}

        for h_pos, h_depth, h_title in headings:
            if h_pos > pos:
                break

            # Set this level
            heading_by_level[h_depth] = h_title

            # Clear deeper levels (Docling pattern)
            for deeper in list(heading_by_level.keys()):
                if deeper > h_depth:
                    del heading_by_level[deeper]

        # Return sorted by level (shallowest first)
        return [heading_by_level[k] for k in sorted(heading_by_level.keys())]

    @staticmethod
    def _extract_section_number(title: str) -> str:
        """Extract numeric section from title: '5.14.3.6. Агрегаты' → '5.14.3.6'."""
        m = re.match(r"^(\d+(?:\.\d+)*)", title)
        return m.group(1) if m else ""
