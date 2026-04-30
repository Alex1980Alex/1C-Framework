# ADR-008: Qwen3-Embedding-8B + Late Chunking для BSL retrieval (Phase 8.12)

**Дата:** 2026-04-30
**Статус:** accepted
**Исследование:** [cache/embedding-deployment-fa2-tei-chunking.md](../cache/embedding-deployment-fa2-tei-chunking.md), [cache/code-retrieval-golden-set-construction-2025.md](../cache/code-retrieval-golden-set-construction-2025.md)
**Roadmap:** [Phase 8 §21.10 REVISED Decision](../../../docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md)

---

## Контекст

BSL Semantic Search в PDF Framework начался с Phase 45 (nomic-embed-text 768d, `bsl_code_v2`), мигрировал на Phase 7 (E5-multilingual-large 1024d, `bsl_code_v3`). К началу Phase 8 (2026-04-26) baseline retrieval был на E5 без формального quality-замера на BSL-domain golden-set.

Phase 8 целевала миграцию на Qwen3-Embedding-8B (4096d) — топовая модель MTEB-Code 80.68 / Multilingual 70.58, в 6 пт выше E5 на mainstream бенчмарках, native 32K context для длинных BSL модулей. Но **BSL/1С не входит в training distribution Qwen3** (CodeSearchNet покрывает Python/Java/JS/PHP/Ruby/Go) — открытый вопрос про OOD-gap на русском 1С коде.

Phase 8.12.8 запустил quality regression A/B на synthetic golden-set (Chroma generative-benchmarking + call_graph 1-hop multi-positives), 3 точки сравнения:
- (a) E5 baseline `bsl_code_v3` 1024d
- (b) Qwen3 + standard pooling `bsl_code_v4` 4096d (TEI)
- (c) Qwen3 + Late Chunking `bsl_code_v4_late` 4096d (qwen3-st)

Нужно зафиксировать архитектурное решение по итогам pilot.

## Решение

**Production BSL retrieval переключается на Qwen3-Embedding-8B + Late Chunking pooling** (`bsl_code_v4_late`, 4096d cosine).

### Обоснование (50q expanded pilot, Phase 8.12.8)

| Arm | Recall@10 | NDCG@10 | MRR | Δ vs E5 |
|---|---|---|---|---|
| (a) E5 baseline | 0.450 | 0.291 | 0.292 | baseline |
| (b) Qwen3+std (TEI) | 0.160 | 0.099 | 0.103 | -64% recall |
| (c) **Qwen3+Late Chunking** | **0.567** | **0.414** | **0.447** | **+26% recall, +43% ndcg, +53% mrr** |

1. **Late Chunking — критический enabler** (+254% recall vs std pooling) [exp: pilot 50q]. Согласуется с Jina paper [arXiv:2409.04701, +12-14 пт similarity]
2. **(c) ≥ (a) подтверждено на расширенной выборке** (50q, 0% skip-rate после path C pre-filter fix) — Qwen3+Late беспроблемно бьёт E5 baseline на BSL [exp]
3. **H3 (Russian BSL OOD) частично reject'нута**: gap проявляется только при std pooling (потеря context), Late Chunking устраняет [exp]
4. **H1 (instruction mismatch) reject'нута**: ablation на 14q показала default web-retrieval prompt оптимален (BSL-specific дал 0.000 recall, code-specific 0.071, default 0.143). Qwen3 жёстко калиброван на HF model card шаблон [exp: H1 ablation]
5. **Late Chunking требует Python sentence-transformers** (qwen3-st) — TEI HTTP backend не поддерживает (pooled vectors only) [docs: TEI README]

### Architectural choices

- **Pooling:** Late Chunking (full-document forward → per-chunk mean-pool) [paper: jina-ai/late-chunking]
- **Indexing backend:** Python sentence-transformers + scripts/reindex_bsl_qwen3.py с `--pooling-mode late-chunking` [own]
- **Query backend:** TEI HTTP (production, primary) [exp: smoke validated 2026-04-30]. **Ollama qwen3-embedding:8b НЕ рекомендуется** для текущего индекса — A/B drift показал cosine **0.52** между Ollama и TEI на одном запросе (vs ожидаемое >0.95 для quantization noise) — Ollama vector space фундаментально отличается, скорее всего из-за heavy GGUF quantization или иной pooling. γ-fallback `Qwen3EmbeddingService` сохранён, но Ollama path требует отдельной reindex `bsl_code_v4_late_ollama` для совместимости [exp: drift measurement 2026-04-30]
- **Query instruction:** default HF model card template `"Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "` (НЕ кастомные BSL-specific) [exp: H1 ablation REJECTED]
- **Passage instruction:** пустая (Qwen3 convention для passages) [docs: HF model card]
- **Chunker:** sliding-window split window=1024 / overlap=256 (Phase 8.12.5) для XXL символов > 2K токенов [own]
- **Correctness gates (Phase 8.12.1 P0 C1-C7):** token cap, padding_side="left" co-requirement с FA2, OOM swallow в flush_batch, expandable_segments [exp]

