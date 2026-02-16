# P3 — Передовые технологии

**Effort:** 10-18 дней | **Impact:** MEDIUM | **Phases:** 55-58
**Зависимости:** Q1 (embedding upgrade) для A2. P0 (tests) для валидации.

---

## A1 — ColPali Visual Retrieval (Phase 55)

**Текущее:** Два раздельных пути: (1) ImageExtractor → Claude Vision → текстовые описания → embed как text; (2) Level 4 Vision OCR для scanned pages. Нет unified visual retrieval.
**Gap:** ColPali v2 / ColQwen2 — end-to-end visual retrieval без OCR. Embed страницу как изображение, ищи по visual similarity.
**Модели:** `vidore/colpali-v1.3` (2B params), `vidore/colqwen2-v1.0` (7B params).

### A1.1 ColPali provider

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A1.1.1 | Добавить `colpali-engine` / `transformers` в dependencies | `pyproject.toml` | +2 | Import works |
| A1.1.2 | Создать `ColPaliProvider` class | `src/pdf_framework/embeddings/providers/colpali.py` | ~100 | Unit test |
| A1.1.3 | Реализовать: load model (GPU/CPU auto-detect) | Тот же файл | ~25 | Model loaded |
| A1.1.4 | Реализовать: `embed_image(PIL.Image) → vector` | Тот же файл | ~20 | 128-dim multi-vector |
| A1.1.5 | Реализовать: `embed_query(text) → vector` | Тот же файл | ~15 | Query vector |
| A1.1.6 | Реализовать: `late_interaction_score(q_vecs, doc_vecs)` | Тот же файл | ~20 | MaxSim score |
| A1.1.7 | Batch processing: embed multiple pages | Тот же файл | ~20 | Batch works |
| A1.1.8 | Memory management: torch.no_grad(), offloading | Тот же файл | ~10 | No OOM on CPU |

---

### A1.2 Visual indexing pipeline

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A1.2.1 | Page renderer: PDF → PIL.Image (pymupdf) | `src/pdf_framework/processing/page_renderer.py` | ~40 | Pages rendered |
| A1.2.2 | Resolution config: 150/200/300 DPI | Тот же файл | ~10 | DPI configurable |
| A1.2.3 | Отдельная Qdrant collection `visual_pages` | `src/pdf_framework/vector_store/providers/qdrant.py` | +20 | Collection created |
| A1.2.4 | Indexer: render pages → ColPali embed → store | `src/pdf_framework/indexing/visual_indexer.py` | ~80 | Pages indexed |
| A1.2.5 | Metadata: page_number, document_id, thumbnail_path | Тот же файл | ~15 | Metadata stored |

---

### A1.3 Visual search strategy

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A1.3.1 | Создать `VisualSearchStrategy(BaseSearchStrategy)` | `src/pdf_framework/search/strategies/visual.py` | ~60 | Unit test |
| A1.3.2 | Query → ColPali embed → search visual_pages collection | Тот же файл | ~20 | Results returned |
| A1.3.3 | Result: page image + page_number + score | Тот же файл | ~15 | Results complete |
| A1.3.4 | Register strategy: `SearchManager.register("visual", ...)` | `src/pdf_framework/search/manager.py` | +2 | Strategy available |
| A1.3.5 | API endpoint: `/search/visual` | `src/api/routes/search.py` | +20 | API works |

---

### A1.4 Hybrid text+visual

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A1.4.1 | Fusion: text results + visual results (RRF) | `src/pdf_framework/search/strategies/visual.py` | +30 | Fusion works |
| A1.4.2 | Auto-detect: visual query (tables, charts, diagrams) | `src/pdf_framework/search/pipelines/two_stage.py` | +15 | Visual queries detected |
| A1.4.3 | Конфиг: `FEATURES__VISUAL_SEARCH=true/false` | `src/pdf_framework/config/features.py` | +3 | Toggle |
| A1.4.4 | Unit test: visual search | `tests/unit/search/test_visual.py` | ~50 | — |
| A1.4.5 | Integration test: PDF → visual index → search | `tests/integration/test_visual.py` | ~60 | — |

**Acceptance:** Visual search находит таблицы/диаграммы по текстовому описанию. Fusion с text search.

---

## A2 — BGE-M3 Unified Model (Phase 56)

**Текущее:** Раздельные embeddings: dense (E5/Jina), sparse (BM25 tokenizer в Qdrant), ColBERT (RAGatouille). 3 отдельных модели.
**Gap:** BGE-M3 — единая модель для dense + sparse + ColBERT. One model, three representations.
**Зависимость:** Q1 (если выбран Jina, A2 — альтернатива; если E5, A2 — апгрейд).

