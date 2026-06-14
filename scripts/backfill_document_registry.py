#!/usr/bin/env python3
"""One-shot backfill of document_registry.db from a Qdrant docs collection.

Closes roadmap 260612 pdf-docs D7: the registry (Phase 32 Multi-Document KB)
had a single writer — REST API routes — while the production corpus was
indexed via CLI/scripts, leaving `list_documents` honestly-but-silently empty.

Scrolls the collection, groups chunks per source document, derives aggregates
(chunk_count, page_count) and registers each document. Idempotent: registry
register() is INSERT OR REPLACE keyed by deterministic document_id.

Payload tolerance: handles both writer dialects —
  - scripts/reindex_pdf_documents.py: {source, page, chunk_index, sha1, content}
  - W1 indexing pipeline:            {source, page_number, document_id, ...}

Usage:
    python scripts/backfill_document_registry.py [--dry-run]
        [--collection pdf_documents] [--qdrant-url http://localhost:6333]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict
from pathlib import Path

from qdrant_client import QdrantClient

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pdf_framework.knowledge_base.document_registry import DocumentRegistry
from src.pdf_framework.utils.id_generator import generate_document_id

logger = logging.getLogger("backfill-registry")


def collect_aggregates(client: QdrantClient, collection: str) -> dict[str, dict]:
    """Scroll the whole collection and aggregate per source document."""
    agg: dict[str, dict] = defaultdict(lambda: {"chunks": 0, "max_page": 0, "document_id": ""})
    offset = None
    scanned = 0
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            limit=500,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        for p in points:
            payload = p.payload or {}
            source = payload.get("source") or payload.get("source_path") or ""
            if not source:
                continue
            a = agg[source]
            a["chunks"] += 1
            page = payload.get("page_number") or payload.get("page") or 0
            if isinstance(page, int) and page > a["max_page"]:
                a["max_page"] = page
            # Prefer the pipeline-stamped document_id when present.
            if not a["document_id"] and payload.get("document_id"):
                a["document_id"] = str(payload["document_id"])
        scanned += len(points)
        if offset is None:
            break
    logger.info("Scanned %d points → %d source document(s)", scanned, len(agg))
    return dict(agg)


async def backfill(agg: dict[str, dict], db_path: Path, dry_run: bool) -> int:
    registry = DocumentRegistry(db_path=db_path)
    written = 0
    for source, a in sorted(agg.items()):
        doc_id = a["document_id"] or generate_document_id(str(PROJECT_ROOT / source))
        logger.info(
            "%s %s → id=%s, %d chunks, %d pages",
            "[DRY-RUN]" if dry_run else "[REGISTER]",
            source,
            doc_id,
            a["chunks"],
            a["max_page"],
        )
        if not dry_run:
            await registry.register(
                document_id=doc_id,
                source_path=source,
                chunk_count=a["chunks"],
                page_count=a["max_page"],
            )
            written += 1
    return written


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill document_registry.db from Qdrant")
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--collection", default="pdf_documents")
    ap.add_argument("--db-path", default=str(PROJECT_ROOT / "data" / "document_registry.db"))
    ap.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    client = QdrantClient(url=args.qdrant_url)
    if not client.collection_exists(args.collection):
        logger.error("Collection %s does not exist", args.collection)
        return 1

    agg = collect_aggregates(client, args.collection)
    if not agg:
        logger.warning("No documents found in %s — nothing to backfill", args.collection)
        return 0

    written = asyncio.run(backfill(agg, Path(args.db_path), args.dry_run))
    logger.info(
        "Done: %d document(s) %s",
        written if not args.dry_run else len(agg),
        "registered" if not args.dry_run else "would be registered",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