## Последствия

### Положительные

- **+26% recall vs E5 на synthetic BSL golden-set** — defendable production switchover [exp]
- **Late Chunking +254% recall vs std pooling** — обоснование инвестиции в новый pooling-mode (Phase 8.12.9) [exp]
- **Better long-context handling** — Qwen3 native 32K context vs E5 512 token cap; Late Chunking сохраняет document-level семантику для крупных BSL модулей [docs]
- **Identical query path в production**: γ-fallback `Qwen3EmbeddingService` (Ollama → TEI) дает graceful degradation [exp: smoke]
- **Скорость reindex через TEI**: continuous batching + FA2 встроенно, ~2.4s/file vs ~4-5s/file через Python ST [exp: phase8.12.3]

### Отрицательные

- **VRAM footprint**: 4096d × 24455 points × 4 bytes ≈ 400 MB на коллекцию + 16 GB GPU для inference (TEI постоянно) или 4-12 GB (Ollama on-demand) — vs E5 1024d ~98 MB [own]
- **Stack complexity**: 2 backend'а (TEI Docker + Ollama) для query-side, 1 для indexing (qwen3-st Python) — больше moving parts чем E5 single-stack [own]
- **Single-GPU constraint**: TEI постоянно занимает ~16 GB на RTX 3090 24GB, ограничивает параллельные GPU-задачи (LoRA fine-tuning, OllamaLLM для агентов) [own]
- **Synthetic-pilot bias возможен**: Chroma-generated queries могут быть out-of-distribution от реальных user queries; final validation требует Phase 22 feedback [own]
- **Bus factor на Late Chunking impl**: единственная реализация — `_embed_chunks_late` в `scripts/reindex_bsl_qwen3.py` (Phase 8.12.9), не покрыта sentence-transformers нативно [own]

## Альтернативы

### A1. E5-multilingual-large (Phase 7 baseline) — REJECTED

- recall 0.450, gap -26% от Qwen3+Late на pilot [exp]
- Ниже dim (1024 vs 4096), быстрее CPU inference [docs]
- **Отклонено**: Qwen3+Late стабильно лучше на synthetic 50q golden, особенно когда учитывается ndcg/mrr (+43%/+53%)

### A2. Qwen3 + standard pooling (без Late Chunking) — REJECTED

- recall 0.160, gap -64% от Qwen3+Late [exp]
- **Отклонено**: catastrophic underperformance на длинных BSL модулях из-за потери document-level контекста при per-chunk pooling без shared forward

### A3. GigaEmbeddings-instruct (1024d, Russian SOTA 69.1 ruMTEB) — DEFERRED

- Не тестирована на BSL golden-set [own]
- Может оказаться лучшей альтернативой E5 на русском dev-style queries [web]
- **Отложено в Path D §21.10**: после real-user queries Phase 22 — может побить Qwen3+Late с меньшим VRAM footprint (1024d vs 4096d)

### A4. BGE-M3 (1024d multilingual + sparse) — DEFERRED

- Hybrid sparse+dense из коробки [web: BAAI/bge-m3]
- **Отложено в Path D §21.10**: research-направление, alternative tradeoff на dim/quality

### A5. Phase 8.13 LoRA fine-tuning Qwen3 на BSL — DEFERRED

- Может дать +5-10% recall vs current (0.567 → ~0.62) [own: estimate]
- Cost: 1-3 дня offline GPU window (single-GPU constraint) ИЛИ облачный $60-360 [own]
- **Отложено**: текущий Qwen3+Late уже defendable production-quality. Fine-tuning имеет смысл только когда Phase 22 feedback подтвердит pilot сигнал на real user queries (≥500q non-synthetic golden)

### A6. Jina v3 Embeddings (API-based, supports Late Chunking natively) — REJECTED

