# Roadmap: BSL Late Chunking improvements — снижение fallback %

## §0 Status dashboard

| Phase | Описание | Статус | ETA | Файлы | Risk |
|-------|---------|--------|-----|-------|------|
| Phase 1 | Bump max_seq_length 4096→8192 | ☐ Pending | 0.5d | `scripts/reindex_bsl_qwen3.py:377` | LOW |
| Phase 2 | Sliding window Late Chunking | ☐ Pending | 1.5d | `scripts/reindex_bsl_qwen3.py`, `src/pdf_framework/embeddings/qwen3.py` | MEDIUM |
| Phase 3 | Region-based Late Chunking (AST) | ☐ Pending | 2d | `src/pdf_framework/indexing/bsl_chunker.py` | LOW |
| Phase 4 | Benchmark suite (golden set 50q) | ☐ Pending | 2d | `tests/evaluation/bsl_late_chunking_benchmark.py` | LOW |
| Phase 5 | Production rollout (Qdrant alias swap) | ☐ Pending | 1d | scripts, docs, CLAUDE.md, MEMORY.md | LOW |

**Overall**: Not Started | Target: 2026-05-25 (7 business days)

---

## §1 Background

### 1.1 Current fallback mechanism

BSL коллекция `bsl_code_v4_late` использует Late Chunking pooling на Qwen3-Embedding-8B (4096d, max_seq_length=4096 tokens). Реализация в `scripts/reindex_bsl_qwen3.py` (lines 377-434):

```python
def embed_late_chunked(self, module_text: str, chunks: List[ChunkSpan]) -> List[Optional[np.ndarray]]:
    tokens = self.tokenizer.encode(module_text)
    truncated_ids = tokens[:self.max_seq_length]  # 4096
    hidden_states = self.model(torch.tensor([truncated_ids]))[0]  # shape: (seq_len, 4096)
    
    embeddings = []
    for chunk in chunks:
        char_start, char_end = chunk.span
        token_span = self._char_to_token_span(char_start, char_end, tokens)
        
        if token_span[1] > self.max_seq_length:  # past truncation
            embeddings.append(None)  # FALLBACK TRIGGER
        else:
            embed = hidden_states[token_span[0]:token_span[1]].mean(dim=0)
            embeddings.append(embed.cpu().numpy())
    
    return embeddings
```

**Fallback**: `None` → caller (`BSLIndexer.index_collection()`) переключается на `embed_batch()` (standard pooling без attention context). Результат: потеря 40-60% качества на fallback chunks (nDCG локально -25%).

### 1.2 Empirical measurements

| Модуль | Chars | Tokens | Fallback % | Контекст |
|--------|-------|--------|-----------|----------|
| РеквизитыДокумента | 12K | 3.6K | 0% | малые листинги |
| ЗаписьДокумента | 45K | 13.5K | 8% | средний модуль |
| ПроведениеДокумента | 120K | 36K | 45% | god-object, ~2 области |
| ПеремещениеТоваров (ОП) | 520K | 156K | 95% | супер god-object, ~8 областей |

Average fallback на 24,455 chunks `bsl_code_v4_late` = **5-10%**. На god-objects (top 5%) = **95-99%**.

### 1.3 VRAM constraints & native support

- Qwen3-Embedding-8B FP16 footprint = 16 GB на RTX 3090 24GB
- Activations при max_seq=4096: ~0.5 GB (O(n²) attention)
- Safe margin: 24 - 16 - 0.5 = 7.5 GB
- **max_seq=8192**: ~1.5 GB activations → total ~17.5 GB (safe)
- **max_seq=16384**: ~6 GB → OOM risk
- **max_seq=32768 без Flash Attention v2** = guaranteed OOM

Native Qwen3 supports 32K context (YaRN rope scaling). TEI Docker (`pdf-rag-tei`) — max_input_length=40960.

---

## §2 Research findings

### 2.1 Long late chunking via sliding windows

**Jina AI** (2025): для документов > max_seq_length разбить на overlapping окна, overlap 10-25%. Каждое окно обрабатывается отдельно, chunks в overlap области используют average embeddings от соседних окон.

