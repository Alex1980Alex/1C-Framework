"""§4.1.14: BGE-M3 alternative model bench on BSL queries.

Test if BGE-M3 (multilingual, 194 langs, MRL native, 1024d) gives
better NDCG on Cyrillic identifier-heavy BSL content than Qwen3-Embedding-8B.

Pipeline:
    1. Load BGE-M3 (1.2 GB FP16 on GPU)
    2. Sample N chunks from bsl_code_v4 (default 2000 for fast test)
    3. Re-embed via BGE-M3 → upsert to new collection bsl_code_v4_bgem3
    4. For each grounded BSL query (15 items from golden_v1 v2.2):
       - Embed query via BGE-M3
       - Query bsl_code_v4_bgem3 top-10
       - Compute NDCG@10 (some grounded chunk_ids may not be in sample)
    5. Compare mean NDCG to Qwen3 baseline (0.4436 from §4.1.9)

Note: sampled chunks may not include grounded ones → NDCG breaks for those
queries. To get fair comparison, sample MUST include all grounded chunk_ids
+ random fill. Script enforces this.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

GOLDEN_PATH = Path(__file__).resolve().parent.parent / "data" / "eval" / "golden_v1.json"


def ndcg_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int = 10) -> float:
    dcg = 0.0
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in expected_ids:
            dcg += 1.0 / math.log2(rank + 1)
    ideal = min(len(expected_ids), k)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal + 1))
    return dcg / idcg if idcg > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="bsl_code_v4")
    ap.add_argument("--target", default="bsl_code_v4_bgem3")
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument(
        "--sample-fill",
        type=int,
        default=2000,
        help="Random chunks added on top of grounded ones (lower=faster)",
    )
    ap.add_argument(
        "--no-truncate", action="store_true", help="Skip sample+embed step, bench existing target"
    )
    ap.add_argument("--batch-size", type=int, default=32)
    args = ap.parse_args()

    from qdrant_client import QdrantClient
    from qdrant_client.http import models

    qclient = QdrantClient(url=args.qdrant_url)

    # === Load grounded items first to compute mandatory chunk set ===
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    items = raw["items"] if isinstance(raw, dict) else raw
    # BSL queries grounded against bsl_code_v4_late OR bsl_code_v4
    grounded_items = [
        it
        for it in items
        if it.get("target_collection") in (args.source, args.source.replace("_v4", "_v4_late"))
        and it.get("expected_chunk_ids")
    ]
    if not grounded_items:
        print(f"ERROR: no grounded items for {args.source}")
        return 1

    mandatory_ids: set[str] = set()
    for it in grounded_items:
        mandatory_ids |= {str(x) for x in it["expected_chunk_ids"]}
    print(
        f"[BGE-M3 BENCH] {len(grounded_items)} grounded queries, {len(mandatory_ids)} mandatory chunk_ids"
    )

    if not args.no_truncate:
        # === Phase 1: Sample + re-embed ===
        from FlagEmbedding import BGEM3FlagModel

        print("Loading BGE-M3 ...")
        t0 = time.time()
        model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True, device="cuda")
        print(f"  Loaded in {time.time() - t0:.1f}s")

        # Scroll source to find mandatory chunks first
        sampled = []
        seen_ids = set()
        next_offset = None
        while True:
            recs, next_offset = qclient.scroll(
                collection_name=args.source,
                limit=512,
                with_payload=True,
                with_vectors=False,
                offset=next_offset,
            )
            for r in recs:
                rid = str(r.id)
                payload = r.payload or {}
                if rid in mandatory_ids:
                    sampled.append({"id": r.id, "payload": payload})
                    seen_ids.add(rid)
                elif len(sampled) - len(mandatory_ids & seen_ids) < args.sample_fill:
                    sampled.append({"id": r.id, "payload": payload})
            if next_offset is None or (
                len(seen_ids & mandatory_ids) == len(mandatory_ids)
                and len(sampled) >= args.sample_fill + len(mandatory_ids)
            ):
                break

        found = seen_ids & mandatory_ids
        print(
            f"  Sampled {len(sampled)} chunks ({len(found)}/{len(mandatory_ids)} mandatory found)"
        )

        # Create target collection (drop if exists)
        if qclient.collection_exists(args.target):
            qclient.delete_collection(args.target)
        qclient.create_collection(
            collection_name=args.target,
            vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE),
        )

        # Embed + upsert
        BATCH = args.batch_size
        for i in range(0, len(sampled), BATCH):
            batch = sampled[i : i + BATCH]
            texts = [b["payload"].get("content", "")[:1500] for b in batch]
            embs = model.encode(texts, batch_size=BATCH, max_length=512)["dense_vecs"]
            points = [
                models.PointStruct(id=b["id"], vector=emb.tolist(), payload=b["payload"])
                for b, emb in zip(batch, embs)
            ]
            qclient.upsert(collection_name=args.target, points=points, wait=False)
            if (i // BATCH) % 10 == 0:
                print(f"  upserted {i + len(batch)}/{len(sampled)}")
        print(f"Done upserting {len(sampled)} pts to {args.target}")

    # === Phase 2: Bench ===
    from FlagEmbedding import BGEM3FlagModel

    if "model" not in dir():
        print("Loading BGE-M3 for query embedding ...")
        model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True, device="cuda")

    scores = []
    for it in grounded_items:
        q = it["query"]
        expected = {str(x) for x in it["expected_chunk_ids"]}
        emb = model.encode([q], batch_size=1, max_length=512)["dense_vecs"][0]
        hits = qclient.query_points(
            collection_name=args.target,
            query=emb.tolist(),
            limit=10,
        ).points
        retrieved = [str(h.id) for h in hits]
        score = ndcg_at_k(retrieved, expected, k=10)
        scores.append(score)
        print(f"  {it['id']}: ndcg={score:.4f}")
    mean = sum(scores) / len(scores) if scores else 0.0
    print(f"\n[BGE-M3 BENCH] mean NDCG@10 = {mean:.4f} on {len(scores)} items")
    print("[QWEN3 BASELINE §4.1.9] = 0.4436 (1024d MRL was 0.3870 = REJECT -12.8%)")
    print(f"Verdict: {'BETTER' if mean > 0.4436 else 'WORSE'} than Qwen3 4096d baseline")

    return 0


if __name__ == "__main__":
    sys.exit(main())
