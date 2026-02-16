"""Embedding Migration Script (Phase 47).

Re-embeds all chunks with a new embedding model/provider, recreates
Qdrant collection if dimensions differ, and rebuilds auxiliary indices.

Usage:
    # Migrate to Jina v3
    python scripts/migrate_embeddings.py --provider jina --jina-key jina_xxxxx

    # Migrate with Matryoshka truncation (smaller dims)
    python scripts/migrate_embeddings.py --provider jina --jina-key jina_xxxxx --jina-truncate-dim 512

    # Dry run (show plan without executing)
    python scripts/migrate_embeddings.py --provider jina --jina-key jina_xxxxx --dry-run

    # Skip graph embeddings rebuild
    python scripts/migrate_embeddings.py --provider jina --jina-key jina_xxxxx --skip-graph
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Embedding Migration (Phase 47)")
    parser.add_argument("--provider", required=True, help="Target embedding provider (local/jina/giga)")
    parser.add_argument("--model", default=None, help="Model name override")
    parser.add_argument("--jina-key", default="", help="Jina API key")
    parser.add_argument("--jina-truncate-dim", type=int, default=None, help="Jina Matryoshka dim")
    parser.add_argument("--batch-size", type=int, default=256, help="Embedding batch size")
    parser.add_argument("--skip-graph", action="store_true", help="Skip graph entity embeddings rebuild")
    parser.add_argument("--skip-bm25-sparse", action="store_true", help="Skip BM25 sparse vectors rebuild")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without executing")
    args = parser.parse_args()

    from src.pdf_framework.config import EmbeddingSettings, get_settings
    from src.pdf_framework.embeddings import get_embedding_engine

    # Build new embedding settings
    settings_kwargs: dict = {"provider": args.provider, "batch_size": args.batch_size}
    if args.model:
        settings_kwargs["model"] = args.model
    if args.provider == "jina":
        if not args.jina_key:
            logger.error("--jina-key is required for Jina provider")
            sys.exit(1)
        settings_kwargs["jina_api_key"] = args.jina_key
        settings_kwargs["model"] = args.model or "jina-embeddings-v3"
        if args.jina_truncate_dim:
            settings_kwargs["jina_truncate_dim"] = args.jina_truncate_dim

    new_settings = EmbeddingSettings(**settings_kwargs)
    new_engine = get_embedding_engine(new_settings)
    new_dims = new_engine.get_dimensions()

    # Get current settings for comparison
    current_settings = get_settings()
    current_dims = current_settings.embedding.dimensions

    logger.info("=== Migration Plan ===")
    logger.info("From: %s (%s, %dd)", current_settings.embedding.provider,
                current_settings.embedding.model, current_dims)
    logger.info("To:   %s (%s, %dd)", args.provider,
                new_engine.get_model_name(), new_dims)
    logger.info("Batch size: %d", args.batch_size)

    dims_changed = new_dims != current_dims
    if dims_changed:
        logger.info("Dimensions changed: %d → %d (collection WILL be recreated)", current_dims, new_dims)
    else:
        logger.info("Dimensions unchanged: %d (in-place update)", current_dims)

    steps = ["1. Read all chunks from Qdrant"]
    if dims_changed:
        steps.append("2. Recreate Qdrant collection with new dimensions")
    steps.append(f"{'2' if not dims_changed else '3'}. Re-embed all chunks with {args.provider}")
    steps.append(f"{'3' if not dims_changed else '4'}. Upsert new embeddings to Qdrant")
    if not args.skip_bm25_sparse:
        steps.append("*. Rebuild BM25 sparse vectors")
    if not args.skip_graph:
        steps.append("*. Rebuild graph entity embeddings")

    for step in steps:
        logger.info("  %s", step)

    if args.dry_run:
        logger.info("=== DRY RUN — no changes made ===")
        if hasattr(new_engine, "close"):
            await new_engine.close()
        return

    # --- Execute migration ---
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import (
        Distance,
        PointStruct,
        SparseVectorParams,
        VectorParams,
        models as qmodels,
    )

    qdrant_settings = current_settings.vector_store
    client = AsyncQdrantClient(
        host=qdrant_settings.qdrant_host,
        port=qdrant_settings.qdrant_port,
    )
    collection_name = qdrant_settings.qdrant_collection

    # Step 1: Read all chunks
    logger.info("[Step 1] Reading all chunks from Qdrant...")
    all_points = []
    offset = None
    while True:
        scroll_kwargs = {
            "collection_name": collection_name,
            "limit": 256,
            "with_payload": True,
            "with_vectors": False,  # Don't need old vectors
        }
        if offset is not None:
            scroll_kwargs["offset"] = offset
        points, next_offset = await client.scroll(**scroll_kwargs)
        all_points.extend(points)
        if next_offset is None:
            break
        offset = next_offset

    logger.info("  Found %d points", len(all_points))
    if not all_points:
        logger.warning("No points found in collection. Nothing to migrate.")
        return

    # Step 2: Recreate collection if dims changed
    if dims_changed:
        logger.info("[Step 2] Recreating collection with %dd vectors...", new_dims)
        await client.delete_collection(collection_name)

        vectors_config = {"dense": VectorParams(size=new_dims, distance=Distance.COSINE)}
        sparse_config = None
        if qdrant_settings.qdrant_bm25_enabled:
            sparse_config = {"bm25": SparseVectorParams(modifier=qmodels.Modifier.IDF)}

        create_kwargs = {
            "collection_name": collection_name,
            "vectors_config": vectors_config,
        }
        if sparse_config:
            create_kwargs["sparse_vectors_config"] = sparse_config
        await client.create_collection(**create_kwargs)
        logger.info("  Collection recreated")

    # Step 3: Re-embed all chunks
    logger.info("[Step 3] Re-embedding %d chunks with %s...", len(all_points), args.provider)
    texts = []
    for p in all_points:
        payload = p.payload or {}
        # Use contextual_content if available, else original content
        text = payload.get("contextual_content") or payload.get("content", "")
        texts.append(text)

    t0 = time.perf_counter()
    new_embeddings = await new_engine.embed_batch(texts)
    embed_time = time.perf_counter() - t0
    logger.info("  Embedded in %.1fs (%.0f texts/sec)",
                embed_time, len(texts) / embed_time if embed_time > 0 else 0)

    # Step 4: Upsert with new embeddings
    logger.info("[Step 4] Upserting %d points to Qdrant...", len(all_points))
    batch_size = 256
    for i in range(0, len(all_points), batch_size):
        batch_points = all_points[i:i + batch_size]
        batch_embeddings = new_embeddings[i:i + batch_size]

        points_to_upsert = []
        for point, embedding in zip(batch_points, batch_embeddings):
            points_to_upsert.append(PointStruct(
                id=point.id,
                vector={"dense": embedding},
                payload=point.payload,
            ))

        await client.upsert(
            collection_name=collection_name,
            points=points_to_upsert,
        )
        logger.info("  Upserted batch %d/%d", i + batch_size, len(all_points))

    # Step 5: Rebuild BM25 sparse vectors
    if not args.skip_bm25_sparse and qdrant_settings.qdrant_bm25_enabled:
        logger.info("[Step 5] Rebuilding BM25 sparse vectors...")
        from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore

        store = QdrantVectorStore(current_settings.vector_store, current_settings.embedding)
        await store.initialize()
        stats = await store.rebuild_sparse_vectors(batch_size=batch_size)
        logger.info("  BM25 sparse: %s", stats)

    # Step 6: Rebuild graph entity embeddings
    if not args.skip_graph:
        logger.info("[Step 6] Rebuilding graph entity embeddings...")
        try:
            from src.pdf_framework.graph_store.entity_embeddings import EntityEmbeddingBuilder
            from src.pdf_framework.graph_store.providers.networkx import NetworkXGraphStore

            graph_store = NetworkXGraphStore(current_settings.graphrag)
            builder = EntityEmbeddingBuilder(
                embedding_engine=new_engine,
                settings=current_settings.lightrag,
            )
            stats = await builder.build(graph_store)
            logger.info("  Graph embeddings: %s", stats)
        except Exception as e:
            logger.warning("  Graph embeddings rebuild failed: %s", e)
            logger.info("  You can rebuild manually: POST /graph/build-entity-embeddings")

    # Cleanup
    if hasattr(new_engine, "close"):
        await new_engine.close()
    await client.close()

    total_time = time.perf_counter() - t0
    logger.info("=== Migration complete in %.1fs ===", total_time)
    logger.info("Update .env: EMBEDDING__PROVIDER=%s", args.provider)
    if args.provider == "jina":
        logger.info("Update .env: EMBEDDING__JINA_API_KEY=%s", args.jina_key[:10] + "...")
        if args.jina_truncate_dim:
            logger.info("Update .env: EMBEDDING__JINA_TRUNCATE_DIM=%d", args.jina_truncate_dim)
    if dims_changed:
        logger.info("Update .env: EMBEDDING__DIMENSIONS=%d", new_dims)


if __name__ == "__main__":
    asyncio.run(main())