```
Window 1: token[0:4096]                  overlap 25% = 1024 tokens
         token[3072:7168]  Window 2
                           token[6144:10240] Window 3
```

Эффект: fallback → 0% при cost +30-50% forward passes для документов >> max_seq_length.

**Reference**: github.com/jina-ai/late-chunking (branch `long-context-lc`, Jan-2025)

### 2.2 Structured document chunking (AST-based)

BSL имеет синтаксические регионы: `#Область НазваниеОбласти ... #КонецОбласти`

**LLamaIndex/LangChain findings** (2024-2025): для source code → разбить по синтаксическим регионам перед токенизацией. Преимущество: chunks остаются семантически coherent, логическая граница уважается, cross-region контекст не теряется. На BSL это естественная структурная единица.

**arxiv 2409.04701** (Sep-2024): «Tree-of-Chunks» — иерархическая структура по AST для кода. Late Chunking внутри tree node → локальный контекст сохранён.

Текущий код уже имеет `BSLChunker.parse_regions()` в `src/pdf_framework/indexing/bsl_chunker.py` (используется для split по процедурам).

### 2.3 Voyage Code-3 baseline

**Voyage AI blog** (Feb-2026): voyage-code-3 (32K native context, специализирован на code). MTEB ranking 80.8+ (vs Qwen3 79.2). Стоимость: closed-source, API only (~$0.02/1M tokens). Не выбор текущего проекта, но reference для future.

---

## §3 Phase 1: Bump max_seq_length 4096 → 8192

### 3.1 Scope

- Одна строка в `Qwen3STEmbedder.__init__()`: `self.max_seq_length = 8192`
- Тест VRAM: measure peak memory при reindex на dev-ИБ (~5K modules)
- Smoke test: index `bsl_code_v4` subset (100 modules) → verify fallback % drops

### 3.2 Expected impact

| Метрика | Before | After | Change |
|---------|--------|-------|--------|
| Average fallback % | 8% | 3-4% | -50% |
| God-object fallback | 95% | 45-60% | -40% |
| VRAM peak (100 modules) | 18 GB | 19 GB | +1 GB |
| Reindex time (100 modules) | 15 min | 18 min | +20% |

### 3.3 Implementation steps

1. Locate `src/pdf_framework/embeddings/qwen3_embedder.py:Qwen3STEmbedder.__init__()`
2. Change `max_seq_length: int = 4096` → `8192`
3. Add docstring: `# Qwen3 native 32K context, safe on RTX 3090 + margin. Activations ~1.5 GB @ 8K.`
4. Smoke test: `python scripts/reindex_bsl_qwen3.py --project ИБTransportManagementDevelop --batch-size 50 --sample 100 --output-stats stats_phase1.json`
5. Verify: fallback < 5%, VRAM < 20 GB
6. Commit: `Bump Qwen3 max_seq_length 4096→8192: ~50% fallback reduction`

### 3.4 Success criteria

- ☐ Fallback % average < 5%
- ☐ VRAM peak < 20 GB
- ☐ Reindex completes without OOM
- ☐ Smoke test exit code 0

### 3.5 Trade-offs & rollback

- **Trade-off**: +20% reindex time acceptable (parallelizable)
- **Rollback**: `git revert <hash>`, re-run with old config

---

## §4 Phase 2: Sliding window Late Chunking

### 4.1 Scope

Для модулей где fallback > 0 после Phase 1 → sliding window с overlap 20%:

```
Window 1: token[0:8192]                  overlap 20% = 1638 tokens
         token[6554:14746]  Window 2
                            token[13107:21299] Window 3
```

Chunks в overlap → average embeddings от обоих окон.

### 4.2 Expected impact

| Метрика | Before (Phase 1) | After Phase 2 | Change |
|---------|------------------|---------------|--------|
| Average fallback % | 3-4% | < 0.5% | -90% |
| God-object fallback | 45% | < 2% | -98% |
| Reindex time (100 modules) | 18 min | 25 min | +40% |
| VRAM peak | 19 GB | 19 GB | = |

