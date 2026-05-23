#!/usr/bin/env python3
"""
Re-embed an existing Qdrant collection's `text` payload field with Qwen3 via TEI.

Used for §28.2.x to migrate E5 1024d -> Qwen3 4096d without regenerating
chunks from source. Workflow:

    1. Scroll source collection, capture (id, payload).
    2. Drop and recreate at new dim (4096d cosine).
    3. Re-embed `text` field (or `--text-field` override) in batches.
    4. Upsert with original ids preserved.

Falls back gracefully if a row has no `text` key — counts and skips.

Usage:
    python scripts/reembed_collection.py --collection wiki_pages_v1
    python scripts/reembed_collection.py --collection graph_embeddings
    python scripts/reembed_collection.py --collection X --text-field content
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.framework_search.embedder import FrameworkTEIEmbedder  # noqa: E402
from src.framework_search.indexer import (  # noqa: E402
    maybe_truncate_vectors,
    recreate_collection_preserving_alias,
    resolve_collection_dim,
)

logger = logging.getLogger("reembed")


def scroll_all(
    client: QdrantClient,
    collection: str,
    text_field: str,
    page_size: int = 256,
) -> list[dict]:
    """Return [{id, payload, text}] for every point that has the text field."""
    out: list[dict] = []
    skipped = 0
    next_offset = None
    while True:
        recs, next_offset = client.scroll(
            collection_name=collection,
            limit=page_size,
            with_payload=True,
            with_vectors=False,
            offset=next_offset,
        )
        if not recs:
            break
        for r in recs:
            p = r.payload or {}
            text = p.get(text_field)
            if not text or not isinstance(text, str) or not text.strip():
                skipped += 1
                continue
            out.append({"id": r.id, "payload": p, "text": text})
        if next_offset is None:
            break
    logger.info("scrolled %d points (skipped %d without %r)", len(out), skipped, text_field)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Re-embed Qdrant collection via TEI")
    ap.add_argument("--collection", required=True)
    ap.add_argument(
        "--text-field", default="text", help="Payload key containing the text (default: 'text')"
    )
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--tei-url", default="http://localhost:8080")
    ap.add_argument("--target-dim", type=int, default=4096)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument(
        "--dry-run", action="store_true", help="Scroll + count only, no recreate/embed/upsert"
    )
    ap.add_argument(
        "--max-text-chars",
        type=int,
        default=8000,
        help="Truncate texts longer than this (TEI MAX_INPUT_LENGTH protection)",
    )
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    client = QdrantClient(url=args.qdrant_url)
    if not client.collection_exists(args.collection):
        logger.error("collection %s does not exist", args.collection)
        return 1

    logger.info("Scrolling source collection %s ...", args.collection)
    rows = scroll_all(client, args.collection, args.text_field)
    if not rows:
        logger.warning("No rows with text field; nothing to do")
        return 0
    logger.info("Total rows to re-embed: %d", len(rows))

    # Stats
    text_lens = [len(r["text"]) for r in rows]
    logger.info(
        "text length: min=%d p50=%d p99=%d max=%d",
        min(text_lens),
        sorted(text_lens)[len(text_lens) // 2],
        sorted(text_lens)[int(len(text_lens) * 0.99)],
        max(text_lens),
    )

    if args.dry_run:
        return 0

    # Recreate at target dim. If `args.collection` is an alias (e.g.
    # wiki_pages_v1 after §4.1.10 swap), Qdrant resolves the alias transparently
    # in get_collection, so we read the existing dim through the alias name and
    # preserve it instead of forcing args.target_dim.
    existing_dim = resolve_collection_dim(client, args.collection)
    effective_dim = existing_dim if existing_dim is not None else args.target_dim
    if existing_dim is not None and effective_dim != args.target_dim:
        logger.warning(
            "Coercing dim to existing collection's %dd (--target-dim=%d ignored to preserve alias contract)",
            effective_dim,
            args.target_dim,
        )

    # Delegate the 4-step alias-aware recreate (resolve → drop → create → restore alias).
    recreate_collection_preserving_alias(client, args.collection, effective_dim)

    # Truncate long texts before embedding (TEI MAX_INPUT_LENGTH=4096 tokens ≈ 16k chars).
    for r in rows:
        if len(r["text"]) > args.max_text_chars:
            r["text"] = r["text"][: args.max_text_chars]

    t0 = time.time()
    upserted = 0
    with FrameworkTEIEmbedder(base_url=args.tei_url) as embedder:
        for s in range(0, len(rows), args.batch_size):
            batch = rows[s : s + args.batch_size]
            texts = [r["text"] for r in batch]
            vectors = embedder.embed_batch(texts, is_query=False)
            if effective_dim < 4096:
                vectors = maybe_truncate_vectors(vectors, effective_dim)
            points = [
                models.PointStruct(id=r["id"], vector=v, payload=r["payload"])
                for r, v in zip(batch, vectors)
            ]
            client.upsert(collection_name=args.collection, points=points, wait=True)
            upserted += len(points)
            if upserted % 256 == 0 or upserted == len(rows):
                logger.info("upserted %d/%d", upserted, len(rows))

    dt = time.time() - t0
    info = client.get_collection(args.collection)
    logger.info(
        "Done. %d -> %d points × %dd in %.1fs",
        len(rows),
        info.points_count,
        info.config.params.vectors.size,
        dt,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
