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

- Range: 0.0-1.0
- Application: success +0.02, failure -0.01
- Decay: `confidence * exp(-0.05 * days/30)`
- Threshold: patterns below 0.3 auto-deleted

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
