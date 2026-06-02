#!/usr/bin/env python3
"""Dedupe + cleanup the `learned_patterns` Qdrant collection.

The collection accumulated exact-content duplicates (e.g. ``calculate_rrf_score``
x4 with distinct point IDs but identical content) plus a couple of test records.
This collapses each group of byte-identical content to a single survivor and
optionally drops known test markers, so the collection is fit for real learning.

SAFETY (this is a destructive, irreversible Qdrant mutation):
  - **dry-run by default** — prints the plan; ``--apply`` is required to mutate.
  - **backup first** — before any delete, every point (id + payload + vector) is
    exported to ``data/memory/backups/learned_patterns_<ts>.json``. Restore with
    ``--restore <file> --apply`` (re-upserts the snapshot). ``--no-backup`` opts out.
  - **conservative** — survivor per content group = the richest schema
    (``pattern_id``) with the earliest ``created_at``, else the earliest overall;
    succ/fail/application_count are SUMMED into the survivor (no learning lost) and
    its ``confidence`` denorm is recomputed from the merged counts (§22 Beta(7,3)).
  - test removal is **opt-in** (``--drop-test``) and matches an explicit exact-content
    allowlist only — never broad heuristics.

Usage:
  python scripts/dedupe_learned_patterns.py                 # dry-run plan
  python scripts/dedupe_learned_patterns.py --drop-test     # include test records in plan
  python scripts/dedupe_learned_patterns.py --apply --drop-test
  python scripts/dedupe_learned_patterns.py --restore data/memory/backups/learned_patterns_<ts>.json --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLECTION = "learned_patterns"
BACKUP_DIR = PROJECT_ROOT / "data" / "memory" / "backups"

# Exact full-content test records to drop with --drop-test (allowlist, not heuristic).
TEST_MARKERS = frozenset(
    {
        "Testing vector-memory save after dimension fix",
        "Entity lookup test content",
    }
)


def _content(payload: dict[str, Any]) -> str:
    return payload.get("content") or payload.get("description") or ""


def content_key(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_content(payload).encode("utf-8", errors="replace")).hexdigest()[:16]


def _num(payload: dict[str, Any], key: str) -> float:
    v = payload.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def derive_confidence(succ: float, fail: float) -> float:
    """§22 Beta(7,3) posterior mean; falls back to the inline formula on import error."""
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.vector_memory.confidence import derive_confidence as _dc

        return float(_dc(succ, fail))
    except Exception:
        return (7.0 + succ) / (10.0 + succ + fail)


def pick_survivor(group: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep the richest schema (has pattern_id) with the earliest created_at.

    Falls back to the earliest created_at overall, then to the first element.
    """
    def sort_key(pt: dict[str, Any]) -> tuple:
        pl = pt["payload"]
        is_rich = 0 if pl.get("pattern_id") else 1   # prefer pattern_id schema
        created = str(pl.get("created_at") or "~")    # "~" sorts after ISO dates
        return (is_rich, created)

    return sorted(group, key=sort_key)[0]


