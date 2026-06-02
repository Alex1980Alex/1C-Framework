"""Alias swap: bsl_code_v4_late -> bsl_code_v4_late_hybrid (atomic via Qdrant aliases).

Sequence:
  1. Backup old: copy `bsl_code_v4_late` (single-vector 4096d) to
     `bsl_code_v4_late_4096_backup` via scroll+upsert. Same layout, no
     transforms — cheaper than snapshot/restore.
  2. Verify backup count == source count.
  3. Delete physical `bsl_code_v4_late` collection.
  4. Create alias `bsl_code_v4_late` -> `bsl_code_v4_late_hybrid`.

After this, BSL search clients addressing `bsl_code_v4_late` get hybrid
layout transparently. Rollback: delete the alias, rename backup back
(via another scroll+upsert) — slow but possible.

Refuses to swap if:
  - source already an alias (means a prior swap ran)
  - hybrid target points_count < source points_count (incomplete migration)
  - backup already exists (idempotency guard — manual cleanup required)

Usage:
    .venv\\Scripts\\python.exe scripts\\alias_swap_bsl_hybrid.py
    .venv\\Scripts\\python.exe scripts\\alias_swap_bsl_hybrid.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _progress import make_tracker
from qdrant_client import QdrantClient, models


def copy_collection(
    client: QdrantClient,
    src: str,
    dst: str,
    batch_size: int = 512,
) -> int:
    """Copy all points (vectors + payload) from `src` to `dst`. Returns total copied.

    Preserves vector layout — single-vector source produces single-vector
    destination. Created destination collection mirrors source dims/distance.
    """
    src_info = client.get_collection(src)
    src_dim = src_info.config.params.vectors.size
    src_distance = src_info.config.params.vectors.distance
    src_count = src_info.points_count

    try:
        client.get_collection(dst)
        raise RuntimeError(
            f"Destination '{dst}' already exists. Delete it manually or pick "
            f"a different name — refusing to clobber."
        )
    except RuntimeError:
        raise
    except Exception:
        pass

    client.create_collection(
        collection_name=dst,
        vectors_config=models.VectorParams(size=src_dim, distance=src_distance),
    )
    print(f"[backup] created {dst} ({src_dim}d, distance={src_distance})")

    offset = None
    copied = 0
    t0 = time.time()
    while True:
        points, next_offset = client.scroll(
            collection_name=src,
            limit=batch_size,
            offset=offset,
            with_vectors=True,
            with_payload=True,
        )
        if not points:
            break
        upsert_points = [
            models.PointStruct(id=str(p.id), vector=p.vector, payload=p.payload or {})
            for p in points
        ]
        client.upsert(collection_name=dst, points=upsert_points, wait=True)
        copied += len(upsert_points)
        if copied % (batch_size * 10) == 0 or next_offset is None:
            elapsed = time.time() - t0
            rate = copied / elapsed if elapsed > 0 else 0
            print(f"[backup] {copied}/{src_count} ({rate:.0f} pts/s)")
        if next_offset is None:
            break
        offset = next_offset

    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdrant-url", default="http://localhost:6333")
    parser.add_argument("--source", default="bsl_code_v4_late")
    parser.add_argument("--hybrid", default="bsl_code_v4_late_hybrid")
    parser.add_argument("--backup", default="bsl_code_v4_late_4096_backup")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify preconditions and print intended actions, then exit without changes.",
    )
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Skip the backup copy step (use only if a backup already exists or is not needed).",
    )
    args = parser.parse_args()

    tracker = make_tracker("alias_swap_bsl_hybrid").start()
    client = QdrantClient(url=args.qdrant_url, timeout=600)

    # Preconditions.
    try:
        aliases_info = client.get_aliases()
        alias_names = {a.alias_name for a in aliases_info.aliases}
    except AttributeError:
        alias_names = set()

    # `bsl_code_v4_late` is already an alias after 2026-05-20 Phase 5 swap to
    # `bsl_code_v4_late_v2` (std pooling + FA2). Atomic re-point of the alias
    # is the safest and cheapest path — the previous physical `_v2` collection
    # remains untouched as the backup, no copy needed.
    current_alias_target: str | None = None
    if args.source in alias_names:
        for a in aliases_info.aliases:
            if a.alias_name == args.source:
                current_alias_target = a.collection_name
                break
        print(f"[check] '{args.source}' is alias -> '{current_alias_target}' (will become backup)")

    try:
        src_info = client.get_collection(args.source)
    except Exception as e:
        print(f"ERROR: cannot read source '{args.source}': {e}")
        tracker.stop(summary={"status": "source_missing", "source": args.source})
        return 1

    try:
        hyb_info = client.get_collection(args.hybrid)
    except Exception as e:
        print(f"ERROR: cannot read hybrid target '{args.hybrid}': {e}")
        tracker.stop(summary={"status": "hybrid_missing", "hybrid": args.hybrid})
        return 1

    src_count = src_info.points_count
    hyb_count = hyb_info.points_count
    print(f"[check] source '{args.source}': {src_count} pts (single-vector)")
    print(f"[check] hybrid '{args.hybrid}': {hyb_count} pts (named dense+sparse)")
    tracker.event("preflight", src_count=src_count, hyb_count=hyb_count)

    if hyb_count < src_count:
        print(
            f"ERROR: hybrid has {hyb_count} pts < source {src_count}. "
            f"Run scripts/migrate_bsl_to_hybrid.py first."
        )
        tracker.stop(summary={"status": "incomplete_migration"})
        return 1

    if args.dry_run:
        print("\n[dry-run] would execute:")
        if current_alias_target:
            print(f"  1. atomic alias re-point: '{args.source}' -> '{args.hybrid}'")
            print(f"     (previous target '{current_alias_target}' kept as implicit backup)")
        else:
            if not args.skip_backup:
                print(f"  1. copy {args.source} -> {args.backup}")
            print(f"  2. delete collection {args.source}")
            print(f"  3. create alias {args.source} -> {args.hybrid}")
        tracker.stop(summary={"status": "dry_run_ok"})
        return 0

    if current_alias_target:
        # Cheap path: source is already an alias. Atomic delete+create in a
        # single update_collection_aliases call — no backup copy needed since
        # the previous alias target physical collection stays in place.
        with tracker.stage("atomic_alias_swap"):
            client.update_collection_aliases(
                change_aliases_operations=[
                    models.DeleteAliasOperation(
                        delete_alias=models.DeleteAlias(alias_name=args.source),
                    ),
                    models.CreateAliasOperation(
                        create_alias=models.CreateAlias(
                            collection_name=args.hybrid,
                            alias_name=args.source,
                        ),
                    ),
                ],
            )
            print(
                f"[swap] alias '{args.source}': '{current_alias_target}' -> '{args.hybrid}' "
                f"(previous physical kept as implicit backup)"
            )
    else:
        # Original path — source is a physical collection.
        if not args.skip_backup:
            with tracker.stage("backup_copy"):
                copied = copy_collection(client, args.source, args.backup)
                print(f"[backup] copied {copied} pts -> {args.backup}")
                backup_info = client.get_collection(args.backup)
                if backup_info.points_count != src_count:
                    print(
                        f"ERROR: backup count mismatch: {backup_info.points_count} vs source {src_count}. "
                        f"Aborting swap — manually inspect {args.backup} and rerun with --skip-backup if OK."
                    )
                    tracker.stop(summary={"status": "backup_mismatch"})
                    return 1

        with tracker.stage("delete_source"):
            client.delete_collection(collection_name=args.source)
            print(f"[swap] deleted physical collection {args.source}")

        with tracker.stage("create_alias"):
            client.update_collection_aliases(
                change_aliases_operations=[
                    models.CreateAliasOperation(
                        create_alias=models.CreateAlias(
                            collection_name=args.hybrid,
                            alias_name=args.source,
                        ),
                    ),
                ],
            )
            print(f"[swap] created alias {args.source} -> {args.hybrid}")

    # Verify alias resolves to hybrid.
    resolved = client.get_collection(args.source)
    print(f"[verify] alias {args.source} resolves to {resolved.points_count} pts")
    sparse_cfg = resolved.config.params.sparse_vectors
    has_sparse = bool(sparse_cfg and "bm25" in sparse_cfg)
    if not has_sparse:
        print("WARN: resolved collection does not advertise sparse 'bm25' — check layout")
    else:
        print("[verify] alias points to hybrid layout (dense + bm25 sparse)")

    tracker.stop(
        summary={
            "status": "ok",
            "source": args.source,
            "hybrid": args.hybrid,
            "backup": args.backup if not args.skip_backup else None,
            "resolved_count": resolved.points_count,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
