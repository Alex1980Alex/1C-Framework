"""Image schemas for multimodal RAG (Phase 15).

Defines Pydantic models for extracted images with Claude Vision descriptions.
Images are indexed alongside text chunks for unified semantic search.
"""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field


class ImageMetadata(BaseModel):
    """Metadata for an extracted image."""

    page_number: int = 0
    image_index: int = 0  # Nth image on this page
    width: int = 0
    height: int = 0
    format: str = ""  # "png", "jpeg", etc.
    size_bytes: int = 0
    bbox: list[float] = Field(default_factory=list)  # [x0, y0, x1, y1]
    extraction_method: str = "pymupdf"  # pymupdf, docling, etc.


class ImageChunk(BaseModel):
    """An image chunk with description for multimodal search.

    The image itself is stored as bytes or base64, while the description
    is used for semantic search. Original image can be retrieved for display.
    """

    id: str
    document_id: str
    page_number: int
    image_index: int

    # Image data
    image_path: str = ""  # Path to saved image file
    image_bytes: bytes = b""  # Optional: in-memory storage
    image_format: str = ""

    # Claude Vision description (for semantic search)
    description: str = ""
    description_model: str = ""
    description_timestamp: datetime = Field(default_factory=datetime.now)

    # Metadata
    metadata: ImageMetadata = Field(default_factory=ImageMetadata)
    caption: str = ""  # Caption from document (if available)
    context_text: str = ""  # Surrounding text before/after image

    # Search-related
    chunk_type: str = "image"  # Distinguishes from text chunks
    embedding: list[float] = Field(default_factory=list)  # Embedding of description

    @property
    def has_image(self) -> bool:
        """Check if image data is available."""
        return bool(self.image_path) or bool(self.image_bytes)

    def get_image_bytes(self) -> bytes | None:
        """Get image bytes for display/processing."""
        if self.image_bytes:
            return self.image_bytes
        if self.image_path:
            try:
                return Path(self.image_path).read_bytes()
            except Exception:
                return None
        return None


class ImageDescriptionRequest(BaseModel):
    """Request for Claude Vision image description."""

    image_bytes: bytes
    image_format: str
    page_number: int
    context: str = ""  # Surrounding text for better description
    prompt: str = "Describe this image in detail. What does it show? What information does it convey?"


class ImageDescriptionResponse(BaseModel):
    """Response from Claude Vision description."""

    description: str
    model_used: str
    timestamp: datetime | None = Field(default_factory=datetime.now)
    processing_time_ms: float = 0.0
    success: bool = True
    error_message: str = ""


class ProcessedImage(BaseModel):
    """A fully processed image with description and metadata."""

    chunk: ImageChunk
    description_response: ImageDescriptionResponse

    @property
    def search_content(self) -> str:
        """Content to use for semantic search (description + context)."""
        parts = [self.chunk.description]
        if self.chunk.caption:
            parts.append(f"Caption: {self.chunk.caption}")
        if self.chunk.context_text:
            parts.append(f"Context: {self.chunk.context_text[:200]}")
        return "\n\n".join(parts)
