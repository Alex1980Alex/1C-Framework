#!/usr/bin/env python3
"""
Framework self-search indexer — Stage 1 (Manual).

Indexes the framework's own codebase (src/, scripts/, .claude/hooks/, .claude/skills/,
docs/, tools/, configs) into Qdrant collection `framework_code_v1` using
Qwen3-Embedding-8B via the running TEI HTTP backend (pdf-rag-tei container).

See docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md §24.

Usage:
    # Full reindex (first run)
    python scripts/index_framework.py --recreate

    # Dry run — chunk only, no embed/upsert (for tuning skip patterns)
    python scripts/index_framework.py --dry-run

    # Smoke test on small subset
    python scripts/index_framework.py --limit 50 --recreate

    # Incremental: re-embed only specific files
    python scripts/index_framework.py --paths src/framework_search/indexer.py
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from _progress import make_tracker  # noqa: E402
from src.framework_search.config import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    DEFAULT_COLLECTION,
    DEFAULT_QDRANT_URL,
    DEFAULT_TEI_URL,
)
from src.framework_search.indexer import run_index  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Index framework codebase into Qdrant")
    ap.add_argument("--collection", default=DEFAULT_COLLECTION)
    ap.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    ap.add_argument("--tei-url", default=DEFAULT_TEI_URL)
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    ap.add_argument("--recreate", action="store_true",
                    help="Drop and recreate the collection")
    ap.add_argument("--dry-run", action="store_true",
                    help="Walk + chunk only, no embedding or upsert")
    ap.add_argument("--limit", type=int, default=0,
                    help="Cap chunks at N (0 = unlimited)")
    ap.add_argument("--paths", nargs="*", default=None,
                    help="Restrict to these repo-relative paths (incremental reindex)")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    only_paths = set(args.paths) if args.paths else None

    # roadmap 260518 follow-up — observability for long-running indexer
    # so callers see heartbeat/[evt] output even when run_index() sits
    # inside a single TEI batch for 20-60s. run_index itself doesn't
    # take a tracker arg (lives in src/), so we wrap only the outer call;
    # finer-grain wiring requires touching src/framework_search/indexer.py.
    tracker = make_tracker("index_framework").start()
    tracker.event(
        "startup",
        collection=args.collection,
        qdrant_url=args.qdrant_url,
        tei_url=args.tei_url,
        batch_size=args.batch_size,
        recreate=bool(args.recreate),
        dry_run=bool(args.dry_run),
        limit=int(args.limit),
        only_paths=len(only_paths) if only_paths else None,
    )

    t0 = time.time()
    with tracker.stage("run_index"):
        stats = run_index(
            only_paths=only_paths,
            collection=args.collection,
            qdrant_url=args.qdrant_url,
            tei_url=args.tei_url,
            batch_size=args.batch_size,
            recreate=args.recreate,
            dry_run=args.dry_run,
            limit=args.limit,
        )
    dt = time.time() - t0

    print()
    print("=" * 60)
    print(f"Framework indexer summary ({dt:.1f}s)")
    print("=" * 60)
    print(f"  files seen:       {stats.get('files_seen', 0)}")
    print(f"  files indexed:    {stats.get('files_indexed', 0)}")
    print(f"  chunks produced:  {stats.get('chunks', 0)}")
    print(f"  embeddings done:  {stats.get('embeddings_done', 0)}")
    by_lang = stats.get("by_language") or {}
    if by_lang:
        print("  by language:")
        for lang, n in sorted(by_lang.items(), key=lambda kv: -kv[1]):
            print(f"    {lang:12s} {n}")
    print(f"  collection:       {args.collection}")
    if args.dry_run:
        print("  (dry-run — nothing was written)")

    tracker.stop(summary={
        "files_seen": stats.get("files_seen", 0),
        "files_indexed": stats.get("files_indexed", 0),
        "chunks": stats.get("chunks", 0),
        "embeddings_done": stats.get("embeddings_done", 0),
        "elapsed_s": round(dt, 1),
        "collection": args.collection,
        "dry_run": bool(args.dry_run),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
