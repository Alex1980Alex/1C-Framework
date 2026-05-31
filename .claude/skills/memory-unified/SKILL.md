---
name: memory-unified
description: "Unified Memory System — кросс-системная память (AI Memory, Vector Memory, Skill Learning). ИСПОЛЬЗУЙ когда работаешь с unified ID, link registry, federated search, pattern learning, confidence decay. Триггеры: 'memory', 'unified id', 'link registry', 'federated search', 'pattern learning', 'confidence decay', 'memory-ai', 'vector-memory', 'skill-learning'. НЕ для MEMORY.md (→ auto-memory)."
---

# Unified Memory System

## When to use
- "memory", "unified id", "link registry", "federated search"
- "pattern learning", "confidence decay", "evidence"
- "memory-ai", "vector-memory", "skill-learning"
- Working with cross-system memory references

## Architecture

```
                    Memory Orchestrator
                   /        |          \
          UnifiedID    LinkRegistry   FederatedSearch
              |            |              |
    ┌─────────┼────────────┼──────────────┼──────────┐
    │         │            │              │          │
  memory-ai  vector-memory  skill-learning  pdf-docs
  (episodic)  (semantic)    (learning)     (docs)
```

### 4 Subsystems

| System | Type | Backend | Collection/DB |
|--------|------|---------|---------------|
| Memory AI | Episodic | SQLite | `data/memory_ai.db` |
| Vector Memory | Semantic | Qdrant | `learned_patterns` (1024d) |
| Skill Learning | Learning | JSONL files | `data/skill_learning/` |
| PDF Docs | Documentation | Qdrant | existing framework collections |

### UnifiedID Format

```
{memory_type}:{source}:{identifier}
```

Examples:
- `episodic:memory-ai:550e8400-e29b-41d4-a716-446655440000`
- `semantic:vector-memory:660f9500-f30c-52e5-b827-557766551111`
- `docs:pdf-docs:a1b2c3d4e5f67890`
- `learning:skill-learning:770g0600-g41d-63f6-c938-668877662222`

### Link Types

| Type | Description |
|------|-------------|
| `based_on` | Pattern based on documentation |
| `supports` | Entity supports another |
| `contradicts` | Entity contradicts another |
| `extends` | Pattern extends another |
| `derives_from` | Fact derived from another |
| `session_context` | Message in session context |

### Confidence System (Vector Memory)

**Обновлено 2026-05-31 (§22 P0, commit `c8409e30b`):** confidence теперь **производный** от Beta(7,3) posterior над time-decayed счётчиками успехов/фейлов (раньше — наивный `+0.02/−0.01`). Чистые функции: [`src/memory/vector_memory/confidence.py`](../../../src/memory/vector_memory/confidence.py).

- Range: 0.0-1.0; **prior Beta(7,3)** → стартовое значение **0.70**.
- Формула (derived, денорм-кэш `confidence` для Qdrant-фильтра): `confidence = (7 + succ) / (10 + succ + fail)`.
- Хранятся sufficient stats: `succ`, `fail` (float-счётчики), `last_decay_at`. Prior — read-time константа, не хранится. Без clamp (ratio ∈ (0,1)).
- Application (`apply_pattern`): сначала decay счётчиков `succ,fail *= exp(−decay_rate·Δdays/30)` (floor <1e-6→0), затем `succ+=1` (success) / `fail+=1` (fail). 5 чистых успехов: 0.70 → **0.80**; +1 фейл → 0.75.
- Decay (`decay_confidence`): затухают **счётчики**, confidence дрейфит к **prior 0.70** (НЕ к 0). Простой → де-промоушен, не обнуление.
- **Lazy decay-on-read (§22 P2, `b05d1081d`):** `confidence.payload_effective_confidence` пересчитывает confidence ПРИ ЧТЕНИИ из stored counts (без записи). `search_patterns` (drop server-prefilter + client-side effective filter/rank), `get_pattern` (отдаёт `effective_confidence`), `WikiPromoter` (gate на effective) — stale-паттерны ранжируются/фильтруются ниже автоматически.
- Legacy-миграция (lazy, on-read): `succ=conf·n, fail=(1−conf)·n` (n=application_count); отсутствие полей → prior 0.70.
- Threshold: `<0.3` auto-delete сохранён (но count-decay floors at 0.70 → срабатывает редко; staleness-архивация — §22 P3, ещё не реализована).
- Полная стратегия (raise/decay/forgetting/enrichment) + research: roadmap §22 ([260523](../../../docs/roadmap/260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md)).