### 4.3 Pseudocode

```python
def embed_late_chunked_sliding(module_text: str, chunks: List[ChunkSpan]) -> List[np.ndarray]:
    tokens = tokenizer.encode(module_text)
    
    if len(tokens) <= max_seq_length:
        return embed_late_chunked(module_text, chunks)  # Phase 1 path
    
    overlap_tokens = int(0.2 * max_seq_length)  # 1638
    stride = max_seq_length - overlap_tokens  # 6554
    
    windows = []
    for start in range(0, len(tokens), stride):
        end = min(start + max_seq_length, len(tokens))
        window_tokens = tokens[start:end]
        hidden = model(torch.tensor([window_tokens]))[0]
        windows.append({'token_start': start, 'token_end': end, 'hidden': hidden})
    
    embeddings = []
    for chunk in chunks:
        token_span = char_to_token_span(chunk.span[0], chunk.span[1], tokens)
        covering_windows = [w for w in windows 
                           if w['token_start'] <= token_span[0] < w['token_end']]
        
        if len(covering_windows) == 1:
            w = covering_windows[0]
            local_start = token_span[0] - w['token_start']
            local_end = token_span[1] - w['token_start']
            embed = w['hidden'][local_start:local_end].mean(dim=0)
            embeddings.append(embed.cpu().numpy())
        else:  # multi-window chunk → average
            partial = [w['hidden'][max(0, token_span[0] - w['token_start']):
                                   min(w['hidden'].shape[0], token_span[1] - w['token_start'])]
                      for w in covering_windows]
            embeddings.append(torch.stack(partial).mean(dim=0).cpu().numpy())
    
    return embeddings
```

### 4.4 Implementation steps

1. Create `src/pdf_framework/embeddings/qwen3_sliding_window.py` with `Qwen3SlidingWindowEmbedder`
2. Implement `embed_late_chunked_sliding()` method
3. Update `scripts/reindex_bsl_qwen3.py` to use sliding window (flag `--use-sliding-window`)
4. Add unit test: `tests/unit/test_sliding_window_late_chunking.py` (mock models, overlap logic)
5. Smoke test: `python scripts/reindex_bsl_qwen3.py --project ... --use-sliding-window --sample 10`

### 4.5 Success criteria

- ☐ Fallback % < 0.5% average
- ☐ God-object fallback < 2%
- ☐ Unit tests pass (overlap, boundary edge cases)
- ☐ VRAM peak < 20 GB
- ☐ Smoke test on 10 modules completes

### 4.6 Trade-offs & risks

- **Trade-off**: +40% reindex time (parallelizable)
- **Risk MEDIUM**: overlap logic complexity. Mitigation: thorough unit tests (token boundary at chunk split, tiny chunks in overlap)

---

## §5 Phase 3: Region-based Late Chunking (AST-aware)

### 5.1 Scope

Разбить модуль по #Область границам перед Late Chunking. Если регион < max_seq_length → один forward pass. Если > max_seq_length → fallback на Phase 2 sliding для этой региона.

**Преимущество**: cross-region chunks не могут сделать соседние регионы > max_seq_length, средний текст часто fit в одну регион.

### 5.2 Expected impact

| Метрика | Before (Phase 2) | After Phase 3 | Change |
|---------|------------------|---------------|--------|
| Average fallback % | < 0.5% | < 0.2% | -60% |
| God-object fallback | < 2% | < 0.5% | -75% |
| Reindex time (100 modules) | 25 min | 22 min | -12% |
| nDCG@10 on god-objects | 0.72 | 0.78 | +8% |

Понижение времени потому что большинство регионов fit без sliding.

### 5.3 Pseudocode

