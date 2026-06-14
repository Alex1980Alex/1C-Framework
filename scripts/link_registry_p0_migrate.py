#!/usr/bin/env python3
"""P0.1 migration: raw-UUID edges in link_registry → unified IDs (roadmap 260612 LinkRegistry).

Находит рёбра, чьи концы не в формате `type:source:identifier` (3 легаси-ребра
эпохи до тест-изоляции 260609), резолвит каждый сырой UUID по живым store'ам:
  - data/memory_ai.db important_messages → `episodic:memory-ai:<uuid>`
  - Qdrant learned_patterns             → `semantic:vector-memory:<uuid>`
Разрешимые концы переписываются (history action=update, reason=P0.1);
ребро с неразрешимым концом удаляется (history action=delete).
Затем rebuild_stats() (P0.2).

Dry-run по умолчанию; --apply для записи. Перед запуском снят дамп
data/reports/memory/link_registry_pre_p0_dump.json (32 ребра, 2026-06-12).
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("link-p0-migrate")

LINK_DB = PROJECT_ROOT / "data" / "link_registry.db"
MEMORY_AI_DB = PROJECT_ROOT / "data" / "memory_ai.db"


def is_unified(entity_id: str) -> bool:
    parts = entity_id.split(":", 2)
    return len(parts) == 3 and all(p.strip() for p in parts)


def resolve_raw(raw_id: str, qdrant_url: str) -> str | None:
    """Map a bare UUID to a unified ID by probing live stores."""
    try:
        conn = sqlite3.connect(MEMORY_AI_DB)
        try:
            hit = conn.execute(
                "SELECT 1 FROM important_messages WHERE id = ?", (raw_id,)
            ).fetchone()
        finally:
            conn.close()
        if hit:
            return f"episodic:memory-ai:{raw_id}"
    except sqlite3.Error as exc:
        logger.warning("memory_ai probe failed for %s: %s", raw_id, exc)

    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=qdrant_url)
        pts = client.retrieve("learned_patterns", ids=[raw_id])
        if pts:
            return f"semantic:vector-memory:{raw_id}"
    except Exception as exc:
        logger.warning("qdrant probe failed for %s: %s", raw_id, exc)

    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate raw-UUID link endpoints to unified IDs")
    ap.add_argument("--apply", action="store_true", help="Write changes (default dry-run)")
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    conn = sqlite3.connect(LINK_DB)
    conn.row_factory = sqlite3.Row
    edges = conn.execute("SELECT * FROM entity_links").fetchall()

    migrated, deleted = 0, 0
    now = datetime.now().isoformat()

    for edge in edges:
        src, tgt = edge["source_id"], edge["target_id"]
        if is_unified(src) and is_unified(tgt):
            continue

        new_src = src if is_unified(src) else resolve_raw(src, args.qdrant_url)
        new_tgt = tgt if is_unified(tgt) else resolve_raw(tgt, args.qdrant_url)
        link_id = edge["link_id"]

        if new_src and new_tgt:
            logger.info(
                "%s MIGRATE %s [%s]: %s -> %s | %s -> %s",
                "[APPLY]" if args.apply else "[DRY-RUN]",
                link_id[:8],
                edge["link_type"],
                src,
                new_src,
                tgt,
                new_tgt,
            )
            if args.apply:
                conn.execute(
                    "UPDATE entity_links SET source_id = ?, target_id = ? WHERE link_id = ?",
                    (new_src, new_tgt, link_id),
                )
                conn.execute(
                    "INSERT INTO link_history (history_id, link_id, action, changed_at, changed_by, reason) "
                    "VALUES (?, ?, 'update', ?, 'link-p0-migrate', ?)",
                    (
                        str(uuid4()),
                        link_id,
                        now,
                        f"P0.1 raw-UUID migration: {src}|{tgt} -> unified",
                    ),
                )
            migrated += 1
        else:
            logger.info(
                "%s DELETE %s [%s]: unresolvable %s -> %s",
                "[APPLY]" if args.apply else "[DRY-RUN]",
                link_id[:8],
                edge["link_type"],
                src,
                tgt,
            )
            if args.apply:
                conn.execute("DELETE FROM entity_links WHERE link_id = ?", (link_id,))
                conn.execute(
                    "INSERT INTO link_history (history_id, link_id, action, changed_at, changed_by, reason) "
                    "VALUES (?, ?, 'delete', ?, 'link-p0-migrate', "
                    "'P0.1: endpoints unresolvable in any live store')",
                    (str(uuid4()), link_id, now),
                )
            deleted += 1

    if args.apply:
        conn.commit()
        conn.close()
        from src.memory.orchestrator.link_registry import LinkRegistry

        stats = LinkRegistry(db_path=str(LINK_DB)).rebuild_stats()
        logger.info("rebuild_stats: %s", json.dumps(stats))
    else:
        conn.close()

    logger.info(
        "Done (%s): migrated=%d deleted=%d",
        "applied" if args.apply else "dry-run",
        migrated,
        deleted,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
