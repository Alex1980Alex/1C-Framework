---
confidence: 0.8034665243897429
content_hash: 0bddab5f9014e539
content_type: wiki
created_at: '2026-07-15T00:07:42.516981'
importance: 0.5
memory_type: wiki
source: obsidian-vault
status: draft
tags:
- hooks
- memory
- project
- qdrant
- skills
- system
- unified
title: Unified Memory System Migration
unified_id: wiki:obsidian-vault:d5db7fab-fb94-4dc7-aac9-a001563708a1
updated_at: '2026-07-15T00:07:42.516983'
version: 1
---

## Content

Unified Memory System Migration | Memory system P0-P5.1 COMPLETE (2026-04-04). Memory-First Hook auto-injects context. 52 MCP tools, 152 tests pass, SQLite+Qdrant+JSONL stack. Bugs fixed 2026-04-04: Qdrant 768→1024d, memory-first-hook created, get_full_context partial, versioning str coercion. | ## Unified Memory System — Migration COMPLETE (2026-04-04)

All 6 phases done: P0 (orchestrator core), P0.5 (memory-first hook), P1 (infrastructure), P2 (search+services), P3 (realtime+adapters), P4 (MCP tools extension).

**Why:** Migrated from heavy stack (TimescaleDB+Neo4j+Redis) to lightweight (SQLite+Qdrant+JSONL) while preserving all functionality. 198 files → 31 files, 72+ tools → 31+ tools.

**How to apply:**
- `src/memory/` — all memory code lives here (orchestrator/, ai_memory/, vector_memory/, skill_learning/, infrastructure/)
- **Memory-First Hook** (`memory-first-hook.py`): UserPromptSubmit hook auto-searches local `.md` memory files, injects top-3 matches as systemMessage. Russian stemming (29 suffixes), weighted scoring (name×3, desc×2, body×1), cooldown 30s, threshold 0.3
- MCP server `memory-orchestrator` provides 31+ tools (unified_search, route_and_save, get_full_context, create_link, propagate_update, health_check, audit, circuit, metrics, TTL, versioning, forgetgate, graph, events, subscriptions, research, surprise, warmup, id_management)
- Key patterns: MemCube abstraction (MemOS), Auto-classify middleware (Memori), Hybrid RRF search (OpenCrabs), Propagation engine (BFS on SQLite adjacency), EventBus (asyncio.Queue)
- Tests: 152 pass (26 P0-P1 + 70 P2 + 28 P3 + 28 P5.1)
- MCP tools: 52 total (33 orchestrator + 5 ai-memory + 7 vector-memory + 7 skill-learning)
- **P5.1 Session Context Extractor** (2026-04-04): Stop hook `session-memory-save.py` auto-saves