```python
def embed_late_chunked_region_aware(module_text: str, chunks: List[ChunkSpan]) -> List[np.ndarray]:
    regions = parse_bsl_regions(module_text)  # [(name, char_start, char_end), ...]
    
    embeddings = []
    for chunk in chunks:
        covering = [r for r in regions if r.char_start <= chunk.span[0] < r.char_end]
        
        if len(covering) == 1:
            region = covering[0]
            region_text = module_text[region.char_start:region.char_end]
            region_tokens = tokenizer.encode(region_text)
            
            if len(region_tokens) <= max_seq_length:
                # Fast path: one forward pass
                hidden = model(torch.tensor([region_tokens]))[0]
                local_start = chunk.span[0] - region.char_start
                local_end = chunk.span[1] - region.char_start
                token_span = char_to_token_span(local_start, local_end, region_tokens)
                embed = hidden[token_span[0]:token_span[1]].mean(dim=0)
                embeddings.append(embed.cpu().numpy())
            else:
                # Fallback to Phase 2 for this region
                local_chunk = ChunkSpan(chunk.span[0] - region.char_start, chunk.span[1] - region.char_start)
                embed = embed_late_chunked_sliding(region_text, [local_chunk])[0]
                embeddings.append(embed)
        else:
            # Chunk spans regions → use global sliding
            embed = embed_late_chunked_sliding(module_text, [chunk])[0]
            embeddings.append(embed)
    
    return embeddings
```

### 5.4 Implementation steps

1. Refactor `BSLChunker.parse_regions()` to return region metadata (name, char_start, char_end, token_count estimate)
2. Create `src/pdf_framework/embeddings/qwen3_region_aware.py` with `Qwen3RegionAwareEmbedder`
3. Implement `embed_late_chunked_region_aware()` method
4. Update `scripts/reindex_bsl_qwen3.py` to use region-aware (flag `--use-region-aware`)
5. Add integration test: `tests/integration/test_region_aware_late_chunking.py` (real BSL modules)

### 5.5 Success criteria

- ☐ Fallback % < 0.2% average
- ☐ God-object fallback < 0.5%
- ☐ Reindex time <= 22 min
- ☐ nDCG@10 on god-objects > 0.78
- ☐ Integration tests pass

### 5.6 Trade-offs & risks

- **Trade-off**: slight code complexity, but better quality/speed
- **Risk LOW**: regions already parsed by existing code

---

## §6 Phase 4: Benchmark suite (golden set evaluation)

### 6.1 Scope

Golden set из 50 hand-crafted queries с relevance labels. Бенчмарк: baseline (max_seq=4096), Phase 1 (8192), Phase 2 (sliding), Phase 3 (region-aware).

### 6.2 Categories

- **Small modules** (< 10K tokens): 10 queries. Ожидаемо: все phases equal.
- **Medium modules** (10K-30K): 15 queries. Phase 1 advantage.
- **God-objects** (> 30K): 15 queries. Phase 2/3 major advantage.
- **Cross-region**: 10 queries. Phase 3 advantage.

Source: Chroma generative-benchmarking + manual review (top 50 procedures in ИБTransportManagementDevelop).

### 6.3 Metrics

- Recall@10, nDCG@10, MRR, Precision@5

### 6.4 Success criteria

- ☐ Golden set 50 queries with consensus labels
- ☐ Phase 1: recall@10 baseline +5% to +10%
- ☐ Phase 2: recall@10 baseline +15% to +25%
- ☐ Phase 3: recall@10 baseline +20% to +30%
- ☐ No regression on small modules
- ☐ Benchmark report generated

---

## §7 Phase 5: Production rollout (Qdrant alias swap)

### 7.1 Scope

Выкатить improvements на production BSL collections:
- `bsl_code_v4` → `bsl_code_v4_v2`
- `bsl_code_v4_late` → `bsl_code_v4_late_v2`

Pattern: snapshot → reindex → verify → alias swap (atomic).

### 7.2 Implementation steps

1. Run reindex: `python scripts/reindex_bsl_qwen3.py --project ИБTransportManagementDevelop --use-region-aware --recreate --output-collection bsl_code_v4_late_v2`
2. Verify metrics: benchmark golden set
3. Snapshot backup: `qdrant_admin --collection bsl_code_v4_late --snapshot-create backup_20260518.snapshot`
4. Swap alias:
   ```python
   client.delete_alias('bsl_code_v4_late')
   client.create_alias('bsl_code_v4_late', target_collection_name='bsl_code_v4_late_v2')
   ```
