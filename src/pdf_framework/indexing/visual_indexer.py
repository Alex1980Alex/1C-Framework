"""Visual Indexer for ColPali Retrieval (Phase 55).

Indexes PDF pages as visual embeddings using ColPali.
Stores multi-vector embeddings in Qdrant for visual similarity search.

Author: Claude Code
Version: 1.0.0 - Phase 55: ColPali Visual Retrieval
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from src.pdf_framework.embeddings.providers.colpali import ColPaliProvider
from src.pdf_framework.processing.page_renderer import (
    PageRenderer,
    RenderConfig,
    RenderDPI,
)

logger = logging.getLogger(__name__)


@dataclass
class VisualIndexConfig:
    """Configuration for visual indexing.

    Attributes:
        collection_name: Qdrant collection name for visual embeddings
        model_name: ColPali model name (colpali-v1.3/colqwen2-v1.0)
        render_dpi: DPI for page rendering
        batch_size: Batch size for embedding
        store_thumbnails: Store page thumbnails
        thumbnail_size: Size for stored thumbnails (width, height)
    """
    collection_name: str = "visual_pages"
    model_name: str = "colpali-v1.3"
    render_dpi: int = 150
    batch_size: int = 4
    store_thumbnails: bool = True
    thumbnail_size: tuple[int, int] = (400, 600)
    max_image_size: int = 1536  # Max dimension before downscaling


@dataclass
class VisualPage:
    """A visually indexed PDF page.

    Attributes:
        page_id: Unique page identifier
        document_id: Source document identifier
        page_number: Zero-based page number
        embedding: Multi-vector embedding (numpy array)
        thumbnail_path: Path to stored thumbnail (if saved)
        page_image: PIL Image (if in memory)
        indexed_at: Timestamp of indexing
        metadata: Additional metadata
    """
    page_id: str
    document_id: str
    page_number: int
    embedding: np.ndarray  # Shape: (n_tokens, dim)
    thumbnail_path: str | None = None
    page_image: Image.Image | None = None
    indexed_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """Convert to Qdrant point payload.

        Returns:
            Dictionary with page data for Qdrant storage
        """
        payload = {
            "page_id": self.page_id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "n_tokens": self.embedding.shape[0],
            "indexed_at": self.indexed_at.isoformat(),
            "has_thumbnail": self.thumbnail_path is not None,
        }

        if self.thumbnail_path:
            payload["thumbnail_path"] = self.thumbnail_path

        payload.update(self.metadata)

        return payload


class VisualIndexer:
    """Indexes PDF pages as visual embeddings.

    Workflow:
        1. Render PDF pages as images (PageRenderer)
        2. Generate ColPali embeddings (ColPaliProvider)
        3. Store in Qdrant collection
        4. Optional: save thumbnails

    Example:
        >>> indexer = VisualIndexer()
        >>> pages = indexer.index_pdf("document.pdf", document_id="doc123")
        >>> print(f"Indexed {len(pages)} pages")
    """

    def __init__(
        self,
        config: VisualIndexConfig | None = None,
        colpali_provider: ColPaliProvider | None = None,
        page_renderer: PageRenderer | None = None,
    ):
        """Initialize visual indexer.

        Args:
            config: Indexing configuration
            colpali_provider: ColPali provider (created if None)
            page_renderer: Page renderer (created if None)
        """
        self._config = config or VisualIndexConfig()
        self._colpali = colpali_provider
        self._renderer = page_renderer

        # Lazy-load dependencies
        if self._colpali is None:
            self._colpali = ColPaliProvider(
                model_name=self._config.model_name
            )

        if self._renderer is None:
            render_config = RenderConfig(
                dpi=self._config.render_dpi,
                max_width=self._config.max_image_size,
                max_height=self._config.max_image_size,
            )
            self._renderer = PageRenderer(config=render_config)

        logger.info(
            f"[VISUAL_INDEXER] Initialized: model={self._config.model_name}, "
            f"dpi={self._config.render_dpi}"
        )

    def index_pdf(
        self,
        pdf_path: str | Path,
        document_id: str,
        pages: list[int] | None = None,
        thumbnail_dir: str | Path | None = None,
    ) -> list[VisualPage]:
        """Index a PDF document as visual embeddings.

        Args:
            pdf_path: Path to PDF file
            document_id: Unique document identifier
            pages: Specific pages to index (None = all)
            thumbnail_dir: Directory for thumbnail storage

        Returns:
            List of indexed VisualPage objects
        """
        pdf_path = Path(pdf_path)
        logger.info(f"[VISUAL_INDEXER] Indexing {pdf_path.name} (doc={document_id})")

        # Render pages
        rendered = self._renderer.render_pages(pdf_path, pages=pages)

        if not rendered:
            logger.warning(f"[VISUAL_INDEXER] No pages rendered from {pdf_path}")
            return []

        logger.info(f"[VISUAL_INDEXER] Rendered {len(rendered)} pages")

        # Create VisualPage objects with embeddings
        indexed_pages = []

        for page_num, img in rendered:
            # Generate page ID
            page_id = f"{document_id}_page_{page_num:04d}"

            # Generate embedding
            embedding = self._colpali.embed_image(img)
            embedding_np = embedding.cpu().numpy()

            # Save thumbnail if enabled
            thumbnail_path = None
            if self._config.store_thumbnails and thumbnail_dir:
                thumbnail_path = self._save_thumbnail(
                    img, page_id, Path(thumbnail_dir)
                )

            # Create VisualPage
            visual_page = VisualPage(
                page_id=page_id,
                document_id=document_id,
                page_number=page_num,
                embedding=embedding_np,
                thumbnail_path=thumbnail_path,
                page_image=img,
                metadata={
                    "pdf_name": pdf_path.name,
                    "image_size": img.size,
                    "dpi": self._config.render_dpi,
                },
            )

            indexed_pages.append(visual_page)

        logger.info(
            f"[VISUAL_INDEXER] Indexed {len(indexed_pages)} pages "
            f"from {pdf_path.name}"
        )

        return indexed_pages

    def index_page(
        self,
        image: Image.Image,
        document_id: str,
        page_number: int,
        page_id: str | None = None,
    ) -> VisualPage:
        """Index a single page image.

        Args:
            image: PIL Image of the page
            document_id: Document identifier
            page_number: Page number
            page_id: Optional custom page ID

        Returns:
            VisualPage object with embedding
        """
        if page_id is None:
            page_id = f"{document_id}_page_{page_number:04d}"

        # Generate embedding
        embedding = self._colpali.embed_image(image)
        embedding_np = embedding.cpu().numpy()

        return VisualPage(
            page_id=page_id,
            document_id=document_id,
            page_number=page_number,
            embedding=embedding_np,
            page_image=image,
            metadata={"image_size": image.size},
        )

    def _save_thumbnail(
        self,
        image: Image.Image,
        page_id: str,
        thumbnail_dir: Path,
    ) -> str:
        """Save a thumbnail image.

        Args:
            image: PIL Image
            page_id: Page identifier
            thumbnail_dir: Thumbnail directory

        Returns:
            Path to saved thumbnail
        """
        thumbnail_dir.mkdir(parents=True, exist_ok=True)

        # Create thumbnail
        thumbnail = image.copy()
        thumbnail.thumbnail(self._config.thumbnail_size, Image.Resampling.LANCZOS)

        # Save
        thumbnail_path = thumbnail_dir / f"{page_id}.jpg"
        thumbnail.save(thumbnail_path, "JPEG", quality=85)

        return str(thumbnail_path)

    def search(
        self,
        query: str,
        indexed_pages: list[VisualPage],
        top_k: int = 10,
    ) -> list[tuple[VisualPage, float]]:
        """Search indexed pages by visual similarity.

        Args:
            query: Text query
            indexed_pages: List of indexed pages to search
            top_k: Return top K results

        Returns:
            List of (VisualPage, score) tuples, sorted by score
        """
        if not indexed_pages:
            return []

        # Embed query
        query_vectors = self._colpali.embed_query(query)

        # Compute scores
        scores = []
        for page in indexed_pages:
            doc_vectors = torch.from_numpy(page.embedding).to(
                self._colpali.model.device
            )
            score = self._colpali.late_interaction_score(
                query_vectors, doc_vectors
            )
            scores.append((page, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

    def get_collection_schema(self) -> dict[str, Any]:
        """Get Qdrant collection schema for visual embeddings.

        Returns:
            Dictionary with collection configuration
        """
        dim = self._colpali.dimensions

        return {
            "name": self._config.collection_name,
            "vectors_config": {
                "size": dim,
                "distance": "Cosine",
            },
            "optimizers_config": {
                "indexing_threshold": 10000,
            },
            "quantization_config": {
                "product": {
                    "compression": "x32",
                },
            },
        }


def create_visual_indexer(
    model_name: str = "colpali-v1.3",
    dpi: int = 150,
    collection_name: str = "visual_pages",
) -> VisualIndexer:
    """Factory function to create visual indexer.

    Args:
        model_name: ColPali model name
        dpi: DPI for page rendering
        collection_name: Qdrant collection name

    Returns:
        Configured VisualIndexer instance
    """
    config = VisualIndexConfig(
        model_name=model_name,
        render_dpi=dpi,
        collection_name=collection_name,
    )
    return VisualIndexer(config=config)


# Import torch for search method
import torch
