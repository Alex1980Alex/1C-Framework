"""Image Extractor for Multimodal RAG (Phase 15.1).

Extracts images from PDF documents using PyMuPDF and Docling.
Supports context extraction (surrounding text) for better descriptions.

Author: Claude Code
Version: 1.0.0 - Phase 15.1: Image Extraction
"""

import io
import logging
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

from src.pdf_framework.schemas.images import ImageChunk, ImageMetadata

logger = logging.getLogger(__name__)


class ImageExtractor:
    """Extracts images from PDF documents with context."""

    def __init__(
        self,
        output_dir: Path | None = None,
        min_image_size: int = 50,  # Minimum pixels
        extract_context: bool = True,
        context_chars: int = 300,  # Characters before/after image
    ):
        """Initialize the image extractor.

        Args:
            output_dir: Directory to save extracted images (default: data/temp/images)
            min_image_size: Minimum image size in pixels (skip smaller)
            extract_context: Extract surrounding text for better descriptions
            context_chars: Characters of context to extract before/after image
        """
        self._output_dir = output_dir or Path.cwd() / "data" / "temp" / "images"
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._min_image_size = min_image_size
        self._extract_context = extract_context
        self._context_chars = context_chars

    def extract_from_pdf(
        self,
        pdf_path: str | Path,
        document_id: str = "",
        max_images: int | None = None,
    ) -> list[ImageChunk]:
        """Extract all images from a PDF document.

        Args:
            pdf_path: Path to PDF file
            document_id: Document ID for image chunks
            max_images: Maximum images to extract (None = all)

        Returns:
            List of ImageChunk objects
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        try:
            images: list[ImageChunk] = []

            for page_num, page in enumerate(doc):
                if max_images and len(images) >= max_images:
                    break

                page_images = self._extract_from_page(
                    page, page_num, document_id, str(pdf_path)
                )
                images.extend(page_images)

            logger.info(
                f"[IMAGE_EXTRACTOR] Extracted {len(images)} images from {pdf_path.name}"
            )
            return images

        finally:
            doc.close()

    def _extract_from_page(
        self,
        page: fitz.Page,
        page_num: int,
        document_id: str,
        pdf_path: str,
    ) -> list[ImageChunk]:
        """Extract images from a single page."""
        images: list[ImageChunk] = []
        image_list = page.get_images()

        # Get page text for context
        page_text = page.get_text() if self._extract_context else ""

        for img_index, img_info in enumerate(image_list):
            try:
                xref = img_info[0]
                base_image = page.parent.extract_image(xref)

                # Skip small images
                if base_image["width"] < self._min_image_size or base_image["height"] < self._min_image_size:
                    continue

                # Get image bbox on page
                img_bbox = self._get_image_bbox(page, xref)

                # Extract context around image
                context = self._extract_context_around_image(
                    page_text, img_bbox
                ) if self._extract_context else ""

                # Save image file
                image_filename = f"{document_id}_{page_num}_{img_index}.{base_image['ext']}"
                image_path = self._output_dir / image_filename

                image_bytes = base_image["image"]
                image_path.write_bytes(image_bytes)

                # Create image chunk
                metadata = ImageMetadata(
                    page_number=page_num,
                    image_index=img_index,
                    width=base_image["width"],
                    height=base_image["height"],
                    format=base_image["ext"],
                    size_bytes=len(image_bytes),
                    bbox=img_bbox,
                    extraction_method="pymupdf",
                )

                chunk = ImageChunk(
                    id=f"{document_id}_img_{page_num}_{img_index}",
                    document_id=document_id,
                    page_number=page_num,
                    image_index=img_index,
                    image_path=str(image_path),
                    image_bytes=image_bytes,
                    image_format=base_image["ext"],
                    description="",  # Will be filled by Claude Vision
                    description_model="",
                    metadata=metadata,
                    context_text=context,
                )

                images.append(chunk)

            except Exception as e:
                logger.warning(
                    f"[IMAGE_EXTRACTOR] Failed to extract image {img_index} "
                    f"on page {page_num}: {e}"
                )
                continue

        return images

    def _get_image_bbox(self, page: fitz.Page, xref: int) -> list[float]:
        """Get bounding box of an image on the page.

        Args:
            page: PyMuPDF page object
            xref: Image cross-reference number

        Returns:
            Bounding box as [x0, y0, x1, y1]
        """
        # Find image rectangles on page
        for item in page.get_images():
            if item[0] == xref:
                # Try to get the image position
                try:
                    # Get all image blocks
                    blocks = page.get_images(full=True)
                    for block in blocks:
                        if block[0] == xref:
                            # block format: (xref, x, y, width, height)
                            return [block[1], block[2], block[1] + block[3], block[2] + block[4]]
                except Exception:
                    pass

        # Fallback: return page bbox
        rect = page.rect
        return [rect.x0, rect.y0, rect.x1, rect.y1]

    def _extract_context_around_image(
        self,
        page_text: str,
        img_bbox: list[float],
    ) -> str:
        """Extract text around an image for context.

        Args:
            page_text: Full page text
            img_bbox: Image bounding box [x0, y0, x1, y1]

        Returns:
            Context text before/after image
        """
        if not page_text:
            return ""

        # Simple approach: extract text around the image position
        # For more accurate results, use layout analysis

        # Split text into paragraphs
        paragraphs = [p.strip() for p in page_text.split("\n\n") if p.strip()]

        # Find paragraphs near the image (by vertical position)
        # This is a simplified approach - for production use layout-aware extraction

        # For now, just return first/last paragraphs as context
        if not paragraphs:
            return ""

        # Get context from beginning and end of page
        before = " ".join(paragraphs[:3]) if len(paragraphs) > 3 else ""
        after = " ".join(paragraphs[-3:]) if len(paragraphs) > 3 else ""

        parts = []
        if before:
            parts.append(before[:self._context_chars])
        if after and after != before:
            parts.append(after[:self._context_chars])

        return " ... ".join(parts)

    def extract_from_bytes(
        self,
        image_bytes: bytes,
        document_id: str = "",
        page_number: int = 0,
        image_index: int = 0,
        image_format: str = "png",
    ) -> ImageChunk:
        """Create an ImageChunk from raw bytes.

        Args:
            image_bytes: Raw image data
            document_id: Document ID
            page_number: Page number
            image_index: Image index on page
            image_format: Image format

        Returns:
            ImageChunk object
        """
        from PIL import Image

        # Get image dimensions
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        # Save image file
        image_filename = f"{document_id}_{page_number}_{image_index}.{image_format}"
        image_path = self._output_dir / image_filename
        image_path.write_bytes(image_bytes)

        # Create metadata
        metadata = ImageMetadata(
            page_number=page_number,
            image_index=image_index,
            width=width,
            height=height,
            format=image_format,
            size_bytes=len(image_bytes),
            extraction_method="bytes",
        )

        chunk = ImageChunk(
            id=f"{document_id}_img_{page_number}_{image_index}",
            document_id=document_id,
            page_number=page_number,
            image_index=image_index,
            image_path=str(image_path),
            image_bytes=image_bytes,
            image_format=image_format,
            description="",
            description_model="",
            metadata=metadata,
        )

        return chunk

    def clear_temp_images(self):
        """Remove all extracted image files."""
        if not self._output_dir.exists():
            return

        count = 0
        for file in self._output_dir.glob("*"):
            if file.is_file():
                file.unlink()
                count += 1

        logger.info(f"[IMAGE_EXTRACTOR] Cleared {count} temporary image files")


# Convenience function
def extract_images_from_pdf(
    pdf_path: str | Path,
    output_dir: str | Path | None = None,
    min_size: int = 50,
) -> list[ImageChunk]:
    """Extract all images from a PDF file.

    Args:
        pdf_path: Path to PDF file
        output_dir: Directory for extracted images
        min_size: Minimum image size in pixels

    Returns:
        List of ImageChunk objects
    """
    extractor = ImageExtractor(
        output_dir=Path(output_dir) if output_dir else None,
        min_image_size=min_size,
    )
    return extractor.extract_from_pdf(pdf_path)
