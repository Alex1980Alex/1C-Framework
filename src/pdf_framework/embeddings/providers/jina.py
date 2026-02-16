"""Jina Embeddings v3 provider (Phase 47).

Uses the Jina AI Embeddings API for high-quality multilingual embeddings.
Jina v3 supports:
- Task-type prompting (retrieval.query / retrieval.passage / separation / classification)
- Matryoshka dimension truncation (1024 → 512 / 256)
- Late Chunking (future Phase 48)
- MTEB 68.5%, multilingual, 1024 default dimensions

Usage:
    EMBEDDING__PROVIDER=jina
    EMBEDDING__JINA_API_KEY=jina_xxxxx
    EMBEDDING__MODEL=jina-embeddings-v3
    EMBEDDING__DIMENSIONS=1024
"""

import logging
import time

import httpx

from src.pdf_framework.config import EmbeddingSettings
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine

logger = logging.getLogger(__name__)

_JINA_API_URL = "https://api.jina.ai/v1/embeddings"


class JinaEmbeddingEngine(BaseEmbeddingEngine):
    """Generate embeddings using the Jina AI Embeddings API.

    Supports Jina v3 features:
    - Task-type prompting for optimal retrieval performance
    - Matryoshka dimension truncation for storage/speed tradeoffs
    - Batch processing with configurable batch size
    """

    def __init__(self, settings: EmbeddingSettings | None = None):
        self._settings = settings or EmbeddingSettings()
        if not self._settings.jina_api_key:
            raise ValueError(
                "Jina API key required. Set EMBEDDING__JINA_API_KEY in .env "
                "or pass jina_api_key in EmbeddingSettings."
            )
        self._model = self._settings.model or "jina-embeddings-v3"
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self._settings.jina_api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
        )

    async def _call_api(self, texts: list[str], task: str) -> list[list[float]]:
        """Call Jina Embeddings API with task-type prompting."""
        body: dict = {
            "model": self._model,
            "input": texts,
            "task": task,
        }
        # Matryoshka truncation
        if self._settings.jina_truncate_dim is not None:
            body["dimensions"] = self._settings.jina_truncate_dim

        response = await self._client.post(_JINA_API_URL, json=body)
        response.raise_for_status()
        data = response.json()

        # Sort by index to ensure order matches input
        embeddings_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings_data]

    async def embed_text(self, text: str) -> list[float]:
        """Embed a single text using 'retrieval.query' task type."""
        results = await self._call_api([text], task="retrieval.query")
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using configured task type (default: 'retrieval.passage').

        Processes in sub-batches of batch_size for large inputs.
        """
        if not texts:
            return []

        task = self._settings.jina_task  # "retrieval.passage" for indexing
        batch_size = self._settings.batch_size

        t0 = time.time()
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self._call_api(batch, task=task)
            all_embeddings.extend(batch_embeddings)

        elapsed = time.time() - t0
        logger.info(
            "[EMBEDDING] Jina v3: %d текстов → %d эмбеддингов за %.2f сек "
            "(%.0f текстов/сек, model=%s, task=%s, dims=%s)",
            len(texts), len(all_embeddings), elapsed,
            len(texts) / elapsed if elapsed > 0 else 0,
            self._model, task,
            self._settings.jina_truncate_dim or self._settings.dimensions,
        )
        return all_embeddings

    def get_dimensions(self) -> int:
        return self._settings.jina_truncate_dim or self._settings.dimensions

    def get_model_name(self) -> str:
        return self._model

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
