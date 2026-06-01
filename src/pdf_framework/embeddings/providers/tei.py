"""TEI (Text Embeddings Inference) provider — Qwen3-Embedding-8B 4096d.

The production embedding stack (Phase 8/9.1) runs Qwen3-Embedding-8B behind a TEI
HTTP server (Docker container ``pdf-rag-tei`` on ``localhost:8080``). This engine
is the factory branch for ``EMBEDDING__PROVIDER=tei`` (the project default) and
mirrors the proven client in ``src/framework_search/embedder.py``:

  - sub-batches requests at TEI's ``MAX_CLIENT_BATCH_SIZE`` (default 32) to avoid
    HTTP 413 Payload Too Large (batch>32 — see memory feedback_tei_batch_size_limit);
  - prepends the Qwen3 ``QUERY_INSTRUCTION`` calibration prefix — the same one
    ``.claude/hooks/shared/semantic_search.embed_query_tei`` uses, so embeddings
    produced here retrieve against the existing collections identically to the
    live memory-first-hook surfacing path;
  - requests ``normalize=true`` + ``truncate`` so vectors are unit-norm and inputs
    over the model window are right-truncated rather than rejected.

URL comes from the ``TEI_URL`` env var (default ``http://localhost:8080``), matching
the hook's shared helper — no extra config is required when TEI runs locally.
"""

from __future__ import annotations

import logging
import os

import httpx

from src.pdf_framework.config import EmbeddingSettings
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine

logger = logging.getLogger(__name__)

# Qwen3 calibration prefix — identical to bsl-semantic-search / HF model card and to
# the memory-first-hook query path. Deviating breaks alignment (roadmap §21.10 H1).
QUERY_INSTRUCTION = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
)

# Keep inputs under the model window; TEI also right-truncates server-side as a backstop.
_MAX_CHARS = 8000


class TEIEmbeddingEngine(BaseEmbeddingEngine):
    """Embeddings via a local TEI HTTP server (Qwen3-Embedding-8B, 4096d)."""

    def __init__(self, settings: EmbeddingSettings | None = None):
        self._settings = settings or EmbeddingSettings()
        # TEI_URL env overrides settings for byte-parity with the hook path
        # (shared/semantic_search reads TEI_URL); both default to localhost:8080.
        base = os.environ.get("TEI_URL", self._settings.tei_base_url).rstrip("/")
        self._url = f"{base}/embed"
        self._model = self._settings.model or "Qwen/Qwen3-Embedding-8B"
        # TEI rejects client batches over MAX_CLIENT_BATCH_SIZE (default 32) with HTTP 413.
        self._client_batch = max(1, int(self._settings.tei_client_batch))
        self._client = httpx.AsyncClient(timeout=120.0)

    async def embed_text(self, text: str) -> list[float]:
        result = await self.embed_batch([text])
        return result[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed texts (query-side calibration).

        Always prepends the Qwen3 ``QUERY_INSTRUCTION`` prefix — this is the
        asymmetric *query* embedding, matching the live memory-first-hook path.
        Passage/document indexing wants the no-prefix passage mode (a separate
        path), not this engine.
        """
        if not texts:
            return []
        inputs = [QUERY_INSTRUCTION + t[:_MAX_CHARS] for t in texts]
        out: list[list[float]] = []
        for start in range(0, len(inputs), self._client_batch):
            sub = inputs[start : start + self._client_batch]
            out.extend(await self._post_embed(sub))
        if len(out) != len(texts):
            raise RuntimeError(f"TEI shape mismatch: {len(out)} vs {len(texts)}")
        return out

    async def _post_embed(self, sub: list[str]) -> list[list[float]]:
        resp = await self._client.post(
            self._url,
            json={
                "inputs": sub,
                "normalize": True,
                "truncate": True,
                "truncation_direction": "Right",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "embeddings" in data:
            data = data["embeddings"]
        if not isinstance(data, list) or len(data) != len(sub):
            got = len(data) if isinstance(data, list) else "?"
            raise RuntimeError(f"TEI response shape: {got} vs {len(sub)}")
        return data

    def get_dimensions(self) -> int:
        return self._settings.dimensions

    def get_model_name(self) -> str:
        return self._model

    async def close(self) -> None:
        await self._client.aclose()
