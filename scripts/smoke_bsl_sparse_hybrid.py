"""Phase 1 smoke: create parallel BSL collection with native Qdrant BM25 sparse.

Plan:
  1. Create target collection with named vectors: {dense (4096d), bm25 (sparse, IDF modifier)}.
  2. Scroll N random points from source production collection (with payload + vectors).
  3. For each point: compute BM25 sparse from payload.content (truncated to 500 chars).
  4. Upsert into target with both dense + sparse.

Source defaults to `bsl_code_v4_late` (production), target to `bsl_code_v4_sparse_smoke`.

Run:
  .venv\\Scripts\\python.exe scripts\\smoke_bsl_sparse_hybrid.py --sample-size 5000
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient, models

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.bsl.semantic_search.services.bm25_tokenizer import normalize_camelcase  # noqa: E402


def create_target_collection(
    client: QdrantClient,
    name: str,
    dense_dim: int,
    recreate: bool = False,
) -> None:
    if recreate:
        try:
            client.delete_collection(collection_name=name)
            print(f"[init] deleted existing: {name}")
        except Exception:
            pass

    try:
        info = client.get_collection(collection_name=name)
        print(f"[init] '{name}' exists: {info.points_count} pts")
        return
    except Exception:
        pass

    client.create_collection(
        collection_name=name,
        vectors_config={
            "dense": models.VectorParams(size=dense_dim, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF),
        },
    )
    print(f"[init] created '{name}' (dense={dense_dim}d cosine, bm25 sparse IDF)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--source", default="bsl_code_v4_late")
    parser.add_argument("--target", default="bsl_code_v4_sparse_smoke")
    parser.add_argument("--sample-size", type=int, default=5000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()

    client = QdrantClient(url=args.qdrant_url, timeout=120)

    src_info = client.get_collection(args.source)
    src_dim = src_info.config.params.vectors.size  # single-vector source
    print(f"[src] {args.source}: {src_info.points_count} pts × {src_dim}d")

    create_target_collection(client, args.target, dense_dim=src_dim, recreate=args.recreate)

    print("[bm25] loading FastEmbed Qdrant/bm25...")
    bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")
    print("[bm25] loaded")

    print(f"[scroll] up to {args.sample_size} pts from {args.source}...")
    t0 = time.time()
    offset = None
    total_upserted = 0
    buffer: list[tuple[str, list[float], dict[str, Any]]] = []

    while total_upserted < args.sample_size:
        remaining = args.sample_size - total_upserted
        page_size = min(args.batch_size, remaining)

        points, next_offset = client.scroll(
            collection_name=args.source,
            limit=page_size,
            offset=offset,
            with_vectors=True,
            with_payload=True,
        )
        if not points:
            break

        for p in points:
            content = p.payload.get("content", "") if p.payload else ""
            if not content:
                continue
            buffer.append((str(p.id), p.vector, p.payload))

        if len(buffer) >= args.batch_size or next_offset is None:
            texts = [normalize_camelcase(payload.get("content", "")) for _, _, payload in buffer]
            sparse_embs = list(bm25.embed(texts))

            upsert_points = []
            for (pid, dense_vec, payload), sparse_emb in zip(buffer, sparse_embs):
                upsert_points.append(
                    models.PointStruct(
                        id=pid,
                        vector={
                            "dense": dense_vec,
                            "bm25": models.SparseVector(
                                indices=sparse_emb.indices.tolist(),
                                values=sparse_emb.values.tolist(),
                            ),
                        },
                        payload=payload,
                    )
                )

            client.upsert(collection_name=args.target, points=upsert_points, wait=True)
            total_upserted += len(upsert_points)
            buffer.clear()
            elapsed = time.time() - t0
            rate = total_upserted / elapsed if elapsed > 0 else 0
            print(f"[upsert] {total_upserted}/{args.sample_size} ({rate:.0f} pts/s)")

        if next_offset is None:
            break
        offset = next_offset

    # Final flush
    if buffer:
        texts = [normalize_camelcase(payload.get("content", "")) for _, _, payload in buffer]
        sparse_embs = list(bm25.embed(texts))
        upsert_points = []
        for (pid, dense_vec, payload), sparse_emb in zip(buffer, sparse_embs):
            upsert_points.append(
                models.PointStruct(
                    id=pid,
                    vector={
                        "dense": dense_vec,
                        "bm25": models.SparseVector(
                            indices=sparse_emb.indices.tolist(),
                            values=sparse_emb.values.tolist(),
                        ),
                    },
                    payload=payload,
                )
            )
        client.upsert(collection_name=args.target, points=upsert_points, wait=True)
        total_upserted += len(upsert_points)

    elapsed = time.time() - t0
    print(
        f"[done] upserted {total_upserted} pts in {elapsed:.1f}s ({total_upserted/elapsed:.0f} pts/s)"
    )

    info = client.get_collection(args.target)
    print(f"[verify] {args.target}: {info.points_count} pts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
