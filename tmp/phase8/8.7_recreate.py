"""Phase 8.7 - Recreate collections per finalised dim policy.

Idempotent: if collection already has target dim, leaves it. If wrong dim, recreates.
"""

import sys
import time

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

# Finalised dim policy (roadmap section 11)
DIM_POLICY = {
    "bsl_code_v4": 4096,
    "pdf_documents": 1024,
    "wiki_pages_v1": 1024,
    "graph_embeddings": 1024,
    "bsl_metadata": 1024,
    "skill_library": 1024,
    "conversation_memory": 1024,
    "learned_patterns": 1024,
    "experience_embeddings": 1024,
}

DROP = {"bsl_code_v3"}                                          # remove without recreate
SKIP = {"visual_grounding"}                                     # leave as-is (5 points)
FREEZE_LEGACY = {"learned_patterns", "experience_embeddings"}   # archive to <name>_e5_legacy first

client = QdrantClient(host="localhost", port=6333, timeout=60)


def existing_collections():
    return {c.name for c in client.get_collections().collections}


def get_dim(name):
    try:
        info = client.get_collection(collection_name=name)
    except (UnexpectedResponse, Exception):
        return None
    cfg = info.config.params.vectors
    if hasattr(cfg, "size"):
        return cfg.size
    if isinstance(cfg, dict) and cfg:
        return next(iter(cfg.values())).size
    return None


def freeze_to_legacy(src):
    """Scroll-copy points from src to src + '_e5_legacy', mirroring source schema.

    Idempotency: if legacy already exists, refuse on point_count mismatch
    (partial copy from a crashed run), accept on exact match.
    """
    legacy = src + "_e5_legacy"
    existing = existing_collections()

    src_info = client.get_collection(collection_name=src)
    src_count = src_info.points_count
    src_vectors_cfg = src_info.config.params.vectors  # VectorParams or dict

    if legacy in existing:
        legacy_count = client.get_collection(collection_name=legacy).points_count
        if legacy_count == src_count:
            print("  legacy '%s' already complete (%d points) - skipping" % (legacy, legacy_count))
            return
        raise RuntimeError(
            "Legacy '%s' exists with %d points but source has %d. "
            "Likely partial copy from a crashed run. Resolve manually "
            "(delete '%s' and re-run, or repair)." % (legacy, legacy_count, src_count, legacy)
        )

    print("  creating archive '%s' (mirroring source schema)..." % legacy)
    client.create_collection(collection_name=legacy, vectors_config=src_vectors_cfg)

    offset = None
    copied = 0
    while True:
        points, offset = client.scroll(
            collection_name=src,
            limit=256,
            with_payload=True,
            with_vectors=True,
            offset=offset,
        )
        if not points:
            break
        # Preserve named-vector dict shape when present (do NOT collapse to first vector).
        upserts = [
            models.PointStruct(id=p.id, vector=p.vector, payload=p.payload)
            for p in points
        ]
        client.upsert(collection_name=legacy, points=upserts)
        copied += len(upserts)
        if offset is None:
            break

    # Sanity: archive count should match source (ignoring concurrent writes — none expected here).
    final = client.get_collection(collection_name=legacy).points_count
    if final != src_count:
        print("  WARN: archived %d but source has %d - investigate" % (final, src_count))
    print("  archived %d points -> %s" % (copied, legacy))


def recreate(name, dim):
    existing = existing_collections()
    if name in existing:
        current = get_dim(name)
        if current == dim:
            info = client.get_collection(collection_name=name)
            print("  '%s' already at dim=%d (%d points) - leaving" % (name, dim, info.points_count))
            return
        print("  '%s' has dim=%s, want=%d - recreating" % (name, current, dim))
        client.delete_collection(collection_name=name)
    else:
        print("  '%s' missing - creating fresh at dim=%d" % (name, dim))
    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
    )


t0 = time.time()
existing = existing_collections()
print("Found %d collections before recreate: %s" % (len(existing), sorted(existing)))

# Step 1: drop bsl_code_v3 (no recreate)
for name in sorted(DROP):
    if name in existing:
        print("DROP %s" % name)
        client.delete_collection(collection_name=name)
    else:
        print("DROP %s - already absent" % name)

# Step 2: freeze legacy collections to archive (PRESERVES E5 vectors)
for name in sorted(FREEZE_LEGACY):
    print("FREEZE %s" % name)
    freeze_to_legacy(name)

# Step 3: recreate per dim policy
for name in sorted(DIM_POLICY):
    print("RECREATE %s" % name)
    recreate(name, DIM_POLICY[name])

# Step 4: verify visual_grounding untouched
if "visual_grounding" in existing:
    info = client.get_collection(collection_name="visual_grounding")
    print("SKIP visual_grounding (%d points, dim=%s)" % (info.points_count, get_dim("visual_grounding")))

after = existing_collections()
print("\nDone in %.1fs. Collections after recreate: %s" % (time.time()-t0, sorted(after)))
