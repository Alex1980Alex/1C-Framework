#!/usr/bin/env python3
"""
BSL Reindex with FastEmbed (ONNX) — ~1.6x faster than PyTorch on CPU.

Single process, ONNX-optimized E5-large via fastembed.
Parse BSL → chunk → embed (ONNX) → upsert Qdrant.

Usage:
    python scripts/reindex_bsl_parallel.py --project path/to/1c --recreate
    python scripts/reindex_bsl_parallel.py --project path --batch-size 64
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

from src.bsl.parser import BSLASTParser, BSLChunker, BSLContextEnricher
from src.bsl.parser.bsl_chunker import BSLChunk

SKIP_PATTERNS = ["node_modules", "bin/", "build/"]
UUID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")
EMBEDDING_DIM = 1024


def should_skip(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    return any(p in path_str for p in SKIP_PATTERNS)


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
        "object_type": m.get("object_type", ""),
        "object_name": m.get("object_name", ""),
        "caller_count": m.get("caller_count", 0),
    }


def flush_batch(
    qdrant: QdrantClient,
    embedder: Any,
    collection: str,
    chunks: list[BSLChunk],
) -> int:
    texts = [c.content[:8000] for c in chunks]
    embeddings = list(embedder.passage_embed(texts))

    points = []
    for chunk, emb in zip(chunks, embeddings):
        vec = emb.tolist() if hasattr(emb, "tolist") else list(emb)
        points.append(
            models.PointStruct(
                id=point_id(chunk.chunk_id),
                vector=vec,
                payload=chunk_payload(chunk),
            )
        )
    if points:
        qdrant.upsert(collection_name=collection, points=points)
    return len(points)


def main() -> None:
    ap = argparse.ArgumentParser(description="BSL reindex with FastEmbed ONNX")
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--collection", default="bsl_code_v3")
    ap.add_argument("--recreate", action="store_true")
    ap.add_argument("--no-context", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Max chunks (0=all)")
    args = ap.parse_args()

    project = args.project.resolve()
    if not project.is_dir():
        print(f"ERROR: {project} is not a directory")
        sys.exit(1)

    t0 = time.time()

    # FastEmbed ONNX model
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning)
    from fastembed import TextEmbedding
    print("Loading FastEmbed E5-large (ONNX)...")
    embedder = TextEmbedding("intfloat/multilingual-e5-large")
    print(f"Model loaded in {time.time() - t0:.1f}s")

    # Parser + enricher
    parser = BSLASTParser()
    chunker = BSLChunker()

    enricher = None
    if not args.no_context:
        try:
            from src.bsl.knowledge_graph.metadata_extractor import MetadataExtractor
            from src.bsl.call_graph.store import CallGraphStore
            extractor = MetadataExtractor(project)
            cg_db = PROJECT_ROOT / "cache" / "bsl_call_graph.db"
            cg = CallGraphStore(cg_db) if cg_db.exists() else None
            enricher = BSLContextEnricher(metadata_extractor=extractor, call_graph=cg)
            obj_stats = extractor.stats()
            print(f"Context enrichment ON: {obj_stats['total']} objects"
                  f"{', call graph loaded' if cg else ''}")
        except Exception as e:
            print(f"Context enrichment unavailable: {e}")

    # Qdrant
    qdrant = QdrantClient(host="localhost", port=6333, timeout=60)
    if args.recreate:
        try:
            qdrant.delete_collection(collection_name=args.collection)
            print(f"Deleted collection: {args.collection}")
        except Exception:
            pass

    try:
        info = qdrant.get_collection(collection_name=args.collection)
        print(f"Collection '{args.collection}' exists: {info.points_count} points")
    except Exception:
        qdrant.create_collection(
            collection_name=args.collection,
            vectors_config=models.VectorParams(size=EMBEDDING_DIM, distance=models.Distance.COSINE),
        )
        print(f"Created collection: {args.collection} ({EMBEDDING_DIM}d, cosine)")

    # Discover files
    bsl_files = sorted(f for f in project.rglob("*.bsl") if not should_skip(f))
    total_files = len(bsl_files)
    print(f"Found {total_files} BSL files")
    print(f"Batch size: {args.batch_size}")
    print()

    if total_files == 0:
        print("Nothing to index.")
        return

    total_symbols = 0
    total_chunks = 0
    errors = 0
    batch: list[BSLChunk] = []

    for i, fp in enumerate(bsl_files, 1):
        try:
            module = parser.parse_file(str(fp))
            chunks = chunker.chunk_module(module)
            if enricher:
                enricher.enrich(chunks)
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

        if i % 50 == 0:
            elapsed = time.time() - t0
            speed = total_chunks / elapsed if elapsed > 0 else 0
            eta = (total_files - i) / (i / elapsed) if elapsed > 0 else 0
            print(f"[{i}/{total_files}] {total_symbols} sym, {total_chunks} chunks, "
                  f"{speed:.1f} ch/s, ETA ~{eta/60:.0f}min")

    # Flush remaining
    if batch:
        n = flush_batch(qdrant, embedder, args.collection, batch)
        total_chunks += n

    elapsed = time.time() - t0
    info = qdrant.get_collection(collection_name=args.collection)

    print()
    print("=" * 60)
    print("REINDEX COMPLETE (FastEmbed ONNX)")
    print("=" * 60)
    print(f"  Files:      {total_files}")
    print(f"  Symbols:    {total_symbols}")
    print(f"  Chunks:     {total_chunks}")
    print(f"  Qdrant pts: {info.points_count}")
    print(f"  Errors:     {errors}")
    print(f"  Time:       {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Speed:      {total_chunks/elapsed:.1f} chunks/s")
    print(f"  Collection: {args.collection}")
    print("=" * 60)


if __name__ == "__main__":
    main()