## Key Files

- Orchestrator: `src/memory/orchestrator/` (unified_id, link_registry, unified_search)
- AI Memory: `src/memory/ai_memory/server.py` (5 MCP tools)
- Vector Memory: `src/memory/vector_memory/server.py` (7 MCP tools)
- Skill Learning: `src/memory/skill_learning/server.py` (7 MCP tools)
- Tests: `tests/integration/test_memory_unified.py` (26 tests)
- MCP config: `.mcp.json` (4 servers registered)

## MCP Tools

### memory-ai (5 tools)
- `get_important_messages` — filter by importance/category
- `save_important_message` — save with importance score
- `search_messages` — full-text search
- `delete_message` — remove by ID
- `get_categories` — list categories with stats

### vector-memory (7 tools)
- `save_pattern` — save with confidence
- `search_patterns` — semantic search + confidence filter
- `apply_pattern` — track usage, update confidence
- `get_pattern` / `delete_pattern` — CRUD
- `decay_confidence` — apply temporal decay
- `health_check` — Qdrant status

### skill-learning (7 tools)
- `capture_pattern` — capture from tool use
- `batch_capture` — multiple patterns
- `get_pending_patterns` — awaiting confirmation
- `confirm_pattern` / `reject_pattern` — review
- `get_learning_stats` — statistics
- `health_check` — storage status

### memory-orchestrator (33 tools)

**Core (8, P0):**
- `unified_search` — federated search across all subsystems
- `route_and_save` — auto-classify and route to targets
- `get_full_context` — entity + BFS graph traversal
- `create_link` — cross-reference between entities
- `get_related` — find related via BFS
- `propagate_update` — confidence propagation through graph
- `get_system_stats` — aggregate statistics (includes P4 services)
- `health_check` — subsystem health (includes P4 services)

**Realtime (8, P3):**
- `memory_subscribe` / `memory_unsubscribe` — event subscriptions
- `memory_publish` — publish custom event
- `memory_get_events` — poll pending events
- `memory_replay` / `memory_event_history` — event replay/history
- `memory_event_stats` — bus/store/subscription stats
- `memory_subscription_health` — heartbeat/list

**Extended (4, P3):**
- `memory_research` — deep analysis (relationships, anomalies, clusters)
- `memory_id_management` — UUIDv7, resolution, conflicts
- `memory_surprise` — novelty scoring
- `memory_warmup` — cache preloading

**Services (13, P4):**
- `memory_audit_log` — query audit log with filters
- `memory_audit_stats` — audit statistics
- `memory_circuit_status` — circuit breaker status
- `memory_circuit_reset` — reset circuit breaker
- `memory_metrics` — aggregated metrics (counters, gauges, durations)
- `memory_ttl_set` — register/update TTL for entity
- `memory_ttl_check` — check TTL status / get expired
- `memory_ttl_cleanup` — remove expired entries
- `memory_version_history` — entity version history
- `memory_version_rollback` — rollback to specific version
- `memory_version_compare` — diff between two versions
- `memory_forget` — ForgetGate evaluation (dry-run by default)
- `memory_graph_analyze` — PageRank, centrality, communities, shortest path

### Hooks (P5)

- `session-memory-save.py` (Stop) — auto-saves session context to SQLite + wiki log on session end
  - Extracts: git diff, activated skills, commits, completed tasks
  - Writes to `data/memory_ai.db` (category: `session_summary`)
  - Also appends brief summary to `docs/wiki/log.md` (Hermes Phase 2)
  - Dedup by session_id or date, auto-importance (0.5-0.95), auto-tags


## Незадокументированные memory_subsystem

