"""Shared eval helpers — used by matryoshka_migrate, ground_golden_v1, test_smoke_gate.

Roadmap 260516 review fix: extract TEI_URL/QUERY_PREFIX/embed_query constants
duplicated across 3 callsites. Single source of truth.

Per Python best-practice (https://discuss.python.org/t/best-practices-for-placing-
common-enumeration-constants-in-a-python-package/38519):
- Constants UPPER_SNAKE_CASE
- Underscore-prefixed module name (`_eval_common`) marks it as internal helper
  for the scripts/ subdirectory — not part of public src/ API
"""

from __future__ import annotations

import os
from typing import Final

import httpx

TEI_URL: Final[str] = os.environ.get("TEI_URL", "http://localhost:8080") + "/embed"
QDRANT_URL: Final[str] = os.environ.get("QDRANT_URL", "http://localhost:6333")
QUERY_PREFIX: Final[str] = (
    "Instruct: Given a web search query, retrieve relevant passages that "
    "answer the query\nQuery: "
)


def embed_query(query: str, http_client: httpx.Client, timeout: int = 30) -> list[float]:
    """Embed query via TEI HTTP with Qwen3 instruction prefix.

    Single source of truth for the prefix and TEI request shape — used by
    grounding script, matryoshka migration, NDCG smoke gate.
    """
    payload = {"inputs": [QUERY_PREFIX + query]}
    resp = http_client.post(TEI_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()[0]
