"""Rebuild knowledge graph from Qdrant chunks.

Reads all text chunks from Qdrant, clears the old graph, and rebuilds
using LLM entity extraction (Claude Sonnet via Z.AI).

Phase 29: Uses batch_mode on NetworkX store to avoid per-entity file writes.

Usage:
    python rebuild_graph.py              # rebuild (keeps old graph as backup)
    python rebuild_graph.py --clear      # clear old graph first
    python rebuild_graph.py --concurrency 10  # parallel entity extraction
"""

import sys
import io
import asyncio
import shutil
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

sys.path.insert(0, str(Path(__file__).parent))

from src.pdf_framework.config import get_settings
from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore
from src.pdf_framework.schemas.documents import DocumentChunk
from src.pdf_framework.vector_store import get_vector_store


async def read_text_chunks() -> list[DocumentChunk]:
    """Read all text chunks from Qdrant (skip image chunks)."""
    settings = get_settings()
    store = get_vector_store(settings.vector_store)
    await store.initialize()

    total = await store.count()
    print(f"Qdrant collection: {total} points")

    if total == 0:
        return []

    all_chunks = await store.scroll(limit=total + 100)

    # Filter: only text chunks (skip images)
    text_chunks = [
        c for c in all_chunks
        if c.metadata.get("chunk_type") != "image"
    ]
    print(f"Text chunks: {len(text_chunks)} (skipped {len(all_chunks) - len(text_chunks)} image chunks)")
    return text_chunks


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Rebuild knowledge graph from Qdrant")
    parser.add_argument("--clear", action="store_true", help="Clear old graph before rebuild")
    parser.add_argument("--concurrency", type=int, default=5, help="Parallel entity extraction tasks")
    args = parser.parse_args()

    settings = get_settings()

    # Initialize graph store
    graph_store = NetworkXGraphStore(settings.graph_store)
    await graph_store.initialize()

    old_stats = await graph_store.get_statistics()
    print(f"Old graph: {old_stats['node_count']} entities, {old_stats['edge_count']} edges")

    # Backup old graph
    persist_path = Path(settings.graph_store.persist_dir) / "graph.json"
    if persist_path.exists():
        backup_path = persist_path.with_suffix(".json.bak")
        shutil.copy2(persist_path, backup_path)
        print(f"Backup saved: {backup_path}")

    if args.clear:
        await graph_store.clear()
        print("Old graph cleared")

    # Read chunks from Qdrant
    print("\n=== Reading chunks from Qdrant ===")
    chunks = await read_text_chunks()

    if not chunks:
        print("No text chunks found. Cannot build graph.")
        return

    # Enable batch mode for faster writes
    graph_store.set_batch_mode(True)

    # Build graph using entity extractor
    print(f"\n=== Building graph (concurrency={args.concurrency}) ===")

    from src.pdf_framework.graph_store.construction.builder import GraphBuilder
    from src.pdf_framework.processing.extractors.entity_extractor import LLMEntityExtractor

    extractor = LLMEntityExtractor(
        settings=settings.agent,
        api_key=settings.anthropic_api_key,
    )
    builder = GraphBuilder(
        extractor, graph_store,
        concurrency=args.concurrency,
    )

    t0 = time.time()
    result = await builder.build_from_chunks(chunks)
    elapsed = time.time() - t0

    # Flush batch writes to file
    graph_store.flush()
    graph_store.set_batch_mode(False)

    # Final stats
    new_stats = await graph_store.get_statistics()

    print(f"\n=== Graph Rebuild Complete ===")
    print(f"Entities:   {old_stats['node_count']} → {new_stats['node_count']}")
    print(f"Edges:      {old_stats['edge_count']} → {new_stats['edge_count']}")
    print(f"Components: {new_stats['connected_components']}")
    print(f"Density:    {new_stats['density']:.6f}")
    print(f"Elapsed:    {elapsed:.1f}s ({len(chunks)} chunks, {len(chunks)/elapsed:.1f} chunks/s)")
    print(f"Result:     {result}")


if __name__ == "__main__":
    asyncio.run(main())
