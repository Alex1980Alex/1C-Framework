# Roadmap: GraphRAG для BSL — максимальное покрытие сложных запросов

> **Created:** 2026-05-02
> **Owner:** Alex Terletskii
> **Goal:** Поднять accuracy AI-агентов на multi-hop / impact / architectural запросах с ~35% до ~80%

---

## §0 Status Dashboard

| Phase | Статус | Артефакт | ETA |
|---|---|---|---|
| **Phase 0** Reindex BSL → bsl_code_v4_late | DONE 2026-05-02 | 54 752 точек | — |
| **Phase 1** Регенерация graph_embeddings | pending | ~30 000 узлов | 3-4 ч |
| **Phase 3** Neo4j docker + bulk import | pending | 30k nodes / 50k edges | 30-60 мин |
| **Phase 2** Leiden communities + LLM summaries | pending | ~150 community summaries | 30-45 мин |
| **Phase 5** Hybrid retrieval router | pending | bsl_hybrid_search upgrade | 2-3 ч |
| **Phase 6** Benchmark complex queries | pending | tests/benchmarks/ 5/5 | 1-2 ч |
| **Phase 7** (опц) FA2 install | pending | Speedup 2-3x | 1-2 ч |
| **Phase 8** (опц) Understand-Anything dashboard | pending | Interactive KG viewer | 4-6 ч |

**Mandatory path (max coverage):** Phase 1 → Phase 3 → Phase 2 → Phase 5 → Phase 6 (~6-8 часов)

**Метрика успеха:** complex queries accuracy 35% → 80%, token cost −33%, latency −30%.

---

## §1 Executive Summary

### 1.1 Проблема

После Phase 8 Qwen3 retrieval семантический поиск работает на recall@10 = 0.567 — достаточно для простых lookup-ов, но НЕ для:

| Тип запроса | Текущий accuracy | Пример |
|---|:---:|---|
| Multi-hop | ~40% | Кто вызывает гкс_АсинхронныеСервисы.ЗапуститьЗадание через 2 уровня |
| Impact analysis | ~25% | Что сломается если переименую функцию X |
| Architectural overview | ~30% | Опиши устройство подсистемы УправлениеТранспортом |
| Dead code detection | ~20% | Какие общие модули нигде не вызываются |
| Cross-cutting | ~30% | Где используется ФО Y и регистр Z вместе |

Семантика теряет связи — без явных рёбер графа агент не может проследить путь между модулями.

### 1.2 GraphRAG stack

- **Layer 1 (DONE Phase 0):** bsl_code_v4_late — текстовые chunks BSL
- **Layer 2 (Phase 1):** graph_embeddings — эмбеддинги УЗЛОВ графа
- **Layer 3 (Phase 3):** Neo4j — native Cypher traversal
- **Layer 4 (Phase 2):** Communities — Leiden + LLM summaries
- **Layer 5 (Phase 5):** Hybrid router — маршрутизация по типу запроса

### 1.3 Ожидаемый прирост

| Метрика | Сейчас | После Phase 1+3+2+5 | Δ |
|---|:---:|:---:|---:|
| Complex queries accuracy (avg) | ~35% | ~80% | **+128%** |
| Multi-hop reasoning | 40% | 80% | +100% |
| Impact analysis | 25% | 80% | +220% |
| Architectural overview | 30% | 85% | +183% |
| Dead code detection | 20% | 75% | +275% |
| Cross-cutting | 30% | 70% | +133% |
| Token cost / complex query | baseline | **−33%** | (Youtu-GraphRAG ICLR-26) |
| Retrieval latency | baseline | **−30-40%** | 1 traversal vs 5-10 vector |
| Hallucinations | baseline | **−30-50%** | structured context |

### 1.4 Стоимость

| Ресурс | Объём |
|---|---|
| Время разработки | 6-8 часов одного дня |
| Compute | RTX 3090 + Docker (есть) |
| Disk | +5 GB Neo4j, +2 GB graph_embeddings |
| LLM cost | ~$0.05 (Z.AI GLM-5) или ~$2 (Claude Haiku) |
| Зависимости | neo4j, neo4j-graphrag, leidenalg, igraph |

---

## §2 Current State

### 2.1 Что уже есть

| Компонент | Статус | Путь |
|---|---|---|
| Call graph store (SQLite) | работает | src/bsl/call_graph/store.py (11 KB) |
| Metadata extractor | работает | src/bsl/knowledge_graph/metadata_extractor.py |
| Qdrant graph_embeddings | устаревшая | 6 694 точек (без EDT) |
| Qdrant bsl_code_v4_late | актуальная | 54 752 точек |
| MCP bsl_call_graph | работает | find_callers, search_symbols |
| MCP bsl_dead_code | работает | flat detection (без traversal) |
| Auto-documenter graphs | работает | Mermaid по требованию |
| TEI Docker | running 2+ days | localhost:8080 |
| Qdrant Docker | running 4+ days | localhost:6333 |
| LLM rotation MCP | зарегистрирован | Z.AI GLM-5 default |

