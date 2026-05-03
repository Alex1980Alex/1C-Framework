"""
BSL Code Search Embedding Service — Phase 8.13 (sentence-transformers inline).

Provides code-optimized embeddings for 1C:Enterprise BSL code search
using Qwen3-Embedding-8B inline via sentence-transformers (singleton load).

Backend chain:
1. sentence-transformers inline (primary) — Qwen3-Embedding-8B FP16, 4096d.
   Reference implementation, matches `bsl_code_v4_late` index pooling exactly,
   no GPU contention with other backends. ~16 GB VRAM, lazy-loaded once.
2. TEI HTTP fallback (Qwen3TEIQueryService) — when ST fails to load.
3. None (graceful degradation → FTS5 text search)
"""

from __future__ import annotations

import logging
import threading
from typing import ClassVar

import httpx

logger = logging.getLogger(__name__)

# Instruction prefixes for Qwen3 instruct-style embeddings.
#
# Phase 8.12.8 H1 ablation (2026-04-30) tested BSL-specific instructions
# ("Find BSL code procedure" → 0.000 recall, "Given a code search query"
# → 0.071) and confirmed Qwen3-Embedding-8B is calibrated only on the
# default web-retrieval template from HF model card. Any deviation breaks
# distribution alignment. bsl_code_v4_late (production) was eval'd with
# this exact prompt → 0.567 recall (+26% vs E5).
QUERY_INSTRUCTION = (
    "Instruct: Given a web search query, retrieve relevant passages "
    "that answer the query\nQuery: "
)
# Passages indexed WITHOUT instruction (Qwen3 convention). DOCUMENT_INSTRUCTION
# is retained empty for re-indexing path compatibility — prepending nothing
# matches the bsl_code_v4_late index format.
DOCUMENT_INSTRUCTION = ""

MAX_INPUT_CHARS = 8000
EXPECTED_DIMS = 4096


class Qwen3EmbeddingService:
    """Embedding service using Qwen3-Embedding-8B inline via sentence-transformers.
    Singleton: model loads once on first call (~15-30s, ~16 GB VRAM)."""

    _instance: ClassVar[Qwen3EmbeddingService | None] = None
    _initialized: ClassVar[bool] = False

    def __new__(
        cls,
        ollama_host: str = "http://localhost:11434",
        model: str = "Qwen/Qwen3-Embedding-8B",
    ) -> Qwen3EmbeddingService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",  # kept for backward-compat, unused
        model: str = "Qwen/Qwen3-Embedding-8B",
    ) -> None:
        if Qwen3EmbeddingService._initialized:
            return
        self.model = model
        self._st_model = None  # lazy SentenceTransformer
        self._dims: int | None = None
        self._lock = threading.Lock()
        Qwen3EmbeddingService._initialized = True
        logger.info("Qwen3EmbeddingService initialized: backend=ST inline, model=%s", model)

    def _ensure_model(self):
        """Lazy-load Qwen3-Embedding-8B via sentence-transformers (~15-30s cold)."""
        if self._st_model is not None:
            return self._st_model
        with self._lock:
            if self._st_model is not None:
                return self._st_model
            from sentence_transformers import SentenceTransformer
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading Qwen3-Embedding-8B on %s (~15-30s, ~16 GB VRAM)...", device)
            self._st_model = SentenceTransformer(
                self.model,
                device=device,
                tokenizer_kwargs={"padding_side": "left"},
            )
            self._dims = EXPECTED_DIMS
            logger.info("Qwen3-Embedding-8B ST loaded on %s", device)
            return self._st_model

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
                return [emb if isinstance(emb, list) else None for emb in embeddings]
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

    def _tei_fallback(self) -> Qwen3TEIQueryService | None:
        """Lazy-init TEI fallback when Ollama unreachable. None if TEI also down."""
        if not hasattr(self, "_tei"):
            self._tei = Qwen3TEIQueryService()
        return self._tei

    def embed_query(self, text: str) -> list[float] | None:
        """Embed query via Ollama; on connect failure fallback to TEI HTTP."""
        instructed = QUERY_INSTRUCTION + text
        result = self._embed_ollama(instructed)
        if result is None:
            tei = self._tei_fallback()
            if tei is not None:
                logger.info("Falling back to TEI for query embedding")
                return tei.embed_query(text)  # tei applies QUERY_INSTRUCTION itself
        return result

    def embed_document(self, text: str) -> list[float] | None:
        """Embed passage via Ollama; on connect failure fallback to TEI HTTP."""
        instructed = DOCUMENT_INSTRUCTION + text
        result = self._embed_ollama(instructed)
        if result is None:
            tei = self._tei_fallback()
            if tei is not None:
                logger.info("Falling back to TEI for document embedding")
                return tei.embed_document(text)
        return result

    def embed_batch(self, texts: list[str], is_query: bool = False) -> list[list[float] | None]:
        """Batch embed via Ollama; on connect failure fallback to TEI HTTP."""
        if not texts:
            return []
        prefix = QUERY_INSTRUCTION if is_query else DOCUMENT_INSTRUCTION
        instructed = [prefix + t for t in texts]
        results = self._embed_ollama_batch(instructed)
        # If ALL results None — Ollama down → fallback to TEI
        if results and all(r is None for r in results):
            tei = self._tei_fallback()
            if tei is not None:
                logger.info("Falling back to TEI for batch embedding (%d texts)", len(texts))
                return tei.embed_batch(texts, is_query=is_query)
        return results

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


