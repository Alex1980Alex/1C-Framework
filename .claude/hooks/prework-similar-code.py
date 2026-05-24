#!/usr/bin/env python3
"""Pre-Work worker: Similar code lookup via Qdrant semantic search.

Reads stdin {prompt} → embed via TEI → Qdrant search в `framework_code_v1`
→ writes stdout {items: [{title, body, score}]}.

Called by shared/prework_dispatcher.py (parallel UPS via asyncio).
Standalone (CLI-callable для testing).

Per ADR-D1 (roadmap 260523 §17.1) + §14.2a (Option A): Qdrant TEI semantic
search для прямого codebase grounding pre-work analysis.

Latency budget: ~1s (TEI embed ~50ms + Qdrant query ~100ms + assembly).
Graceful degradation: TEI/Qdrant down → empty items, dispatcher continues.

References:
- Skill: framework-search (детали `framework_code_v1` collection: 31k chunks,
  Qwen3-Embedding-8B 4096d via TEI Docker)
- Worker contract: shared/prework_dispatcher.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

TEI_URL = "http://localhost:8080"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "framework_code_v1"
TIMEOUT_SEC = 1.5

TOP_K = 5
MIN_SCORE = 0.35
MAX_BODY_CHARS = 200

# Collection uses MRL (Matryoshka Representation Learning) — first 1024 dims
# of 4096d Qwen3 vector stored for storage efficiency. Query vector must be
# truncated + re-normalized to match (see _mrl_truncate).
COLLECTION_DIM = 1024

# Qwen3 query instruction prefix (parity с FrameworkTEIEmbedder.QUERY_INSTRUCTION)
QUERY_INSTRUCTION = (
    "Instruct: Given a query, retrieve relevant code snippets that solve the query\n"
    "Query: "
)


def _embed_query(text: str) -> list[float] | None:
    """Embed query via TEI HTTP. Returns vector or None on failure."""
    try:
        import httpx
    except ImportError:
        return None
    try:
        prefixed = QUERY_INSTRUCTION + text
        with httpx.Client(base_url=TEI_URL, timeout=TIMEOUT_SEC) as client:
            resp = client.post(
                "/embed",
                json={"inputs": [prefixed], "normalize": True, "truncate": True},
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                first = data[0]
                if isinstance(first, list):
                    return [float(x) for x in first]
                if isinstance(first, dict) and "embedding" in first:
                    return [float(x) for x in first["embedding"]]
    except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError):
        pass
    return None


def _query_qdrant(vector: list[float]) -> list[dict]:
    """Query Qdrant collection. Returns list of payload dicts with score."""
    try:
        import httpx
    except ImportError:
        return []
    try:
        with httpx.Client(base_url=QDRANT_URL, timeout=TIMEOUT_SEC) as client:
            resp = client.post(
                f"/collections/{COLLECTION_NAME}/points/search",
                json={
                    "vector": vector,
                    "limit": TOP_K,
                    "with_payload": True,
                    "score_threshold": MIN_SCORE,
                },
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            result = data.get("result", [])
            if not isinstance(result, list):
                return []
            return result
    except (httpx.HTTPError, httpx.TimeoutException, ValueError, KeyError):
        return []


def _format_item(hit: dict) -> dict | None:
    """Convert Qdrant hit → worker item {title, body, score}."""
    score = float(hit.get("score", 0.0))
    payload = hit.get("payload") or {}
    rel_path = payload.get("relative_path", "?")
    symbol = payload.get("symbol_name")
    line_start = payload.get("line_start")
    chunk_type = payload.get("chunk_type", "")
    content = payload.get("content", "") or ""

    title_parts = [rel_path]
    if line_start is not None:
        title_parts.append(f":L{line_start}")
    if symbol:
        title_parts.append(f" — {symbol}")
    title = "".join(title_parts)

    # Body: first non-empty line of content (signature/docstring hint)
    body_lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
    if chunk_type:
        body = f"[{chunk_type}] " + (body_lines[0] if body_lines else "")
    else:
        body = body_lines[0] if body_lines else ""
    body = body[:MAX_BODY_CHARS]

    return {"title": title, "body": body, "score": round(score, 3)}


def _extract_signal(prompt: str) -> str:
    """Distill prompt to embedding-friendly query string.

    Drop punctuation noise, keep enough tokens for semantic meaning.
    """
    # Take first 500 chars (avoid embedding huge prompts)
    text = prompt[:500].strip()
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text


def main() -> int:
    """CLI entry. Reads stdin JSON {prompt}, writes stdout JSON {items}."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    prompt = payload.get("prompt", "")
    if not prompt or len(prompt.strip()) < 10:
        print(json.dumps({"items": []}, ensure_ascii=False))
        return 0

    query_text = _extract_signal(prompt)
    if not query_text:
        print(json.dumps({"items": []}, ensure_ascii=False))
        return 0

    # Step 1: embed query via TEI
    vector = _embed_query(query_text)
    if not vector:
        # TEI down → graceful empty (dispatcher continues)
        print(json.dumps({"items": []}, ensure_ascii=False))
        return 0

    # Step 2: Qdrant search
    hits = _query_qdrant(vector)
    if not hits:
        print(json.dumps({"items": []}, ensure_ascii=False))
        return 0

    # Step 3: format
    items = []
    for hit in hits:
        item = _format_item(hit)
        if item:
            items.append(item)

    print(json.dumps({"items": items}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