- `LinkType` (src\memory\orchestrator\link_registry.py)
- `EntityLink` (src\memory\orchestrator\link_registry.py)
- `RelatedEntity` (src\memory\orchestrator\link_registry.py)
- `ContentType` (src\memory\orchestrator\memcube.py)
- `AiMemorySearchAdapter` (src\memory\orchestrator\memory_orchestrator.py)
- `VectorMemorySearchAdapter` (src\memory\orchestrator\memory_orchestrator.py)
- `SkillLearningSearchAdapter` (src\memory\orchestrator\memory_orchestrator.py)
- `MemoryOrchestrator` (src\memory\orchestrator\memory_orchestrator.py)
- `RoutingDecision` (src\memory\orchestrator\memory_router.py)
- `RoutingStats` (src\memory\orchestrator\memory_router.py)
- `ClassificationResult` (src\memory\orchestrator\memory_router.py)
- `ContentClassifier` (src\memory\orchestrator\memory_router.py)
- `MemoryRouter` (src\memory\orchestrator\memory_router.py)
- `PropagationEvent` (src\memory\orchestrator\propagation_engine.py)
- `PropagationResult` (src\memory\orchestrator\propagation_engine.py)
- `PropagationEngine` (src\memory\orchestrator\propagation_engine.py)
- `MemoryType` (src\memory\orchestrator\unified_id.py)
- `SourceServer` (src\memory\orchestrator\unified_id.py)
- `IDRegistry` (src\memory\orchestrator\unified_id.py)
- `SearchOptions` (src\memory\orchestrator\unified_search.py)
- `LinkedEntity` (src\memory\orchestrator\unified_search.py)
- `SearchResultItem` (src\memory\orchestrator\unified_search.py)
- `UnifiedSearchResult` (src\memory\orchestrator\unified_search.py)
- `BaseSearchAdapter` (src\memory\orchestrator\unified_search.py)
- `ScoreNormalizer` (src\memory\orchestrator\unified_search.py)
- `RRFMerger` (src\memory\orchestrator\unified_search.py)
- `Deduplicator` (src\memory\orchestrator\unified_search.py)
- `Reranker` (src\memory\orchestrator\unified_search.py)
- `LinkEnricher` (src\memory\orchestrator\unified_search.py)
- `UnifiedSearchEngine` (src\memory\orchestrator\unified_search.py)
- `PatternType` (src\memory\vector_memory\models.py)
- `ConfidenceLevel` (src\memory\vector_memory\models.py)
- `EvidenceSource` (src\memory\vector_memory\models.py)
- `LearnedPattern` (src\memory\vector_memory\models.py)
- `PatternSearchResult` (src\memory\vector_memory\models.py)
- `LearningStats` (src\memory\vector_memory\models.py)
- `WikiDecayService` (src\memory\librarian\wiki_decay.py)
- `CacheEntry` (src\memory\infrastructure\cache.py)
- `LRUCache` (src\memory\infrastructure\cache.py)
- `CircuitState` (src\memory\infrastructure\circuit_breaker.py)
- `CircuitStats` (src\memory\infrastructure\circuit_breaker.py)
- `CircuitBreaker` (src\memory\infrastructure\circuit_breaker.py)
- `CircuitBreakerRegistry` (src\memory\infrastructure\circuit_breaker.py)
- `ConflictStrategy` (src\memory\infrastructure\conflict_resolver.py)
- `ConflictRecord` (src\memory\infrastructure\conflict_resolver.py)
- `ConflictResult` (src\memory\infrastructure\conflict_resolver.py)
- `ConflictResolver` (src\memory\infrastructure\conflict_resolver.py)
- `EventBusStats` (src\memory\infrastructure\event_bus.py)
- `EventStore` (src\memory\infrastructure\event_store.py)
- `MetricsCollector` (src\memory\infrastructure\metrics.py)
- `MetricsTimer` (src\memory\infrastructure\metrics.py)
- `ManagedSubscription` (src\memory\infrastructure\subscription_manager.py)
- `SubscriptionManager` (src\memory\infrastructure\subscription_manager.py)