### A2.1 BGE-M3 provider

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A2.1.1 | Создать `BGEM3Provider(BaseEmbeddingProvider)` | `src/pdf_framework/embeddings/providers/bgem3.py` | ~120 | Unit test |
| A2.1.2 | Load model: `BAAI/bge-m3` через FlagEmbedding | Тот же файл | ~20 | Model loaded |
| A2.1.3 | Реализовать: `embed_texts() → dense vectors (1024d)` | Тот же файл | ~20 | Dense correct |
| A2.1.4 | Реализовать: `embed_sparse() → sparse vectors` | Тот же файл | ~25 | Sparse correct |
| A2.1.5 | Реализовать: `embed_colbert() → token vectors` | Тот же файл | ~25 | ColBERT correct |
| A2.1.6 | Реализовать: `embed_multi() → {dense, sparse, colbert}` | Тот же файл | ~15 | All three at once |
| A2.1.7 | Batch processing: batch_size=256 | Тот же файл | ~15 | Batch works |
| A2.1.8 | Конфиг: `EMBEDDING__PROVIDER=bge-m3` | `src/pdf_framework/config/embedding.py` | +3 | Config loads |

---

### A2.2 Unified Qdrant collection

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A2.2.1 | 3 named vectors: `dense`, `sparse`, `colbert` | `src/pdf_framework/vector_store/providers/qdrant.py` | +30 | Collection schema |
| A2.2.2 | Indexing: одна модель → 3 вектора одновременно | `src/pdf_framework/indexing/indexer.py` | +15 | All 3 stored |
| A2.2.3 | Search: multi-vector RRF (dense + sparse + colbert) | `src/pdf_framework/vector_store/providers/qdrant.py` | +25 | Triple fusion |
| A2.2.4 | Fallback: если ColBERT disabled → dense + sparse only | Тот же файл | +10 | Graceful degradation |

---

### A2.3 Migration & benchmark

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A2.3.1 | Migration script: re-embed with BGE-M3 | `scripts/migrate_bgem3.py` | ~80 | All re-embedded |
| A2.3.2 | Remove dependency on RAGatouille ColBERT | `pyproject.toml` | -1 | Simplified deps |
| A2.3.3 | Remove dependency on Qdrant BM25 tokenizer | `src/pdf_framework/vector_store/providers/qdrant.py` | -20 | Use BGE-M3 sparse |
| A2.3.4 | Benchmark: E5 vs BGE-M3 (recall@5, recall@10, MRR) | `scripts/embedding_benchmark.py` | +30 | improvement measured |
| A2.3.5 | Unit test: BGE-M3 multi-output | `tests/unit/embeddings/test_bgem3.py` | ~60 | — |

**Acceptance:** Единая модель для всех 3 типов vectors. recall@10 ≥ E5. Simplified architecture.

---

## A3 — Agentic RAG: Plan-Execute (Phase 57)

**Текущее:** RAG Agent (Self-RAG, 7 nodes), Research Agent v2 (plan-tree DAG), Multi-Agent (4 agents). Все LangGraph.
**Gap:** Нет Plan-Execute паттерна для complex queries. Текущий agent не разбивает задачу на шаги.

### A3.1 Plan-Execute agent

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A3.1.1 | Создать `PlanExecuteAgent` (LangGraph) | `src/pdf_framework/agents/plan_execute/agent.py` | ~120 | Unit test |
| A3.1.2 | Node: `planner` — LLM разбивает query на steps | `src/pdf_framework/agents/plan_execute/nodes/planner.py` | ~60 | Steps generated |
| A3.1.3 | Node: `executor` — выполняет один step (search + answer) | `src/pdf_framework/agents/plan_execute/nodes/executor.py` | ~50 | Step executed |
| A3.1.4 | Node: `replanner` — корректирует план по результатам | `src/pdf_framework/agents/plan_execute/nodes/replanner.py` | ~50 | Plan updated |
| A3.1.5 | Node: `synthesizer` — собирает финальный ответ из steps | `src/pdf_framework/agents/plan_execute/nodes/synthesizer.py` | ~40 | Answer composed |
| A3.1.6 | State: `PlanExecuteState` (plan, results, current_step) | `src/pdf_framework/agents/plan_execute/state.py` | ~30 | State correct |
| A3.1.7 | Graph: planner → [executor → replanner]* → synthesizer | `src/pdf_framework/agents/plan_execute/agent.py` | ~40 | Graph compiled |
| A3.1.8 | Max iterations: 5 (prevent infinite loops) | Тот же файл | ~5 | Loop stops |

