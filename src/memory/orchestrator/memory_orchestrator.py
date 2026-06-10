"""
Memory Orchestrator MCP Server — Unified Memory Coordination.

Full MCP server (stdio) that ties together 3 memory subsystems:
- memory-ai (episodic facts, important messages)
- vector-memory (patterns, code conventions, semantic knowledge)
- skill-learning (captured skills, workflow patterns)

Provides 33 MCP tools across 4 phases:
  P0 (Core, 8): unified_search, route_and_save, get_full_context, create_link,
                 get_related, propagate_update, get_system_stats, health_check
  P3 (Realtime, 8): memory_subscribe, memory_unsubscribe, memory_publish,
                     memory_get_events, memory_replay, memory_event_history,
                     memory_event_stats, memory_subscription_health
  P3 (Extended, 4): memory_research, memory_id_management, memory_surprise, memory_warmup
  P4 (Services, 13): memory_audit_log, memory_audit_stats, memory_circuit_status,
                      memory_circuit_reset, memory_metrics, memory_ttl_set,
                      memory_ttl_check, memory_ttl_cleanup, memory_version_history,
                      memory_version_rollback, memory_version_compare,
                      memory_forget, memory_graph_analyze

Migrated from D:\\1C-Enterprise_Framework\\memory-orchestrator\\src\\memory_orchestrator.py
Adapted: Direct function calls instead of HTTP, 3 target servers, MCP server.
"""

import asyncio
import json
import logging
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from mcp import stdio_server
from mcp.server import Server
from mcp.types import TextContent, Tool

