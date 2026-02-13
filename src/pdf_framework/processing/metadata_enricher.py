"""Metadata enricher for adding structured fields to chunks.

Phase 1.3: Adds document_type, section, language, version fields
to chunk metadata for filtering support.
"""

import re
from pathlib import Path
from typing import Any

from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument


class MetadataEnricher:
    """Enrich chunk metadata with structured fields for filtering."""

    @staticmethod
    def enrich_chunk(
        chunk: DocumentChunk,
        document: ProcessedDocument,
    ) -> DocumentChunk:
        """Add structured metadata fields to a chunk.

        Phase 1.3 structured fields:
        - document_type: Inferred from filename/content
        - section: Extracted from content or chunk position
        - language: Detected from content
        - version: Extracted from filename
        - source: Document source path
        - title: Document title
        """
        # Get document info
        filename = Path(document.source_path).name
        doc_title = document.metadata.title or filename

        # Infer document type from filename/title
        document_type = MetadataEnricher._infer_document_type(filename, doc_title)

        # Extract version from filename
        version = MetadataEnricher._extract_version(filename)

        # Detect language (simple heuristic)
        language = MetadataEnricher._detect_language(chunk.content)

        # Enrich metadata
        chunk.metadata.update({
            "document_type": document_type,
            "language": language,
            "version": version,
            "source": document.source_path,
            "title": doc_title,
            "page_number": chunk.page_number,
            "section": chunk.section,
        })

        return chunk

    @staticmethod
    def _infer_document_type(filename: str, title: str) -> str:
        """Infer document type from filename and title.

        Types: documentation, manual, guide, api, tutorial, reference
        """
        text = (filename + " " + title).lower()

        if any(kw in text for kw in ["руководство", "guide", "manual"]):
            if "пользователя" in text or "user" in text:
                return "user_manual"
            elif "разработчика" in text or "developer" in text:
                return "developer_guide"
            elif "администратора" in text or "admin" in text:
                return "admin_guide"
            return "manual"

        if any(kw in text for kw in ["документация", "documentation", "docs"]):
            return "documentation"

        if any(kw in text for kw in ["api", "reference", "справочник"]):
            return "api_reference"

        if any(kw in text for kw in ["tutorial", "учебник", "обучение"]):
            return "tutorial"

        if any(kw in text for kw in ["введение", "introduction", "getting started"]):
            return "introduction"

        return "document"

    @staticmethod
    def _extract_version(filename: str) -> str:
        """Extract version number from filename.

        Examples:
        - "1С Предприятие 8.3.26" -> "8.3.26"
        - "Python 3.11 Guide" -> "3.11"
        """
        # Pattern for version numbers: X.Y or X.Y.Z
        pattern = r'(\d+\.\d+(?:\.\d+)?)'
        match = re.search(pattern, filename)
        if match:
            return match.group(1)
        return ""

    @staticmethod
    def _detect_language(text: str) -> str:
        """Detect language from text content.

        Simple heuristic: Check for Cyrillic characters.
        """
        # Count Cyrillic characters
        cyrillic_count = sum(1 for char in text if '\u0400' <= char <= '\u04FF')
        total_alpha = sum(1 for char in text if char.isalpha())

        if total_alpha == 0:
            return "unknown"

        # If >30% Cyrillic, classify as Russian
        if cyrillic_count / total_alpha > 0.3:
            return "ru"

        return "en"

    @staticmethod
    def enrich_chunks(
        chunks: list[DocumentChunk],
        document: ProcessedDocument,
    ) -> list[DocumentChunk]:
        """Enrich all chunks in a list."""
        return [MetadataEnricher.enrich_chunk(chunk, document) for chunk in chunks]


def apply_metadata_filters(
    chunks: list[DocumentChunk],
    filters: dict[str, Any],
) -> list[DocumentChunk]:
    """Filter chunks by metadata fields.

    Phase 1.3: Supports filtering by any metadata field.

    Args:
        chunks: List of chunks to filter
        filters: Dict of field_name -> value
                 Examples:
                 - {"document_type": "documentation"}
                 - {"language": "ru", "version": "8.3"}

    Returns:
        Filtered chunks matching all filter criteria
    """
    if not filters:
        return chunks

    filtered = []
    for chunk in chunks:
        matches_all = True
        for field, expected_value in filters.items():
            actual_value = chunk.metadata.get(field)

            # Support partial string matching for version
            if isinstance(expected_value, str) and isinstance(actual_value, str):
                if expected_value not in actual_value:
                    matches_all = False
                    break
            elif actual_value != expected_value:
                matches_all = False
                break

        if matches_all:
            filtered.append(chunk)

    return filtered
