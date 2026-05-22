"""Migrate bsl_code_v4_late to hybrid (dense + BM25 sparse) layout.

Source collection has single-vector 4096d layout. Target gets named-vector
layout `{dense: 4096d cosine, bm25: sparse IDF}`. Existing dense vectors are
reused (no re-embedding). BM25 sparse is computed client-side from
payload.content via FastEmbed Qdrant/bm25 with CamelCase normalization
(critical for BSL — `ОбработкаПроведения` must match `обработка проведения`
query tokens).

Anchor benchmark (scripts/bench_bsl_sparse_smoke.py, 30 queries, k=10) showed
dense Hit@10 ~16% vs BM25/hybrid Hit@10 ~90% on this corpus. The win is
content-specific (Cyrillic identifiers + repetitive BSL syntax) — see memory
feedback_bsl_sparse_bm25_dominance.md.

This script is idempotent: skips points that already exist in target. Safe
to rerun after interruption.

Usage:
    .venv\\Scripts\\python.exe scripts\\migrate_bsl_to_hybrid.py \\
        --source bsl_code_v4_late --target bsl_code_v4_late_hybrid

The alias swap is performed by scripts/alias_swap_bsl_hybrid.py once this
migration completes and verification passes.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _progress import make_tracker  # noqa: E402
from fastembed import SparseTextEmbedding  # noqa: E402
from qdrant_client import QdrantClient, models  # noqa: E402

CAMELCASE_RE = re.compile(r"[А-ЯЁ][а-яё]*|[A-Z][a-z]*|[а-яё]+|[a-z]+|\d+")


def normalize_camelcase(text: str) -> str:
    """Split CamelCase identifiers into space-separated tokens.

    BSL identifiers like `ОбработкаПроведения` tokenize to
    `обработка проведения` so BM25 can match queries that use the same
    words in different surface forms. Without this normalization BM25
    treats each CamelCase identifier as a single opaque token and recall
    collapses for natural-language-style queries.
    """
    parts = CAMELCASE_RE.findall(text)
    return " ".join(parts).lower() if parts else text.lower()


def create_target_collection(
    client: QdrantClient,
    name: str,
    dense_dim: int,
    recreate: bool = False,
) -> bool:
    """Return True if collection was created (or recreated), False if reused."""
    if recreate:
        try:
            client.delete_collection(collection_name=name)
            print(f"[init] deleted existing: {name}")
        except Exception:
            pass

    try:
        info = client.get_collection(collection_name=name)
        vec_cfg = info.config.params.vectors
        sparse_cfg = info.config.params.sparse_vectors
        ok_dense = isinstance(vec_cfg, dict) and "dense" in vec_cfg
        ok_sparse = bool(sparse_cfg and "bm25" in sparse_cfg)
        if not (ok_dense and ok_sparse):
            raise RuntimeError(
                f"target '{name}' exists with wrong layout "
                f"(vectors={list(vec_cfg.keys()) if isinstance(vec_cfg, dict) else 'single'}, "
                f"sparse={list(sparse_cfg.keys()) if sparse_cfg else 'none'}). "
                f"Drop manually or pass --recreate."
            )
        print(f"[init] reusing '{name}' ({info.points_count} pts, hybrid layout)")
        return False
    except RuntimeError:
        raise
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
    return True


def get_existing_target_ids(client: QdrantClient, target: str) -> set[str]:
    """Scroll target and return set of existing point IDs for idempotent rerun."""
    ids: set[str] = set()
    offset = None
    while True:
        points, next_offset = client.scroll(
            collection_name=target,
            limit=2000,
            offset=offset,
            with_vectors=False,
            with_payload=False,
        )
        ids.update(str(p.id) for p in points)
        if next_offset is None:
            break
        offset = next_offset
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--source", default="bsl_code_v4_late")
    parser.add_argument("--target", default="bsl_code_v4_late_hybrid")
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop target collection before migration (default: idempotent reuse).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Cap total upserted points (0 = all). Useful for staged migrations.",
    )
    args = parser.parse_args()

    tracker = make_tracker("migrate_bsl_to_hybrid").start()

    client = QdrantClient(url=args.qdrant_url, timeout=120)

    src_info = client.get_collection(args.source)
    src_dim = src_info.config.params.vectors.size
    src_count = src_info.points_count
    print(f"[src] {args.source}: {src_count} pts × {src_dim}d")
    tracker.event(
        "startup",
        source=args.source,
        target=args.target,
        src_count=src_count,
        src_dim=src_dim,
        recreate=bool(args.recreate),
    )
    tracker.set_state(total_pts=src_count, done=0, source=args.source, target=args.target)

    with tracker.stage("init_target"):
        created = create_target_collection(
            client, args.target, dense_dim=src_dim, recreate=args.recreate,
        )

    existing_ids: set[str] = set()
    if not created:
        with tracker.stage("scan_existing"):
            existing_ids = get_existing_target_ids(client, args.target)
            print(f"[idempotent] target has {len(existing_ids)} pts already; will skip")
            tracker.event("idempotent_scan", existing=len(existing_ids))

    with tracker.stage("bm25_load"):
        bm25 = SparseTextEmbedding(model_name="Qdrant/bm25")
        print("[bm25] FastEmbed Qdrant/bm25 loaded")

    t0 = time.time()
    offset = None
    total_upserted = 0
    total_skipped = 0
    total_no_content = 0
    buffer: list[tuple[str, list[float], dict[str, Any]]] = []

    def flush_buffer() -> None:
        nonlocal total_upserted, total_no_content
        if not buffer:
            return

        texts_for_bm25: list[str] = []
        for _, _, payload in buffer:
            content = payload.get("content", "") if payload else ""
            texts_for_bm25.append(normalize_camelcase(content) if content else "")

        sparse_embs = list(bm25.embed(texts_for_bm25))

        upsert_points = []
        for (pid, dense_vec, payload), sparse_emb, norm_text in zip(
            buffer, sparse_embs, texts_for_bm25,
        ):
            vector_data: dict[str, Any] = {"dense": dense_vec}
            if norm_text:
                vector_data["bm25"] = models.SparseVector(
                    indices=sparse_emb.indices.tolist(),
                    values=sparse_emb.values.tolist(),
                )
            else:
                total_no_content += 1
            upsert_points.append(
                models.PointStruct(id=pid, vector=vector_data, payload=payload),
            )

        client.upsert(collection_name=args.target, points=upsert_points, wait=True)
        total_upserted += len(upsert_points)
        tracker.set_state(done=total_upserted)
        elapsed = time.time() - t0
        rate = total_upserted / elapsed if elapsed > 0 else 0
        print(
            f"[upsert] {total_upserted}/{src_count - len(existing_ids)} "
            f"({rate:.0f} pts/s, skipped={total_skipped}, no_content={total_no_content})"
        )
        buffer.clear()

    with tracker.stage("migrate"):
        while True:
            if args.limit and total_upserted >= args.limit:
                break

            points, next_offset = client.scroll(
                collection_name=args.source,
                limit=args.batch_size,
                offset=offset,
                with_vectors=True,
                with_payload=True,
            )
            if not points:
                break

            for p in points:
                pid = str(p.id)
                if pid in existing_ids:
                    total_skipped += 1
                    continue
                buffer.append((pid, p.vector, p.payload or {}))

            if len(buffer) >= args.batch_size:
                flush_buffer()
                if args.limit and total_upserted >= args.limit:
                    break

            if next_offset is None:
                break
            offset = next_offset

        flush_buffer()

    elapsed = time.time() - t0
    info = client.get_collection(args.target)
    print(f"[done] {info.points_count} pts in target after {elapsed:.1f}s")
    print(f"       upserted={total_upserted} skipped={total_skipped} no_content={total_no_content}")

    expected = min(src_count, args.limit or src_count)
    delta = info.points_count - expected
    if delta < 0:
        print(
            f"[WARN] target has {info.points_count} pts, expected {expected} (delta={delta}). "
            f"Some points may have failed to upsert — check logs."
        )

    tracker.stop(summary={
        "source": args.source,
        "target": args.target,
        "src_count": src_count,
        "target_count": info.points_count,
        "upserted": total_upserted,
        "skipped": total_skipped,
        "no_content": total_no_content,
        "elapsed_s": round(elapsed, 1),
    })
    return 0 if delta >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())