from ..ai_memory.services.audit_service import AuditAction, AuditQuery, AuditService
from ..ai_memory.services.ttl_service import TTLPolicy, TTLService
from ..ai_memory.services.versioning_service import VersioningService
from ..infrastructure.cache import LRUCache
from ..infrastructure.circuit_breaker import (
    CircuitBreakerRegistry,
)
from ..infrastructure.event_bus import EventBus
from ..infrastructure.event_store import EventStore, EventStoreConfig
from ..infrastructure.metrics import MetricsCollector, get_metrics_collector
from ..infrastructure.subscription_manager import SubscriptionManager
from ..vector_memory.graph.algorithms import GraphAlgorithms
from ..vector_memory.services.forgetgate_service import (
    ForgetCandidate,
    ForgetGateConfig,
    ForgetGateService,
    ForgetStrategy,
)
from .link_registry import LinkRegistry, LinkType
from .memory_router import (
    MemoryRouter,
    RouterConfig,
    RoutingDecision,
)
from .propagation_engine import PropagationEngine, PropagationResult
from .tools.id_management import IDManagementTool
from .tools.research import ResearchTool
from .tools.surprise import SurpriseTool
from .tools.warmup import WarmupTool
from .unified_id import MemoryType, SourceServer, UnifiedID
from .unified_search import (
    BaseSearchAdapter,
    SearchOptions,
    SearchResultItem,
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

        # Tokenize query: split on whitespace, keep tokens >= 3 chars.
        # Fallback to full query if no tokens survive filter (short/CJK queries).
        tokens = [t.lower() for t in query.split() if len(t) >= 3]
        if not tokens:
            tokens = [query.lower()]

        results = []

        def _do_search():
            conn = sqlite3.connect(str(self._db_path))
            try:
                cursor = conn.cursor()
                # OR-join LIKE for each token across content + tags (case-insensitive).
                where_parts = ["(LOWER(content) LIKE ? OR LOWER(tags) LIKE ?)"] * len(tokens)
                params: list = []
                for t in tokens:
                    params.extend([f"%{t}%", f"%{t}%"])
                # Fetch more than limit for reranking by match ratio.
                fetch_limit = max(limit * 3, 30)
                params.append(fetch_limit)
                cursor.execute(
                    "SELECT id, content, importance, category, tags, created_at "
                    "FROM important_messages "
                    f"WHERE {' OR '.join(where_parts)} "
                    "ORDER BY importance DESC LIMIT ?",
                    params,
                )
                rows = cursor.fetchall()
            finally:
                conn.close()

            # Python-side rerank: score = 0.5 * match_ratio + 0.5 * importance.
            scored = []
            for row in rows:
                content_lower = (row[1] or "").lower()
                tags_lower = (row[4] or "").lower()
                matched = sum(1 for t in tokens if t in content_lower or t in tags_lower)
                match_ratio = matched / len(tokens) if tokens else 0.0
                importance = min(row[2] or 0.0, 1.0)
                combined = min(match_ratio * 0.5 + importance * 0.5, 1.0)
                scored.append((combined, match_ratio, row))

            # Sort by combined score, keep only items with at least one token match.
            scored = [s for s in scored if s[1] > 0.0]
            scored.sort(key=lambda x: x[0], reverse=True)
            for combined, _match_ratio, row in scored[:limit]:
                results.append(
                    SearchResultItem(
                        unified_id=f"episodic:memory-ai:{row[0]}",
                        source=SourceServer.MEMORY_AI,
                        memory_type=MemoryType.EPISODIC,
                        content=row[1],
                        raw_score=combined,
                        created_at=datetime.fromisoformat(row[5]) if row[5] else None,
                        tags=json.loads(row[4]) if row[4] else [],
                    )
                )

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
            from ..vector_memory.server import _get_embedding, _get_qdrant, _pattern_from_payload

            client = await asyncio.to_thread(_get_qdrant)
            vector = await _get_embedding(query)

            from qdrant_client.http import models as qmodels

            conditions = [
                qmodels.FieldCondition(key="confidence", range=qmodels.Range(gte=min_confidence))
            ]
            qresults = await asyncio.to_thread(
                client.query_points,
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
                results.append(
                    SearchResultItem(
                        unified_id=f"semantic:vector-memory:{pattern.pattern_id}",
                        source=SourceServer.VECTOR_MEMORY,
                        memory_type=MemoryType.SEMANTIC,
                        content=pattern.content,
                        title=pattern.name,
                        raw_score=similarity * pattern.confidence,
                        created_at=pattern.created_at,
                        tags=pattern.tags,
                        metadata={
                            "pattern_type": pattern.pattern_type.value,
                            "confidence": pattern.confidence,
                        },
                    )
                )
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
                results.append(
                    SearchResultItem(
                        unified_id=f"learning:skill-learning:{item.get('pattern_id', '')}",
                        source=SourceServer.SKILL_LEARNING,
                        memory_type=MemoryType.LEARNING,
                        content=item.get("content", ""),
                        title=item.get("name", ""),
                        raw_score=score,
                        created_at=datetime.fromisoformat(item["created_at"])
                        if item.get("created_at")
                        else None,
                        tags=item.get("tags", []),
                    )
                )

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
        self._event_bus: EventBus | None = None
        self._event_store: EventStore | None = None
        self._subscription_manager: SubscriptionManager | None = None
        self._cache: LRUCache = LRUCache(max_size=256, default_ttl=3600.0)
        self._research_tool: ResearchTool | None = None
        self._id_tool: IDManagementTool | None = None
        self._surprise_tool: SurpriseTool | None = None
        self._warmup_tool: WarmupTool | None = None
        self._request_counts: dict[str, int] = {}
        # P4 services
        self._audit_service: AuditService | None = None
        self._versioning_service: VersioningService | None = None
        self._ttl_service: TTLService | None = None
        self._forgetgate_service: ForgetGateService | None = None
        self._circuit_registry: CircuitBreakerRegistry | None = None
        self._metrics: MetricsCollector | None = None
        self._graph_algorithms: GraphAlgorithms | None = None

    async def start(self):
        """Initialize all orchestrator components."""
        data_dir = _PROJECT_ROOT / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Link Registry
        db_path = self.config.link_registry_path
        if db_path is None:
            db_path = str(data_dir / "link_registry.db")
        self._link_registry = LinkRegistry(db_path=db_path)

        # Router
        self._router = MemoryRouter(self.config.router_config)

        # Search Engine with adapters
        self._search_engine = UnifiedSearchEngine(self._link_registry)
        self._search_engine.register_adapter(
            AiMemorySearchAdapter(_PROJECT_ROOT / "data" / "memory_ai.db")
        )
        self._search_engine.register_adapter(VectorMemorySearchAdapter())
        self._search_engine.register_adapter(
            SkillLearningSearchAdapter(_PROJECT_ROOT / "data" / "skill_learning")
        )

        # Pre-warm vector-memory (Qdrant gRPC connect + E5 model load)
        try:
            from ..vector_memory.server import _get_embedding, _get_qdrant

            await asyncio.to_thread(_get_qdrant)
            await _get_embedding("warmup")
            logger.info("Vector-memory pre-warmed (Qdrant + E5)")
        except Exception as e:
            logger.warning(f"Vector-memory pre-warm failed: {e}")

        # Event Bus + Store (P3)
        self._event_bus = EventBus()
        await self._event_bus.start()
        self._event_store = EventStore(
            EventStoreConfig(
                hot_buffer_path=str(data_dir / "events.jsonl"),
                cold_db_path=str(data_dir / "events.db"),
            )
        )
        await self._event_store.start()

        # Subscription Manager (P3)
        self._subscription_manager = SubscriptionManager(self._event_bus)
        await self._subscription_manager.start()

        # Tools (P3)
        self._research_tool = ResearchTool(self._link_registry, self._search_engine)
        self._id_tool = IDManagementTool()
        self._surprise_tool = SurpriseTool(self._search_engine)
        self._warmup_tool = WarmupTool(self._cache, self._search_engine, self._event_store)

        # P4 services
        services_dir = data_dir / "services"
        services_dir.mkdir(parents=True, exist_ok=True)

        self._audit_service = AuditService(
            storage_path=str(services_dir / "audit.jsonl"),
        )
        self._versioning_service = VersioningService(
            storage_path=services_dir / "versions.jsonl",
        )
        self._ttl_service = TTLService(
            storage_path=services_dir / "ttl.jsonl",
        )
        self._forgetgate_service = ForgetGateService()
        self._circuit_registry = CircuitBreakerRegistry()
        self._metrics = get_metrics_collector()
        self._graph_algorithms = GraphAlgorithms()

        logger.info("MemoryOrchestrator started")

    async def stop(self):
        """Tear down orchestrator."""
        if self._subscription_manager:
            await self._subscription_manager.stop()
            self._subscription_manager = None
        if self._propagation_engine:
            await self._propagation_engine.stop()
            self._propagation_engine = None
        if self._event_store:
            await self._event_store.stop()
            self._event_store = None
        if self._event_bus:
            await self._event_bus.stop()
            self._event_bus = None
        if self._ttl_service:
            await self._ttl_service.stop_cleanup_task()
            self._ttl_service = None
        self._link_registry = None
        self._router = None
        self._search_engine = None
        self._research_tool = None
        self._id_tool = None
        self._surprise_tool = None
        self._warmup_tool = None
        # P4 services — flush buffered audit entries to disk before teardown (§27 P0 D0.3),
        # else buffered CREATE/LINK/PROPAGATE audits never reach audit.jsonl.
        if self._audit_service:
            try:
                await self._audit_service.flush()
            except Exception:
                pass
        self._audit_service = None
        self._versioning_service = None
        self._forgetgate_service = None
        self._circuit_registry = None
        # §27 P2 D2.1: persist the in-process metrics snapshot before teardown — the
        # counters/gauges/durations are otherwise lost on restart (no longitudinal series).
        if self._metrics:
            try:
                from ..infrastructure.trace_log import write_trace

                write_trace(
                    "memory-metrics.jsonl",
                    "snapshot",
                    disable_env="MEMORY_METRICS_LOG_DISABLE",
                    **self._metrics.get_all(),
                )
            except Exception:
                pass
        self._metrics = None
        self._graph_algorithms = None
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
        # §27 P1 D1.1: persist the routing decision (targets/method/confidences) — fail-soft.
        try:
            from ..infrastructure.trace_log import write_trace

            write_trace(
                "memory-routing.log",
                "route",
                disable_env="MEMORY_ROUTING_LOG_DISABLE",
                targets=decision.targets,
                method=decision.method,
                confidences=decision.confidences,
            )
        except Exception:
            pass

        # Save to each target. A target that fails (raises or returns None) must
        # NOT be silently swallowed into a success:true response (roadmap 260609
        # P1.4 / §26 A6): callers cannot retry or alert on a loss they can't see.
        saved_entities = []
        failed_targets: list[str] = []
        for target in decision.targets:
            try:
                entity_id = await self._save_to_target(target, content, metadata)
            except Exception as e:  # per-target isolation — failure recorded below
                logger.warning(f"route_and_save: target {target} raised: {e}")
                entity_id = None
            if entity_id:
                saved_entities.append({"target": target, "entity_id": entity_id})
            else:
                failed_targets.append(target)

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

        # success only when EVERY routed target persisted; saved_partial flags the
        # mixed case (some saved, some lost) so the caller can distinguish it from a
        # total failure (nothing saved) or a clean success.
        all_saved = not failed_targets
        result = {
            "success": all_saved,
            "saved_partial": bool(saved_entities) and bool(failed_targets),
            "routing": decision.to_dict(),
            "saved_entities": saved_entities,
            "failed_targets": failed_targets,
            "cross_links_created": max(0, len(saved_entities) - 1),
        }
        await self._emit_event(
            "memory.save",
            {
                "targets": decision.targets,
                "entity_count": len(saved_entities),
            },
        )
        await self._audit(
            AuditAction.CREATE,
            "memory",
            resource_id=(saved_entities[0]["entity_id"] if saved_entities else None),
            metadata={
                "targets": decision.targets,
                "entity_count": len(saved_entities),
                "auto_propagate": auto_propagate,
            },
        )
        return result

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

        # Get entity from subsystems (may be None for link-only entities)
        entity = await self._get_entity(entity_id)

        result: dict[str, Any] = {
            "entity": entity,
            "related_entities": [],
            "links": [],
        }

        if include_related:
            related = self._link_registry.get_related_entities(entity_id, max_depth=max_depth)
            result["links"] = [
                {
                    "entity_id": r.entity_id,
                    "depth": r.depth,
                    "strength": r.effective_strength,
                    "path": r.link_path,
                }
                for r in related[:max_entities]
            ]

        if not entity and not result["links"]:
            raise EntityNotFoundError(f"Entity not found: {entity_id}")

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
        await self._emit_event(
            "memory.link",
            {
                "source_id": source_id,
                "target_id": target_id,
                "link_type": link_type,
            },
        )
        await self._audit(
            AuditAction.LINK,
            "link",
            resource_id=f"{source_id}->{target_id}",
            metadata={"link_type": link_type, "strength": strength},
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

    def _build_propagation_handlers(self) -> dict:
        """Real update handlers wiring PropagationEngine to the backing stores
        (roadmap 260609 P2.3). Without these the engine could only *simulate*
        updates; with them ``propagate_update`` actually mutates:

        - **vector-memory** (``semantic:vector-memory:<uuid>``): nudge the
          pattern's Beta succ/fail counts by ``|delta|`` (sign = direction) and
          re-derive confidence — mirrors ``vector_memory.server._cascade_confidence``
          but for a single explicitly-propagated node. Reuses the warm Qdrant
          client (``_get_qdrant``) pre-warmed in :meth:`start`.
        - **memory-ai** (``episodic:memory-ai:<id>``): nudge the message's
          importance by ``delta`` (clamped to ``[0, 1]``) in SQLite.

        Each handler returns ``True`` only on a real mutation (entity found and
        written), ``False`` otherwise — so a missing entity is *not* counted as
        ``entities_updated``. Blocking store I/O runs in a worker thread.
        """
        from ..vector_memory.confidence import derive_confidence, seed_counts_from_legacy
        from .unified_id import SourceServer, UnifiedID

        ai_db = str(_PROJECT_ROOT / "data" / "memory_ai.db")

        async def _vector_memory_handler(entity_id: str, delta: float) -> bool:
            def _apply() -> bool:
                from ..vector_memory.server import COLLECTION_NAME, _get_qdrant

                try:
                    pid = UnifiedID.parse(entity_id).identifier
                except ValueError:
                    return False
                client = _get_qdrant()
                pts = client.retrieve(
                    collection_name=COLLECTION_NAME, ids=[pid], with_payload=True
                )
                if not pts:
                    return False  # not a learned_pattern → honest no-op
                pay = pts[0].payload or {}
                succ, fail = pay.get("succ"), pay.get("fail")
                if succ is None or fail is None:
                    succ, fail = seed_counts_from_legacy(
                        float(pay.get("confidence", 0.70)),
                        int(pay.get("application_count", 0) or 0),
                    )
                succ, fail = float(succ), float(fail)
                if delta >= 0:
                    succ += abs(delta)
                else:
                    fail += abs(delta)
                now_iso = datetime.now().isoformat()
                client.set_payload(
                    collection_name=COLLECTION_NAME,
                    payload={
                        "succ": round(succ, 6),
                        "fail": round(fail, 6),
                        "confidence": round(derive_confidence(succ, fail), 6),
                        "updated_at": now_iso,
                    },
                    points=[pid],
                )
                return True

            return await asyncio.to_thread(_apply)

        async def _memory_ai_handler(entity_id: str, delta: float) -> bool:
            def _apply() -> bool:
                try:
                    mid = UnifiedID.parse(entity_id).identifier
                except ValueError:
                    return False
                try:
                    conn = sqlite3.connect(ai_db, timeout=2)
                except sqlite3.Error:
                    return False
                try:
                    row = conn.execute(
                        "SELECT importance FROM important_messages WHERE id = ?", (mid,)
                    ).fetchone()
                    if row is None:
                        return False
                    new_imp = max(0.0, min(1.0, float(row[0] or 0.5) + delta))
                    conn.execute(
                        "UPDATE important_messages SET importance = ?, updated_at = ? "
                        "WHERE id = ?",
                        (round(new_imp, 4), datetime.now().isoformat(), mid),
                    )
                    conn.commit()
                    return True
                finally:
                    conn.close()

            return await asyncio.to_thread(_apply)

        return {
            SourceServer.VECTOR_MEMORY: _vector_memory_handler,
            SourceServer.MEMORY_AI: _memory_ai_handler,
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

        # Lazy-init propagation engine with real store-backed update handlers
        # (roadmap 260609 P2.3) so propagated updates actually mutate the stores
        # instead of simulating success.
        if self._propagation_engine is None:
            self._propagation_engine = PropagationEngine(
                self._link_registry,
                update_handlers=self._build_propagation_handlers(),
            )
            await self._propagation_engine.start()

        # Sign carries the direction: the BFS uses the delta's sign (positive =
        # boost, negative = penalty), so fold `success` into it.
        signed_delta = abs(delta) if success else -abs(delta)
        result: PropagationResult = await self._propagation_engine.propagate(
            entity_id=entity_id,
            base_delta=signed_delta,
            success=success,
            metadata=metadata,
        )
        await self._audit(
            AuditAction.PROPAGATE,
            "memory",
            resource_id=entity_id,
            metadata={"delta": delta, "outcome_success": success},
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

        # P4 service stats
        if self._audit_service:
            stats["audit"] = await self._audit_service.get_stats()
        if self._versioning_service:
            stats["versioning"] = await self._versioning_service.get_stats()
        if self._ttl_service:
            stats["ttl"] = await self._ttl_service.get_stats()
        if self._circuit_registry:
            stats["circuit_breakers"] = self._circuit_registry.get_all_stats()
        if self._metrics:
            stats["metrics"] = self._metrics.get_all()
        if self._graph_algorithms:
            stats["graph"] = self._graph_algorithms.get_stats()
        if self._forgetgate_service:
            stats["forgetgate"] = self._forgetgate_service.get_stats()

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

        # P4 services health
        for name, svc in [
            ("audit_service", self._audit_service),
            ("versioning_service", self._versioning_service),
            ("ttl_service", self._ttl_service),
        ]:
            if svc:
                try:
                    health["components"][name] = {"status": "healthy"}
                except Exception as e:
                    health["components"][name] = {"status": "unhealthy", "error": str(e)}

        if self._circuit_registry:
            all_stats = self._circuit_registry.get_all_stats()
            open_circuits = [n for n, s in all_stats.items() if s.get("state") == "open"]
            health["components"]["circuit_breakers"] = {
                "status": "degraded" if open_circuits else "healthy",
                "total": len(all_stats),
                "open": open_circuits,
            }

        if self._metrics:
            health["components"]["metrics"] = {"status": "healthy"}

        if self._graph_algorithms:
            try:
                gstats = self._graph_algorithms.get_stats()
                health["components"]["graph"] = {
                    "status": "healthy",
                    "nodes": gstats.get("total_nodes", 0),
                }
            except Exception as e:
                health["components"]["graph"] = {"status": "unhealthy", "error": str(e)}

        # Determine overall status
        unhealthy = [k for k, v in health["components"].items() if v.get("status") != "healthy"]
        if unhealthy:
            health["status"] = (
                "degraded" if len(unhealthy) < len(health["components"]) else "unhealthy"
            )

        return health

    # ----- Realtime tools (P3) -----

    async def memory_subscribe(
        self,
        client_id: str,
        pattern: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Subscribe to realtime memory events."""
        self._track("memory_subscribe")
        if not self._subscription_manager:
            raise SubsystemUnavailableError("Subscription manager not initialized")
        sub = await self._subscription_manager.create(client_id, pattern, metadata)
        return {"success": True, "subscription": sub.to_dict()}

    async def memory_unsubscribe(self, subscription_id: str) -> dict[str, Any]:
        """Unsubscribe from memory events."""
        self._track("memory_unsubscribe")
        if not self._subscription_manager:
            raise SubsystemUnavailableError("Subscription manager not initialized")
        removed = await self._subscription_manager.remove(subscription_id)
        return {"success": removed, "subscription_id": subscription_id}

    async def memory_publish(
        self,
        event_type: str,
        data: dict[str, Any],
        source: str | None = None,
    ) -> dict[str, Any]:
        """Publish a custom event to the event bus."""
        self._track("memory_publish")
        if not self._event_bus:
            raise SubsystemUnavailableError("Event bus not initialized")
        event_id = await self._event_bus.publish(event_type, data, source=source)
        if self._event_store:
            from ..infrastructure.event_bus import Event

            event = Event(
                event_id=event_id,
                event_type=event_type,
                data=data,
                timestamp=datetime.now(),
                source=source,
            )
            await self._event_store.append(event)
        return {"success": True, "event_id": event_id}

    async def memory_get_events(
        self,
        subscription_id: str,
        max_events: int = 10,
    ) -> dict[str, Any]:
        """Poll pending events from a subscription."""
        self._track("memory_get_events")
        if not self._subscription_manager:
            raise SubsystemUnavailableError("Subscription manager not initialized")
        events = await self._subscription_manager.get_events(subscription_id, max_events)
        return {"subscription_id": subscription_id, "events": events, "count": len(events)}

    async def memory_replay(
        self,
        event_type: str | None = None,
        start: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Replay events from persistent storage."""
        self._track("memory_replay")
        if not self._event_store:
            raise SubsystemUnavailableError("Event store not initialized")
        start_dt = datetime.fromisoformat(start) if start else None
        events = await self._event_store.query(event_type=event_type, start=start_dt, limit=limit)
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "data": e.data,
                    "timestamp": e.timestamp.isoformat()
                    if isinstance(e.timestamp, datetime)
                    else str(e.timestamp),
                    "source": e.source,
                }
                for e in events
            ],
            "count": len(events),
        }

    async def memory_event_history(
        self,
        event_type: str | None = None,
        start: str | None = None,
        end: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Query event history with filters."""
        self._track("memory_event_history")
        if not self._event_store:
            raise SubsystemUnavailableError("Event store not initialized")
        start_dt = datetime.fromisoformat(start) if start else None
        end_dt = datetime.fromisoformat(end) if end else None
        events = await self._event_store.query(
            event_type=event_type, start=start_dt, end=end_dt, limit=limit
        )
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "data": e.data,
                    "timestamp": e.timestamp.isoformat()
                    if isinstance(e.timestamp, datetime)
                    else str(e.timestamp),
                    "source": e.source,
                }
                for e in events
            ],
            "count": len(events),
        }

    async def memory_event_stats(self) -> dict[str, Any]:
        """Get event bus and store statistics."""
        self._track("memory_event_stats")
        stats: dict[str, Any] = {}
        if self._event_bus:
            bus_stats = self._event_bus.get_stats()
            stats["event_bus"] = {
                "published_count": bus_stats.published_count,
                "subscriber_count": bus_stats.subscriber_count,
                "dropped_count": bus_stats.dropped_count,
            }
        if self._event_store:
            stats["event_store"] = await self._event_store.get_stats()
        if self._subscription_manager:
            stats["subscriptions"] = self._subscription_manager.get_stats()
        return stats

    async def memory_subscription_health(
        self, subscription_id: str | None = None
    ) -> dict[str, Any]:
        """Check subscription health or send heartbeat."""
        self._track("memory_subscription_health")
        if not self._subscription_manager:
            raise SubsystemUnavailableError("Subscription manager not initialized")
        if subscription_id:
            ok = await self._subscription_manager.heartbeat(subscription_id)
            return {"subscription_id": subscription_id, "heartbeat": ok}
        subs = await self._subscription_manager.list_subscriptions()
        return {"subscriptions": subs, "total": len(subs)}

    # ----- Extended tools (P3) -----

    async def memory_research(
        self,
        query: str | None = None,
        entity_ids: list[str] | None = None,
        analysis_type: str = "relationships",
        max_depth: int = 3,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Deep analysis of entity relationships and anomalies."""
        self._track("memory_research")
        if not self._research_tool:
            raise SubsystemUnavailableError("Research tool not initialized")
        return await self._research_tool.analyze(
            query=query,
            entity_ids=entity_ids,
            analysis_type=analysis_type,
            max_depth=max_depth,
            limit=limit,
        )

    async def memory_id_management(
        self,
        operation: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """UUIDv7 generation, ID resolution, conflict handling."""
        self._track("memory_id_management")
        if not self._id_tool:
            raise SubsystemUnavailableError("ID management tool not initialized")
        return await self._id_tool.execute(operation=operation, **kwargs)

    async def memory_surprise(
        self,
        content: str,
        context: str | None = None,
        detail: bool = False,
    ) -> dict[str, Any]:
        """Calculate unexpectedness score for new content."""
        self._track("memory_surprise")
        if not self._surprise_tool:
            raise SubsystemUnavailableError("Surprise tool not initialized")
        return await self._surprise_tool.score(content=content, context=context, detail=detail)

    async def memory_warmup(
        self,
        strategy: str = "frequent",
        limit: int = 50,
        query: str | None = None,
    ) -> dict[str, Any]:
        """Preload frequently used data into LRU cache."""
        self._track("memory_warmup")
        if not self._warmup_tool:
            raise SubsystemUnavailableError("Warmup tool not initialized")
        return await self._warmup_tool.warmup(strategy=strategy, limit=limit, query=query)

    # ----- P4: Service wrapper tools -----

    async def memory_audit_log(
        self,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query audit log entries with filters."""
        self._track("memory_audit_log")
        if not self._audit_service:
            raise SubsystemUnavailableError("Audit service not initialized")
        query = AuditQuery(
            action=AuditAction(action) if action else None,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
            offset=offset,
        )
        entries = await self._audit_service.query(query)
        return {
            "entries": [e.to_dict() for e in entries],
            "count": len(entries),
            "offset": offset,
            "limit": limit,
        }

    async def memory_audit_stats(self) -> dict[str, Any]:
        """Get audit log statistics."""
        self._track("memory_audit_stats")
        if not self._audit_service:
            raise SubsystemUnavailableError("Audit service not initialized")
        stats = await self._audit_service.get_stats()
        stats["buffer_size"] = len(self._audit_service._buffer)
        return stats

    async def memory_circuit_status(self, name: str | None = None) -> dict[str, Any]:
        """Get circuit breaker status for one or all named breakers."""
        self._track("memory_circuit_status")
        if not self._circuit_registry:
            raise SubsystemUnavailableError("Circuit breaker registry not initialized")
        if name:
            cb = self._circuit_registry.get(name)
            if not cb:
                return {
                    "error": f"Circuit breaker '{name}' not found",
                    "available": list(self._circuit_registry._breakers.keys()),
                }
            return cb.stats
        return {"breakers": self._circuit_registry.get_all_stats()}

    async def memory_circuit_reset(self, name: str) -> dict[str, Any]:
        """Reset a circuit breaker to CLOSED state."""
        self._track("memory_circuit_reset")
        if not self._circuit_registry:
            raise SubsystemUnavailableError("Circuit breaker registry not initialized")
        cb = self._circuit_registry.get(name)
        if not cb:
            return {"error": f"Circuit breaker '{name}' not found"}
        cb.reset()
        return {"success": True, "name": name, "state": cb.state.value}

    async def memory_metrics(self, reset: bool = False) -> dict[str, Any]:
        """Get aggregated metrics from all subsystems."""
        self._track("memory_metrics")
        if not self._metrics:
            raise SubsystemUnavailableError("Metrics collector not initialized")
        if reset:
            self._metrics.reset()
            return {"success": True, "action": "reset"}
        return self._metrics.get_all()

    async def memory_ttl_set(
        self,
        entity_id: str,
        policy: str = "long",
        ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        """Register or update TTL for an entity."""
        self._track("memory_ttl_set")
        if not self._ttl_service:
            raise SubsystemUnavailableError("TTL service not initialized")
        entry = await self._ttl_service.register(
            entity_id=entity_id,
            policy=TTLPolicy(policy),
            ttl_seconds=ttl_seconds,
        )
        return {"success": True, "entry": entry.to_dict()}

    async def memory_ttl_check(
        self,
        entity_id: str | None = None,
        include_expired: bool = False,
    ) -> dict[str, Any]:
        """Check TTL status. If entity_id given, check that entity. Otherwise list stats + expiring."""
        self._track("memory_ttl_check")
        if not self._ttl_service:
            raise SubsystemUnavailableError("TTL service not initialized")
        if entity_id:
            entry = await self._ttl_service.get_entry(entity_id)
            if not entry:
                return {"entity_id": entity_id, "status": "not_found"}
            expired = entry.is_expired()
            result: dict[str, Any] = {
                "entity_id": entity_id,
                "expired": expired,
                "entry": entry.to_dict(),
            }
            if not expired:
                result["record_access"] = True
                await self._ttl_service.record_access(entity_id)
            return result
        stats = await self._ttl_service.get_stats()
        if include_expired:
            expired = await self._ttl_service.get_expired()
            stats["expired_entries"] = [e.to_dict() for e in expired[:20]]
        return stats

    async def memory_ttl_cleanup(self) -> dict[str, Any]:
        """Remove expired TTL entries. Returns list of removed entity IDs."""
        self._track("memory_ttl_cleanup")
        if not self._ttl_service:
            raise SubsystemUnavailableError("TTL service not initialized")
        removed = await self._ttl_service.cleanup_expired()
        return {"success": True, "removed_count": len(removed), "removed": removed}

    async def memory_version_history(
        self,
        entity_id: str,
        limit: int = 50,
        include_content: bool = True,
    ) -> dict[str, Any]:
        """Get version history for an entity."""
        self._track("memory_version_history")
        if not self._versioning_service:
            raise SubsystemUnavailableError("Versioning service not initialized")
        versions = await self._versioning_service.get_version_history(
            entity_id=entity_id,
            limit=limit,
            include_content=include_content,
        )
        return {
            "entity_id": entity_id,
            "versions": [v.to_dict() for v in versions],
            "count": len(versions),
        }

    async def memory_version_rollback(
        self,
        entity_id: str,
        target_version: int,
        rollback_by: str = "",
    ) -> dict[str, Any]:
        """Rollback entity to a specific version."""
        self._track("memory_version_rollback")
        if not self._versioning_service:
            raise SubsystemUnavailableError("Versioning service not initialized")
        result = await self._versioning_service.rollback_to_version(
            entity_id=entity_id,
            target_version=target_version,
            rollback_by=rollback_by,
        )
        if result is None:
            return {
                "success": False,
                "error": f"Version {target_version} not found for entity {entity_id}",
            }
        await self._audit(
            AuditAction.ROLLBACK,
            "memory",
            resource_id=entity_id,
            metadata={"target_version": target_version, "rollback_by": rollback_by},
        )
        return {"success": True, "new_version": result.to_dict()}

    async def memory_version_compare(
        self,
        entity_id: str,
        version_a: int,
        version_b: int,
    ) -> dict[str, Any]:
        """Compare two versions of an entity."""
        self._track("memory_version_compare")
        if not self._versioning_service:
            raise SubsystemUnavailableError("Versioning service not initialized")
        return await self._versioning_service.compare_versions(
            entity_id=entity_id,
            version_a=version_a,
            version_b=version_b,
        )

    async def memory_forget(
        self,
        strategy: str = "composite",
        dry_run: bool = True,
        candidates: list[dict[str, Any]] | None = None,
        min_confidence: float = 0.1,
        decay_rate: float = 0.05,
    ) -> dict[str, Any]:
        """Run ForgetGate evaluation on candidates. Default is dry-run (no actual deletion)."""
        self._track("memory_forget")
        if not self._forgetgate_service:
            raise SubsystemUnavailableError("ForgetGate service not initialized")
        config = ForgetGateConfig(
            strategy=ForgetStrategy(strategy),
            dry_run=dry_run,
            min_confidence=min_confidence,
            decay_rate=decay_rate,
        )
        gate = ForgetGateService(config)
        if candidates:
            fc = [
                ForgetCandidate(
                    entity_id=c.get("entity_id", ""),
                    current_confidence=c.get("confidence", 0.5),
                    last_accessed=datetime.fromisoformat(c["last_accessed"])
                    if c.get("last_accessed")
                    else None,
                    access_count=c.get("access_count", 0),
                    created_at=datetime.fromisoformat(c["created_at"])
                    if c.get("created_at")
                    else datetime.now(),
                    tags=c.get("tags", []),
                    metadata=c.get("metadata", {}),
                )
                for c in candidates
            ]
        else:
            fc = []
        decisions = gate.evaluate(fc)
        stats = gate.apply(decisions)
        return {
            "stats": {
                "total_evaluated": stats.total_evaluated,
                "kept": stats.kept,
                "decayed": stats.decayed,
                "archived": stats.archived,
                "deleted": stats.deleted,
                "duration_ms": stats.duration_ms,
                "dry_run": dry_run,
            },
            "decisions": [
                {
                    "entity_id": d.entity_id,
                    "action": d.action.value,
                    "new_confidence": round(d.new_confidence, 4),
                    "reason": d.reason,
                }
                for d in decisions[:50]
            ],
        }

    async def memory_graph_analyze(
        self,
        algorithm: str = "stats",
        source: str | None = None,
        target: str | None = None,
        damping: float = 0.85,
        max_iterations: int = 100,
    ) -> dict[str, Any]:
        """Run graph algorithms: pagerank, centrality, communities, shortest_path, stats."""
        self._track("memory_graph_analyze")
        if not self._graph_algorithms:
            raise SubsystemUnavailableError("Graph algorithms not initialized")

        if algorithm == "stats":
            return self._graph_algorithms.get_stats()
        elif algorithm == "pagerank":
            ranks = self._graph_algorithms.pagerank(damping=damping, max_iterations=max_iterations)
            sorted_ranks = sorted(ranks.items(), key=lambda x: x[1], reverse=True)[:20]
            return {
                "algorithm": "pagerank",
                "results": [{"node": n, "score": round(s, 6)} for n, s in sorted_ranks],
            }
        elif algorithm == "centrality":
            cent = self._graph_algorithms.degree_centrality()
            sorted_cent = sorted(cent.items(), key=lambda x: x[1], reverse=True)[:20]
            return {
                "algorithm": "centrality",
                "results": [{"node": n, "degree": d} for n, d in sorted_cent],
            }
        elif algorithm == "communities":
            communities = self._graph_algorithms.detect_communities()
            return {
                "algorithm": "communities",
                "count": len(communities),
                "communities": [
                    {"id": c.community_id, "members": c.members, "modularity": c.modularity}
                    for c in communities
                ],
            }
        elif algorithm == "shortest_path":
            if not source or not target:
                return {"error": "source and target required for shortest_path"}
            result = self._graph_algorithms.shortest_path(source, target)
            if result is None:
                return {"algorithm": "shortest_path", "found": False}
            return {
                "algorithm": "shortest_path",
                "found": True,
                "path": result.path,
                "total_weight": result.total_weight,
                "hop_count": result.hop_count,
            }
        elif algorithm == "connected_components":
            components = self._graph_algorithms.connected_components()
            return {
                "algorithm": "connected_components",
                "count": len(components),
                "components": [
                    {"size": len(c), "nodes": sorted(c)[:20]}
                    for c in sorted(components, key=len, reverse=True)
                ],
            }
        else:
            return {
                "error": f"Unknown algorithm: {algorithm}. Use: stats, pagerank, centrality, communities, shortest_path, connected_components"
            }

    # ----- Private helpers -----

    async def _save_to_target(
        self, target: str, content: str, metadata: dict[str, Any] | None
    ) -> str | None:
        """Save content to a specific subsystem. Returns entity ID or None."""
        entity_id = str(uuid4())
        # §26 P1.3 write-contract: stamp the cross-store idempotency key on every
        # path and emit an ingestion event (saved/dup/error) so these direct writes
        # are visible to cross_store_sync / fact-trace, not just the harvesters.
        try:
            from .content_hash import hash_content

            content_hash = hash_content(content)
        except Exception:
            content_hash = ""
        # target string -> cross-store canonical store name (matches cross_store_index).
        _store_name = {
            "memory-ai": "memory_ai",
            "vector-memory": "learned_patterns",
            "skill-learning": "skill_learning",
            "wiki": "wiki",
        }.get(target, target)

        def _ingest(action: str, **kw: Any) -> None:
            try:
                from .ingest_metrics import record_ingest

                record_ingest(
                    _store_name, action, content_hash=content_hash, harvester="route_and_save", **kw
                )
            except Exception:
                pass

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
                            (
                                entity_id,
                                content,
                                importance,
                                category,
                                json.dumps(tags),
                                now,
                                now,
                                json.dumps({"content_hash": content_hash}),
                            ),
                        )
                        conn.commit()
                    finally:
                        conn.close()

                await asyncio.to_thread(_save)
                _ingest("saved")

            elif target == "vector-memory":
                from ..vector_memory.server import _get_embedding, _get_qdrant
                from .content_hash import point_id as _point_id

                client = await asyncio.to_thread(_get_qdrant)

                # Deterministic content-derived id → re-routing identical content
                # dedups (no duplicate point) and collides with save_pattern/harvest.
                if content_hash:
                    entity_id = _point_id(content_hash)
                    try:
                        existing = await asyncio.to_thread(
                            client.retrieve,
                            collection_name="learned_patterns",
                            ids=[entity_id],
                        )
                    except Exception:
                        existing = []
                    if existing:
                        _ingest("dup", pattern_id=entity_id)
                        return entity_id

                vector = await _get_embedding(content)

                from qdrant_client.http import models as qmodels

                now = datetime.now()
                payload = {
                    "pattern_id": entity_id,
                    "pattern_type": (metadata or {}).get("pattern_type", "code-convention"),
                    "name": (metadata or {}).get("name", content[:50]),
                    "description": (metadata or {}).get("description", ""),
                    "content": content,
                    "content_hash": content_hash,
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
                _ingest("saved", pattern_id=entity_id)

            elif target == "skill-learning":
                storage_dir = _PROJECT_ROOT / "data" / "skill_learning"
                storage_dir.mkdir(parents=True, exist_ok=True)
                patterns_file = storage_dir / "patterns.jsonl"

                pattern = {
                    "pattern_id": entity_id,
                    "pattern_type": (metadata or {}).get("pattern_type", "workflow-pattern"),
                    "name": (metadata or {}).get("name", content[:50]),
                    "content": content,
                    "content_hash": content_hash,
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
                _ingest("saved")

            elif target == "wiki":
                from .memcube import ContentType as CType
                from .memcube import MemoryCube

                slug = (metadata or {}).get("slug")
                if not slug:
                    slug = content[:40].lower().replace(" ", "-")
                    slug = "".join(c if c.isalnum() or c == "-" else "" for c in slug)
                    slug = slug or entity_id[:16]

                cube = MemoryCube(
                    cube_id=entity_id,
                    content=content,
                    content_type=CType.WIKI,
                    source=SourceServer.OBSIDIAN_VAULT,
                    memory_type=MemoryType.WIKI,
                    confidence=(metadata or {}).get("confidence", 0.7),
                    importance=(metadata or {}).get("importance", 0.5),
                    tags=(metadata or {}).get("tags", []),
                )
                wiki_md = cube.to_wiki_page()

                drafts_dir = _PROJECT_ROOT / "docs" / "wiki" / "drafts"
                draft_path = drafts_dir / f"{slug}.md"

                def _write_draft():
                    drafts_dir.mkdir(parents=True, exist_ok=True)
                    draft_path.write_text(wiki_md, encoding="utf-8")

                await asyncio.to_thread(_write_draft)
                _ingest("saved")

            else:
                logger.warning(f"Unknown target: {target}")
                return None

            return entity_id

        except Exception as e:
            logger.error(f"Failed to save to {target}: {e}")
            _ingest("error", reason=f"{type(e).__name__}")
            return None

    async def _get_entity(self, unified_id: str) -> dict[str, Any] | None:
        """Get entity data from the appropriate subsystem."""
        try:
            uid = UnifiedID.parse(unified_id)
        except ValueError:
            # Plain UUID — try all subsystems
            return await self._get_entity_by_raw_id(unified_id)

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

    async def _get_entity_by_raw_id(self, raw_id: str) -> dict[str, Any] | None:
        import sqlite3

        db_path = _PROJECT_ROOT / "data" / "memory_ai.db"
        connection = None
        try:
            connection = sqlite3.connect(str(db_path), timeout=1)
            cursor = connection.cursor()
            cursor.execute(
                "SELECT id, content, importance, category, tags, created_at "
                "FROM important_messages WHERE id = ?",
                (raw_id,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "unified_id": f"episodic:memory-ai:{row[0]}",
                    "content": row[1],
                    "importance": row[2],
                    "category": row[3],
                    "created_at": row[5],
                }
            return None
        except Exception:
            return None
        finally:
            if connection:
                connection.close()

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

    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish event to bus and persist to store (fire-and-forget)."""
        if self._event_bus:
            try:
                event_id = await self._event_bus.publish(event_type, data, source="orchestrator")
                if self._event_store:
                    from ..infrastructure.event_bus import Event

                    event = Event(
                        event_id=event_id,
                        event_type=event_type,
                        data=data,
                        timestamp=datetime.now(),
                        source="orchestrator",
                    )
                    await self._event_store.append(event)
            except Exception as e:
                logger.debug("Event emission failed: %s", e)

    async def _audit(
        self,
        action: AuditAction,
        resource_type: str,
        resource_id: str | None = None,
        *,
        new_value: dict[str, Any] | None = None,
        old_value: dict[str, Any] | None = None,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Fail-soft audit write (§27 P0 D0.3) — revives the audit write-path.

        Mirrors ``_emit_event``'s fire-and-forget contract: never raises into the
        caller. Metadata only (no content bodies). Buffered by AuditService and
        flushed on ``stop()`` (DELETE/ROLLBACK persist immediately).
        """
        if not self._audit_service:
            return
        try:
            await self._audit_service.log(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                new_value=new_value,
                old_value=old_value,
                success=success,
                metadata=metadata or {},
            )
        except Exception as e:
            logger.debug("Audit log failed: %s", e)


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
                    "min_score": {
                        "type": "number",
                        "default": 0.3,
                        "description": "Minimum relevance score (0-1)",
                    },
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
                    "metadata": {
                        "type": "object",
                        "description": "Optional metadata (importance, category, tags, etc.)",
                    },
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
                    "direction": {
                        "type": "string",
                        "default": "both",
                        "description": "outgoing, incoming, or both",
                    },
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
        # --- Realtime tools (P3) ---
        Tool(
            name="memory_subscribe",
            description="Subscribe to realtime memory events. Returns subscription ID for polling.",
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Client identifier"},
                    "pattern": {
                        "type": "string",
                        "description": "Event pattern with wildcards (e.g. 'memory.*', 'memory.**')",
                    },
                    "metadata": {"type": "object", "description": "Optional subscription metadata"},
                },
                "required": ["client_id", "pattern"],
            },
        ),
        Tool(
            name="memory_unsubscribe",
            description="Remove a subscription by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                },
                "required": ["subscription_id"],
            },
        ),
        Tool(
            name="memory_publish",
            description="Publish a custom event to the memory event bus. Persisted to event store.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "description": "Dotted event type (e.g. 'memory.custom.alert')",
                    },
                    "data": {"type": "object", "description": "Event payload"},
                    "source": {"type": "string", "description": "Source identifier"},
                },
                "required": ["event_type", "data"],
            },
        ),
        Tool(
            name="memory_get_events",
            description="Poll pending events from a subscription queue.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {"type": "string"},
                    "max_events": {"type": "integer", "default": 10},
                },
                "required": ["subscription_id"],
            },
        ),
        Tool(
            name="memory_replay",
            description="Replay events from persistent storage. Useful for rebuilding state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "description": "Filter by event type"},
                    "start": {"type": "string", "description": "ISO datetime to replay from"},
                    "limit": {"type": "integer", "default": 100},
                },
            },
        ),
        Tool(
            name="memory_event_history",
            description="Query event history with type and time range filters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "start": {"type": "string", "description": "ISO datetime range start"},
                    "end": {"type": "string", "description": "ISO datetime range end"},
                    "limit": {"type": "integer", "default": 50},
                },
            },
        ),
        Tool(
            name="memory_event_stats",
            description="Get event bus, event store, and subscription statistics.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="memory_subscription_health",
            description="Send heartbeat for a subscription or list all subscriptions with health status.",
            inputSchema={
                "type": "object",
                "properties": {
                    "subscription_id": {
                        "type": "string",
                        "description": "Send heartbeat for this subscription (omit to list all)",
                    },
                },
            },
        ),
        # --- Extended tools (P3) ---
        Tool(
            name="memory_research",
            description="Deep analysis of entity relationships, anomalies, clusters, and timeline patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query to find entities"},
                    "entity_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific entity IDs",
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["relationships", "anomalies", "clusters", "timeline", "summary"],
                        "default": "relationships",
                    },
                    "max_depth": {"type": "integer", "default": 3},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        ),
        Tool(
            name="memory_id_management",
            description="Unified ID management: UUIDv7 generation, ID resolution, conflict handling, batch registration.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": [
                            "generate",
                            "resolve",
                            "reverse_lookup",
                            "resolve_conflict",
                            "batch_register",
                            "stats",
                        ],
                    },
                    "source": {"type": "string", "description": "Source server name"},
                    "memory_type": {"type": "string"},
                    "count": {"type": "integer", "default": 1},
                    "unified_id": {"type": "string"},
                    "original_id": {"type": "string"},
                    "id_a": {"type": "string"},
                    "id_b": {"type": "string"},
                    "strategy": {"type": "string", "default": "keep_newer"},
                    "items": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["operation"],
            },
        ),
        Tool(
            name="memory_surprise",
            description="Calculate unexpectedness/novelty score for new content (0=known, 1=surprising).",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to evaluate"},
                    "context": {"type": "string", "description": "Optional domain/topic context"},
                    "detail": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include detailed comparison data",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="memory_warmup",
            description="Preload frequently used data into LRU cache to reduce cold-start latency.",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {
                        "type": "string",
                        "enum": ["frequent", "recent", "important", "pattern"],
                        "default": "frequent",
                    },
                    "limit": {"type": "integer", "default": 50},
                    "query": {"type": "string", "description": "Query for 'pattern' strategy"},
                },
            },
        ),
        # --- P4: Service wrapper tools ---
        Tool(
            name="memory_audit_log",
            description="Query audit log entries with optional filters (action, resource_type, resource_id).",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "Filter by action type (create, read, update, delete, search, link, propagate, merge, rollback, export, config_change, health_check)",
                    },
                    "resource_type": {"type": "string", "description": "Filter by resource type"},
                    "resource_id": {"type": "string", "description": "Filter by resource ID"},
                    "limit": {"type": "integer", "default": 50},
                    "offset": {"type": "integer", "default": 0},
                },
            },
        ),
        Tool(
            name="memory_audit_stats",
            description="Get audit log statistics: entry counts by action, error rate, buffer size.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="memory_circuit_status",
            description="Get circuit breaker status. Omit name to get all breakers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Named circuit breaker (omit for all)",
                    },
                },
            },
        ),
        Tool(
            name="memory_circuit_reset",
            description="Reset a circuit breaker to CLOSED state.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Circuit breaker name to reset"},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="memory_metrics",
            description="Get aggregated metrics from all subsystems (counters, gauges, durations). Pass reset=true to clear.",
            inputSchema={
                "type": "object",
                "properties": {
                    "reset": {
                        "type": "boolean",
                        "default": False,
                        "description": "Reset all metrics after reading",
                    },
                },
            },
        ),
        Tool(
            name="memory_ttl_set",
            description="Register or update TTL for an entity. Policy: never, short (1h), medium (24h), long (7d), extended (30d), custom.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "policy": {
                        "type": "string",
                        "default": "long",
                        "description": "TTL policy preset",
                    },
                    "ttl_seconds": {
                        "type": "integer",
                        "description": "Custom TTL in seconds (for policy=custom)",
                    },
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="memory_ttl_check",
            description="Check TTL status for an entity, or get overall TTL stats. Set include_expired=true to list expired entries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "string",
                        "description": "Check specific entity (omit for stats)",
                    },
                    "include_expired": {"type": "boolean", "default": False},
                },
            },
        ),
        Tool(
            name="memory_ttl_cleanup",
            description="Remove expired TTL entries. Returns list of removed entity IDs.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="memory_version_history",
            description="Get version history for an entity with optional content inclusion.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 50},
                    "include_content": {"type": "boolean", "default": True},
                },
                "required": ["entity_id"],
            },
        ),
        Tool(
            name="memory_version_rollback",
            description="Rollback entity to a specific version number.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "target_version": {
                        "type": "integer",
                        "description": "Version number to rollback to",
                    },
                    "rollback_by": {"type": "string", "default": ""},
                },
                "required": ["entity_id", "target_version"],
            },
        ),
        Tool(
            name="memory_version_compare",
            description="Compare two versions of an entity and return the diff.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity_id": {"type": "string"},
                    "version_a": {"type": "integer"},
                    "version_b": {"type": "integer"},
                },
                "required": ["entity_id", "version_a", "version_b"],
            },
        ),
        Tool(
            name="memory_forget",
            description="Run ForgetGate evaluation on memory candidates. Default is dry-run (no actual deletion). Strategies: confidence_decay, access_based, surprise_based, composite.",
            inputSchema={
                "type": "object",
                "properties": {
                    "strategy": {
                        "type": "string",
                        "default": "composite",
                        "description": "Forget strategy",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": True,
                        "description": "If true, evaluate without applying",
                    },
                    "candidates": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Candidate entries to evaluate (omit for empty evaluation)",
                    },
                    "min_confidence": {"type": "number", "default": 0.1},
                    "decay_rate": {"type": "number", "default": 0.05},
                },
            },
        ),
        Tool(
            name="memory_graph_analyze",
            description="Run graph algorithms on the memory knowledge graph. Algorithms: stats, pagerank, centrality, communities, shortest_path, connected_components.",
            inputSchema={
                "type": "object",
                "properties": {
                    "algorithm": {
                        "type": "string",
                        "enum": [
                            "stats",
                            "pagerank",
                            "centrality",
                            "communities",
                            "shortest_path",
                            "connected_components",
                        ],
                        "default": "stats",
                    },
                    "source": {"type": "string", "description": "Source node (for shortest_path)"},
                    "target": {"type": "string", "description": "Target node (for shortest_path)"},
                    "damping": {
                        "type": "number",
                        "default": 0.85,
                        "description": "Damping factor (for pagerank)",
                    },
                    "max_iterations": {"type": "integer", "default": 100},
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
        # --- Realtime tools (P3) ---
        elif name == "memory_subscribe":
            result = await orch.memory_subscribe(
                client_id=arguments["client_id"],
                pattern=arguments["pattern"],
                metadata=arguments.get("metadata"),
            )
        elif name == "memory_unsubscribe":
            result = await orch.memory_unsubscribe(
                subscription_id=arguments["subscription_id"],
            )
        elif name == "memory_publish":
            result = await orch.memory_publish(
                event_type=arguments["event_type"],
                data=arguments["data"],
                source=arguments.get("source"),
            )
        elif name == "memory_get_events":
            result = await orch.memory_get_events(
                subscription_id=arguments["subscription_id"],
                max_events=arguments.get("max_events", 10),
            )
        elif name == "memory_replay":
            result = await orch.memory_replay(
                event_type=arguments.get("event_type"),
                start=arguments.get("start"),
                limit=arguments.get("limit", 100),
            )
        elif name == "memory_event_history":
            result = await orch.memory_event_history(
                event_type=arguments.get("event_type"),
                start=arguments.get("start"),
                end=arguments.get("end"),
                limit=arguments.get("limit", 50),
            )
        elif name == "memory_event_stats":
            result = await orch.memory_event_stats()
        elif name == "memory_subscription_health":
            result = await orch.memory_subscription_health(
                subscription_id=arguments.get("subscription_id"),
            )
        # --- Extended tools (P3) ---
        elif name == "memory_research":
            result = await orch.memory_research(
                query=arguments.get("query"),
                entity_ids=arguments.get("entity_ids"),
                analysis_type=arguments.get("analysis_type", "relationships"),
                max_depth=arguments.get("max_depth", 3),
                limit=arguments.get("limit", 20),
            )
        elif name == "memory_id_management":
            result = await orch.memory_id_management(
                operation=arguments["operation"],
                **{k: v for k, v in arguments.items() if k != "operation"},
            )
        elif name == "memory_surprise":
            result = await orch.memory_surprise(
                content=arguments["content"],
                context=arguments.get("context"),
                detail=arguments.get("detail", False),
            )
        elif name == "memory_warmup":
            result = await orch.memory_warmup(
                strategy=arguments.get("strategy", "frequent"),
                limit=arguments.get("limit", 50),
                query=arguments.get("query"),
            )
        # --- P4: Service wrapper tools ---
        elif name == "memory_audit_log":
            result = await orch.memory_audit_log(
                action=arguments.get("action"),
                resource_type=arguments.get("resource_type"),
                resource_id=arguments.get("resource_id"),
                limit=arguments.get("limit", 50),
                offset=arguments.get("offset", 0),
            )
        elif name == "memory_audit_stats":
            result = await orch.memory_audit_stats()
        elif name == "memory_circuit_status":
            result = await orch.memory_circuit_status(
                name=arguments.get("name"),
            )
        elif name == "memory_circuit_reset":
            result = await orch.memory_circuit_reset(
                name=arguments["name"],
            )
        elif name == "memory_metrics":
            result = await orch.memory_metrics(
                reset=arguments.get("reset", False),
            )
        elif name == "memory_ttl_set":
            result = await orch.memory_ttl_set(
                entity_id=arguments["entity_id"],
                policy=arguments.get("policy", "long"),
                ttl_seconds=arguments.get("ttl_seconds"),
            )
        elif name == "memory_ttl_check":
            result = await orch.memory_ttl_check(
                entity_id=arguments.get("entity_id"),
                include_expired=arguments.get("include_expired", False),
            )
        elif name == "memory_ttl_cleanup":
            result = await orch.memory_ttl_cleanup()
        elif name == "memory_version_history":
            result = await orch.memory_version_history(
                entity_id=arguments["entity_id"],
                limit=arguments.get("limit", 50),
                include_content=arguments.get("include_content", True),
            )
        elif name == "memory_version_rollback":
            result = await orch.memory_version_rollback(
                entity_id=arguments["entity_id"],
                target_version=arguments["target_version"],
                rollback_by=arguments.get("rollback_by", ""),
            )
        elif name == "memory_version_compare":
            result = await orch.memory_version_compare(
                entity_id=arguments["entity_id"],
                version_a=arguments["version_a"],
                version_b=arguments["version_b"],
            )
        elif name == "memory_forget":
            result = await orch.memory_forget(
                strategy=arguments.get("strategy", "composite"),
                dry_run=arguments.get("dry_run", True),
                candidates=arguments.get("candidates"),
                min_confidence=arguments.get("min_confidence", 0.1),
                decay_rate=arguments.get("decay_rate", 0.05),
            )
        elif name == "memory_graph_analyze":
            result = await orch.memory_graph_analyze(
                algorithm=arguments.get("algorithm", "stats"),
                source=arguments.get("source"),
                target=arguments.get("target"),
                damping=arguments.get("damping", 0.85),
                max_iterations=arguments.get("max_iterations", 100),
            )
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

        return [
            TextContent(
                type="text", text=json.dumps(result, ensure_ascii=False, indent=2, default=str)
            )
        ]

    except OrchestratorError as e:
        return [
            TextContent(type="text", text=json.dumps({"error": str(e), "type": type(e).__name__}))
        ]
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
