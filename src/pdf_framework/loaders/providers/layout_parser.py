"""Layout-aware PDF loader using unstructured library (Phase 10).

Detects and preserves document structure: titles, paragraphs, tables, images, lists.

Author: Claude Code
Version: 1.1.0 - Phase 10.1: Layout Detection Provider
"""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from src.pdf_framework.loaders.base import BaseLoader
from src.pdf_framework.schemas.documents import ProcessedDocument

logger = logging.getLogger(__name__)


class LayoutElement(BaseModel):
    """Single detected element from PDF layout analysis."""

    type: Literal[
        "title",
        "paragraph",
        "table",
        "image",
        "list",
        "header",
        "footer",
        "page_number",
        "section_header",
    ] = Field(description="Element type from layout detection")
    content: str = Field(description="Extracted text content")
    page_number: int = Field(description="Page number (1-based)")
    bbox: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Bounding box (x0, y0, x1, y1) in PDF coordinates"
    )
    element_id: str | None = Field(
        default=None,
        description="Unique identifier for deduplication"
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional element attributes"
    )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "type": self.type,
            "content": self.content,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "element_id": self.element_id,
            "metadata": self.metadata,
        }


class LayoutAwareLoader(BaseLoader):
    """
    Layout-aware PDF loader using unstructured library.

    Detects document structure elements and preserves them for
    structure-aware chunking. Falls back to PyMuPDF if unstructured
    is not available.
    """

    def __init__(
        self,
        strategy: str = "hi_res",
        infer_table_structure: bool = True,
        extract_images: bool = False,
        skip_headers_and_footers: bool = True,
        min_image_size: int = 50,  # pixels
    ):
        """
        Initialize layout-aware loader.

        Args:
            strategy: Unstructured strategy ("hi_res" or "fast")
            infer_table_structure: Whether to detect table structure
            extract_images: Whether to extract images from PDF
            skip_headers_and_footers: Whether to skip header/footer elements
            min_image_size: Minimum image size to consider (filters icons)
        """
        self._strategy = strategy
        self._infer_table_structure = infer_table_structure
        self._extract_images = extract_images
        self._skip_headers_and_footers = skip_headers_and_footers
        self._min_image_size = min_image_size

        # Check if unstructured is available
        self._unstructured_available = self._check_unstructured()

        if not self._unstructured_available:
            logger.warning("[LAYOUT] unstructured not available, will use PyMuPDF fallback")

    @staticmethod
    def _check_unstructured() -> bool:
        """Check if unstructured library is available."""
        try:
            import unstructured  # noqa: F401
            return True
        except ImportError:
            return False

    def supported_extensions(self) -> list[str]:
        """Return supported file extensions."""
        return [".pdf"]

    async def load(self, source: str | Path) -> ProcessedDocument:
        """
        Load PDF with layout detection.

        Args:
            source: Path to PDF file

        Returns:
            ProcessedDocument with layout_elements in metadata
        """
        source_path = Path(source)

        if not source_path.exists():
            raise FileNotFoundError(f"PDF file not found: {source_path}")

        logger.info(f"[LAYOUT] Loading {source_path.name} with layout detection...")

        if self._unstructured_available:
            doc = await self._load_with_unstructured(source_path)
        else:
            doc = await self._load_with_pymupdf(source_path)

        return doc

    async def _load_with_unstructured(self, source_path: Path) -> ProcessedDocument:
        """Load PDF using unstructured library."""
        from unstructured.partition.pdf import partition_pdf

        # Partition PDF with layout detection
        elements = partition_pdf(
            filename=str(source_path),
            strategy=self._strategy,
            infer_table_structure=self._infer_table_structure,
            extract_images_in_pdf=self._extract_images,
            languages=["ru", "en"],  # Support Russian and English
        )

        # Convert unstructured elements to LayoutElement
        layout_elements = []
        content_parts = []

        for element in elements:
            layout_el = self._convert_unstructured_element(element)
            if layout_el:
                layout_elements.append(layout_el)

                # Add to full text (skip headers/footers)
                if layout_el.type not in ("header", "footer", "page_number"):
                    content_parts.append(layout_el.content)

        # Create ProcessedDocument
        full_text = "\n\n".join(content_parts)

        doc = ProcessedDocument(
            id=self._generate_doc_id(source_path),
            source_path=str(source_path),
            content=full_text,
            metadata={
                "layout_elements": [el.to_dict() for el in layout_elements],
                "layout_detection_method": "unstructured",
                "layout_strategy": self._strategy,
                "total_elements": len(layout_elements),
                "pages": max((el.page_number for el in layout_elements), default=1),
                "loaded_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Log statistics
        element_counts = self._count_element_types(layout_elements)
        logger.info(f"[LAYOUT] Detected {len(layout_elements)} elements:")
        for el_type, count in element_counts.items():
            logger.info(f"  - {el_type}: {count}")

        return doc

    async def _load_with_pymupdf(self, source_path: Path) -> ProcessedDocument:
        """Fallback: Load with PyMuPDF without layout detection."""
        import fitz  # PyMuPDF

        doc = fitz.open(str(source_path))

        layout_elements = []
        content_parts = []

        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            if text.strip():
                # Treat entire page as paragraph (no structure detection)
                layout_el = LayoutElement(
                    type="paragraph",
                    content=text.strip(),
                    page_number=page_num,
                )
                layout_elements.append(layout_el)
                content_parts.append(text.strip())

        full_text = "\n\n".join(content_parts)

        return ProcessedDocument(
            id=self._generate_doc_id(source_path),
            source_path=str(source_path),
            content=full_text,
            metadata={
                "layout_elements": [el.to_dict() for el in layout_elements],
                "layout_detection_method": "pymupdf_fallback",
                "total_elements": len(layout_elements),
                "pages": len(doc),
                "loaded_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _convert_unstructured_element(self, element) -> LayoutElement | None:
        """
        Convert unstructured element to LayoutElement.

        Args:
            element: Unstructured Element object

        Returns:
            LayoutElement or None if element should be skipped
        """
        from unstructured.documents.elements import Element

        if not isinstance(element, Element):
            return None

        # Map unstructured categories to our types
        category = element.category
        type_mapping = {
            "Title": "title",
            "NarrativeText": "paragraph",
            "ListItem": "list",
            "Table": "table",
            "Image": "image",
            "Header": "header",
            "Footer": "footer",
            "PageNumber": "page_number",
            "SectionHeader": "section_header",
        }

        element_type = type_mapping.get(category, "paragraph")

        # Skip headers/footers if configured
        if self._skip_headers_and_footers:
            if element_type in ("header", "footer", "page_number"):
                return None

        # Get content
        content = element.text or ""

        # Get bounding box if available
        bbox = None
        if hasattr(element, "metadata"):
            coord = element.metadata.coordinates
            if coord:
                bbox = (
                    coord.points[0][0],  # x0
                    coord.points[0][1],  # y0
                    coord.points[2][0],  # x1
                    coord.points[2][1],  # y1
                )

        # Generate element ID for deduplication
        element_id = self._generate_element_id(
            element_type, content, element.metadata.page_number
        )

        # Extract additional metadata
        extra_metadata = {}
        if hasattr(element, "metadata"):
            if element.metadata.category:
                extra_metadata["unstructured_category"] = element.metadata.category
            if element.metadata.element_id:
                extra_metadata["unstructured_id"] = element.metadata.element_id

        return LayoutElement(
            type=element_type,
            content=content,
            page_number=element.metadata.page_number,
            bbox=bbox,
            element_id=element_id,
            metadata=extra_metadata,
        )

    def _generate_element_id(
        self,
        element_type: str,
        content: str,
        page_number: int,
    ) -> str:
        """Generate unique ID for an element."""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{element_type}_{page_number}_{content_hash}"

    def _generate_doc_id(self, source_path: Path) -> str:
        """Generate document ID from file path."""
        path_hash = hashlib.md5(str(source_path).encode()).hexdigest()
        return f"doc_{path_hash[:12]}"

    def _count_element_types(self, elements: list[LayoutElement]) -> dict[str, int]:
        """Count elements by type."""
        counts: dict[str, int] = {}
        for el in elements:
            counts[el.type] = counts.get(el.type, 0) + 1
        return counts