class Qwen3TEIQueryService:
    """TEI-based Qwen3 query embedder (Phase 8.12.8 production switchover).

    Uses HuggingFace text-embeddings-inference HTTP service (compose --profile tei)
    instead of Ollama. Produces vectors compatible with bsl_code_v4_late since
    the index was built via TEI/qwen3-st with identical safetensors model.
    """

    DEFAULT_BASE_URL = "http://localhost:8080"

    _instance: ClassVar[Qwen3TEIQueryService | None] = None
    _initialized: ClassVar[bool] = False

    def __new__(cls, base_url: str = DEFAULT_BASE_URL) -> Qwen3TEIQueryService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        if Qwen3TEIQueryService._initialized:
            return
        self.base_url = base_url.rstrip("/")
        self._client: httpx.Client | None = None
        self._dims: int | None = None
        Qwen3TEIQueryService._initialized = True
        logger.info("Qwen3TEIQueryService initialized: base_url=%s", base_url)

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(timeout=120.0)
        return self._client

    @property
    def dims(self) -> int:
        return self._dims or EXPECTED_DIMS

    def _truncate(self, text: str) -> str:
        return text[:MAX_INPUT_CHARS] if len(text) > MAX_INPUT_CHARS else text

    def _embed_tei(self, text: str) -> list[float] | None:
        text = self._truncate(text)
        try:
            r = self._get_client().post(
                f"{self.base_url}/embed",
                json={"inputs": [text], "normalize": True,
                      "truncate": True, "truncation_direction": "Right"},
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and data and isinstance(data[0], list):
                vec = data[0]
            elif isinstance(data, dict) and "embeddings" in data:
                vec = data["embeddings"][0]
            else:
                logger.warning("Unexpected TEI response shape: %s", type(data).__name__)
                return None
            if self._dims is None:
                self._dims = len(vec)
                logger.info("TEI dims detected: %d", self._dims)
            return vec
        except httpx.HTTPStatusError as e:
            logger.error("TEI HTTP error: %s", e.response.status_code)
            return None
        except (httpx.ConnectError, httpx.ReadTimeout):
            logger.error("TEI not reachable at %s", self.base_url)
            return None
        except Exception as e:
            logger.error("TEI embedding error: %s", e)
            return None

    def _embed_tei_batch(self, texts: list[str]) -> list[list[float] | None]:
        texts = [self._truncate(t) for t in texts]
        try:
            r = self._get_client().post(
                f"{self.base_url}/embed",
                json={"inputs": texts, "normalize": True,
                      "truncate": True, "truncation_direction": "Right"},
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict) and "embeddings" in data:
                data = data["embeddings"]
            if not isinstance(data, list) or len(data) != len(texts):
                logger.warning("TEI batch shape mismatch: %d expected", len(texts))
                return [None] * len(texts)
            if self._dims is None and data:
                self._dims = len(data[0])
            return [v if isinstance(v, list) else None for v in data]
        except httpx.HTTPStatusError as e:
            logger.error("TEI batch HTTP error: %s", e.response.status_code)
            return [None] * len(texts)
        except (httpx.ConnectError, httpx.ReadTimeout):
            logger.error("TEI not reachable at %s", self.base_url)
            return [None] * len(texts)
        except Exception as e:
            logger.error("TEI batch error: %s", e)
            return [None] * len(texts)

    def embed_query(self, text: str) -> list[float] | None:
        return self._embed_tei(QUERY_INSTRUCTION + text)

    def embed_document(self, text: str) -> list[float] | None:
        return self._embed_tei(DOCUMENT_INSTRUCTION + text)

    def embed_batch(self, texts: list[str], is_query: bool = False) -> list[list[float] | None]:
        if not texts:
            return []
        prefix = QUERY_INSTRUCTION if is_query else DOCUMENT_INSTRUCTION
        return self._embed_tei_batch([prefix + t for t in texts])

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Qwen3TEIQueryService HTTP client closed")

    @classmethod
    def reset(cls) -> None:
        if cls._instance is not None:
            cls._instance.close()
        cls._instance = None
        cls._initialized = False