### 2.2 Gaps

1. graph_embeddings устарела — без EDT-проекта
2. Нет graph database — multi-hop через Qdrant медленно
3. Нет community detection — overview не работают
4. Нет hybrid router — bsl_hybrid_search без graph

---

## §3 Phase 1 — Регенерация graph_embeddings

### 3.1 Объём работы

**Узлы (~30k):** Configuration objects (~500-1000), Modules (~2 066), Symbols (~30 000)

**Рёбра (~50-80k):** CONTAINS, DECLARES, CALLS, REFERENCES, WRITES, READS, USES_FO

### 3.2 Артефакты

- src/bsl/call_graph/store.py (есть) — расширить bulk-import API
- scripts/build_graph_embeddings.py (новый) — main script
- scripts/git_post_commit_reindex.py — добавить graph reindex

### 3.3 Time Budget

| Этап | Backend | Время |
|---|---|---|
| Discovery (find_bsl_projects) | filesystem | ~1 sec |
| Parse 2066+ файлов | CPU (parallel 8 workers) | 30-45 мин |
| SQLite bulk insert | local I/O | 2-5 мин |
| Embedding 30k узлов | RTX 3090 (qwen3-st) | 30-45 мин |
| Qdrant upsert | localhost:6333 | 5 мин |
| **Total** | | **~1.5-2 ч** |

### 3.4 Acceptance Criteria

- find_bsl_projects(REPO_ROOT) ≥ 3 проекта
- data/call_graph.db ≥ 30 000 узлов, ≥ 50 000 рёбер
- Qdrant graph_embeddings ≥ 30 000 точек, status green
- FK integrity по рёбрам CALLS
- Smoke: bsl_object_info("гкс_НаправлениеНаРазгрузку") возвращает узел + связи
- Smoke: bsl_call_graph(symbol="ВыполнитьПроверкуОтклоненияБрутто") ≥ 1 caller

### 3.5 Rollback

curl POST .../snapshots → snapshot перед запуском.

---

## §4 Phase 3 — Neo4j Graph DB

### 4.1 Зачем Neo4j (а не Memgraph/FalkorDB)

| Критерий | Neo4j | Memgraph | FalkorDB |
|---|---|---|---|
| Production-grade | 15+ лет | 6 лет | 3 года |
| Official GraphRAG package | neo4j-graphrag-python | нет | нет |
| Cypher | полный | subset | subset |
| APOC + GDS plugins | rich | limited | minimal |
| Документация | excellent | good | OK |

**Решение:** Neo4j Community Edition (бесплатна).

### 4.2 Schema (Cypher)

CREATE CONSTRAINT FOR (n:Module|Procedure|Function|Catalog|Document|Register|Subsystem|FunctionalOption) REQUIRE n.id IS UNIQUE.

Индексы по name/path для быстрых lookup-ов.

Edge types: DECLARES, CALLS, WRITES, READS, REFERENCES, USES_FO, CONTAINS.

### 4.3 Time Budget

| Этап | Время |
|---|---|
| Pull neo4j:5-community | 3-5 мин (~600 MB) |
| Container start | 30 сек |
| Schema + indices | < 1 сек |
| Bulk 30k nodes (UNWIND batch=1000) | 5-10 мин |
| Bulk 50-80k edges (UNWIND batch=5000) | 10-20 мин |
| **Total** | **~30-45 мин** |

### 4.4 Acceptance Criteria

- Container bsl-graph-neo4j healthy
- MATCH (n) RETURN count(n) ≥ 30 000
- MATCH ()-[r]->() RETURN count(r) ≥ 50 000
- APOC + GDS установлены
- Smoke Cypher: multi-hop CALLS path ≥ 5 paths

### 4.5 Rollback

docker compose down -v + удаление volumes.

---

## §5 Phase 2 — Hierarchical Communities + LLM Summaries

### 5.1 Алгоритм Leiden (а не Louvain)

Гарантирует connected communities, использован в Microsoft GraphRAG.

### 5.2 Hint для 1С

В метаданных есть Subsystems/Name/Content — естественные communities. Strategy:
1. Subsystem-based partition (если автор честно расставил)
2. Leiden как валидация
3. Mix: subsystem + leiden-fallback

### 5.3 LLM Summaries

Через mcp__llm-rotation__llm_complete(model="zai/glm-5", max_tokens=500) для каждой community. См. Appendix B.

### 5.4 Time + Cost Budget