---

### A3.2 Tool integration

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A3.2.1 | Tool: `search` — vector/hybrid search | `src/pdf_framework/agents/plan_execute/tools.py` | ~20 | Search tool |
| A3.2.2 | Tool: `graph_query` — entity/relation lookup | Тот же файл | ~20 | Graph tool |
| A3.2.3 | Tool: `calculate` — simple math | Тот же файл | ~15 | Calc tool |
| A3.2.4 | Tool: `web_search` — external search (if MCP) | Тот же файл | ~15 | Web tool |
| A3.2.5 | Executor uses tool selection по step type | `src/pdf_framework/agents/plan_execute/nodes/executor.py` | +10 | Correct tool selected |

---

### A3.3 Integration

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A3.3.1 | Auto-routing: complex queries → PlanExecute agent | `src/pdf_framework/agents/routing/classifier.py` | +10 | Complex routed |
| A3.3.2 | API endpoint: `/search/plan-execute` | `src/api/routes/search.py` | +20 | API works |
| A3.3.3 | SSE streaming: plan steps + results + final answer | `src/pdf_framework/agents/plan_execute/streaming.py` | ~40 | Steps streamed |
| A3.3.4 | MCP tool: `plan_execute_query` | `src/mcp_server/server.py` | +15 | MCP tool |
| A3.3.5 | Unit test: plan generation | `tests/unit/agents/test_plan_execute.py` | ~60 | — |
| A3.3.6 | Integration test: full plan-execute cycle | `tests/integration/test_plan_execute.py` | ~60 | — |

**Acceptance:** Complex queries разбиваются на 2-5 шагов. Каждый шаг выполняется с нужным tool. Финальный ответ синтезируется.

---

## A4 — Proposition-based Chunking (Phase 58)

**Текущее:** 4 splitters: recursive, semantic, parent_child, structure_aware. Recursive — default (by char count).
**Gap:** Proposition chunking — LLM разбивает текст на атомарные утверждения. Каждое proposition — 1 chunk.

### A4.1 Proposition extractor

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A4.1.1 | Создать `PropositionSplitter(BaseSplitter)` | `src/pdf_framework/processing/splitters/proposition.py` | ~100 | Unit test |
| A4.1.2 | LLM prompt: "Extract atomic propositions from text" | Тот же файл | ~20 | Prompt works |
| A4.1.3 | Parse output: numbered list → list[str] | Тот же файл | ~20 | Parsing correct |
| A4.1.4 | Ralph Wiggum: retry on too-few propositions | Тот же файл | ~15 | Self-correction |
| A4.1.5 | Batch: process N chunks parallel | Тот же файл | ~20 | Parallel works |
| A4.1.6 | Конфиг: `PDF__SPLITTER=proposition` | `src/pdf_framework/config/pdf.py` | +2 | Config |

---

### A4.2 Integration

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| A4.2.1 | Register in pipeline splitter factory | `src/pdf_framework/processing/pipeline.py` | +5 | Factory dispatch |
| A4.2.2 | Metadata: original_chunk_id → proposition | `src/pdf_framework/schemas/document.py` | +2 | Traceability |
| A4.2.3 | Pre-filter: skip propositions from image chunks | `src/pdf_framework/processing/splitters/proposition.py` | +5 | Images skip |
| A4.2.4 | Cost estimation: Haiku for proposition extraction | Тот же файл | +5 | Cost tracked |
| A4.2.5 | Benchmark: proposition vs recursive chunking recall | `scripts/chunking_benchmark.py` | ~60 | recall measured |
| A4.2.6 | Unit test: proposition extraction | `tests/unit/processing/test_proposition.py` | ~50 | — |
| A4.2.7 | Integration test: full pipeline with proposition | `tests/integration/test_proposition.py` | ~40 | — |

**Acceptance:** Proposition chunking генерирует 3-5x больше чанков. recall@10 improvement ≥2% на factual queries.

---

## Чеклист завершения P3

- [ ] ColPali provider: image → vector, visual search strategy
- [ ] Visual + text fusion search (RRF)
- [ ] BGE-M3: dense + sparse + ColBERT в одной модели
- [ ] Unified Qdrant collection с 3 named vectors
- [ ] Plan-Execute agent: 2-5 шагов, tool selection
- [ ] SSE streaming for plan steps
- [ ] Proposition chunking: atomic statements
- [ ] Benchmarks для каждого improvement
- [ ] All new code covered by tests
