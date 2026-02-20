"""ColPali Visual Retrieval Provider (Phase 55).

End-to-end visual retrieval without OCR. Embed PDF pages as images
and search by visual similarity using ColPali/ColQwen2 models.

Models supported:
- vidore/colpali-v1.3 (2B params)
- vidore/colqwen2-v1.0 (7B params)

Author: Claude Code
Version: 1.0.0 - Phase 55: ColPali Visual Retrieval
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from PIL import Image

logger = logging.getLogger(__name__)


# Supported models with their configurations
COLPALI_MODELS = {
    "colpali-v1.3": {
        "model_id": "vidore/colpali-v1.3",
        "dim": 128,
        "multi_vector": True,
        "params": "2B",
    },
    "colqwen2-v1.0": {
        "model_id": "vidore/colqwen2-v1.0",
        "dim": 128,
        "multi_vector": True,
        "params": "7B",
    },
}


class ColPaliProvider:
    """ColPali visual embedding provider for end-to-end visual retrieval.

    Generates multi-vector embeddings for images and text queries using
    ColPali's late interaction mechanism. Eliminates need for OCR.

    Example:
        >>> provider = ColPaliProvider(model_name="colpali-v1.3")
        >>> image = Image.open("page.png")
        >>> doc_vectors = provider.embed_image(image)  # (N, dim)
        >>> query_vectors = provider.embed_query("find table with revenue")
        >>> score = provider.late_interaction_score(query_vectors, doc_vectors)
    """

    def __init__(
        self,
        model_name: str = "colpali-v1.3",
        device: str | None = None,
        torch_dtype: str | None = None,
        cache_dir: str | Path | None = None,
    ):
        """Initialize ColPali provider.

        Args:
            model_name: Model name (colpali-v1.3 or colqwen2-v1.0)
            device: Device to use (cuda/cpu, auto-detected if None)
            torch_dtype: Torch dtype (float16/float32, auto-detected if None)
            cache_dir: Directory for model cache
        """
        if model_name not in COLPALI_MODELS:
            raise ValueError(
                f"Unknown model: {model_name}. "
                f"Supported: {list(COLPALI_MODELS.keys())}"
            )

        self._model_name = model_name
        self._model_config = COLPALI_MODELS[model_name]
        self._cache_dir = Path(cache_dir) if cache_dir else None

        # Auto-detect device
        if device is None:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = device

        # Auto-detect dtype
        if torch_dtype is None:
            self._dtype = torch.float16 if self._device == "cuda" else torch.float32
        else:
            self._dtype = getattr(torch, torch_dtype)

        logger.info(
            f"[COLPALI] Initializing {model_name} on {self._device} "
            f"({self._model_config['params']} params)"
        )

        self._model = None
        self._processor = None

    @property
    def model(self) -> Any:
        """Lazy-load the model."""
        if self._model is None:
            self._load_model()
        return self._model

    @property
    def processor(self) -> Any:
        """Lazy-load the processor."""
        if self._processor is None:
            self._load_model()
        return self._processor

    @property
    def dimensions(self) -> int:
        """Return embedding dimension."""
        return self._model_config["dim"]

    @property
    def is_multi_vector(self) -> bool:
        """Return True if model uses multi-vector embeddings."""
        return self._model_config["multi_vector"]

    def _load_model(self):
        """Load ColPali model and processor."""
        try:
            from colpali_engine.models import ColPali

            model_kwargs = {
                "torch_dtype": self._dtype,
                "device_map": self._device,
            }

            if self._cache_dir:
                model_kwargs["cache_dir"] = str(self._cache_dir)

            self._model = ColPali.from_pretrained(
                self._model_config["model_id"],
                **model_kwargs,
            )
            self._model.eval()

            # Load processor
            from transformers import AutoProcessor

            self._processor = AutoProcessor.from_pretrained(
                self._model_config["model_id"]
            )

            logger.info(f"[COLPALI] Model loaded: {self._model_config['model_id']}")

        except ImportError as e:
            raise ImportError(
                "colpali-engine not installed. "
                "Install with: pip install colpali-engine transformers[torch]"
            ) from e
        except Exception as e:
            logger.error(f"[COLPALI] Failed to load model: {e}")
            raise

    def embed_image(
        self,
        image: Image.Image | str | Path,
        batch_size: int = 4,
    ) -> torch.Tensor:
        """Generate multi-vector embedding for an image.

        Args:
            image: PIL Image or path to image file
            batch_size: Batch size for processing (if multiple images)

        Returns:
            Multi-vector embedding tensor of shape (N, dim) where N is the
            number of visual tokens (typically 100-500 depending on image size)

        Example:
            >>> vectors = provider.embed_image(page_image)
            >>> print(vectors.shape)  # torch.Size([256, 128])
        """
        # Load image if path provided
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")

        # Ensure RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Process with torch.no_grad() for memory efficiency
        with torch.no_grad():
            # Prepare inputs
            inputs = self.processor(images=image, return_tensors="pt")
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            # Generate embeddings
            outputs = self.model(**inputs)

            # Extract multi-vector embeddings
            # ColPali returns (batch, n_tokens, dim)
            embeddings = outputs.embeddings[0]  # (n_tokens, dim)

        return embeddings

    def embed_images(
        self,
        images: list[Image.Image] | list[str | Path],
        batch_size: int = 4,
    ) -> list[torch.Tensor]:
        """Generate embeddings for multiple images.

        Args:
            images: List of PIL Images or paths
            batch_size: Batch size for processing

        Returns:
            List of multi-vector embedding tensors
        """
        results = []

        for i in range(0, len(images), batch_size):
            batch = images[i : i + batch_size]

            # Load images if paths provided
            pil_images = []
            for img in batch:
                if isinstance(img, (str, Path)):
                    pil_images.append(Image.open(img).convert("RGB"))
                else:
                    pil_images.append(img)

            # Process batch
            with torch.no_grad():
                inputs = self.processor(images=pil_images, return_tensors="pt")
                inputs = {k: v.to(self._device) for k, v in inputs.items()}

                outputs = self.model(**inputs)

                # Extract embeddings for each image in batch
                for j in range(len(batch)):
                    results.append(outputs.embeddings[j])

            # Clear cache to avoid OOM on CPU
            if self._device == "cpu":
                torch.cuda.empty_cache() if torch.cuda.is_available() else None

        logger.debug(f"[COLPALI] Embedded {len(results)} images")
        return results

    def embed_query(self, query: str) -> torch.Tensor:
        """Generate embedding for a text query.

        Args:
            query: Text query string

        Returns:
            Multi-vector embedding tensor of shape (N, dim)

        Example:
            >>> query_vectors = provider.embed_query("table showing revenue")
            >>> print(query_vectors.shape)  # torch.Size([32, 128])
        """
        with torch.no_grad():
            # Prepare inputs
            inputs = self.processor(text=query, return_tensors="pt")
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            # Generate embeddings
            outputs = self.model(**inputs)

            # Extract query embeddings
            embeddings = outputs.embeddings[0]

        return embeddings

    def late_interaction_score(
        self,
        query_vectors: torch.Tensor,
        doc_vectors: torch.Tensor,
    ) -> float:
        """Calculate MaxSim late interaction score.

        Score = mean of max similarities between each query vector
        and all document vectors.

        Args:
            query_vectors: Query embeddings (q_tokens, dim)
            doc_vectors: Document embeddings (d_tokens, dim)

        Returns:
            Similarity score (higher = more relevant)

        Example:
            >>> score = provider.late_interaction_score(query_vecs, doc_vecs)
            >>> print(score)  # 0.7234
        """
        # Compute cosine similarity matrix
        # Shape: (q_tokens, d_tokens)
        sim_matrix = torch.nn.functional.normalize(query_vectors, dim=-1) @ torch.nn.functional.normalize(
            doc_vectors, dim=-1
        ).T

        # MaxSim: take max similarity for each query token
        max_sim = sim_matrix.max(dim=1).values

        # Return mean as final score
        return max_sim.mean().item()

    def compute_scores(
        self,
        query_vectors: torch.Tensor,
        docs_vectors: list[torch.Tensor],
    ) -> list[float]:
        """Compute scores for query against multiple documents.

        Args:
            query_vectors: Query embeddings
            docs_vectors: List of document embeddings

        Returns:
            List of similarity scores
        """
        scores = []

        for doc_vecs in docs_vectors:
            score = self.late_interaction_score(query_vectors, doc_vecs)
            scores.append(score)

        return scores

    def rank_documents(
        self,
        query: str,
        docs_vectors: list[torch.Tensor],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Rank documents by query similarity.

        Args:
            query: Text query
            docs_vectors: List of document embeddings
            top_k: Return top K results

        Returns:
            List of (doc_index, score) tuples, sorted by score descending
        """
        query_vectors = self.embed_query(query)
        scores = self.compute_scores(query_vectors, docs_vectors)

        # Sort by score descending
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        return ranked[:top_k]

    def offload_model(self):
        """Offload model from GPU to CPU memory (for GPU inference).

        Useful for freeing GPU memory when model is not in use.
        """
        if self._device == "cuda" and self._model is not None:
            self._model.cpu()
            torch.cuda.empty_cache()
            logger.debug("[COLPALI] Model offloaded to CPU")

    def reload_model(self):
        """Reload model back to GPU (after offloading)."""
        if self._device == "cuda" and self._model is not None:
            self._model.to(self._device)
            logger.debug("[COLPALI] Model reloaded to GPU")

    @classmethod
    def get_supported_models(cls) -> dict[str, dict[str, Any]]:
        """Get supported model configurations.

        Returns:
            Dictionary mapping model names to their configs
        """
        return COLPALI_MODELS.copy()


def create_colpali_provider(
    model_name: str = "colpali-v1.3",
    device: str | None = None,
) -> ColPaliProvider:
    """Factory function to create ColPali provider.

    Args:
        model_name: Model name (colpali-v1.3 or colqwen2-v1.0)
        device: Device override (auto-detected if None)

    Returns:
        Configured ColPaliProvider instance
    """
    return ColPaliProvider(model_name=model_name, device=device)


# Cache for provider instances (useful for singleton pattern)
@lru_cache(maxsize=2)
def get_cached_colpali_provider(model_name: str = "colpali-v1.3") -> ColPaliProvider:
    """Get cached ColPali provider instance.

    Args:
        model_name: Model name

    Returns:
        Cached ColPaliProvider instance
    """
    return create_colpali_provider(model_name=model_name)
