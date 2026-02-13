"""GigaEmbeddings provider (Phase 31).

Sber's SOTA Russian embedding model: ai-sage/Giga-Embeddings-instruct.
69.1 on ruMTEB vs ~60 for E5 multilingual — +15% quality for Russian text.

Uses instruction-based prompting (E5-instruct family):
- Query: instruction prefix + query text
- Passage: plain text (no prefix)

Also supports BGE-M3 as fallback (568M params, 100+ languages, dense+sparse).
"""

import asyncio
import logging
import time

from sentence_transformers import SentenceTransformer

from src.pdf_framework.config import EmbeddingSettings
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine

logger = logging.getLogger(__name__)

# Instruction prefix for GigaEmbeddings retrieval tasks
_GIGA_QUERY_PREFIX = (
    "Instruct: Given a search query, retrieve relevant passages "
    "that answer the query\nQuery: "
)

# BGE-M3 does not need any prefix
_BGE_QUERY_PREFIX = ""


class GigaEmbeddingEngine(BaseEmbeddingEngine):
    """GigaEmbeddings: Sber's SOTA Russian embedding model.

    Model: ai-sage/Giga-Embeddings-instruct (1024 dims)
    Performance: 69.1 on ruMTEB (SOTA for Russian, Feb 2026)
    Fallback: BAAI/bge-m3 (568M, 100+ languages)

    Uses instruction prompting for queries (E5-instruct family).
    """

    def __init__(self, settings: EmbeddingSettings | None = None):
        self._settings = settings or EmbeddingSettings()
        self._model: SentenceTransformer | None = None

        # Detect model type for prefix handling
        model_lower = self._settings.model.lower()
        if "giga" in model_lower:
            self._query_prefix = _GIGA_QUERY_PREFIX
            self._passage_prefix = ""
        elif "bge" in model_lower:
            self._query_prefix = _BGE_QUERY_PREFIX
            self._passage_prefix = ""
        else:
            # Generic: no prefix
            self._query_prefix = ""
            self._passage_prefix = ""

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            import torch

            device = self._settings.device
            if device == "auto":
                if torch.cuda.is_available():
                    device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"

            t0 = time.time()
            logger.info(
                "[GIGA_EMBED] Loading model '%s' (%d dims) on %s...",
                self._settings.model, self._settings.dimensions, device,
            )
            self._model = SentenceTransformer(
                self._settings.model,
                device=device,
                trust_remote_code=True,  # Required for GigaEmbeddings
            )
            logger.info(
                "[GIGA_EMBED] Model loaded in %.2fs (device=%s, CUDA=%s)",
                time.time() - t0, device, torch.cuda.is_available(),
            )
        return self._model

    def _add_prefix(self, texts: list[str], prefix: str) -> list[str]:
        if not prefix:
            return texts
        return [f"{prefix}{t}" for t in texts]

    def _embed_sync(self, texts: list[str], prefix: str) -> list[list[float]]:
        model = self._get_model()
        prefixed = self._add_prefix(texts, prefix)
        embeddings = model.encode(
            prefixed,
            batch_size=self._settings.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    async def embed_text(self, text: str) -> list[float]:
        """Embed single text with query instruction prefix."""
        results = await asyncio.to_thread(
            self._embed_sync, [text], self._query_prefix,
        )
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed batch of texts with passage prefix (empty for GigaEmbeddings)."""
        if not texts:
            return []
        t0 = time.time()
        result = await asyncio.to_thread(
            self._embed_sync, texts, self._passage_prefix,
        )
        elapsed = time.time() - t0
        logger.info(
            "[GIGA_EMBED] %d texts -> %d embeddings in %.2fs (%.0f texts/sec)",
            len(texts), len(result), elapsed,
            len(texts) / elapsed if elapsed > 0 else 0,
        )
        return result

    def get_dimensions(self) -> int:
        return self._settings.dimensions

    def get_model_name(self) -> str:
        return self._settings.model