| Этап | Backend | Время | Cost |
|---|---|---|---|
| Leiden 30k nodes | CPU (igraph + leidenalg) | 5-10 мин | $0 |
| LLM summaries × 150 (5 parallel) | Z.AI GLM-5 | 5-7 мин | **~$0.05** |
| Embedding summaries | RTX 3090 | 1 мин | $0 |
| Qdrant + Neo4j upsert | local | 2 мин | $0 |
| **Total** | | **~15-20 мин** | **~$0.05** |

### 5.5 Acceptance Criteria

- ≥ 50 communities (≥ 5 nodes each)
- ≥ 80% узлов в нетривиальных communities
- LLM-summary 200-600 токенов на каждую
- MATCH (c:Community) RETURN count(c) ≥ 50

---

## §6 Phase 5 — Hybrid Retrieval Router

### 6.1 Маршрутизация

| Тип | Pipeline | Слои |
|---|---|---|
| semantic | Qdrant bsl_code_v4_late top-K | Layer 1 |
| multi_hop_callers | Qdrant entry → Cypher CALLS*1..3 | Layer 2+3 |
| impact_analysis | Cypher reverse <-[CALLS,REFERENCES]- | Layer 3 |
| architectural | Qdrant Community → expand | Layer 4 |
| dead_code | Cypher WHERE NOT incoming CALLS | Layer 3 |
| mixed (default) | All + rerank | All |

### 6.2 Расширение MCP

В src/bsl/semantic_search/mcp.py добавить параметр strategy: vector | graph | community | hybrid.

### 6.3 Time Budget

| Этап | Время |
|---|---|
| Классификатор | 30 мин |
| Маршрутизатор | 1 ч |
| MCP extension | 30 мин |
| Unit tests | 1 ч |
| **Total** | **~3 ч** |

### 6.4 Acceptance Criteria

- classify_query("кто вызывает X") → multi_hop_callers
- bsl_hybrid_search(strategy="hybrid") использует 2+ слоя
- Latency hybrid query < 2 сек
- tests/integration/test_hybrid_retrieval.py: 5/5 PASS

---

## §7 Phase 6 — Benchmark Complex Queries

### 7.1 Тестовый набор

5 категорий × 5 запросов = 25 golden queries в tests/benchmarks/bsl_complex_queries.py:
- MH (multi_hop_callers)
- IA (impact_analysis)
- AR (architectural)
- DC (dead_code)
- CC (cross_cutting)

### 7.2 Baseline + Target

| Тип | Baseline (Layer 1) | Target (full stack) |
|---|:---:|:---:|
| MH | 1/5 (20%) | 5/5 (100%) |
| IA | 1/5 (20%) | 4-5/5 (80-100%) |
| AR | 1/5 (20%) | 4-5/5 (80-100%) |
| DC | 0/5 (0%) | 4/5 (80%) |
| CC | 2/5 (40%) | 5/5 (100%) |
| **Avg** | **~20%** | **~88%** |

### 7.3 Acceptance Criteria

- 25 golden queries в tests/benchmarks/bsl_complex_queries.py
- Baseline (без graph) → ~20% PASS rate
- After-Phase-5 → ≥ 80% PASS rate

---

## §8 Phase 7 (опц) — FA2 Install

Wrapper готов: scripts/reindex_bsl_fast.ps1. Auto-detect FA2 → batch=100 при наличии.

Источники wheels:
- github.com/bdashore3/flash-attention/releases — Windows
- github.com/Dao-AILab/flash-attention — Linux only

Source build: pip install flash-attn --no-build-isolation (30-60 мин с MSVC + CUDA 12.x).

### Acceptance

- pip show flash-attn ≥ 2.5
- Полный реиндекс 2066: < 90 мин (vs 178 мин baseline)

---

## §9 Phase 8 (опц) — Understand-Anything Plugin

git clone github.com/Lum1104/Understand-Anything tools/understand-anything. Адаптация parser-а под 1c-syntax/tree-sitter-bsl. Время: 4-6 часов. Opt-in для будущего.

---

## §10 Hybrid Retrieval Pipeline (после всех phases)

USER QUERY: Что сломается если переименую гкс_АсинхронныеСервисы.ЗапуститьЗадание?
- Phase 5 Classifier: type=impact_analysis
- Phase 1+2: Find target node (Qdrant graph_embeddings → top-1)
- Phase 3: Cypher reverse traversal MATCH (caller)-[CALLS*1..3]->(target) → ~30 callers
- Phase 4: Add architectural context (Qdrant Community-search → 2 summaries)
- Layer 1: Source code chunks (bsl_code_v4_late → top-5 snippets)
- Merge + Rerank
- FINAL ANSWER (≤ 2 сек, ~3000 tokens context)

---

