"""§4.1.16 PROOF: Hybrid dense+BM25 retrieval for pdf_documents.

Recreate pdf_documents as named-vector collection with dense (1024d Qwen3 MRL)
+ sparse (BM25 idf). Bench RRF fusion vs dense-only on 16 grounded PDF queries.

Pipeline:
    1. Scroll pdf_documents_4096_backup (830 pts × 4096d)
    2. For each: truncate to 1024d + L2-renorm; BM25 sparse from content
    3. Create new pdf_documents_hybrid with named vectors + SQ int8
    4. Upsert all 830 points
    5. Delete pdf_documents alias + pdf_documents_mrl_1024 physical
    6. Create pdf_documents → pdf_documents_hybrid alias
    7. Bench: 16 grounded PDF queries, compare dense-only vs RRF
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import httpx
import numpy as np
from fastembed import SparseTextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http import models

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "golden_v1.json"
QDRANT = "http://localhost:6333"
TEI = "http://localhost:8080"
SOURCE = "pdf_documents_4096_backup"  # has full 4096d originals
TARGET = "pdf_documents_hybrid"


def ndcg_at_k(retrieved, expected, k=10):
    dcg = 0.0
    for rank, rid in enumerate(retrieved[:k], 1):
        if rid in expected:
            dcg += 1.0 / math.log2(rank + 1)
    ideal = min(len(expected), k)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal + 1))
    return dcg / idcg if idcg else 0.0


def truncate_renorm(vec, target_dim=1024):
    arr = np.asarray(vec[:target_dim], dtype=np.float32)
    n = float(np.linalg.norm(arr))
    return (arr / n).tolist() if n > 0 else arr.tolist()


def main():
    client = QdrantClient(url=QDRANT)
    http = httpx.Client()

    print("=== Phase 1: Load BM25 model ===")
    t0 = time.time()
    bm25 = SparseTextEmbedding("Qdrant/bm25")
    print(f"  Loaded BM25 in {time.time()-t0:.1f}s")

    print("\n=== Phase 2: Create target collection ===")
    if client.collection_exists(TARGET):
        client.delete_collection(TARGET)
    client.create_collection(
        collection_name=TARGET,
        vectors_config={
            "dense": models.VectorParams(size=1024, distance=models.Distance.COSINE),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF),
        },
        quantization_config=models.ScalarQuantization(
            scalar=models.ScalarQuantizationConfig(
                type=models.ScalarType.INT8,
                quantile=0.99,
                always_ram=True,
            )
        ),
    )
    print(f"  Created {TARGET}")

    print("\n=== Phase 3: Scroll + truncate + BM25 + upsert ===")
    t0 = time.time()
    next_offset = None
    upserted = 0
    BATCH = 32
    while True:
        recs, next_offset = client.scroll(
            collection_name=SOURCE,
            limit=BATCH,
            with_payload=True,
            with_vectors=True,
            offset=next_offset,
        )
        if not recs:
            break
        texts = [(r.payload or {}).get("content", "") for r in recs]
        bm25_vecs = list(bm25.embed(texts))
        points = []
        for r, bm25_vec in zip(recs, bm25_vecs):
            dense = truncate_renorm(list(r.vector), 1024)
            points.append(
                models.PointStruct(
                    id=r.id,
                    vector={
                        "dense": dense,
                        "bm25": models.SparseVector(
                            indices=[int(i) for i in bm25_vec.indices],
                            values=[float(v) for v in bm25_vec.values],
                        ),
                    },
                    payload=r.payload,
                )
            )
        client.upsert(collection_name=TARGET, points=points, wait=False)
        upserted += len(points)
        if upserted % (BATCH * 5) == 0:
            print(f"  upserted {upserted}")
        if next_offset is None:
            break
    print(f"  Done: {upserted} points in {time.time()-t0:.1f}s")

    print("\n=== Phase 4: Bench grounded PDF queries (dense-only vs RRF) ===")
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) else raw
    pdf_grounded = [
        it
        for it in items
        if it.get("target_collection") == "pdf_documents" and it.get("expected_chunk_ids")
    ]
    print(f"  {len(pdf_grounded)} grounded items")

    PREFIX = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
    dense_scores, hybrid_scores = [], []

    for it in pdf_grounded:
        q = it["query"]
        expected = {str(x) for x in it["expected_chunk_ids"]}

        # Embed query
        r = http.post(TEI + "/embed", json={"inputs": [PREFIX + q]}, timeout=30)
        dense_q = truncate_renorm(r.json()[0], 1024)
        sparse_q = next(bm25.embed([q]))
        sparse_q_v = models.SparseVector(
            indices=[int(i) for i in sparse_q.indices],
            values=[float(v) for v in sparse_q.values],
        )

        # Dense-only
        dh = client.query_points(
            collection_name=TARGET,
            query=dense_q,
            using="dense",
            limit=10,
        ).points
        dense_scores.append(ndcg_at_k([str(h.id) for h in dh], expected))

        # Hybrid RRF
        hh = client.query_points(
            collection_name=TARGET,
            prefetch=[
                models.Prefetch(query=dense_q, using="dense", limit=20),
                models.Prefetch(query=sparse_q_v, using="bm25", limit=20),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=10,
        ).points
        hybrid_scores.append(ndcg_at_k([str(h.id) for h in hh], expected))

    dense_mean = sum(dense_scores) / len(dense_scores)
    hybrid_mean = sum(hybrid_scores) / len(hybrid_scores)
    delta = (hybrid_mean - dense_mean) / dense_mean * 100 if dense_mean > 0 else 0

    print(f"\n  dense-only:  mean NDCG@10 = {dense_mean:.4f}")
    print(f"  hybrid RRF:  mean NDCG@10 = {hybrid_mean:.4f}")
    print(f"  Δ:           {delta:+.1f}%")
    print(f"  Verdict: {'BETTER (≥5%)' if delta >= 5 else 'MARGINAL/WORSE'}")

    http.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