def build_plan(points: list[dict[str, Any]], drop_test: bool) -> dict[str, Any]:
    """Pure planner: group by content, choose survivors, compute merges/deletes."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for pt in points:
        groups.setdefault(content_key(pt["payload"]), []).append(pt)

    delete_ids: list[str] = []
    survivor_updates: list[dict[str, Any]] = []
    dup_groups = 0

    for group in groups.values():
        survivor = pick_survivor(group)
        losers = [p for p in group if p["id"] != survivor["id"]]
        if not losers:
            continue
        dup_groups += 1
        delete_ids.extend(p["id"] for p in losers)
        # Merge counts across the whole group into the survivor.
        succ = sum(_num(p["payload"], "succ") for p in group)
        fail = sum(_num(p["payload"], "fail") for p in group)
        appc = sum(_num(p["payload"], "application_count") for p in group)
        cur = survivor["payload"]
        if (
            _num(cur, "succ") != succ
            or _num(cur, "fail") != fail
            or _num(cur, "application_count") != appc
        ):
            survivor_updates.append(
                {
                    "id": survivor["id"],
                    "succ": succ,
                    "fail": fail,
                    "application_count": int(appc),
                    "confidence": round(derive_confidence(succ, fail), 6),
                }
            )

    test_ids: list[str] = []
    if drop_test:
        kept_after_dedup = {p["id"] for p in points} - set(delete_ids)
        for pt in points:
            if pt["id"] in kept_after_dedup and _content(pt["payload"]).strip() in TEST_MARKERS:
                test_ids.append(pt["id"])

    return {
        "total": len(points),
        "unique_groups": len(groups),
        "dup_groups": dup_groups,
        "dup_delete_ids": delete_ids,
        "survivor_updates": survivor_updates,
        "test_delete_ids": test_ids,
        "final_count": len(points) - len(delete_ids) - len(test_ids),
    }


# --------------------------------------------------------------------------- I/O
def _client():
    from qdrant_client import QdrantClient

    return QdrantClient(host="127.0.0.1", port=6333, timeout=30)


def fetch_points(client, with_vectors: bool = False) -> list[dict[str, Any]]:
    points, _ = client.scroll(
        collection_name=COLLECTION, limit=10000,
        with_payload=True, with_vectors=with_vectors,
    )
    out = []
    for p in points:
        rec = {"id": str(p.id), "payload": p.payload or {}}
        if with_vectors:
            rec["vector"] = p.vector
        out.append(rec)
    return out


def write_backup(client, stamp: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    full = fetch_points(client, with_vectors=True)
    path = BACKUP_DIR / f"{COLLECTION}_{stamp}.json"
    blob = json.dumps({"collection": COLLECTION, "points": full}, ensure_ascii=False)
    # Atomic write: the backup is the recovery artifact, so a crash mid-write must not
    # leave it truncated. Write to a temp file, then os.replace (atomic on win32 + posix).
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(blob, encoding="utf-8")
    os.replace(tmp, path)
    return path


def restore_backup(client, path: Path) -> int:
    from qdrant_client.models import PointStruct

    data = json.loads(path.read_text(encoding="utf-8"))
    pts = data.get("points", [])
    structs = [
        PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload", {}))
        for p in pts
        if p.get("vector") is not None
    ]
    if structs:
        client.upsert(collection_name=COLLECTION, points=structs)
    return len(structs)


def apply_plan(client, plan: dict[str, Any]) -> None:
    for upd in plan["survivor_updates"]:
        client.set_payload(
            collection_name=COLLECTION,
            payload={
                "succ": upd["succ"], "fail": upd["fail"],
                "application_count": upd["application_count"], "confidence": upd["confidence"],
            },
            points=[upd["id"]],
        )
    to_delete = plan["dup_delete_ids"] + plan["test_delete_ids"]
    if to_delete:
        client.delete(collection_name=COLLECTION, points_selector=to_delete)


def main() -> int:
    ap = argparse.ArgumentParser(description="dedupe + cleanup learned_patterns")
    ap.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    ap.add_argument("--drop-test", action="store_true", help="also drop exact test records")
    ap.add_argument("--no-backup", action="store_true", help="skip backup (not recommended)")
    ap.add_argument("--restore", default=None, help="restore from a backup JSON (needs --apply)")
    ap.add_argument("--stamp", default=None, help="override backup timestamp (tests)")
    args = ap.parse_args()

    try:
        client = _client()
    except Exception as exc:
        print(f"Qdrant unavailable: {exc}", file=sys.stderr)
        return 1

    if args.restore:
        if not args.apply:
            print(f"Dry-run: would restore {COLLECTION} from {args.restore} (use --apply).")
            return 0
        n = restore_backup(client, Path(args.restore))
        print(f"Restored {n} points into {COLLECTION} from {args.restore}.")
        return 0

    points = fetch_points(client)
    plan = build_plan(points, drop_test=args.drop_test)

    print(f"# learned_patterns dedupe (apply={args.apply}, drop_test={args.drop_test})")
    print(f"total={plan['total']} unique_content_groups={plan['unique_groups']} "
          f"dup_groups={plan['dup_groups']}")
    print(f"dup copies to delete: {len(plan['dup_delete_ids'])}")
    print(f"survivor stat-merges: {len(plan['survivor_updates'])}")
    print(f"test records to delete: {len(plan['test_delete_ids'])}")
    print(f"final count: {plan['final_count']} (from {plan['total']})")

    if not args.apply:
        print("\n-> dry-run; re-run with --apply to execute.")
        return 0

    stamp = args.stamp or _safe_stamp()
    if not args.no_backup:
        bpath = write_backup(client, stamp)
        print(f"\nbackup: {bpath}")
    apply_plan(client, plan)
    remaining = len(fetch_points(client))
    print(f"-> DONE. collection now has {remaining} points "
          f"(restore: --restore {BACKUP_DIR / (COLLECTION + '_' + stamp + '.json')} --apply)")
    return 0


def _safe_stamp() -> str:
    # Date.now() is fine here (CLI, not a resumable workflow).
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


if __name__ == "__main__":
    raise SystemExit(main())
