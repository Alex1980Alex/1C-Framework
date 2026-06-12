#!/usr/bin/env python3
"""memory-ai hygiene backfill (roadmap 260612 P0.1/P0.2).

Three idempotent steps over ``data/memory_ai.db`` (``important_messages``):

1. **content_hash backfill** — stamp the canonical cross-store idempotency key
   (``memory.orchestrator.content_hash.hash_content``) into ``metadata`` for
   every row that lacks it, so ``cross_store_sync`` / ``fact-trace`` see the
   episodic store (was 12/107).
2. **dup merge** — collapse legacy duplicate groups (identical ``content``,
   pre-P1.3 dedup era): the OLDEST row survives; link_registry edges that
   reference a removed duplicate (``episodic:memory-ai:<id>``) are re-pointed
   at the survivor; survivor keeps ``max(importance)`` / ``max(indexed_in_qdrant)``
   of the group.
3. **index-flag fix (G1)** — ``indexed_in_qdrant=1`` rows are verified against
   the live ``learned_patterns`` collection by the retired deferred-indexer's
   deterministic point id (``uuid5(NAMESPACE_URL, "session:<row_id>")``); flags
   whose points no longer exist are reset to 0. Re-inventory 2026-06-12: 18/33
   points are alive (re-embedded 4096d during the Qwen3 migration), only 15 are
   dead — so the reset is surgical, not the blanket 33 the roadmap assumed.

Dry-run by default; pass ``--apply`` to write. ``MEMORY_AI_DB_PATH`` /
``LINK_REGISTRY_PATH`` env overrides are honored (test isolation).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory.ai_memory.db import connect as ai_connect
from memory.ai_memory.db import resolve_db_path
from memory.orchestrator.content_hash import hash_content

QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION = "learned_patterns"


def _link_registry_path() -> Path:
    return Path(
        os.environ.get("LINK_REGISTRY_PATH") or PROJECT_ROOT / "data" / "link_registry.db"
    )


def _load_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return conn.execute(
        "SELECT id, content, importance, category, tags, created_at, metadata, "
        "indexed_in_qdrant FROM important_messages ORDER BY created_at"
    ).fetchall()


def _metadata_dict(raw: str | None) -> dict:
    try:
        md = json.loads(raw or "{}")
        return md if isinstance(md, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def backfill_hashes(conn: sqlite3.Connection, apply: bool) -> int:
    """Step 1: stamp content_hash into metadata where missing."""
    pending = []
    for row in _load_rows(conn):
        md = _metadata_dict(row["metadata"])
        if not md.get("content_hash"):
            md["content_hash"] = hash_content(row["content"] or "")
            pending.append((json.dumps(md, ensure_ascii=False), row["id"]))
    if apply and pending:
        conn.executemany(
            "UPDATE important_messages SET metadata = ? WHERE id = ?", pending
        )
        conn.commit()
    return len(pending)


def merge_duplicates(conn: sqlite3.Connection, apply: bool) -> list[dict]:
    """Step 2: oldest row per identical content survives; edges transferred."""
    groups: dict[str, list[sqlite3.Row]] = {}
    for row in _load_rows(conn):
        groups.setdefault(row["content"] or "", []).append(row)

    merged: list[dict] = []
    lr_path = _link_registry_path()
    lr_conn = sqlite3.connect(str(lr_path)) if lr_path.exists() else None
    try:
        for content, rows in groups.items():
            if len(rows) < 2:
                continue
            rows.sort(key=lambda r: r["created_at"] or "")
            survivor, dups = rows[0], rows[1:]
            survivor_uid = f"episodic:memory-ai:{survivor['id']}"
            moved_edges = 0
            for dup in dups:
                dup_uid = f"episodic:memory-ai:{dup['id']}"
                if lr_conn is not None:
                    for col in ("source_id", "target_id"):
                        cur = lr_conn.execute(
                            f"SELECT COUNT(*) FROM entity_links WHERE {col} = ?", (dup_uid,)
                        )
                        moved_edges += cur.fetchone()[0]
                        if apply:
                            lr_conn.execute(
                                f"UPDATE entity_links SET {col} = ? WHERE {col} = ?",
                                (survivor_uid, dup_uid),
                            )
                if apply:
                    conn.execute(
                        "DELETE FROM important_messages WHERE id = ?", (dup["id"],)
                    )
            if apply:
                # Self-loops can appear when both endpoints were in-group.
                if lr_conn is not None:
                    lr_conn.execute(
                        "DELETE FROM entity_links WHERE source_id = ? AND target_id = ?",
                        (survivor_uid, survivor_uid),
                    )
                    # Re-pointing can collide with an identical existing edge —
                    # keep the oldest of each (source,target,type) group.
                    lr_conn.execute(
                        "DELETE FROM entity_links WHERE link_id NOT IN ("
                        "  SELECT MIN(link_id) FROM entity_links"
                        "  WHERE source_id = ? OR target_id = ?"
                        "  GROUP BY source_id, target_id, link_type"
                        ") AND (source_id = ? OR target_id = ?)",
                        (survivor_uid, survivor_uid, survivor_uid, survivor_uid),
                    )
                conn.execute(
                    "UPDATE important_messages SET importance = ?, indexed_in_qdrant = ? "
                    "WHERE id = ?",
                    (
                        max(float(r["importance"] or 0.0) for r in rows),
                        max(int(r["indexed_in_qdrant"] or 0) for r in rows),
                        survivor["id"],
                    ),
                )
            merged.append(
                {
                    "survivor": survivor["id"],
                    "removed": [d["id"] for d in dups],
                    "edges_moved": moved_edges,
                    "content_preview": content[:60],
                }
            )
        if apply:
            conn.commit()
            if lr_conn is not None:
                lr_conn.commit()
    finally:
        if lr_conn is not None:
            lr_conn.close()
    return merged


def _qdrant_existing(point_ids: list[str]) -> set[str] | None:
    """Return ids that exist in learned_patterns, or None if Qdrant unreachable."""
    if not point_ids:
        return set()
    req = urllib.request.Request(
        f"{QDRANT_URL}/collections/{COLLECTION}/points",
        data=json.dumps(
            {"ids": point_ids, "with_payload": False, "with_vector": False}
        ).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = json.load(urllib.request.urlopen(req, timeout=10))
        return {str(p["id"]) for p in resp.get("result", [])}
    except Exception as exc:  # Qdrant down → honest skip, no blind flag reset
        print(f"[flags] Qdrant unreachable ({exc}) — step skipped", file=sys.stderr)
        return None


def fix_index_flags(conn: sqlite3.Connection, apply: bool) -> dict:
    """Step 3 (G1): reset indexed_in_qdrant only for rows whose point is dead."""
    rows = conn.execute(
        "SELECT id FROM important_messages WHERE indexed_in_qdrant = 1"
    ).fetchall()
    row_to_point = {
        r[0]: str(uuid.uuid5(uuid.NAMESPACE_URL, f"session:{r[0]}")) for r in rows
    }
    existing = _qdrant_existing(list(row_to_point.values()))
    if existing is None:
        return {"flagged": len(rows), "alive": None, "reset": 0, "skipped": True}
    dead = [rid for rid, pid in row_to_point.items() if pid not in existing]
    if apply and dead:
        conn.executemany(
            "UPDATE important_messages SET indexed_in_qdrant = 0 WHERE id = ?",
            [(rid,) for rid in dead],
        )
        conn.commit()
    return {
        "flagged": len(rows),
        "alive": len(rows) - len(dead),
        "reset": len(dead),
        "skipped": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument(
        "--skip-flags", action="store_true", help="Skip the Qdrant index-flag verification step"
    )
    args = parser.parse_args()
    mode = "APPLY" if args.apply else "DRY-RUN"

    db_path = resolve_db_path()
    if not db_path.exists():
        print(f"[ERROR] DB not found: {db_path}")
        return 1
    conn = ai_connect(db_path)
    try:
        stamped = backfill_hashes(conn, args.apply)
        print(f"[{mode}] content_hash stamped: {stamped}")

        merged = merge_duplicates(conn, args.apply)
        for g in merged:
            print(
                f"[{mode}] dup-group survivor={g['survivor'][:8]} "
                f"removed={len(g['removed'])} edges_moved={g['edges_moved']} "
                f"| {g['content_preview']!r}"
            )
        print(f"[{mode}] dup groups merged: {len(merged)}")

        if args.skip_flags:
            print(f"[{mode}] index-flag step skipped (--skip-flags)")
        else:
            flags = fix_index_flags(conn, args.apply)
            print(f"[{mode}] index flags: {flags}")

        total = conn.execute("SELECT COUNT(*) FROM important_messages").fetchone()[0]
        print(f"[{mode}] rows now: {total}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