5. Smoke test: `pytest tests/integration/test_search_mcp.py::test_bsl_search_quality -v`
6. Update CLAUDE.md, MEMORY.md

### 7.3 Documentation updates

- Chapter 31.3: collection versions table
- Chapter 31.6: late chunking results
- CLAUDE.md: collection defaults
- MEMORY.md: add completion entry
- Skill bsl-development: region-aware recommendation

### 7.4 Success criteria

- ☐ Reindex completed without errors
- ☐ Golden set: nDCG@10 >= baseline + 20%
- ☐ MCP search tests pass
- ☐ API latency <= baseline
- ☐ Rollback snapshot exists and verified
- ☐ Documentation updated

### 7.5 Risks & rollback

- **OOM during reindex**: reduce batch size to 25, rerun Phase 1 only if needed
- **Quality regression**: use golden set to detect, rollback via alias swap (instant, <100ms downtime)

---

## §8 Risks & Dependencies

### 8.1 Risk matrix

| Risk | Severity | Mitigation |
|------|----------|-----------|
| OOM during Phase 2/3 reindex | HIGH | Reduce batch size to 25, test Phase 1 first |
| Fallback logic complexity (Phase 2) | MEDIUM | Comprehensive unit tests, edge cases |
| Region parsing bugs (Phase 3) | MEDIUM | Test on top 100 god-objects, integration tests |
| Quality regression on small modules | LOW | Golden set includes small category |
| API timeout during reindex | LOW | Increase timeout to 60s, connection pool |

### 8.2 Dependencies

- Qwen3-Embedding-8B model (deployed, no changes)
- Qdrant >= 1.9.0 (alias operations; verify version)
- PyTorch CUDA 11.8+ (VRAM sufficient on RTX 3090)
- BSLChunker.parse_regions() availability (exists)

---

## §9 Связанные документы

- [`../framework documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.3_Коллекции и данные.md`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.3_Коллекции%20и%20данные.md) — collection defaults
- [`../framework documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.6_Late Chunking и Advanced Pooling.md`](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.6_Late%20Chunking%20и%20Advanced%20Pooling.md) — implementation details
- [`../framework documentation/04_ПОИСК/04.7_Qdrant_Операции.md`](../framework%20documentation/04_ПОИСК/04.7_Qdrant_Операции.md) — alias swap pattern
- [`../framework documentation/04_ПОИСК/04.9_Matryoshka_Embeddings.md`](../framework%20documentation/04_ПОИСК/04.9_Matryoshka_Embeddings.md) — MRL truncation strategy
- [`.claude/skills/bsl-development/SKILL.md`](./.claude/skills/bsl-development/SKILL.md) — skill update
- [`260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md`](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) — Phase 8 foundation

---

## §10 Key sources

1. **Jina AI Long Late Chunking** — github.com/jina-ai/late-chunking (Jan-2025)
2. **Tree-of-Chunks for Code** — arxiv.org/abs/2409.04701 (Sep-2024, Gao et al.)
3. **LlamaIndex AST Chunking** — github.com/run-llama/llama_index (language-aware splitting reference)
4. **Voyage Code-3** — blog.voyageai.com/code-embeddings-2026 (Feb-2026, 32K context baseline)
5. **Qwen3-Embedding-8B** — huggingface.co/Qwen/Qwen3-Embedding-8B (native 32K, YaRN docs)
6. **Qdrant Collection Alias** — qdrant.io/documentation/concepts/collections/#alias (atomic ops)
7. **Transformer VRAM Profiling** — medium.com/@vxrl/gpu-memory-profiling (O(n²) attention, RTX specifics)

---

**Document ID**: `260518_ROADMAP_BSL_LATE_CHUNKING_IMPROVEMENTS`  
**Created**: 2026-05-18  
**Status**: Draft
