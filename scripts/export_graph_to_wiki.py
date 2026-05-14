"""CLI for wiki export pipeline (Hermes Phase 4).

Usage:
    python -m scripts.export_graph_to_wiki export-all [--output-dir PATH] [--batch-size N] [--dry-run]
    python -m scripts.export_graph_to_wiki export-entity ENTITY_ID [--dry-run]
    python -m scripts.export_graph_to_wiki sync-incremental
    python -m scripts.export_graph_to_wiki index-search [--wiki-dir PATH]
    python -m scripts.export_graph_to_wiki verify [--output-dir PATH]
    python -m scripts.export_graph_to_wiki promote-patterns [--min-confidence F] [--min-usage N] [--drafts-dir PATH]
    python -m scripts.export_graph_to_wiki decay-confidence [--min-confidence F] [--dry-run]
    python -m scripts.export_graph_to_wiki archive-stale [--max-age-days N] [--min-confidence F] [--dry-run]

Exit codes: 0 success, 1 partial failure, 2 total failure.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export GraphStore entities to wiki pages (Hermes Phase 4)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # export-all
    p_all = sub.add_parser("export-all", help="Export all entities to wiki")
    p_all.add_argument("--output-dir", type=Path, default=Path("docs/wiki/entities"))
    p_all.add_argument("--batch-size", type=int, default=50)
    p_all.add_argument("--dry-run", action="store_true")
    p_all.add_argument("--overwrite", action="store_true")
    p_all.add_argument("--verbose", "-v", action="store_true")

    # export-entity
    p_ent = sub.add_parser("export-entity", help="Export single entity")
    p_ent.add_argument("entity_id", help="Entity ID to export")
    p_ent.add_argument("--output-dir", type=Path, default=Path("docs/wiki/entities"))
    p_ent.add_argument("--dry-run", action="store_true")
    p_ent.add_argument("--verbose", "-v", action="store_true")

    # sync-incremental
    p_sync = sub.add_parser("sync-incremental", help="Start incremental sync daemon")
    p_sync.add_argument("--verbose", "-v", action="store_true")

    # index-search
    p_idx = sub.add_parser("index-search", help="Index wiki pages in HybridSearchService")
    p_idx.add_argument("--wiki-dir", type=Path, default=Path("docs/wiki/entities"))
    p_idx.add_argument("--verbose", "-v", action="store_true")

    # verify
    p_ver = sub.add_parser("verify", help="Verify wiki pages match graph state")
    p_ver.add_argument("--output-dir", type=Path, default=Path("docs/wiki/entities"))
    p_ver.add_argument("--verbose", "-v", action="store_true")

    # promote-patterns (L2 -> L5 drafts via WikiPromoter)
    p_prom = sub.add_parser(
        "promote-patterns",
        help="Scan learned_patterns (L2) and promote high-confidence ones to docs/wiki/drafts/ (L5)",
    )
    p_prom.add_argument("--min-confidence", type=float, default=0.8,
                        help="Minimum confidence for promotion (default 0.8, per spec)")
    p_prom.add_argument("--min-usage", type=int, default=5,
                        help="Minimum usage_count for promotion (default 5, per spec)")
    p_prom.add_argument("--similarity-threshold", type=float, default=0.85,
                        help="Dedup threshold against existing wiki content (default 0.85)")
    p_prom.add_argument("--drafts-dir", type=Path, default=Path("docs/wiki/drafts"))
    p_prom.add_argument("--qdrant-url", type=str, default="http://localhost:6333")
    p_prom.add_argument("--qdrant-api-key", type=str, default=None,
                        help="Qdrant API key (default: $QDRANT__API_KEY env var)")
    p_prom.add_argument("--verbose", "-v", action="store_true")

    return parser.parse_args()


async def _get_graph_store():
    from src.pdf_framework.graph_store import get_graph_store
    store = get_graph_store()
    await store.initialize()
    return store


async def cmd_export_all(args: argparse.Namespace) -> int:
    from src.pdf_framework.indexing.wiki_exporter import WikiExportConfig, WikiExporter

    store = await _get_graph_store()
    config = WikiExportConfig(
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        overwrite_existing=args.overwrite,
    )
    exporter = WikiExporter(store, config)
    result = await exporter.export_all()

    print(result.summary())
    if result.errors:
        print(f"\nErrors ({len(result.errors)}):")
        for err in result.errors[:10]:
            print(f"  - {err.get('entity_id', '?')}: {err.get('reason', '?')}")

    if result.failed_pages == result.total_entities and result.total_entities > 0:
        return 2
    if result.failed_pages > 0:
        return 1
    return 0


async def cmd_export_entity(args: argparse.Namespace) -> int:
    from src.pdf_framework.indexing.wiki_exporter import WikiExportConfig, WikiExporter

    store = await _get_graph_store()
    config = WikiExportConfig(
        output_dir=args.output_dir,
        dry_run=args.dry_run,
    )
    exporter = WikiExporter(store, config)
    path = await exporter.export_entity(args.entity_id)

    if path:
        print(f"Exported: {path}")
        return 0
    print(f"Entity not found or skipped: {args.entity_id}")
    return 1


async def cmd_sync_incremental(args: argparse.Namespace) -> int:
    from src.pdf_framework.indexing.wiki_exporter import (
        ForwardSyncService,
        IncrementalWikiSync,
        WikiExporter,
    )

    store = await _get_graph_store()
    exporter = WikiExporter(store)
    forward_sync = ForwardSyncService(store, exporter)
    inc_sync = IncrementalWikiSync(forward_sync, exporter)

    await inc_sync.start()
    print("Incremental sync started. Press Ctrl+C to stop.")
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await inc_sync.stop()
    return 0


async def cmd_index_search(args: argparse.Namespace) -> int:
    from src.memory.orchestrator.search.hybrid_search import HybridSearchService
    from src.pdf_framework.indexing.wiki_exporter import WikiSearchIndexer

    hs = HybridSearchService()
    indexer = WikiSearchIndexer(hs, wiki_dir=args.wiki_dir)
    count = await indexer.index_all_pages()
    print(f"Indexed {count} wiki pages")
    return 0 if count > 0 else 1


async def cmd_verify(args: argparse.Namespace) -> int:
    from src.pdf_framework.indexing.wiki_exporter import WikiExporter

    store = await _get_graph_store()
    graph = getattr(store, "_graph", None)

    if graph is None:
        print("ERROR: Graph store unavailable")
        return 2

    output_dir = args.output_dir
    inconsistencies = 0

    # Check 1: Every entity → has wiki page
    entity_ids = [
        nid for nid, data in graph.nodes(data=True)
        if data.get("node_type") != "COMMUNITY" and data.get("name")
    ]

    for eid in entity_ids:
        data = graph.nodes[eid]
        name = data.get("name", eid)
        fname = WikiExporter._sanitize_filename(name)
        wp = output_dir / f"{fname}.md"
        if not wp.exists():
            print(f"  MISSING wiki: {name} → {wp}")
            inconsistencies += 1

    # Check 2: Every wiki page → has entity in graph
    if output_dir.exists():
        graph_names = {WikiExporter._sanitize_filename(data.get("name", nid)) for nid, data in graph.nodes(data=True)}
        for wp in output_dir.glob("*.md"):
            if wp.stem not in graph_names:
                print(f"  ORPHAN wiki: {wp.name} (no entity in graph)")
                inconsistencies += 1

    if inconsistencies == 0:
        print(f"OK: {len(entity_ids)} entities verified, no inconsistencies")
        return 0
    print(f"FOUND {inconsistencies} inconsistencies")
    return 1


async def cmd_promote_patterns(args: argparse.Namespace) -> int:
    import os

    from qdrant_client import QdrantClient

    from src.memory.librarian.wiki_promoter import WikiPromoter

    api_key = args.qdrant_api_key or os.environ.get("QDRANT__API_KEY")
    client = QdrantClient(url=args.qdrant_url, api_key=api_key)
    promoter = WikiPromoter(
        qdrant_client=client,
        wiki_drafts_dir=args.drafts_dir,
        confidence_threshold=args.min_confidence,
        usage_threshold=args.min_usage,
        similarity_threshold=args.similarity_threshold,
    )
    created = await promoter.scan_and_promote()
    if created:
        print(f"Promoted {len(created)} pattern(s) to drafts:")
        for slug in created:
            print(f"  - {args.drafts_dir / (slug + '.md')}")
        return 0
    print(
        f"No patterns met thresholds (confidence>={args.min_confidence}, "
        f"usage_count>={args.min_usage}). Drafts dir unchanged.",
        file=sys.stderr,
    )
    return 0


async def main() -> int:
    args = parse_args()

    if getattr(args, "verbose", False):
        logging.getLogger().setLevel(logging.DEBUG)

    commands = {
        "export-all": cmd_export_all,
        "export-entity": cmd_export_entity,
        "sync-incremental": cmd_sync_incremental,
        "index-search": cmd_index_search,
        "verify": cmd_verify,
        "promote-patterns": cmd_promote_patterns,
    }

    handler = commands.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}")
        return 2

    return await handler(args)


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
