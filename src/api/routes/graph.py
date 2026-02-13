"""Graph API endpoints for knowledge graph access.

Provides REST API for graph statistics, entity browsing, search,
and community detection (Leiden + LLM summarization).
"""

import logging

from fastapi import APIRouter, HTTPException

from src.api.dependencies.components import get_components

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/stats")
async def graph_stats():
    """Get knowledge graph statistics."""
    components = await get_components()
    stats = await components.graph_store.get_statistics()
    return stats


@router.get("/entities")
async def list_entities(
    name: str | None = None,
    entity_type: str | None = None,
    limit: int = 50,
):
    """Search or list entities in the knowledge graph."""
    components = await get_components()
    entities = await components.graph_store.find_entities(
        name=name,
        entity_type=entity_type,
        limit=limit,
    )
    return {
        "entities": [
            {
                "id": e.id,
                "name": e.name,
                "type": e.entity_type,
                "properties": e.properties,
                "source_document_id": e.source_document_id,
            }
            for e in entities
        ],
        "count": len(entities),
    }


@router.delete("/clear")
async def clear_graph():
    """Clear all entities and relations from the knowledge graph."""
    components = await get_components()
    stats_before = await components.graph_store.get_statistics()
    await components.graph_store.clear()
    return {
        "status": "ok",
        "deleted_nodes": stats_before.get("node_count", 0),
        "deleted_edges": stats_before.get("edge_count", 0),
    }


@router.post("/build-communities")
async def build_communities():
    """Run Leiden community detection + LLM summarization on the knowledge graph.

    This enables GraphRAG Global search by:
    1. Detecting communities via Leiden algorithm (graspologic)
    2. Generating LLM summaries for each community
    3. Creating COMMUNITY nodes in the graph (with summary attribute)
    4. Persisting updated graph to disk

    Requires: graspologic package (pip install graspologic)
    """
    components = await get_components()
    graph = getattr(components.graph_store, "_graph", None)
    if graph is None:
        raise HTTPException(
            status_code=501,
            detail="Graph store does not expose internal graph (only NetworkX backend supported)",
        )

    if graph.number_of_nodes() == 0:
        raise HTTPException(status_code=400, detail="Graph is empty — index documents first")

    # Step 0: Remove old COMMUNITY nodes (if re-running)
    old_community_nodes = [
        nid for nid, data in graph.nodes(data=True)
        if data.get("node_type") == "COMMUNITY"
    ]
    for nid in old_community_nodes:
        graph.remove_node(nid)
    logger.info("[COMMUNITIES] Removed %d old COMMUNITY nodes", len(old_community_nodes))

    # Step 1: Leiden community detection
    try:
        from src.pdf_framework.graph_store.community import CommunityDetector

        detector = CommunityDetector(settings=components.settings.graph_rag)
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="graspologic not installed. Run: pip install graspologic",
        )

    communities = await detector.detect(graph)
    await detector.apply_to_graph(graph, communities, level=0)
    stats = detector.get_community_stats(graph, communities)

    logger.info(
        "[COMMUNITIES] Leiden detected %d communities from %d entities",
        stats["num_communities"], stats["num_entities"],
    )

    # Step 2: LLM summarization for each community
    from src.pdf_framework.graph_store.summarizer import CommunitySummarizer

    summarizer = CommunitySummarizer(
        api_key=components.settings.anthropic_api_key,
        base_url=components.settings.agent.base_url,
        settings=components.settings.graph_rag,
    )
    summaries = await summarizer.summarize_all(graph, communities, level=0)

    logger.info("[COMMUNITIES] Generated %d community summaries", len(summaries))

    # Step 3: Create COMMUNITY nodes in the graph (for GraphRAG Global)
    for comm_id, summary in summaries.items():
        node_id = f"community_{comm_id}_L0"
        graph.add_node(
            node_id,
            node_type="COMMUNITY",
            community_id=comm_id,
            level=0,
            summary=summary,
            name=f"Community {comm_id}",
        )

    # Step 4: Save graph to disk
    components.graph_store._save_to_file()

    logger.info(
        "[COMMUNITIES] Done: %d communities, %d summaries, graph saved",
        stats["num_communities"], len(summaries),
    )

    return {
        "status": "ok",
        "communities_detected": stats["num_communities"],
        "entities_assigned": stats["num_entities"],
        "summaries_generated": len(summaries),
        "avg_community_size": round(stats["avg_community_size"], 1),
        "max_community_size": stats["max_community_size"],
        "old_community_nodes_removed": len(old_community_nodes),
    }


@router.post("/build-entity-embeddings")
async def build_entity_embeddings():
    """Build entity and relation embeddings for LightRAG (Phase 38).

    Creates vector embeddings for all graph entities and relations,
    stored in a separate Qdrant collection for fast retrieval.
    This enables LightRAG search (~100 tokens/query vs ~5000 for Full GraphRAG).

    Prerequisite: documents must be indexed and graph must be built.
    """
    components = await get_components()

    if components.entity_embeddings is None:
        raise HTTPException(
            status_code=501,
            detail="LightRAG is disabled. Set LIGHTRAG__ENABLED=true in .env",
        )

    graph = getattr(components.graph_store, "_graph", None)
    if graph is None:
        raise HTTPException(
            status_code=501,
            detail="Graph store does not expose internal graph (only NetworkX backend supported)",
        )

    if graph.number_of_nodes() == 0:
        raise HTTPException(
            status_code=400,
            detail="Graph is empty — index documents first",
        )

    try:
        stats = await components.entity_embeddings.build(components.graph_store)
        return {
            "status": "ok",
            **stats,
        }
    except Exception as e:
        logger.error("[LIGHTRAG] Build entity embeddings failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity-embeddings/stats")
async def entity_embeddings_stats():
    """Get stats for the entity/relation embeddings collection."""
    components = await get_components()

    if components.entity_embeddings is None:
        return {"enabled": False}

    stats = await components.entity_embeddings.get_stats()
    return {"enabled": True, **stats}


@router.get("/neighbors/{entity_id}")
async def get_neighbors(entity_id: str, depth: int = 1):
    """Get neighboring entities for a given entity."""
    components = await get_components()
    subgraph = await components.graph_store.get_neighbors(entity_id, depth=depth)
    return {
        "entities": [
            {"id": e.id, "name": e.name, "type": e.entity_type}
            for e in subgraph.entities
        ],
        "relations": [
            {
                "source": r.source_entity_id,
                "target": r.target_entity_id,
                "type": r.relation_type,
            }
            for r in subgraph.relations
        ],
    }
