"""Image extraction and description using Claude Vision (Phase 10).

Extracts images from PDF and generates text descriptions via Claude Vision API.

Author: Claude Code
Version: 1.1.0 - Phase 10.4: Image Understanding
"""

import base64
import hashlib
import logging
from pathlib import Path
from typing import Literal

from anthropic import Anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ImageDescription(BaseModel):
    """Image with text description from Claude Vision."""

    image_bytes: bytes = Field(description="Raw image data")
    description: str = Field(description="Text description from Claude Vision")
    page_number: int = Field(description="Page number where image was found")
    bbox: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Bounding box on page"
    )
    image_format: str = Field(description="Image format (png, jpeg, etc.)")
    size: tuple[int, int] = Field(description="Image size (width, height) in pixels")
    description_model: str = Field(description="Claude model used for description")

    def to_markdown_chunk(self) -> str:
        """Convert to markdown chunk for embedding."""
        return f"[Image on page {self.page_number}]\n{self.description}"

    def to_dict(self) -> dict:
        """Convert to dictionary (excluding binary data)."""
        return {
            "description": self.description,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "image_format": self.image_format,
            "size": self.size,
            "description_model": self.description_model,
        }


class ImageExtractor:
    """
    Extracts images from PDF and generates descriptions using Claude Vision.

    Features:
    - Image extraction via PyMuPDF
    - Size filtering (skip decorative icons)
    - Claude Vision description generation
    - Description caching
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        min_size: int = 50,  # pixels
        max_size: int = 4096,  # pixels (limit for Vision API)
        cache_enabled: bool = True,
    ):
        """
        Initialize image extractor.

        Args:
            api_key: Anthropic API key
            model: Claude model for Vision API
            min_size: Minimum image dimension (filters icons)
            max_size: Maximum image dimension (will resize)
            cache_enabled: Enable description caching
        """
        self._api_key = api_key
        self._model = model
        self._min_size = min_size
        self._max_size = max_size
        self._cache_enabled = cache_enabled

        self._client = Anthropic(api_key=api_key) if api_key else None
        self._description_cache: dict[str, str] = {}

        # Check if PyMuPDF is available
        self._pymupdf_available = self._check_pymupdf()

        if not self._pymupdf_available:
            logger.warning("[IMAGE] PyMuPDF not available")

    @staticmethod
    def _check_pymupdf() -> bool:
        """Check if PyMuPDF is available."""
        try:
            import fitz  # PyMuPDF
            return True
        except ImportError:
            return False

    def has_vision_support(self) -> bool:
        """Check if Vision API is available."""
        return bool(self._api_key) and self._client is not None

    async def extract_all(
        self,
        pdf_path: str | Path,
    ) -> list[ImageDescription]:
        """
        Extract and describe all images from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of ImageDescription objects
        """
        if not self._pymupdf_available:
            return []

        import fitz  # PyMuPDF

        descriptions = []

        with fitz.open(str(pdf_path)) as doc:
            for page_num, page in enumerate(doc, start=1):
                page_images = await self._extract_from_page(page, page_num)
                descriptions.extend(page_images)

        logger.info(f"[IMAGE] Extracted {len(descriptions)} images from PDF")

        return descriptions

    async def extract_from_page(
        self,
        pdf_path: str | Path,
        page_number: int,
    ) -> list[ImageDescription]:
        """
        Extract and describe images from specific page.

        Args:
            pdf_path: Path to PDF file
            page_number: Page number (1-based)

        Returns:
            List of ImageDescription objects
        """
        if not self._pymupdf_available:
            return []

        import fitz  # PyMuPDF

        with fitz.open(str(pdf_path)) as doc:
            if page_number < 1 or page_number > len(doc):
                return []

            page = doc[page_number - 1]
            return await self._extract_from_page(page, page_number)

    async def _extract_from_page(
        self,
        page,
        page_number: int,
    ) -> list[ImageDescription]:
        """Extract images from a single PyMuPDF page."""
        descriptions = []

        # Get image references
        image_list = page.get_images()

        for img_index, img in enumerate(image_list):
            try:
                # Extract image
                xref = img[0]
                base_image = page.parent.extract_image(xref)

                if not base_image:
                    continue

                image_bytes = base_image["image"]
                image_format = base_image.get("ext", "png")

                # Check image size
                import io
                from PIL import Image

                pil_image = Image.open(io.BytesIO(image_bytes))
                width, height = pil_image.size

                # Filter small images (icons, decorative elements)
                if width < self._min_size or height < self._min_size:
                    logger.debug(f"[IMAGE] Skipping small image: {width}x{height}")
                    continue

                # Resize if too large
                if width > self._max_size or height > self._max_size:
                    pil_image.thumbnail((self._max_size, self._max_size))
                    output = io.BytesIO()
                    pil_image.save(output, format=image_format)
                    image_bytes = output.getvalue()

                # Generate description
                description = await self._describe_image(image_bytes)

                descriptions.append(ImageDescription(
                    image_bytes=image_bytes,
                    description=description,
                    page_number=page_number,
                    bbox=None,  # Could calculate from image position
                    image_format=image_format,
                    size=(width, height),
                    description_model=self._model,
                ))

            except Exception as e:
                logger.warning(f"[IMAGE] Error extracting image {img_index}: {e}")

        return descriptions

    async def describe_image(self, image_bytes: bytes) -> str:
        """
        Generate text description of image using Claude Vision.

        Args:
            image_bytes: Raw image data

        Returns:
            Text description
        """
        if not self.has_vision_support():
            return "[Image description not available - no API key]"

        # Check cache
        if self._cache_enabled:
            cache_key = hashlib.md5(image_bytes).hexdigest()
            if cache_key in self._description_cache:
                logger.debug("[IMAGE] Using cached description")
                return self._description_cache[cache_key]

        # Encode image to base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Determine media type
        media_type = self._guess_media_type(image_bytes)

        try:
            message = {
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
                        "text": (
                            "Describe this image in the context of a technical document. "
                            "Focus on what information it conveys - text content, "
                            "diagrams, charts, or structural elements. Be concise."
                        ),
                    },
                ],
            }

            response = self._client.messages.create(
                model=self._model,
                max_tokens=512,
                messages=[message],
            )

            description = response.content[0].text.strip()

            # Cache description
            if self._cache_enabled:
                self._description_cache[cache_key] = description

            return description

        except Exception as e:
            logger.error(f"[IMAGE] Vision API error: {e}")
            return "[Image description failed]"

    def _guess_media_type(self, image_bytes: bytes) -> str:
        """Guess media type from image bytes."""
        # Check for common magic numbers
        if image_bytes.startswith(b"\x89PNG"):
            return "image/png"
        elif image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        elif image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
            return "image/gif"
        elif image_bytes.startswith(b"WEBP", 0, 4):
            return "image/webp"
        else:
            return "image/png"  # Default

    def descriptions_to_chunks(
        self,
        descriptions: list[ImageDescription],
        document_id: str = "unknown",
    ) -> list[dict]:
        """
        Convert image descriptions to chunks for embedding.

        Args:
            descriptions: List of ImageDescription objects
            document_id: Document identifier

        Returns:
            List of chunk dicts with content and metadata
        """
        chunks = []

        for img_desc in descriptions:
            chunks.append({
                "content": img_desc.to_markdown_chunk(),
                "metadata": {
                    "element_type": "image",
                    "page_number": img_desc.page_number,
                    "bbox": img_desc.bbox,
                    "image_data": img_desc.to_dict(),
                    "chunk_type": "image",
                    "document_id": document_id,
                },
            })

        return chunks

    def clear_cache(self) -> None:
        """Clear description cache."""
        self._description_cache.clear()
