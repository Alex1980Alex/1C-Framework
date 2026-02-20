"""Jina Embeddings v3 provider (Phase 47).

Uses the Jina AI Embeddings API for high-quality multilingual embeddings.
Jina v3 supports:
- Task-type prompting (retrieval.query / retrieval.passage / separation / classification)
- Matryoshka dimension truncation (1024 → 512 / 256)
- Late Chunking (Phase 48): embed full context, then split by chunk boundaries
- MTEB 68.5%, multilingual, 1024 default dimensions

Usage:
    EMBEDDING__PROVIDER=jina
    EMBEDDING__JINA_API_KEY=jina_xxxxx
    EMBEDDING__MODEL=jina-embeddings-v3
    EMBEDDING__DIMENSIONS=1024
    EMBEDDING__LATE_CHUNKING=true  # Phase 48
"""

import logging
import time

import httpx

from src.pdf_framework.config import EmbeddingSettings
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine

logger = logging.getLogger(__name__)

_JINA_API_URL = "https://api.jina.ai/v1/embeddings"

# Approximate chars per token for Russian text (conservative estimate)
_CHARS_PER_TOKEN = 3


class JinaEmbeddingEngine(BaseEmbeddingEngine):
    """Generate embeddings using the Jina AI Embeddings API.

    Supports Jina v3 features:
    - Task-type prompting for optimal retrieval performance
    - Matryoshka dimension truncation for storage/speed tradeoffs
    - Late Chunking: preserves cross-chunk context within token window
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

    async def _call_api(
        self,
        texts: list[str],
        task: str,
        *,
        late_chunking: bool = False,
    ) -> list[list[float]]:
        """Call Jina Embeddings API with task-type prompting."""
        body: dict = {
            "model": self._model,
            "input": texts,
            "task": task,
        }
        # Matryoshka truncation
        if self._settings.jina_truncate_dim is not None:
            body["dimensions"] = self._settings.jina_truncate_dim

        # Late Chunking (Phase 48)
        if late_chunking:
            body["late_chunking"] = True

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
        """Embed a batch of texts using configured task type.

        When late_chunking is enabled, groups texts into windows that fit
        within the model's context limit (~8K tokens for v3) and sends each
        window with late_chunking=true. This preserves cross-chunk context
        within each window.

        When disabled, processes in sub-batches of batch_size.
        """
        if not texts:
            return []

        task = self._settings.jina_task  # "retrieval.passage" for indexing

        t0 = time.time()

        if self._settings.late_chunking:
            all_embeddings = await self._embed_late_chunking(texts, task)
        else:
            all_embeddings = await self._embed_regular(texts, task)

        elapsed = time.time() - t0
        logger.info(
            "[EMBEDDING] Jina v3: %d текстов → %d эмбеддингов за %.2f сек "
            "(%.0f текстов/сек, model=%s, task=%s, dims=%s, late_chunking=%s)",
            len(texts), len(all_embeddings), elapsed,
            len(texts) / elapsed if elapsed > 0 else 0,
            self._model, task,
            self._settings.jina_truncate_dim or self._settings.dimensions,
            self._settings.late_chunking,
        )
        return all_embeddings

    async def _embed_regular(self, texts: list[str], task: str) -> list[list[float]]:
        """Regular embedding: sub-batch by batch_size."""
        batch_size = self._settings.batch_size
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_embeddings = await self._call_api(batch, task=task)
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    async def _embed_late_chunking(
        self, texts: list[str], task: str,
    ) -> list[list[float]]:
        """Late Chunking: group consecutive texts into token windows.

        The Jina API concatenates all input texts internally, runs the
        transformer over the full context, then applies mean pooling per
        chunk boundary. All chunks in a window share cross-chunk context.

        Window size is limited by the model's context window (~8192 tokens).
        """
        max_tokens = self._settings.late_chunking_max_tokens
        max_chars = max_tokens * _CHARS_PER_TOKEN

        windows = self._group_into_windows(texts, max_chars)
        logger.info(
            "[EMBEDDING] Late Chunking: %d текстов → %d окон (макс %d токенов/окно)",
            len(texts), len(windows), max_tokens,
        )

        all_embeddings: list[list[float]] = []
        for window_idx, window_texts in enumerate(windows):
            window_embeddings = await self._call_api(
                window_texts, task=task, late_chunking=True,
            )
            all_embeddings.extend(window_embeddings)
            logger.debug(
                "[EMBEDDING] Late Chunking окно %d/%d: %d чанков",
                window_idx + 1, len(windows), len(window_texts),
            )

        return all_embeddings

    @staticmethod
    def _group_into_windows(
        texts: list[str], max_chars: int,
    ) -> list[list[str]]:
        """Group consecutive texts into windows within max_chars limit.

        Each window contains consecutive texts whose combined character
        count does not exceed max_chars. This preserves document order
        so the Jina API can correctly concatenate for cross-chunk context.
        """
        windows: list[list[str]] = []
        current_window: list[str] = []
        current_chars = 0

        for text in texts:
            text_chars = len(text)

            # If single text exceeds limit, send it alone (no late chunking benefit)
            if text_chars > max_chars:
                if current_window:
                    windows.append(current_window)
                    current_window = []
                    current_chars = 0
                windows.append([text])
                continue

            if current_chars + text_chars > max_chars:
                # Start new window
                windows.append(current_window)
                current_window = [text]
                current_chars = text_chars
            else:
                current_window.append(text)
                current_chars += text_chars

        if current_window:
            windows.append(current_window)

        return windows

    def get_dimensions(self) -> int:
        return self._settings.jina_truncate_dim or self._settings.dimensions

    def get_model_name(self) -> str:
        return self._model

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
