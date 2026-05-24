"""TEI HTTP client for Qwen3-Embedding-8B (passage mode, no instruction prefix).

Mirrors the API of `Qwen3TEIEmbedder` in scripts/reindex_bsl_qwen3.py:
sub-batches outgoing requests at TEI's MAX_CLIENT_BATCH_SIZE (default 32)
to avoid 413 Payload Too Large.
"""

from __future__ import annotations

import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from .config import (
    DEFAULT_TEI_CLIENT_BATCH,
    DEFAULT_TEI_URL,
    MAX_CHUNK_CHARS,
)

logger = logging.getLogger(__name__)

# Same QUERY_INSTRUCTION as bsl-semantic-search and HF model card.
QUERY_INSTRUCTION = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
)


class FrameworkTEIEmbedder:
    """TEI HTTP embedder. Document mode = no prefix; query mode = QUERY_INSTRUCTION."""

    def __init__(
        self,
        base_url: str = DEFAULT_TEI_URL,
        client_batch_size: int = DEFAULT_TEI_CLIENT_BATCH,
        max_chars: int = MAX_CHUNK_CHARS,
        timeout: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.client_batch_size = client_batch_size
        self.max_chars = max_chars
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)
        self._dims: int | None = None

    @property
    def dims(self) -> int:
        return self._dims or 4096

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FrameworkTEIEmbedder:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def embed_batch(
        self,
        texts: list[str],
        is_query: bool = False,
    ) -> list[list[float]]:
        if not texts:
            return []
        prefix = QUERY_INSTRUCTION if is_query else ""
        inputs = [prefix + t[: self.max_chars] for t in texts]

        out: list[list[float]] = []
        bs = self.client_batch_size
        for s in range(0, len(inputs), bs):
            sub = inputs[s : s + bs]
            out.extend(self._post_embed_sub(sub))

        if len(out) != len(texts):
            raise RuntimeError(f"TEI concat shape: {len(out)} vs {len(texts)}")
        if self._dims is None and out:
            self._dims = len(out[0])
            logger.info("FrameworkTEIEmbedder dims=%d", self._dims)
        return out

    @retry(  # type: ignore[misc,unused-ignore]
        stop=stop_after_attempt(4),
        wait=wait_exponential_jitter(initial=2.0, max=30.0, jitter=2.0),
        retry=retry_if_exception_type(
            (httpx.HTTPStatusError, httpx.TransportError, httpx.ReadTimeout)
        ),
        reraise=True,
    )
    def _post_embed_sub(self, sub: list[str]) -> list[list[float]]:
        resp = self._client.post(
            "/embed",
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
            raise RuntimeError(
                f"TEI shape mismatch: {len(data) if isinstance(data, list) else '?'} vs {len(sub)}"
            )
        return data
