#!/usr/bin/env python3
"""
One-shot reindex of `pdf_documents` Qdrant collection to Qwen3 4096d via TEI.

Closes Phase 8 §28.2.1. Replaces existing 1024d E5-baseline index with
Qwen3-Embedding-8B vectors. Reuses the framework_search TEI client to avoid
duplicating embedder code; uses pymupdf for text extraction; sliding-window
chunking (1000 chars / 200 overlap).

Source: data/pdfs/*.pdf (single PDF currently: Глава 5 1С Документация).

Usage:
    python scripts/reindex_pdf_documents.py [--dry-run] [--recreate]
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
import uuid
from pathlib import Path

import pymupdf  # PyMuPDF
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
    resolve_physical_collection,
)

logger = logging.getLogger("reindex-pdf")

COLLECTION = "pdf_documents"
PDF_DIR = PROJECT_ROOT / "data" / "pdfs"
WINDOW = 1000
OVERLAP = 200
UUID_NS = uuid.UUID("c1f3b2a4-8e6d-5d4c-9b3a-7f8e9d0c1b2a")


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    """Return [(page_num_1based, text)] for each page with text."""
    doc = pymupdf.open(str(pdf_path))
    pages: list[tuple[int, str]] = []
    try:
        for i, page in enumerate(doc, 1):
            text = page.get_text("text") or ""
            text = text.strip()
            if text:
                pages.append((i, text))
    finally:
        doc.close()
    return pages


def chunk_page(text: str) -> list[str]:
    """Sliding window over a single page's text."""
    if len(text) <= WINDOW:
        return [text] if text.strip() else []
    out: list[str] = []
    step = WINDOW - OVERLAP
    for offset in range(0, len(text), step):
        piece = text[offset : offset + WINDOW]
        if piece.strip():
            out.append(piece)
        if offset + WINDOW >= len(text):
            break
    return out


def make_point_id(source: str, page: int, chunk_idx: int, content_sha1: str) -> str:
    key = f"{source}:p{page}:c{chunk_idx}:{content_sha1[:12]}"
    return str(uuid.uuid5(UUID_NS, key))


def main() -> int:
    ap = argparse.ArgumentParser(description="Reindex pdf_documents to Qwen3 4096d")
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--tei-url", default="http://localhost:8080")
    ap.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate collection (REQUIRED for dim change E5 1024d -> Qwen3 4096d)",
    )
    ap.add_argument("--dry-run", action="store_true", help="Extract+chunk only, no embed/upsert")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error("No PDFs in %s", PDF_DIR)
        return 1
    logger.info("Found %d PDF(s) under %s", len(pdf_files), PDF_DIR)

    # Collect all chunks across all PDFs.
    chunks: list[dict] = []
    for pdf in pdf_files:
        rel = str(pdf.relative_to(PROJECT_ROOT)).replace("\\", "/")
        logger.info("Loading %s ...", rel)
        pages = extract_pages(pdf)
        logger.info("  %d pages with text", len(pages))
        for page_num, text in pages:
            for ci, piece in enumerate(chunk_page(text)):
                sha1 = hashlib.sha1(piece.encode("utf-8", errors="ignore")).hexdigest()
                chunks.append(
                    {
                        "id": make_point_id(rel, page_num, ci, sha1),
                        "content": piece,
                        "payload": {
                            "source": rel,
                            "page": page_num,
                            "chunk_index": ci,
                            "sha1": sha1,
                            "content": piece,
                        },
                    }
                )

    logger.info("Total chunks: %d", len(chunks))
    if args.dry_run or not chunks:
        return 0

    client = QdrantClient(url=args.qdrant_url)

    if args.recreate:
        if client.collection_exists(COLLECTION):
            # Atomic 4-step alias-aware recreate (resolve → drop → create → restore alias).
            recreate_collection_preserving_alias(client, COLLECTION, 4096)
        else:
            # Fresh create: resolve to handle dangling-alias edge case.
            physical = resolve_physical_collection(client, COLLECTION)
            logger.info("Creating collection %s (4096d cosine)", physical)
            client.create_collection(
                collection_name=physical,
                vectors_config=models.VectorParams(size=4096, distance=models.Distance.COSINE),
            )
    elif not client.collection_exists(COLLECTION):
        logger.error("Collection %s missing and --recreate not given", COLLECTION)
        return 1

    t0 = time.time()
    target_dim = resolve_collection_dim(client, COLLECTION)
    with FrameworkTEIEmbedder(base_url=args.tei_url) as embedder:
        # Pre-flight: probe embedder dim, verify it can satisfy collection target.
        probe = embedder.embed_batch([chunks[0]["content"]], is_query=False)
        embed_dim = len(probe[0])
        if target_dim is not None and target_dim > embed_dim:
            logger.error(
                "Embedder dim %d cannot satisfy collection target dim %d; aborting "
                "(check TEI model — should be Qwen3-Embedding-8B at 4096d).",
                embed_dim,
                target_dim,
            )
            return 1
        truncate = target_dim is not None and target_dim < embed_dim
        if truncate:
            logger.info("MRL truncation %dd -> %dd active", embed_dim, target_dim)
        for s in range(0, len(chunks), args.batch_size):
            batch = chunks[s : s + args.batch_size]
            texts = [c["content"] for c in batch]
            vectors = embedder.embed_batch(texts, is_query=False)
            if truncate:
                vectors = maybe_truncate_vectors(vectors, target_dim)  # type: ignore[arg-type]
            points = [
                models.PointStruct(id=c["id"], vector=v, payload=c["payload"])
                for c, v in zip(batch, vectors)
            ]
            client.upsert(collection_name=COLLECTION, points=points, wait=True)
            logger.info("upserted %d/%d", s + len(batch), len(chunks))

    dt = time.time() - t0
    logger.info("Done. %d chunks in %.1fs", len(chunks), dt)
    info = client.get_collection(COLLECTION)
    logger.info(
        "Final collection: %d points × %dd", info.points_count, info.config.params.vectors.size
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
