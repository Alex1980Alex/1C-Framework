"""Image Processor for Multimodal RAG (Phase 15).

Combines image extraction, Claude Vision description, and embedding generation.
Creates image chunks that are indexed alongside text chunks for unified search.

Author: Claude Code
Version: 1.0.0 - Phase 15: Image Understanding
"""

import logging
from pathlib import Path
from typing import Any

from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.embeddings.vision import ImageDescriber
from src.pdf_framework.loaders.image_extractor import ImageExtractor
from src.pdf_framework.schemas.images import (
    ImageChunk,
    ImageDescriptionRequest,
    ImageDescriptionResponse,
    ProcessedImage,
)

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Process images: extract, describe, and embed for search.

    Workflow:
        1. Extract images from PDF (ImageExtractor)
        2. Generate descriptions (Claude Vision)
        3. Create embeddings (Embedding model)
        4. Return ProcessedImage chunks for indexing
    """

    def __init__(
        self,
        describer: ImageDescriber | None = None,
        embedder: BaseEmbeddingEngine | None = None,
        extractor: ImageExtractor | None = None,
        enable_description: bool = True,
        enable_embedding: bool = True,
    ):
        """Initialize the image processor.

        Args:
            describer: Claude Vision describer (created if None)
            embedder: Embedding model for descriptions (created if None)
            extractor: Image extractor (created if None)
            enable_description: Enable Claude Vision description
            enable_embedding: Enable embedding generation
        """
        self._describer = describer
        self._embedder = embedder
        self._extractor = extractor or ImageExtractor()
        self._enable_description = enable_description
        self._enable_embedding = enable_embedding

    def process_pdf(
        self,
        pdf_path: str | Path,
        document_id: str = "",
        max_images: int | None = None,
    ) -> list[ProcessedImage]:
        """Extract and describe all images from a PDF.

        Args:
            pdf_path: Path to PDF file
            document_id: Document ID for chunks
            max_images: Maximum images to process

        Returns:
            List of ProcessedImage objects with descriptions
        """
        # Extract images
        logger.info(f"[IMAGE_PROCESSOR] Extracting images from {Path(pdf_path).name}")
        images = self._extractor.extract_from_pdf(
            pdf_path, document_id=document_id, max_images=max_images
        )

        if not images:
            logger.info(f"[IMAGE_PROCESSOR] No images found in {Path(pdf_path).name}")
            return []

        # Describe images
        if self._enable_description and self._describer:
            logger.info(f"[IMAGE_PROCESSOR] Describing {len(images)} images with Claude Vision")
            descriptions = self._describe_batch(images)
        else:
            descriptions = [ImageDescriptionResponse(
                description="[Description disabled]",
                model_used="none",
                success=True,
            ) for _ in images]

        # Create processed images
        processed: list[ProcessedImage] = []
        for img, desc in zip(images, descriptions):
            img.description = desc.description
            img.description_model = desc.model_used

            # Generate embedding if enabled
            if self._enable_embedding and self._embedder:
                img.embedding = self._embed_description(desc.description)

            processed.append(ProcessedImage(chunk=img, description_response=desc))

        logger.info(
            f"[IMAGE_PROCESSOR] Processed {len(processed)} images: "
            f"{sum(1 for p in processed if p.description_response.success)} successful"
        )

        return processed

    def process_from_chunks(
        self,
        image_chunks: list[ImageChunk],
    ) -> list[ProcessedImage]:
        """Process pre-extracted image chunks.

        Args:
            image_chunks: List of ImageChunk objects

        Returns:
            List of ProcessedImage objects
        """
        if not image_chunks:
            return []

        # Describe images
        if self._enable_description and self._describer:
            descriptions = self._describe_batch(image_chunks)
        else:
            descriptions = [ImageDescriptionResponse(
                description="[Description disabled]",
                model_used="none",
                success=True,
            ) for _ in image_chunks]

        # Create processed images
        processed: list[ProcessedImage] = []
        for img, desc in zip(image_chunks, descriptions):
            img.description = desc.description
            img.description_model = desc.model_used

            if self._enable_embedding and self._embedder:
                img.embedding = self._embed_description(desc.description)

            processed.append(ProcessedImage(chunk=img, description_response=desc))

        return processed

    def _describe_batch(
        self,
        images: list[ImageChunk],
    ) -> list[ImageDescriptionResponse]:
        """Describe multiple images in batch.

        Args:
            images: List of ImageChunk objects

        Returns:
            List of description responses
        """
        if not self._describer:
            return []

        # Build description requests
        requests = [
            ImageDescriptionRequest(
                image_bytes=img.get_image_bytes() or b"",
                image_format=img.image_format,
                page_number=img.page_number,
                context=img.context_text,
                prompt="Describe this image in detail. What does it show?",
            )
            for img in images
            if img.get_image_bytes()
        ]

        if not requests:
            return []

        # Describe in parallel
        responses = self._describer.describe_batch(requests, parallel=True)

        return responses

    async def _embed_description(self, description: str) -> list[float]:
        """Generate embedding for image description.

        Args:
            description: Image description text

        Returns:
            Embedding vector
        """
        if not self._embedder:
            return []

        try:
            return await self._embedder.embed_text(description)
        except Exception as e:
            logger.warning(f"[IMAGE_PROCESSOR] Failed to embed description: {e}")
            return []

    def get_searchable_content(self, processed: ProcessedImage) -> str:
        """Get searchable text content from processed image.

        Args:
            processed: ProcessedImage object

        Returns:
            Text for semantic search
        """
        return processed.search_content

    def to_document_chunks(
        self,
        processed_images: list[ProcessedImage],
        document_id: str = "",
    ) -> list[dict[str, Any]]:
        """Convert processed images to document chunk format for indexing.

        Args:
            processed_images: List of ProcessedImage objects
            document_id: Document ID

        Returns:
            List of chunk dictionaries for vector store
        """
        chunks = []

        for proc in processed_images:
            img = proc.chunk

            chunk_dict = {
                "id": img.id,
                "content": proc.search_content,
                "document_id": document_id or img.document_id,
                "page_number": img.page_number,
                "section": "image",
                "chunk_index": img.image_index,
                "metadata": {
                    "chunk_type": "image",
                    "image_path": img.image_path,
                    "image_format": img.image_format,
                    "image_size": img.metadata.size_bytes,
                    "page_number": img.page_number,
                    "image_index": img.image_index,
                    "description_model": img.description_model,
                    "caption": img.caption,
                    "width": img.metadata.width,
                    "height": img.metadata.height,
                },
            }

            # Add embedding if available
            if img.embedding:
                chunk_dict["embedding"] = img.embedding

            chunks.append(chunk_dict)

        return chunks


def create_image_processor(
    api_key: str = "",
    embedding_model: str = "intfloat/multilingual-e5-large",
    vision_model: str = "claude-sonnet-4-5-20250929",
    output_dir: str | Path | None = None,
) -> ImageProcessor:
    """Factory function to create a fully configured ImageProcessor.

    Args:
        api_key: Anthropic API key (empty = use env)
        embedding_model: Embedding model name
        vision_model: Claude Vision model name
        output_dir: Directory for extracted images

    Returns:
        Configured ImageProcessor instance
    """
    # Create describer
    describer = ImageDescriber(
        api_key=api_key,
        model=vision_model,
    )

    # Create embedder
    from src.pdf_framework.embeddings import get_embedding
    embedder = get_embedding(model=embedding_model)

    # Create extractor
    extractor = ImageExtractor(output_dir=Path(output_dir) if output_dir else None)

    return ImageProcessor(
        describer=describer,
        embedder=embedder,
        extractor=extractor,
    )
