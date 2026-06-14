"""
Deferred Qdrant Indexing — Session Memory Bridge (P5.3)

Background / scheduled indexing of `important_messages` rows from the local
SQLite database (`data/memory_ai.db`) into the Qdrant vector collection
`learned_patterns`.

What it does
------------
1. Ensures the `indexed_in_qdrant` column exists in `important_messages`.
2. Fetches rows that have not yet been indexed (flag = 0 or NULL).
3. Embeds each row's content with the multilingual-E5-large model
   (`intfloat/multilingual-e5-large`, 1024-d vectors).
4. Upserts the vectors + metadata into the Qdrant `learned_patterns`
   collection with deterministic UUIDs (uuid5).
5. Marks the processed rows as indexed so they are skipped on future runs.

Usage
-----
    python scripts/deferred_qdrant_indexing.py
    python scripts/deferred_qdrant_indexing.py --batch 25 --max-batches 50 -v
    python scripts/deferred_qdrant_indexing.py --dry-run

Requirements
------------
- sentence-transformers  (pip install sentence-transformers)
- qdrant-client          (pip install qdrant-client)
- A running Qdrant instance with a `learned_patterns` collection.

Idempotency
-----------
Safe to re-run: already-indexed rows are skipped via `indexed_in_qdrant` flag.
Qdrant point IDs are derived via uuid5 from the original row id, so
re-upserting the same row simply overwrites the previous vector.
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQLITE_DB = PROJECT_ROOT / "data" / "memory_ai.db"
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION = "learned_patterns"
VECTOR_DIM = 1024
EMBED_MODEL = "intfloat/multilingual-e5-large"
BATCH_SIZE = 10


def ensure_schema(conn):
    """Add indexed_in_qdrant column if missing."""
    cur = conn.execute("PRAGMA table_info(important_messages)")
    cols = [r[1] for r in cur.fetchall()]
    if "indexed_in_qdrant" not in cols:
        conn.execute(
            "ALTER TABLE important_messages ADD COLUMN indexed_in_qdrant INTEGER DEFAULT 0"
        )
        conn.commit()
        print("[schema] Added column indexed_in_qdrant")


def fetch_unindexed(conn, limit):
    """Return list of rows where indexed_in_qdrant = 0 (or NULL)."""
    cur = conn.execute(
        "SELECT id, content, importance, category, tags, created_at, metadata "
        "FROM important_messages "
        "WHERE indexed_in_qdrant IS NULL OR indexed_in_qdrant = 0 "
        "ORDER BY importance DESC, created_at DESC "
        "LIMIT ?",
        (limit,),
    )
    return [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]


def get_embedder():
    """Lazy-load E5 model."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBED_MODEL)


def embed_texts(model, texts):
    """Embed with 'passage: ' prefix for E5."""
    prefixed = [f"passage: {t}" for t in texts]
    vectors = model.encode(prefixed, show_progress_bar=False, normalize_embeddings=True)
    return vectors.tolist()


def upsert_to_qdrant(client, rows, vectors):
    """Upsert rows to learned_patterns with payload."""
    import uuid

    from qdrant_client.models import PointStruct

    points = []
    for row, vec in zip(rows, vectors):
        pid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"session:{row['id']}"))
        points.append(
            PointStruct(
                id=pid,
                vector=vec,
                payload={
                    "original_id": row["id"],
                    "content": row["content"],
                    "category": row["category"],
                    "importance": row["importance"],
                    "tags": row.get("tags"),
                    "created_at": row["created_at"],
                    "source": "memory_ai_session",
                },
            )
        )
    client.upsert(collection_name=COLLECTION, points=points)


def mark_indexed(conn, row_ids):
    """Flag the given row ids as indexed in SQLite."""
    placeholders = ",".join(["?"] * len(row_ids))
    conn.execute(
        f"UPDATE important_messages SET indexed_in_qdrant = 1 WHERE id IN ({placeholders})",
        row_ids,
    )
    conn.commit()


def main():
    parser = argparse.ArgumentParser(
        description="Deferred Qdrant indexing of memory_ai session summaries"
    )
    parser.add_argument("--batch", type=int, default=BATCH_SIZE, help="Batch size per run")
    parser.add_argument("--max-batches", type=int, default=10, help="Max batches in one run")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to Qdrant/SQLite")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not SQLITE_DB.exists():
        print(f"[ERROR] SQLite not found: {SQLITE_DB}")
        return 1

    conn = sqlite3.connect(str(SQLITE_DB), timeout=5)
    ensure_schema(conn)

    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(QDRANT_HOST, port=QDRANT_PORT, timeout=5)
        collections = [c.name for c in client.get_collections().collections]
        if COLLECTION not in collections:
            print(f"[ERROR] Collection {COLLECTION} not found")
            conn.close()
            return 1
    except Exception as e:
        print(f"[ERROR] Qdrant not available: {e}")
        conn.close()
        return 1

    print(f"[embed] Loading {EMBED_MODEL}...")
    t0 = time.time()
    embedder = get_embedder() if not args.dry_run else None
    print(f"[embed] Loaded in {time.time() - t0:.1f}s")

    total_indexed = 0
    for batch_num in range(args.max_batches):
        rows = fetch_unindexed(conn, args.batch)
        if not rows:
            print(f"[done] No more unindexed rows after {total_indexed} total")
            break

        print(f"[batch {batch_num + 1}] Processing {len(rows)} rows...")

        if args.dry_run:
            for r in rows:
                row_id = r["id"]
                display_id = row_id[:8] if isinstance(row_id, str) else row_id
                print(f"  [dry] would index {display_id}... category={r['category']}")
            total_indexed += len(rows)
            continue

        texts = [r["content"] for r in rows]
        t0 = time.time()
        try:
            vectors = embed_texts(embedder, texts)
        except Exception as exc:
            print(f"  [ERROR] Embedding failed: {exc}")
            break
        if args.verbose:
            print(f"  [embed] {len(texts)} texts in {time.time() - t0:.2f}s")

        try:
            upsert_to_qdrant(client, rows, vectors)
            mark_indexed(conn, [r["id"] for r in rows])
            total_indexed += len(rows)
            print(f"  [upsert] OK, total indexed: {total_indexed}")
        except Exception as e:
            print(f"  [ERROR] Upsert failed: {e}")
            break

    conn.close()
    print(f"[SUMMARY] Indexed {total_indexed} rows to {COLLECTION}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