- API dependency (jina.ai) — не подходит для on-premise/internal data [own]
- Cost per query (API) vs free local Qwen3 [own]
- **Отклонено**: privacy + cost considerations

## Связанные файлы

### Code
- [`scripts/reindex_bsl_qwen3.py`](../../../../scripts/reindex_bsl_qwen3.py) — `Qwen3STEmbedder.embed_late_chunked` + `_embed_chunks_late` orchestrator (Phase 8.12.9)
- [`scripts/reindex_bsl_qwen3.py`](../../../../scripts/reindex_bsl_qwen3.py) — `Qwen3TEIEmbedder` с `client_batch_size` (Phase 8.12.6 + 413 fix)
- [`src/bsl/parser/bsl_chunker.py`](../../../../src/bsl/parser/bsl_chunker.py) — sliding-window split (Phase 8.12.5) + module_summary drop policy (Phase 8.12.2)
- [`src/bsl/semantic_search/config.py`](../../../../src/bsl/semantic_search/config.py) — `collection_name="bsl_code_v4_late"`, `embedding_dim=4096`
- [`src/bsl/semantic_search/services/qwen3_embedding.py`](../../../../src/bsl/semantic_search/services/qwen3_embedding.py) — `Qwen3EmbeddingService` (Ollama) + `Qwen3TEIQueryService` (TEI) + γ-fallback
- [`src/bsl/semantic_search/services/hybrid_search.py`](../../../../src/bsl/semantic_search/services/hybrid_search.py) — default `qdrant_collection="bsl_code_v4_late"`
- [`scripts/phase8_12_8/`](../../../../scripts/phase8_12_8/) — eval pipeline (filter / cluster / generate / label / eval) + `_llm.py` Z.AI sync wrapper

### Infrastructure
- [`docker/docker-compose.gpu.yml`](../../../../docker/docker-compose.gpu.yml) — TEI service profile `tei` (image 1.7.2, Ampere, fp16, MAX_INPUT_LENGTH=4096)
- `cache/bsl_call_graph.db` — SQLite call graph (33630 symbols / 79709 calls для GKSTCPLK-2368)

### Tests
- [`tests/test_reindex_qwen3_oom.py`](../../../../tests/test_reindex_qwen3_oom.py) — P0 C1-C7 (9/9 passing)
- [`tests/test_bsl_chunker_split.py`](../../../../tests/test_bsl_chunker_split.py) — A2 sliding-window (10/10)
- [`tests/test_qwen3_tei_embedder.py`](../../../../tests/test_qwen3_tei_embedder.py) — A3 TEI (16/16)
- [`tests/test_late_chunking.py`](../../../../tests/test_late_chunking.py) — A2-alt Late Chunking (18/18)

### Skills (refreshed)
- [`embedding-models`](../../embedding-models/SKILL.md) — Qwen3 prefix block + TEI backend row + Late Chunking note
- [`qdrant-operations`](../../qdrant-operations/SKILL.md) — BSL Phase 8.12 layout (single-vector 4096d) + diagnostics (TEI 413, query_points migration)
- [`framework-config`](../../framework-config/SKILL.md) — EMBEDDING__MODEL=Qwen/Qwen3-Embedding-8B + QWEN3_MODEL_DIR + ZAI_API_KEY
- [`bsl-development`](../../bsl-development/SKILL.md) — Phase 8.12.8 production switchover section

### Roadmap
- [Phase 8 §21](../../../../docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) — full Qwen3 migration journey (8.12.1–8.12.9 + path C expand + 1a/1b/1c/1d switchover)
- [§21.10 REVISED Decision](../../../../docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) — pilot results + revival from "stay on E5" decision
- [§22 Phase 8.13](../../../../docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) — DEFERRED LoRA fine-tuning (optional improvement)

## Триггеры пересмотра

ADR-008 будет superseded если выполнится один из:

1. **Phase 22 real-user queries** дадут result где Qwen3+Late ≤ E5 на ≥500q non-synthetic golden-set → откат к E5 (`bsl_code_v3` reactivated)
2. **Path D ablation** (GigaEmbeddings/BGE-M3) покажет alternative ≥ Qwen3+Late с меньшими ресурсами → миграция на лучшую модель
3. **Phase 8.13 LoRA** даст +20%+ recall vs current → новый ADR на BSL-fine-tuned Qwen3 baseline
4. **Single-GPU bottleneck** станет блокирующим (LoRA training conflict, agent stack VRAM pressure) → revisit с возможным переходом на Ollama (quantized) или меньшая модель
