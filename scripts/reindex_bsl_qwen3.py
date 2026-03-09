#!/usr/bin/env python3
"""
BSL Qwen3 Reindex — Phase 60

Parse BSL files → chunk by symbols → embed with Qwen3 → store in Qdrant bsl_code_v3.

Usage:
    python scripts/reindex_bsl_qwen3.py --project path/to/1c/project
    python scripts/reindex_bsl_qwen3.py --project path --batch-size 20 --recreate
"""

import argparse
import sys
import time
import uuid
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

from src.bsl.parser import BSLASTParser, BSLChunker
from src.bsl.parser.bsl_chunker import BSLChunk
from src.bsl.semantic_search.services.qwen3_embedding import Qwen3EmbeddingService

SKIP_PATTERNS = ["node_modules", "bin/", "build/"]
VECTOR_DIMS = 4096
UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def should_skip(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    return any(p in path_str for p in SKIP_PATTERNS)


def create_collection(client: QdrantClient, name: str, dims: int, recreate: bool = False) -> None:
    if recreate:
        try:
            client.delete_collection(collection_name=name)
            print(f"Deleted existing collection: {name}")
        except (UnexpectedResponse, Exception):
            pass

    try:
        info = client.get_collection(collection_name=name)
        print(f"Collection '{name}' exists: {info.points_count} points")
    except (UnexpectedResponse, Exception):
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=dims,
                distance=models.Distance.COSINE,
            ),
        )
        print(f"Created collection: {name} (dims={dims}, cosine)")


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, f"bsl-v3-{chunk_id}"))


def chunk_payload(chunk: BSLChunk) -> dict[str, Any]:
    m = chunk.metadata
    calls = m.get("calls", [])
    return {
        "chunk_id": chunk.chunk_id,
        "content": chunk.content[:500],
        "name": m.get("name", ""),
        "chunk_type": m.get("chunk_type", ""),
        "symbol_type": m.get("symbol_type", ""),
        "is_export": m.get("is_export", False),
        "module_path": m.get("module_path", ""),
        "module_name": m.get("module_name", ""),
        "module_type": m.get("module_type", ""),
        "params": m.get("params", ""),
        "calls": calls[:20] if isinstance(calls, list) else [],
        "signature": m.get("signature", ""),
        "region": m.get("region", ""),
        "line_start": m.get("line_start", 0),
        "line_end": m.get("line_end", 0),
    }


def flush_batch(
    client: QdrantClient,
    embedder: Qwen3EmbeddingService,
    collection: str,
    chunks: list[BSLChunk],
) -> int:
    """Embed and upsert a batch. Returns count of successfully upserted points."""
    texts = [c.content for c in chunks]
    vectors = embedder.embed_batch(texts, is_query=False)

    points = []
    for chunk, vec in zip(chunks, vectors):
        if vec is None:
            continue
        points.append(
            models.PointStruct(
                id=point_id(chunk.chunk_id),
                vector=vec,
                payload=chunk_payload(chunk),
            )
        )

    if points:
        client.upsert(collection_name=collection, points=points)
    return len(points)


def main() -> None:
    ap = argparse.ArgumentParser(description="Reindex BSL with Qwen3 embeddings")
    ap.add_argument("--project", type=Path, required=True, help="Project root with BSL files")
    ap.add_argument("--batch-size", type=int, default=50)
    ap.add_argument("--collection", default="bsl_code_v3")
    ap.add_argument("--recreate", action="store_true", help="Drop and recreate collection")
    ap.add_argument("--limit", type=int, default=0, help="Max chunks to index (0=all)")
    args = ap.parse_args()

    project = args.project.resolve()
    if not project.is_dir():
        print(f"ERROR: {project} is not a directory")
        sys.exit(1)

    t0 = time.time()
    parser = BSLASTParser()
    chunker = BSLChunker()
    embedder = Qwen3EmbeddingService()

    qdrant = QdrantClient(host="localhost", port=6333, timeout=30)
    create_collection(qdrant, args.collection, VECTOR_DIMS, args.recreate)

    bsl_files = sorted(f for f in project.rglob("*.bsl") if not should_skip(f))
    print(f"Found {len(bsl_files)} BSL files")

    total_symbols = 0
    total_chunks = 0
    errors = 0
    batch: list[BSLChunk] = []

    for i, fp in enumerate(bsl_files, 1):
        try:
            module = parser.parse_file(str(fp))
            chunks = chunker.chunk_module(module)
            total_symbols += len(module.symbols)

            for chunk in chunks:
                batch.append(chunk)
                if len(batch) >= args.batch_size:
                    n = flush_batch(qdrant, embedder, args.collection, batch)
                    total_chunks += n
                    batch.clear()
                    if args.limit and total_chunks >= args.limit:
                        break

            if args.limit and total_chunks >= args.limit:
                break

        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"[ERROR] {fp.name}: {e}")

        if i % 100 == 0:
            elapsed = time.time() - t0
            print(f"[{i}/{len(bsl_files)}] {total_symbols} symbols, {total_chunks} chunks, {elapsed:.0f}s")

    # Flush remaining
    if batch:
        n = flush_batch(qdrant, embedder, args.collection, batch)
        total_chunks += n

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"REINDEX COMPLETE")
    print(f"{'='*50}")
    print(f"  Files:    {len(bsl_files)}")
    print(f"  Symbols:  {total_symbols}")
    print(f"  Chunks:   {total_chunks}")
    print(f"  Errors:   {errors}")
    print(f"  Time:     {elapsed:.1f}s ({elapsed/max(len(bsl_files),1):.2f}s/file)")
    print(f"  Collection: {args.collection}")
    print(f"{'='*50}")

    embedder.close()


if __name__ == "__main__":
    main()
