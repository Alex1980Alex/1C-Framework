#!/usr/bin/env python3
"""
Framework-search file watcher daemon — Stage 3.

Polling-based: every POLL_INTERVAL_SEC scans for files whose on-disk mtime
exceeds the indexed mtime, then triggers incremental reindex on the changed
set. Complements the MCP server's lazy-check (which fires on demand) by
keeping the index warm in the background.

Why polling, not watchdog/inotify:
  - Zero extra deps (watchdog not in this repo's stack)
  - Cross-platform (no Windows-specific quirks of ReadDirectoryChangesW)
  - For ~30k files a 5-second scan is ~50-100ms in practice; CPU cost negligible
  - No risk of dropped events (inotify queue overflow on bulk operations)

Usage:
    # Foreground (Ctrl+C to stop)
    python scripts/watch_framework.py

    # With debounce + custom interval
    python scripts/watch_framework.py --poll-interval 10 --debounce 3.0

    # Background daemon-style (Windows: use Task Scheduler or nssm)
    python scripts/watch_framework.py --quiet > watcher.log 2>&1 &
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from collections.abc import Iterable
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from qdrant_client import QdrantClient  # noqa: E402

from src.framework_search.config import (  # noqa: E402
    DEFAULT_COLLECTION,
    DEFAULT_QDRANT_URL,
    DEFAULT_TEI_URL,
)
from src.framework_search.file_walker import iter_indexable_files  # noqa: E402
from src.framework_search.indexer import run_index  # noqa: E402

logger = logging.getLogger("watch-framework")

DEFAULT_POLL_INTERVAL_SEC = 5.0
DEFAULT_DEBOUNCE_SEC = 2.0
DEFAULT_MAX_FILES_PER_BATCH = 100


_stop_requested = False


def _handle_signal(signum: int, _frame) -> None:
    global _stop_requested
    logger.info("watcher: received signal %d, shutting down gracefully", signum)
    _stop_requested = True


def _load_indexed_mtimes(client: QdrantClient, collection: str) -> dict[str, float]:
    """Return {relative_path: max_indexed_mtime} from Qdrant payload."""
    indexed: dict[str, float] = {}
    if not client.collection_exists(collection):
        return indexed
    next_offset = None
    while True:
        recs, next_offset = client.scroll(
            collection_name=collection,
            limit=512,
            with_payload=["relative_path", "mtime"],
            with_vectors=False,
            offset=next_offset,
        )
        if not recs:
            break
        for r in recs:
            p = r.payload or {}
            rel = p.get("relative_path")
            mt = float(p.get("mtime") or 0.0)
            if rel and mt > indexed.get(rel, 0.0):
                indexed[rel] = mt
        if next_offset is None:
            break
    return indexed


def _scan_changed(indexed: dict[str, float], debounce_sec: float) -> set[str]:
    """Return repo-relative POSIX paths whose on-disk mtime is newer than indexed.

    Excludes files modified within the last `debounce_sec` (still being edited).
    """
    now = time.time()
    changed: set[str] = set()
    for fp, rel, _lang in iter_indexable_files():
        try:
            on_disk = fp.stat().st_mtime
        except OSError:
            continue
        if now - on_disk < debounce_sec:
            continue  # still being edited, skip this round
        idx_mt = indexed.get(rel)
        if idx_mt is None or on_disk > idx_mt + 1.0:  # +1s for FS clock skew
            changed.add(rel)
    return changed


def _reindex(
    paths: Iterable[str],
    *,
    collection: str,
    qdrant_url: str,
    tei_url: str,
) -> int:
    paths = list(paths)
    if not paths:
        return 0
    logger.info("watcher: reindexing %d files (sample: %s)", len(paths), paths[:3])
    stats = run_index(
        only_paths=set(paths),
        collection=collection,
        qdrant_url=qdrant_url,
        tei_url=tei_url,
    )
    return stats.get("embeddings_done", 0)


def _watch_loop(args: argparse.Namespace) -> None:
    client = QdrantClient(url=args.qdrant_url)
    logger.info(
        "watcher: started — collection=%s poll=%.1fs debounce=%.1fs",
        args.collection,
        args.poll_interval,
        args.debounce,
    )

    last_full_reload_ts = 0.0
    indexed: dict[str, float] = {}

    while not _stop_requested:
        # Refresh the indexed-mtime snapshot every ~5 minutes (cheap scroll).
        if time.time() - last_full_reload_ts > 300:
            indexed = _load_indexed_mtimes(client, args.collection)
            last_full_reload_ts = time.time()
            logger.info("watcher: loaded %d indexed paths", len(indexed))

        changed = _scan_changed(indexed, args.debounce)
        if changed:
            # Cap per-iteration to avoid huge stalls during bulk operations
            # (e.g. git checkout); the next iteration will catch the rest.
            batch = list(changed)[: args.max_files_per_batch]
            try:
                _reindex(
                    batch,
                    collection=args.collection,
                    qdrant_url=args.qdrant_url,
                    tei_url=args.tei_url,
                )
                # Update local snapshot so next iter doesn't re-trigger.
                now = time.time()
                for rel in batch:
                    indexed[rel] = now
            except Exception as e:
                logger.error("watcher: reindex error (will retry next tick): %s", e)

        time.sleep(args.poll_interval)

    logger.info("watcher: stopped")


def main() -> int:
    ap = argparse.ArgumentParser(description="Framework-search file watcher daemon")
    ap.add_argument("--collection", default=DEFAULT_COLLECTION)
    ap.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    ap.add_argument("--tei-url", default=DEFAULT_TEI_URL)
    ap.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SEC,
        help=f"Seconds between scans (default: {DEFAULT_POLL_INTERVAL_SEC})",
    )
    ap.add_argument(
        "--debounce",
        type=float,
        default=DEFAULT_DEBOUNCE_SEC,
        help=f"Skip files modified within last N seconds (default: {DEFAULT_DEBOUNCE_SEC})",
    )
    ap.add_argument(
        "--max-files-per-batch",
        type=int,
        default=DEFAULT_MAX_FILES_PER_BATCH,
        help=f"Cap per iteration (default: {DEFAULT_MAX_FILES_PER_BATCH})",
    )
    ap.add_argument("--quiet", "-q", action="store_true", help="WARNING level only")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        _watch_loop(args)
    except Exception as e:
        logger.exception("watcher: fatal error: %s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
