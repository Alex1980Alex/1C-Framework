"""
BSL Code Search Embedding Service — Phase 60

Provides code-optimized embeddings for 1C:Enterprise BSL code search
using Qwen3-Embedding model via Ollama.

3-level fallback:
1. Ollama local (primary) — qwen3-embedding, 1024d
2. Ollama nomic-embed-text (fallback) — 768d (incompatible with v3 collection)
3. None (graceful degradation → FTS5 text search)

Instruction prompts optimize retrieval for BSL code patterns.
"""

from __future__ import annotations

import logging
from typing import ClassVar

import httpx

logger = logging.getLogger(__name__)

# Instruction prefixes for Qwen3 instruct-style embeddings
QUERY_INSTRUCTION = "Instruct: Find BSL code procedure or function\nQuery: "
DOCUMENT_INSTRUCTION = "Instruct: BSL code module from 1C Enterprise\nDocument: "

MAX_INPUT_CHARS = 8000
EXPECTED_DIMS = 1024


class Qwen3EmbeddingService:
    """Embedding service for BSL code search using Qwen3-Embedding via Ollama."""

    _instance: ClassVar[Qwen3EmbeddingService | None] = None
    _initialized: ClassVar[bool] = False

    def __new__(
        cls,
        ollama_host: str = "http://localhost:11434",
        model: str = "qwen3-embedding",
    ) -> Qwen3EmbeddingService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "qwen3-embedding",
    ) -> None:
        if Qwen3EmbeddingService._initialized:
            return

        self.ollama_host = ollama_host.rstrip("/")
        self.model = model
        self.embed_endpoint = f"{self.ollama_host}/api/embed"
        self._client: httpx.Client | None = None
        self._dims: int | None = None

        Qwen3EmbeddingService._initialized = True
        logger.info(
            "Qwen3EmbeddingService initialized: host=%s, model=%s",
            ollama_host,
            model,
        )

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=120.0)
        return self._client

    @property
    def dims(self) -> int:
        """Return embedding dimensions (detected on first call)."""
        return self._dims or EXPECTED_DIMS

    def _truncate(self, text: str) -> str:
        return text[:MAX_INPUT_CHARS] if len(text) > MAX_INPUT_CHARS else text

    def _embed_ollama(self, text: str) -> list[float] | None:
        """Single embedding via Ollama /api/embed endpoint."""
        text = self._truncate(text)
        try:
            client = self._get_client()
            response = client.post(
                self.embed_endpoint,
                json={"model": self.model, "input": text},
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings", [])
            if embeddings and isinstance(embeddings[0], list):
                result = embeddings[0]
                if self._dims is None:
                    self._dims = len(result)
                    logger.info("Detected embedding dimensions: %d", self._dims)
                return result
            logger.warning("No embeddings in Ollama response")
            return None
        except httpx.HTTPStatusError as e:
            logger.error("Ollama HTTP error: %s", e.response.status_code)
            return None
        except httpx.ConnectError:
            logger.error("Ollama not available at %s", self.ollama_host)
            return None
        except Exception as e:
            logger.error("Ollama embedding error: %s", e)
            return None

    def _embed_ollama_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Batch embedding via Ollama /api/embed (supports list input)."""
        texts = [self._truncate(t) for t in texts]
        try:
            client = self._get_client()
            response = client.post(
                self.embed_endpoint,
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            data = response.json()
            embeddings = data.get("embeddings", [])
            if len(embeddings) == len(texts):
                if self._dims is None and embeddings:
                    self._dims = len(embeddings[0])
                    logger.info("Detected embedding dimensions: %d", self._dims)
                return [
                    emb if isinstance(emb, list) else None for emb in embeddings
                ]
            logger.warning(
                "Ollama batch: expected %d, got %d embeddings",
                len(texts),
                len(embeddings),
            )
            return [None] * len(texts)
        except httpx.HTTPStatusError as e:
            logger.error("Ollama batch HTTP error: %s", e.response.status_code)
            return [None] * len(texts)
        except httpx.ConnectError:
            logger.error("Ollama not available at %s", self.ollama_host)
            return [None] * len(texts)
        except Exception as e:
            logger.error("Ollama batch error: %s", e)
            return [None] * len(texts)

    def embed_query(self, text: str) -> list[float] | None:
        """Embed a search query with query instruction prefix."""
        instructed = QUERY_INSTRUCTION + text
        return self._embed_ollama(instructed)

    def embed_document(self, text: str) -> list[float] | None:
        """Embed a document/code chunk with document instruction prefix."""
        instructed = DOCUMENT_INSTRUCTION + text
        return self._embed_ollama(instructed)

    def embed_batch(
        self, texts: list[str], is_query: bool = False
    ) -> list[list[float] | None]:
        """Batch embed texts with appropriate instruction prefix."""
        if not texts:
            return []
        prefix = QUERY_INSTRUCTION if is_query else DOCUMENT_INSTRUCTION
        instructed = [prefix + t for t in texts]
        return self._embed_ollama_batch(instructed)

    def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Qwen3EmbeddingService HTTP client closed")

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        if cls._instance is not None:
            cls._instance.close()
        cls._instance = None
        cls._initialized = False
