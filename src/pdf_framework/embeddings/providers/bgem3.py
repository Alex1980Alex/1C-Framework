"""BGE-M3 Unified Embedding Provider (Phase 56).

BGE-M3 is a unified model that generates dense, sparse, and ColBERT
embeddings simultaneously. Simplifies architecture by replacing 3 separate models.

Model: BAAI/bge-m3
- Dense: 1024 dimensions
- Sparse: up to 250k vocabulary
- ColBERT: multi-token vectors

Author: Claude Code
Version: 1.0.0 - Phase 56: BGE-M3 Unified Model
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)


@dataclass
class BGEM3Output:
    """Output from BGE-M3 embedding generation.

    Attributes:
        dense: Dense embedding vector (1024-dim)
        sparse: Sparse embedding dict (token_id → weight)
        colbert: ColBERT multi-token vectors
    """
    dense: list[float] | np.ndarray | None = None
    sparse: dict[int, float] | None = None
    colbert: list[list[float]] | np.ndarray | None = None


class BGEM3Provider:
    """BGE-M3 unified embedding provider.

    Generates three types of embeddings in a single forward pass:
    1. Dense vectors for semantic similarity (1024-dim)
    2. Sparse vectors for exact keyword matching (BM25-like)
    3. ColBERT multi-vectors for fine-grained similarity

    Example:
        >>> provider = BGEM3Provider()
        >>> output = provider.embed_multi("example text")
        >>> print(output.dense.shape)  # (1024,)
        >>> print(len(output.sparse))  # ~50-100 tokens
        >>> print(output.colbert.shape)  # (n_tokens, 1024)
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str | None = None,
        batch_size: int = 256,
        cache_dir: str | None = None,
    ):
        """Initialize BGE-M3 provider.

        Args:
            model_name: HuggingFace model name
            device: Device to use (cuda/cpu, auto-detected if None)
            batch_size: Batch size for embedding
            cache_dir: Model cache directory
        """
        self._model_name = model_name
        self._batch_size = batch_size
        self._cache_dir = cache_dir

        # Auto-detect device
        if device is None:
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self._device = device

        self._model = None
        self._tokenizer = None

        logger.info(
            f"[BGE-M3] Initializing {model_name} on {self._device}"
        )

    @property
    def model(self) -> Any:
        """Lazy-load the model."""
        if self._model is None:
            self._load_model()
        return self._model

    @property
    def tokenizer(self) -> Any:
        """Lazy-load the tokenizer."""
        if self._tokenizer is None:
            self._load_model()
        return self._tokenizer

    @property
    def dimensions(self) -> int:
        """Return dense embedding dimension."""
        return 1024

    def _load_model(self):
        """Load BGE-M3 model and tokenizer."""
        try:
            from FlagEmbedding import BGEM3FlagModel

            self._model = BGEM3FlagModel(
                self._model_name,
                device=self._device,
                cache_dir=self._cache_dir,
            )

            logger.info(f"[BGE-M3] Model loaded: {self._model_name}")

        except ImportError:
            raise ImportError(
                "FlagEmbedding is not installed. "
                "Install with: pip install -U FlagEmbedding"
            )
        except Exception as e:
            logger.error(f"[BGE-M3] Failed to load model: {e}")
            raise

    def embed_dense(
        self,
        texts: list[str] | str,
    ) -> list[list[float]] | list[float]:
        """Generate dense embeddings.

        Args:
            texts: Single text or list of texts

        Returns:
            Dense embeddings (1024-dim each)

        Example:
            >>> vectors = provider.embed_dense("example text")
            >>> print(len(vectors))  # 1024
        """
        single = isinstance(texts, str)
        if single:
            texts = [texts]

        with torch.no_grad():
            output = self.model.encode(
                texts,
                batch_size=self._batch_size,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )["dense_vecs"]

        # Convert to list
        result = output.tolist()

        return result[0] if single else result

    def embed_sparse(
        self,
        texts: list[str] | str,
    ) -> list[dict[int, float]] | dict[int, float]:
        """Generate sparse embeddings (lexical weights).

        Args:
            texts: Single text or list of texts

        Returns:
            Sparse embeddings as {token_id: weight} dicts

        Example:
            >>> sparse = provider.embed_sparse("machine learning")
            >>> print(list(sparse.keys())[:5])  # Token IDs
        """
        single = isinstance(texts, str)
        if single:
            texts = [texts]

        with torch.no_grad():
            output = self.model.encode(
                texts,
                batch_size=self._batch_size,
                return_dense=False,
                return_sparse=True,
                return_colbert_vecs=False,
            )["lexical_weights"]

        # Convert list of dicts
        result = output

        return result[0] if single else result

    def embed_colbert(
        self,
        texts: list[str] | str,
    ) -> list[list[list[float]]] | list[list[float]]:
        """Generate ColBERT multi-token embeddings.

        Args:
            texts: Single text or list of texts

        Returns:
            ColBERT embeddings (n_tokens, 1024) each

        Example:
            >>> colbert = provider.embed_colbert("short text")
            >>> print(len(colbert))  # n_tokens (~3-5)
            >>> print(len(colbert[0]))  # 1024
        """
        single = isinstance(texts, str)
        if single:
            texts = [texts]

        with torch.no_grad():
            output = self.model.encode(
                texts,
                batch_size=self._batch_size,
                return_dense=False,
                return_sparse=False,
                return_colbert_vecs=True,
            )["colbert_vecs"]

        # Convert to list
        result = [vec.tolist() for vec in output]

        return result[0] if single else result

    def embed_multi(
        self,
        texts: list[str] | str,
    ) -> BGEM3Output | list[BGEM3Output]:
        """Generate all three embedding types simultaneously.

        This is the most efficient method as it computes all embeddings
        in a single forward pass.

        Args:
            texts: Single text or list of texts

        Returns:
            BGEM3Output with dense, sparse, and colbert embeddings

        Example:
            >>> output = provider.embed_multi("example text")
            >>> print(output.dense.shape)  # (1024,)
            >>> print(len(output.sparse))  # ~50-100 tokens
            >>> print(len(output.colbert))  # n_tokens
        """
        single = isinstance(texts, str)
        if single:
            texts = [texts]

        with torch.no_grad():
            result = self.model.encode(
                texts,
                batch_size=self._batch_size,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=True,
            )

        outputs = []
        for i in range(len(texts)):
            outputs.append(BGEM3Output(
                dense=result["dense_vecs"][i].tolist(),
                sparse=result["lexical_weights"][i],
                colbert=result["colbert_vecs"][i].tolist(),
            ))

        return outputs[0] if single else outputs

    async def embed_text(self, text: str) -> list[float]:
        """Generate dense embedding for a single text (async compatibility).

        Args:
            text: Input text

        Returns:
            Dense embedding vector (1024-dim)
        """
        result = self.embed_multi(text)
        return result.dense if isinstance(result.dense, list) else result.dense.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate dense embeddings for a batch of texts (async compatibility).

        Args:
            texts: List of input texts

        Returns:
            List of dense embedding vectors
        """
        outputs = self.embed_multi(texts)
        return [
            out.dense if isinstance(out.dense, list) else out.dense.tolist()
            for out in outputs
        ]

    def get_model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    def get_dimensions(self) -> int:
        """Return dense embedding dimension."""
        return self.dimensions


def create_bgem3_provider(
    model_name: str = "BAAI/bge-m3",
    device: str | None = None,
) -> BGEM3Provider:
    """Factory function to create BGE-M3 provider.

    Args:
        model_name: HuggingFace model name
        device: Device override (auto-detected if None)

    Returns:
        Configured BGEM3Provider instance
    """
    return BGEM3Provider(model_name=model_name, device=device)


# Cache for provider instances
@lru_cache(maxsize=1)
def get_cached_bgem3_provider(model_name: str = "BAAI/bge-m3") -> BGEM3Provider:
    """Get cached BGE-M3 provider instance.

    Args:
        model_name: Model name

    Returns:
        Cached BGEM3Provider instance
    """
    return create_bgem3_provider(model_name=model_name)
