"""
Memory Orchestrator MCP Server — Unified Memory Coordination.

Full MCP server (stdio) that ties together 3 memory subsystems:
- memory-ai (episodic facts, important messages)
- vector-memory (patterns, code conventions, semantic knowledge)
- skill-learning (captured skills, workflow patterns)

Provides 8 MCP tools:
- unified_search: Federated search across all subsystems
- route_and_save: Auto-classify and route content to targets
- get_full_context: Entity + BFS graph traversal
- create_link: Cross-reference between entities
- get_related: Find related entities via BFS
- propagate_update: Trigger confidence propagation (stub for P1)
- get_system_stats: Aggregate statistics from all subsystems
- health_check: Check subsystem availability

Migrated from D:\\1C-Enterprise_Framework\\memory-orchestrator\\src\\memory_orchestrator.py
Adapted: Direct function calls instead of HTTP, 3 target servers, MCP server.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp import stdio_server
from mcp.server import Server
from mcp.types import TextContent, Tool

from .link_registry import LinkRegistry, LinkType
from .memory_router import (
    MemoryRouter,
    RouterConfig,
    RoutingDecision,
)
from .propagation_engine import PropagationConfig, PropagationEngine, PropagationResult
from .unified_id import MemoryType, SourceServer, UnifiedID
from .unified_search import (
    BaseSearchAdapter,
    SearchResultItem,
    SearchOptions,
    UnifiedSearchEngine,
    UnifiedSearchResult,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("memory-orchestrator")

# Project root for data paths
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class OrchestratorConfig:
    """Configuration for MemoryOrchestrator."""

    link_registry_path: str | None = None
    enable_auto_routing: bool = True
    enable_health_monitoring: bool = True
    enable_link_creation: bool = True
    search_timeout: float = 5.0
    health_check_interval: float = 60.0
    router_config: RouterConfig = field(default_factory=RouterConfig)
    search_options: SearchOptions = field(default_factory=SearchOptions)


# =============================================================================
# Error Hierarchy
# =============================================================================


class OrchestratorError(Exception):
    """Base exception for orchestrator operations."""


class EntityNotFoundError(OrchestratorError):
    """Entity not found in any subsystem."""


class InvalidLinkError(OrchestratorError):
    """Invalid link operation (self-link, duplicate, etc.)."""


class SubsystemUnavailableError(OrchestratorError):
    """One or more subsystems are unavailable."""


# =============================================================================
# Subsystem Adapters
# =============================================================================


class AiMemorySearchAdapter(BaseSearchAdapter):
    """Search adapter for memory-ai subsystem (SQLite)."""

    def __init__(self, db_path: Path):
        self._db_path = db_path

    def source_name(self) -> str:
        return "memory-ai"

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        import sqlite3

        results = []

        def _do_search():
            conn = sqlite3.connect(str(self._db_path))
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, content, importance, category, tags, created_at "
                    "FROM important_messages "
                    "WHERE content LIKE ? OR tags LIKE ? "
                    "ORDER BY importance DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                )
                for row in cursor.fetchall():
                    results.append(SearchResultItem(
                        unified_id=f"episodic:memory-ai:{row[0]}",
                        source=SourceServer.MEMORY_AI,
                        memory_type=MemoryType.EPISODIC,
                        content=row[1],
                        raw_score=min(row[2], 1.0),
                        created_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        tags=json.loads(row[4]) if row[4] else [],
                    ))
            finally:
                conn.close()

        await asyncio.to_thread(_do_search)
        return results


class VectorMemorySearchAdapter(BaseSearchAdapter):
    """Search adapter for vector-memory subsystem (Qdrant)."""

    def source_name(self) -> str:
        return "vector-memory"

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        min_confidence = kwargs.get("min_confidence", 0.3)
        results = []

        try:
            from ..vector_memory.server import _get_qdrant, _get_embedding, _pattern_from_payload

            client = await asyncio.to_thread(_get_qdrant)
            vector = await _get_embedding(query)

            from qdrant_client.http import models as qmodels

            conditions = [
                qmodels.FieldCondition(key="confidence", range=qmodels.Range(gte=min_confidence))
            ]
            qresults = client.query_points(
                collection_name="learned_patterns",
                query=vector,
                query_filter=qmodels.Filter(must=conditions),
                limit=limit,
                with_payload=True,
            )

            for point in qresults.points:
                payload = point.payload or {}
                pattern = _pattern_from_payload(str(point.id), payload)
                similarity = point.score or 0.0
                results.append(SearchResultItem(
                    unified_id=f"semantic:vector-memory:{pattern.pattern_id}",
                    source=SourceServer.VECTOR_MEMORY,
                    memory_type=MemoryType.SEMANTIC,
                    content=pattern.content,
                    title=pattern.name,
                    raw_score=similarity * pattern.confidence,
                    created_at=pattern.created_at,
                    tags=pattern.tags,
                    metadata={"pattern_type": pattern.pattern_type.value, "confidence": pattern.confidence},
                ))
        except Exception as e:
            logger.warning(f"Vector memory search failed: {e}")

        return results


class SkillLearningSearchAdapter(BaseSearchAdapter):
    """Search adapter for skill-learning subsystem (JSONL files)."""

    def __init__(self, storage_dir: Path):
        self._storage_dir = storage_dir
        self._patterns_file = storage_dir / "patterns.jsonl"

    def source_name(self) -> str:
        return "skill-learning"

    async def search(self, query: str, limit: int = 10, **kwargs) -> list[SearchResultItem]:
        if not self._patterns_file.exists():
            return []

        query_lower = query.lower()
        results: list[SearchResultItem] = []

        def _search():
            items = []
            with open(self._patterns_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            scored = []
            for item in items:
                text = f"{item.get('name', '')} {item.get('content', '')} {item.get('description', '')}".lower()
                # Simple keyword overlap scoring
                query_words = set(query_lower.split())
                content_words = set(text.split())
                overlap = len(query_words & content_words)
                if overlap > 0:
                    score = overlap / max(len(query_words), 1)
                    scored.append((item, score))

            scored.sort(key=lambda x: x[1], reverse=True)
            for item, score in scored[:limit]:
                results.append(SearchResultItem(
                    unified_id=f"learning:skill-learning:{item.get('pattern_id', '')}",
                    source=SourceServer.SKILL_LEARNING,
                    memory_type=MemoryType.LEARNING,
                    content=item.get("content", ""),
                    title=item.get("name", ""),
                    raw_score=score,
                    created_at=datetime.fromisoformat(item["created_at"]) if item.get("created_at") else None,
                    tags=item.get("tags", []),
                ))

        await asyncio.to_thread(_search)
        return results


# =============================================================================
# MemoryOrchestrator
# =============================================================================


class MemoryOrchestrator:
    """Orchestrates unified memory operations across all subsystems."""

    def __init__(self, config: OrchestratorConfig | None = None):
        self.config = config or OrchestratorConfig()
        self._link_registry: LinkRegistry | None = None
        self._router: MemoryRouter | None = None
        self._search_engine: UnifiedSearchEngine | None = None
        self._propagation_engine: PropagationEngine | None = None
        self._request_counts: dict[str, int] = {}

    async def start(self):
        """Initialize all orchestrator components."""
        # Link Registry
        db_path = self.config.link_registry_path
        if db_path is None:
            data_dir = _PROJECT_ROOT / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "link_registry.db")
        self._link_registry = LinkRegistry(db_path=db_path)

        # Router
        self._router = MemoryRouter(self.config.router_config)

        # Search Engine with adapters
        self._search_engine = UnifiedSearchEngine(self._link_registry)
        self._search_engine.register_adapter(AiMemorySearchAdapter(
            _PROJECT_ROOT / "data" / "memory_ai.db"
        ))
        self._search_engine.register_adapter(VectorMemorySearchAdapter())
        self._search_engine.register_adapter(SkillLearningSearchAdapter(
            _PROJECT_ROOT / "data" / "skill_learning"
        ))

        logger.info("MemoryOrchestrator started")

    async def stop(self):
        """Tear down orchestrator."""
        if self._propagation_engine:
            await self._propagation_engine.stop()
            self._propagation_engine = None
        self._link_registry = None
        self._router = None
        self._search_engine = None
        logger.info("MemoryOrchestrator stopped")

    # ----- Tool implementations -----

    async def unified_search(
        self,
        query: str,
        include: list[str] | None = None,
        exclude: list[str] | None = None,
        min_score: float = 0.3,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Federated search across all memory subsystems."""
        self._track("unified_search")
        if not self._search_engine:
            raise SubsystemUnavailableError("Search engine not initialized")

        sources = None
        if include:
            sources = [SourceServer(s) for s in include]
        if exclude:
            exclude_set = {SourceServer(s) for s in exclude}
            sources = [s for s in (sources or list(SourceServer)) if s not in exclude_set]

        result: UnifiedSearchResult = await self._search_engine.search(
            query=query,
            sources=sources,
            min_score=min_score,
            limit=limit,
            include_links=True,
            options=self.config.search_options,
        )
        return result.to_dict()

    async def route_and_save(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        auto_propagate: bool = False,
    ) -> dict[str, Any]:
        """Auto-route content to appropriate subsystems and save."""
        self._track("route_and_save")
        if not self._router:
            raise SubsystemUnavailableError("Router not initialized")

        # Route
        decision: RoutingDecision = await self._router.route(content, metadata)

        # Save to each target
        saved_entities = []
        for target in decision.targets:
            entity_id = await self._save_to_target(target, content, metadata)
            if entity_id:
                saved_entities.append({"target": target, "entity_id": entity_id})

        # Create cross-links between saved entities
        if self.config.enable_link_creation and len(saved_entities) > 1:
            for i in range(len(saved_entities) - 1):
                try:
                    self._link_registry.create_link(
                        source_id=saved_entities[i]["entity_id"],
                        target_id=saved_entities[i + 1]["entity_id"],
                        link_type=LinkType.SESSION_CONTEXT,
                        strength=0.7,
                    )
                except Exception as e:
                    logger.warning(f"Failed to create cross-link: {e}")

        return {
            "success": True,
            "routing": decision.to_dict(),
            "saved_entities": saved_entities,
            "cross_links_created": max(0, len(saved_entities) - 1),
        }

    async def get_full_context(
        self,
        entity_id: str,
        include_related: bool = True,
        max_depth: int = 2,
        max_entities: int = 20,
    ) -> dict[str, Any]:
        """Get entity with BFS graph traversal for full context."""
        self._track("get_full_context")
        if not self._link_registry:
            raise SubsystemUnavailableError("Link registry not initialized")

        # Get entity from subsystems
        entity = await self._get_entity(entity_id)
        if not entity:
            raise EntityNotFoundError(f"Entity not found: {entity_id}")

        result: dict[str, Any] = {
            "entity": entity,
            "related_entities": [],
            "links": [],
        }

        if include_related:
            related = self._link_registry.get_related_entities(
                entity_id, max_depth=max_depth
            )
            result["links"] = [
                {
                    "entity_id": r.entity_id,
                    "depth": r.depth,
                    "strength": r.effective_strength,
                    "path": r.link_path,
                }
                for r in related[:max_entities]
            ]

        return result

    async def create_link(
        self,
        source_id: str,
        target_id: str,
        link_type: str = "supports",
        strength: float = 0.8,
        bidirectional: bool = False,
    ) -> dict[str, Any]:
        """Create a cross-reference link between entities."""
        self._track("create_link")
        if not self._link_registry:
            raise SubsystemUnavailableError("Link registry not initialized")

        try:
            lt = LinkType.from_string(link_type)
        except ValueError:
            raise InvalidLinkError(f"Unknown link type: {link_type}")

        link = self._link_registry.create_link(
            source_id=source_id,
            target_id=target_id,
            link_type=lt,
            strength=strength,
            bidirectional=bidirectional,
        )
        return {"success": True, "link": link.to_dict()}

    async def get_related(
        self,
        entity_id: str,
        link_types: list[str] | None = None,
        direction: str = "both",
        max_depth: int = 2,
        min_strength: float = 0.5,
    ) -> dict[str, Any]:
        """Find related entities via BFS graph traversal."""
        self._track("get_related")
        if not self._link_registry:
            raise SubsystemUnavailableError("Link registry not initialized")

        types = None
        if link_types:
            types = [LinkType.from_string(lt) for lt in link_types]

        related = self._link_registry.get_related_entities(
            entity_id,
            link_types=types,
            min_strength=min_strength,
            max_depth=max_depth,
            direction=direction,
        )
        return {
            "entity_id": entity_id,
            "related_count": len(related),
            "related": [r.to_dict() for r in related],
        }

    async def propagate_update(
        self,
        entity_id: str,
        delta: float = 0.1,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Propagate confidence update through entity graph."""
        self._track("propagate_update")
        if not self._link_registry:
            raise SubsystemUnavailableError("Link registry not initialized")

        # Lazy-init propagation engine
        if self._propagation_engine is None:
            self._propagation_engine = PropagationEngine(self._link_registry)
            await self._propagation_engine.start()

        result: PropagationResult = await self._propagation_engine.propagate(
            entity_id=entity_id,
            base_delta=delta,
            success=success,
            metadata=metadata,
        )
        return {
            "success": True,
            "result": result.to_dict(),
        }

    async def get_system_stats(self, include_subsystems: bool = True) -> dict[str, Any]:
        """Get aggregate statistics from all subsystems."""
        self._track("get_system_stats")
        stats: dict[str, Any] = {
            "orchestrator": {
                "request_counts": dict(self._request_counts),
                "total_requests": sum(self._request_counts.values()),
            }
        }

        if self._link_registry:
            stats["link_registry"] = self._link_registry.get_registry_stats()
        if self._router:
            stats["router"] = self._router.get_stats().to_dict()
        if self._propagation_engine:
            stats["propagation"] = self._propagation_engine.get_stats()

        if include_subsystems:
            stats["subsystems"] = await self._get_subsystem_stats()

        return stats

    async def health_check(self, subsystems: list[str] | None = None) -> dict[str, Any]:
        """Check health of all subsystems."""
        self._track("health_check")
        health: dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {},
        }

        # Link Registry
        if self._link_registry:
            try:
                reg_stats = self._link_registry.get_registry_stats()
                health["components"]["link_registry"] = {
                    "status": "healthy",
                    "total_links": reg_stats["total_links"],
                }
            except Exception as e:
                health["components"]["link_registry"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"

        # Subsystems
        subsystem_health = await self._check_subsystems(subsystems)
        health["components"].update(subsystem_health)

        # Determine overall status
        unhealthy = [k for k, v in health["components"].items() if v.get("status") != "healthy"]
        if unhealthy:
            health["status"] = "degraded" if len(unhealthy) < len(health["components"]) else "unhealthy"

        return health

    # ----- Private helpers -----

    async def _save_to_target(
        self, target: str, content: str, metadata: dict[str, Any] | None
    ) -> str | None:
        """Save content to a specific subsystem. Returns entity ID or None."""
        entity_id = str(uuid4())
        try:
            if target == "memory-ai":
                import sqlite3

                db_path = _PROJECT_ROOT / "data" / "memory_ai.db"
                importance = (metadata or {}).get("importance", 0.7)
                category = (metadata or {}).get("category", "general")
                tags = (metadata or {}).get("tags", [])

                def _save():
                    conn = sqlite3.connect(str(db_path))
                    try:
                        cursor = conn.cursor()
                        now = datetime.now().isoformat()
                        cursor.execute(
                            "INSERT INTO important_messages "
                            "(id, content, importance, category, tags, created_at, updated_at, metadata) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (entity_id, content, importance, category,
                             json.dumps(tags), now, now, json.dumps({})),
                        )
                        conn.commit()
                    finally:
                        conn.close()

                await asyncio.to_thread(_save)

            elif target == "vector-memory":
                from ..vector_memory.server import _get_qdrant, _get_embedding

                client = await asyncio.to_thread(_get_qdrant)
                vector = await _get_embedding(content)

                from qdrant_client.http import models as qmodels

                now = datetime.now()
                payload = {
                    "pattern_id": entity_id,
                    "pattern_type": (metadata or {}).get("pattern_type", "code-convention"),
                    "name": (metadata or {}).get("name", content[:50]),
                    "description": (metadata or {}).get("description", ""),
                    "content": content,
                    "confidence": (metadata or {}).get("confidence", 0.7),
                    "evidence_sources": [],
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "last_applied": None,
                    "decay_rate": 0.05,
                    "application_count": 0,
                    "version": 1,
                    "tags": (metadata or {}).get("tags", []),
                    "metadata": {},
                }

                await asyncio.to_thread(
                    client.upsert,
                    collection_name="learned_patterns",
                    points=[qmodels.PointStruct(id=entity_id, vector=vector, payload=payload)],
                )

            elif target == "skill-learning":
                storage_dir = _PROJECT_ROOT / "data" / "skill_learning"
                storage_dir.mkdir(parents=True, exist_ok=True)
                patterns_file = storage_dir / "patterns.jsonl"

                pattern = {
                    "pattern_id": entity_id,
                    "pattern_type": (metadata or {}).get("pattern_type", "workflow-pattern"),
                    "name": (metadata or {}).get("name", content[:50]),
                    "content": content,
                    "description": (metadata or {}).get("description", ""),
                    "confidence": (metadata or {}).get("confidence", 0.7),
                    "tags": (metadata or {}).get("tags", []),
                    "application_count": 0,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "version": 1,
                }

                def _append():
                    with open(patterns_file, "a", encoding="utf-8") as f:
                        f.write(json.dumps(pattern, ensure_ascii=False) + "\n")

                await asyncio.to_thread(_append)

            else:
                logger.warning(f"Unknown target: {target}")
                return None

            return entity_id

        except Exception as e:
            logger.error(f"Failed to save to {target}: {e}")
            return None

    async def _get_entity(self, unified_id: str) -> dict[str, Any] | None:
        """Get entity data from the appropriate subsystem."""
        try:
            uid = UnifiedID.parse(unified_id)
        except ValueError:
            return None

        try:
            if uid.source == SourceServer.MEMORY_AI:
                import sqlite3

                db_path = _PROJECT_ROOT / "data" / "memory_ai.db"

                def _get():
                    conn = sqlite3.connect(str(db_path))
                    try:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id, content, importance, category, tags, created_at "
                            "FROM important_messages WHERE id = ?",
                            (uid.identifier,),
                        )
                        row = cursor.fetchone()
                        if row:
                            return {
                                "unified_id": unified_id,
                                "content": row[1],
                                "importance": row[2],
                                "category": row[3],
                                "created_at": row[5],
                            }
                        return None
                    finally:
                        conn.close()

                return await asyncio.to_thread(_get)

            elif uid.source == SourceServer.VECTOR_MEMORY:
                from ..vector_memory.server import _get_qdrant, _pattern_from_payload

                client = await asyncio.to_thread(_get_qdrant)
                points = await asyncio.to_thread(
                    client.retrieve,
                    collection_name="learned_patterns",
                    ids=[uid.identifier],
                    with_payload=True,
                )
                if points:
                    pattern = _pattern_from_payload(str(points[0].id), points[0].payload)
                    return {"unified_id": unified_id, **pattern.to_dict()}
                return None

            elif uid.source == SourceServer.SKILL_LEARNING:
                patterns_file = _PROJECT_ROOT / "data" / "skill_learning" / "patterns.jsonl"

                def _get():
                    if not patterns_file.exists():
                        return None
                    with open(patterns_file, encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                item = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if item.get("pattern_id") == uid.identifier:
                                return {"unified_id": unified_id, **item}
                    return None

                return await asyncio.to_thread(_get)

        except Exception as e:
            logger.warning(f"Failed to get entity {unified_id}: {e}")
            return None

        return None

    async def _get_subsystem_stats(self) -> dict[str, Any]:
        """Get stats from each subsystem."""
        stats: dict[str, Any] = {}
        try:
            import sqlite3

            db_path = _PROJECT_ROOT / "data" / "memory_ai.db"

            def _ai_stats():
                conn = sqlite3.connect(str(db_path))
                try:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM important_messages")
                    count = cursor.fetchone()[0]
                    cursor.execute("SELECT AVG(importance) FROM important_messages")
                    avg_importance = cursor.fetchone()[0] or 0.0
                    return {"count": count, "avg_importance": round(avg_importance, 2)}
                finally:
                    conn.close()

            stats["memory-ai"] = await asyncio.to_thread(_ai_stats)
        except Exception as e:
            stats["memory-ai"] = {"error": str(e)}

        try:
            from ..vector_memory.server import _get_qdrant

            def _vm_stats():
                client = _get_qdrant()
                info = client.get_collection("learned_patterns")
                return {"count": info.points_count, "status": "green"}

            stats["vector-memory"] = await asyncio.to_thread(_vm_stats)
        except Exception as e:
            stats["vector-memory"] = {"error": str(e)}

        try:
            patterns_file = _PROJECT_ROOT / "data" / "skill_learning" / "patterns.jsonl"
            pending_file = _PROJECT_ROOT / "data" / "skill_learning" / "pending_patterns.jsonl"

            def _sl_stats():
                saved = 0
                pending = 0
                if patterns_file.exists():
                    with open(patterns_file, encoding="utf-8") as f:
                        saved = sum(1 for line in f if line.strip())
                if pending_file.exists():
                    with open(pending_file, encoding="utf-8") as f:
                        pending = sum(1 for line in f if line.strip())
                return {"saved": saved, "pending": pending}

            stats["skill-learning"] = await asyncio.to_thread(_sl_stats)
        except Exception as e:
            stats["skill-learning"] = {"error": str(e)}

        return stats

    async def _check_subsystems(self, subsystems: list[str] | None = None) -> dict[str, Any]:
        """Check subsystem availability."""
        checks: dict[str, Any] = {}

        if subsystems is None or "memory-ai" in subsystems:
            try:
                db_path = _PROJECT_ROOT / "data" / "memory_ai.db"
                checks["memory-ai"] = {
                    "status": "healthy" if db_path.exists() else "no_data",
                    "db_path": str(db_path),
                }
            except Exception as e:
                checks["memory-ai"] = {"status": "unhealthy", "error": str(e)}

        if subsystems is None or "vector-memory" in subsystems:
            try:
                from ..vector_memory.server import _get_qdrant

                def _check():
                    client = _get_qdrant()
                    collections = [c.name for c in client.get_collections().collections]
                    return "learned_patterns" in collections

                ok = await asyncio.to_thread(_check)
                checks["vector-memory"] = {"status": "healthy" if ok else "no_collection"}
            except Exception as e:
                checks["vector-memory"] = {"status": "unhealthy", "error": str(e)}

        if subsystems is None or "skill-learning" in subsystems:
            storage_dir = _PROJECT_ROOT / "data" / "skill_learning"
            checks["skill-learning"] = {
                "status": "healthy" if storage_dir.exists() else "no_data",
                "storage_dir": str(storage_dir),
            }

        return checks

    def _track(self, tool_name: str):
        """Track request counts per tool."""
        self._request_counts[tool_name] = self._request_counts.get(tool_name, 0) + 1


# =============================================================================
# MCP Server
# =============================================================================

app = Server("memory-orchestrator")

_orchestrator: MemoryOrchestrator | None = None


def _get_orchestrator() -> MemoryOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator()
    return _orchestrator


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="unified_search",
            description="Federated search across all memory subsystems (ai-memory, vector-memory, skill-learning). Returns ranked, deduplicated results with cross-links.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "include": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Subsystem names to include",
                    },
                    "exclude": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Subsystem names to exclude",
                    },
                    "min_score": {"type": "number", "default": 0.3, "description": "Minimum relevance score (0-1)"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="route_and_save",
            description="Auto-classify content and route to appropriate memory subsystem(s). Creates cross-links between multi-target saves.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to save"},
                    "metadata": {"type": "object", "description": "Optional metadata (importance, category, tags, etc.)"},
                    "auto_propagate": {"type": "boolean", "default": False},
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="get_full_context",
            description="Get entity with related entities via BFS graph traversal. Returns entity data + linked entities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string", "description": "Unified entity ID"},
                    "include_related": {"type": "boolean", "default": True},
                    "max_depth": {"type": "integer", "default": 2},
                    "max_entities": {"type": "integer", "default": 20},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="create_link",
            description="Create a cross-reference link between two entities in the unified namespace.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "target_id": {"type": "string"},
                    "link_type": {
                        "type": "string",
                        "default": "supports",
                        "description": "based_on, supports, contradicts, extends, derives_from, session_context",
                    },
                    "strength": {"type": "number", "default": 0.8},
                    "bidirectional": {"type": "boolean", "default": False},
                },
                "required": ["source_id", "target_id"],
            },
        ),
        Tool(
            name="get_related",
            description="Find related entities via BFS graph traversal. Returns entities ranked by effective strength.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "link_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by link types",
                    },
                    "direction": {"type": "string", "default": "both", "description": "outgoing, incoming, or both"},
                    "max_depth": {"type": "integer", "default": 2},
                    "min_strength": {"type": "number", "default": 0.5},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="propagate_update",
            description="Propagate a confidence/importance update through the entity graph via BFS with decay.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "delta": {"type": "number", "default": 0.1},
                    "success": {"type": "boolean", "default": True},
                    "metadata": {"type": "object"},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="get_system_stats",
            description="Get aggregate statistics from all memory subsystems, link registry, and router.",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_subsystems": {"type": "boolean", "default": True},
                },
            },
        ),
        Tool(
            name="health_check",
            description="Check health of memory subsystems: SQLite, Qdrant, JSONL file accessibility.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subsystems": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific subsystems to check (default: all)",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    orch = _get_orchestrator()
    try:
        if name == "unified_search":
            result = await orch.unified_search(
                query=arguments["query"],
                include=arguments.get("include"),
                exclude=arguments.get("exclude"),
                min_score=arguments.get("min_score", 0.3),
                limit=arguments.get("limit", 20),
            )
        elif name == "route_and_save":
            result = await orch.route_and_save(
                content=arguments["content"],
                metadata=arguments.get("metadata"),
                auto_propagate=arguments.get("auto_propagate", False),
            )
        elif name == "get_full_context":
            result = await orch.get_full_context(
                entity_id=arguments["entity_id"],
                include_related=arguments.get("include_related", True),
                max_depth=arguments.get("max_depth", 2),
                max_entities=arguments.get("max_entities", 20),
            )
        elif name == "create_link":
            result = await orch.create_link(
                source_id=arguments["source_id"],
                target_id=arguments["target_id"],
                link_type=arguments.get("link_type", "supports"),
                strength=arguments.get("strength", 0.8),
                bidirectional=arguments.get("bidirectional", False),
            )
        elif name == "get_related":
            result = await orch.get_related(
                entity_id=arguments["entity_id"],
                link_types=arguments.get("link_types"),
                direction=arguments.get("direction", "both"),
                max_depth=arguments.get("max_depth", 2),
                min_strength=arguments.get("min_strength", 0.5),
            )
        elif name == "propagate_update":
            result = await orch.propagate_update(
                entity_id=arguments["entity_id"],
                delta=arguments.get("delta", 0.1),
                success=arguments.get("success", True),
                metadata=arguments.get("metadata"),
            )
        elif name == "get_system_stats":
            result = await orch.get_system_stats(
                include_subsystems=arguments.get("include_subsystems", True),
            )
        elif name == "health_check":
            result = await orch.health_check(
                subsystems=arguments.get("subsystems"),
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2, default=str))]

    except OrchestratorError as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e), "type": type(e).__name__}))]
    except Exception as e:
        logger.error(f"Error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Start the Memory Orchestrator MCP server."""
    global _orchestrator
    logger.info("Starting Memory Orchestrator MCP Server...")

    _orchestrator = MemoryOrchestrator()
    await _orchestrator.start()

    try:
        async with stdio_server() as (read_stream, write_stream):
            await app.run(read_stream, write_stream, app.create_initialization_options())
    finally:
        await _orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