## §11 Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Phase 1 parsing slow | +1-2 ч | Multiprocessing 4-8 workers |
| Neo4j memory pressure | 2-4 GB heap | NEO4J_dbms_memory_heap_max=2G |
| Leiden degenerate clusters | Useless | Fallback: subsystem partition |
| LLM hallucinations | Misleading | Validation: ≥ 50% nodes mentioned |
| Hybrid router misroutes | Latency | LLM classifier с rule fallback |
| Dim mismatch | Old vs new 4096d | --recreate перед загрузкой |
| Concurrent reindex race | Corruption | Lock data/.graph_build.lock |

---

## §12 Total Time + Cost

| Path | Phases | Время | Cost |
|---|---|---|---|
| Минимально полезный | 1+3+6 | 4-5 ч | $0 |
| **Рекомендуемый (max coverage)** | 1+3+2+5+6 | **6-8 ч** | **~$0.05** |
| Production-ready | + Phase 7 | +2 ч | $0 |
| Premium UX | + Phase 8 | +6 ч | $0 |
| All-in | 1+2+3+5+6+7+8 | ~14-16 ч | ~$0.05 |

---

## §13 Dependencies

pip install neo4j neo4j-graphrag leidenalg igraph
docker pull neo4j:5-community

Уже есть: Qdrant, Sentence-transformers, Qwen3-Embedding-8B, LLM rotation MCP, TEI, Tree-sitter via 1c-syntax.

---

## §14 Roll-back Plan

| Phase | Rollback |
|---|---|
| 1 | qdrant snapshot recover graph_embeddings |
| 3 | docker compose down -v |
| 2 | Qdrant delete type=Community + Cypher MATCH (c:Community) DETACH DELETE c |
| 5 | git revert mcp.py |
| 7 | pip uninstall flash-attn |

Полный rollback ~10 минут.

---

## §15 Appendix A — Cypher Cheatsheet

Multi-hop callers:
MATCH p=(caller:Procedure)-[:CALLS*1..3]->(target:Procedure {name: \$name\})
RETURN DISTINCT caller.name, length(p) AS distance ORDER BY distance;

Impact analysis:
MATCH (target {name: \$name\})<-[:CALLS|REFERENCES*]-(impacted)
RETURN DISTINCT impacted.name, labels(impacted) AS type LIMIT 100;

Documents writing to register:
MATCH (d:Document)-[:WRITES]->(r:Register {name: \$reg_name\}) RETURN d.name;

Dead common modules:
MATCH (m:Module {type: 'CommonModule'})
WHERE NOT EXISTS { (m)-[:DECLARES]->(:Procedure)<-[:CALLS]-() } RETURN m.name;

Subsystem boundaries:
MATCH (s:Subsystem {name: \$name\})-[:CONTAINS*]->(n)
RETURN labels(n)[0] AS type, count(n) ORDER BY count(n) DESC;

Cross-cutting (FO + register):
MATCH (m:Module)-[:USES_FO]->(fo:FunctionalOption {name: \$fo_name\})
MATCH (m)-[:DECLARES]->(p:Procedure)
MATCH (p)-[:READS|WRITES]->(r:Register {name: \$reg_name\})
RETURN DISTINCT m.name;

---

## §16 Appendix B — LLM Summary Prompt

Ты — архитектор 1С:Предприятие 8.3 с 10+ лет опыта.
Опиши подсистему (4-6 предложений):
1. Бизнес-функция
2. 2-3 ключевых документа/справочника
3. Регистры — что пишут, что читают
4. Связи с другими подсистемами через ФО

Узлы (тип: имя): {nodes_listing}
Связи (источник → цель, тип): {edges_listing}

Стиль: Markdown без header-ов, точные имена, не выдумывай связи.
Ответ:

---

## §17 References

- microsoft/graphrag — Hierarchical GraphRAG reference
- DEEP-PolyU/Awesome-GraphRAG — Curated list ICLR-26
- GraphRAG-Bench (ICLR-26) — When to use Graphs in RAG
- Youtu-GraphRAG (ICLR-26) — −33% tokens, +16% accuracy
- neo4j/neo4j-graphrag-python — Production package
- Lum1104/Understand-Anything — Claude Code plugin (Phase 8)
- vitali87/code-graph-rag — Tree-sitter + Memgraph + MCP
- Falkor CodeGraph blog — AST → graph DB overview
- leidenalg paper arxiv:1810.08473 — From Louvain to Leiden
- Internal: docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md
- Internal: .claude/skills/tech-research/cache/qwen3-embedding-speedup.md
- Internal: CLAUDE.md §31

---

## §18 Changelog

| Date | Change | Author |
|---|---|---|
| 2026-05-02 | Initial roadmap created | Alex Terletskii |