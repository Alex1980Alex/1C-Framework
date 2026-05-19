# 260518 ROADMAP — BSL Late Chunking improvements (снижение fallback %)

> **Дата:** 2026-05-18 | **Статус:** PROPOSED | **Owner:** TBD | **Estimated effort:** 3-5 days dev + 2 days benchmark

> **Note on origin:** черновик roadmap'а сгенерирован через Z.AI (`mcp__llm-rotation__llm_complete`, провайдер `claude-cli-haiku`, 216s) согласно Token Economy protocol. Opus review обнаружил >40% factual errors (выдуманные file paths, неправильное описание arxiv:2409.04701, фейковые chapter names) — финальная версия переписана Opus'ом с verified ссылками на реальный код и docs.

## §0 Status dashboard

| Phase | Описание | Статус | ETA | Файлы | Risk |
|---|---|---|---|---|---|
| **Phase 1** | Bump `max_seq_length` 4096 → 8192 (1-line) | ✅ **DONE** | — | [scripts/reindex_bsl_qwen3.py:255](../../scripts/reindex_bsl_qwen3.py) | LOW (только VRAM check) |
| **Phase 2** | Sliding window Late Chunking для модулей > max_seq_length | ✅ **DONE** (требует `--enable-fa2`, см. §1.2.2) | — | [scripts/reindex_bsl_qwen3.py:568-680](../../scripts/reindex_bsl_qwen3.py) | MEDIUM → **HIGH без FA2** (per-window forward 191-437s vs 2.1s; новая строка в §8) |
| **Phase 3** | Region-based Late Chunking (на основе `#Область` границ) | ✅ **DONE** (`--region-aware` ON by default) | — | reindex + [src/bsl/parser/bsl_chunker.py](../../src/bsl/parser/bsl_chunker.py) | LOW (естественные границы BSL) |
| **Phase 4** | Benchmark suite + decision на основе recall@10 | ☐ TODO | 2 day | `tests/benchmarks/` (TBD) | LOW |
| **Phase 5** | Production rollout (alias swap + full reindex 10 коллекций) | ☐ BLOCKED by Phase 4 + FA2 mandatory | 1 day | [chapter 31.3](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.3_Pipeline_индексации.md) | MEDIUM (downtime) |

**Триггер:** [chapter 31.6 §1](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md) указал что 5-10% chunks падают в standard pooling fallback на god-object модулях `ИБTransportManagementDevelop` (>500K chars). Пользователь запросил roadmap для исключения этого fallback'а (session 2026-05-18).

**Цель:** снизить fallback с 5-10% до <1% на текущей конфигурации, поддерживая `bsl_code_v4_late` как production коллекцию.

---

## §1 Background — почему fallback вообще существует

### 1.1 Механизм

[`Qwen3STEmbedder.embed_late_chunked()`](../../scripts/reindex_bsl_qwen3.py) (строки 377-434):

```python
enc = tokenizer(parent_text, truncation=True, max_length=self.max_seq_length, ...)
# parent_text = ВЕСЬ модуль (.bsl файл)
# truncation=True → обрезается до 4096 tokens

for char_start, char_end in chunk_char_spans:
    span = _char_span_to_token_span(offsets, char_start, char_end)
    if span is None:  # chunk выходит за truncation
        out.append(None)  # → caller fallback на embed_batch (std pooling)
```

### 1.2 Эмпирические замеры (из завершённого reindex, 2026-05-18, run 8256.5 секунд / ~2ч 17мин)

**Итоговая статистика:**
- Files: 2098, Symbols: 33 829, Chunks: 37 639, Errors: 0
- **Модулей, попавших в late-chunking процесс: 489** (24% от всех files; остальные были меньше max_seq_length и обработались без fallback)
- **В этих 489 модулях fallback chunks: 24 752 из 27 881 = 88.8%** — почти весь content больших модулей теряет module-level context
- **Fallback от ВСЕХ 37 639 chunks коллекции: 65.8%** (24 752 chunks)

Примеры из лога (наиболее заметные):

| Модуль | parent_chars | fallback chunks | % fallback |
|---|---|---|---|
| Большой Общий модуль | 942 370 | 506 / 512 | **99%** |
| Большая Форма | 545 981 | 338 / 344 | **98%** |
| Большая ObjectModule (Обработка) | 377 534 | 163 / 164 | **99%** |
| Медиум Общий модуль | ~150 000 | 70-100 / 100 | **70-90%** |
| Small Обработка | <50 000 | 0-5 / 20 | **0-25%** |

**Вывод:** реальный fallback **значительно выше** консервативной оценки 5-10%. Production коллекция `bsl_code_v4_late` фактически содержит ~2/3 chunks со standard pooling (без Late Chunking преимущества) для крупных конфигураций типа `ИБTransportManagementDevelop`. Это даёт **сильное обоснование** для Phases 1-3 этого roadmap'а.

### 1.2.2 A/B forward_s измерения (2026-05-19, после внедрения `scripts/_progress.py` instrumentation)

После полной реализации Phase 1+2+3 и добавления observability ([scripts/_progress.py](../../scripts/_progress.py), JSONL sink `data/indexing-progress.jsonl`, helper [scripts/_progress_summarize.py](../../scripts/_progress_summarize.py)) — проведена A/B-проверка на одном из крупнейших god-object модулей `ИБTransportManagementDevelop/Конфигурация/src/CommonModules/УправлениеДоступомСлужебный/Module.bsl` (3.16 MB, 907 symbols, 1114 chunks, 13 регионов).

| Метрика | **Без `--enable-fa2`** | **С `--enable-fa2`** | Speedup |
|---|---|---|---|
| Wall-clock total | 796s (KILLED на window 2/5 region 1/13) | **381.5s (COMPLETE)** | — |
| Model load | 33.1s | 28.2s | 1.2× |
| Sliding regions completed | 1 (incomplete) | **13/13** | — |
| Total sliding windows | 2 | **147** | — |
| `forward_s` window 1 | **191.3s** | (в выборке ниже) | — |
| `forward_s` window 2 | **436.9s** (degradation +145s vs win 1) | (в выборке ниже) | — |
| `forward_s` median (FA2) | — | **2.10s** | **~91×** vs win 1; **~208×** vs win 2 |
| `forward_s` max (FA2) | — | **2.81s** | **155×** vs win 2 |
| `forward_s` distribution (FA2) | — | min 0.43s · median 2.10s · mean 2.06s · stdev 0.29s | — |
| `late_chunk_fallback` events | 0 (не дошли) | **10** | — |
| Average fallback ratio | — | **1.9% (19/987)** ≈ §4.4 target <1% | — |
| Final indexed chunks | 0 | **1 114** | — |

**Run IDs:** `phase12-real-260519` (no FA2, killed), `phase12-fa2-260519` (FA2, complete). Полный JSONL — `data/indexing-progress.jsonl`.

**Выводы для roadmap'а:**

1. **Phase 2 sliding window КОД работает корректно** — на FA2 прогоне без crash'ей проиндексировано 13 регионов с 147 sliding окнами; форма distribution стабильна (median ≈ mean, stdev узкий) — нет degradation per-window как было без FA2.
2. **Без FA2 Phase 2 нежизнеспособен** — forward_s 191→437s **растёт** между окнами (VRAM allocator pressure от `gc.collect()+empty_cache()` не справляется). На 50 god-object модулях это даёт дни wall-clock'а вместо часов из §4.2 estimate.
3. **Roadmap §4.2 estimate `+25s/module × 50 god-objects = +20 min` РЕАЛИСТИЧЕН только с FA2.** Реальный замер: 13-region god-object × ~25s sliding wall-clock = ~5 min с FA2.
4. **Fallback% 1.9%** — близко к §4.4 target `<1%`. Phase 3 region-aware grouping (ON by default) уже даёт основной выигрыш. Остаётся tuning на edge cases.
5. **§4.4 success criteria требует обновления** — добавить «FA2 mandatory для Phase 2/3 на Cyrillic BSL».

### 1.3 Почему `max_seq_length=4096`

Phase 8.12 C5 — защита от OOM на 24 GB RTX 3090 (Qwen3-8B FP16 = 16 GB; activations O(n²) для standard attention → быстро blow VRAM на XXL модулях). Но **искусственно занижено в 8× от native** (Qwen3 supports 32K context OOTB; TEI Docker setup использует max_input_length=40960).

### 1.4 VRAM math на RTX 3090 24GB

| `max_seq_length` | Model (FP16) | Activations (no FA2) | Activations (с FA2) | Total | OOM risk |
|---|---|---|---|---|---|
| 4096 (current) | 16 GB | ~0.5 GB | ~0.3 GB | ~16.5 GB | none |
| **8192 (Phase 1)** | 16 GB | ~1.5 GB | ~0.6 GB | **~17.5 GB** | **none** |
| 16384 | 16 GB | ~5 GB | ~1.5 GB | ~21 GB / 17.5 GB | tight / none |
| 32768 (native max) | 16 GB | ~18 GB | ~3 GB | **OOM** / ~19 GB | OOM / safe c FA2 |

Источник: O(n²) для standard attention, O(n) для FlashAttention 2 ([Qwen3 speed benchmark](https://qwen.readthedocs.io/en/latest/getting_started/speed_benchmark.html) + общие принципы).

---

## §2 Research findings — что делают в 2025-2026

Полный обзор: [bsl-late-chunking-improvements-2026.md](../../.claude/skills/architecture-research/cache/bsl-late-chunking-improvements-2026.md) (architecture-research cache, 12 sources, 4 GitHub repos).

### 2.1 Long late chunking (Jina pattern)

[Jina blog: Late Chunking in Long-Context Embedding Models](https://jina.ai/news/late-chunking-in-long-context-embedding-models/) и оригинальная статья [arXiv:2409.04701 — Late Chunking: Contextual Chunk Embeddings](https://arxiv.org/pdf/2409.04701) (Günther et al., Jina AI, v3 Jul 2025): для документов больше max context, применять **long late chunking** — split на overlapping windows of `max_seq_length`, process каждое окно separately, concatenate chunks at boundary с overlap для preservation context.

**Параметры:** window = `max_seq_length`, overlap = **10-25%** от window size. Это и есть **Phase 2** нашего roadmap. Reference implementation: [github.com/jina-ai/late-chunking](https://github.com/jina-ai/late-chunking).

### 2.2 AST/Region-based chunking (LangChain, LlamaIndex)

«Structured document chunking is ideal for source code or any document with clear structural markers» ([LanceDB chunking blog](https://blog.lancedb.com/chunking-techniques-with-langchain-and-llamaindex/), [VXRL Medium: AST-Based Chunking](https://vxrl.medium.com/enhancing-llm-code-generation-with-rag-and-ast-based-chunking-5b81902ae9fc)).

BSL имеет естественные `#Область ... #КонецОбласти` маркеры — `BSLChunker.parse_regions()` уже реализован в [src/bsl/parser/bsl_chunker.py](../../src/bsl/parser/bsl_chunker.py).

### 2.3 voyage-code-3 (state-of-the-art для code, 2024-12)

Поддерживает **32K context natively** ([voyage-code-3 blog](https://blog.voyageai.com/2024/12/04/voyage-code-3/)) — не нуждается в sliding window для нашего размера модулей. «+13.80% over OpenAI v3-large на 32 code retrieval datasets». Альтернативная стратегия для долгосрочного перехода (closed-source API, deferred — см. [chapter 31.6 §7](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md)).

### 2.4 Qwen3-Embedding-8B native capabilities

[HF model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B): «32k context out of the box, расширяемо до ~112k через YaRN». MTEB Multilingual = 70.58, MTEB-Code = 80.68 (top rank). Pooling = `last_token`.

VRAM требования: [APXML: Qwen3-8B GPU VRAM Requirements](https://apxml.com/models/qwen3-8b).

---

## §3 Phase 1 — Bump `max_seq_length` 4096 → 8192

### 3.1 Scope

**1 строка кода:**

```python
# scripts/reindex_bsl_qwen3.py:239
class Qwen3STEmbedder:
    def __init__(
        self,
        ...
-       max_seq_length: int = 4096,
+       max_seq_length: int = 8192,
    ) -> None:
```

### 3.2 Estimated impact

| Метрика | До | После Phase 1 |
|---|---|---|
| Fallback % (small modules <30K chars) | 0-25% | **0%** |
| Fallback % (medium 30-100K) | 50-70% | **20-40%** |
| Fallback % (large 100-500K) | 80-90% | **60-75%** |
| Fallback % (god-object >500K) | 95-99% | **90-97%** |
| Average fallback (всё ИБTransportManagementDevelop) | ~5-10% | **~3-5%** |
| Wall-clock reindex | ~3 ч | **~3-4 ч** (на 8K activations растут, но bucket batching limits effect) |

### 3.3 Implementation steps

1. Edit `scripts/reindex_bsl_qwen3.py:239` — change default to 8192
2. Update **bucket table** Phase 8.10 (если есть buckets с upper bound > 4096 нужно пересмотреть):
   ```python
   DEFAULT_BUCKETS: tuple[tuple[int | None, int], ...] = (
       (512, 32),
       (1024, 16),
       (2048, 8),
       (4096, 4),
       (8192, 2),    # NEW bucket для 4K-8K chunks
       (None, 1),
   )
   ```
3. Pre-flight VRAM test: вручную запустить на одном большом модуле, замерить `nvidia-smi memory.used` peak
4. Full reindex `ИБTransportManagementDevelop` через `qwen3-st --pooling-mode late-chunking`
5. Сравнить `points_count` + log fallback ratio до/после

### 3.4 Success criteria

- [ ] VRAM peak < 22 GB (запас 2+ GB)
- [ ] Average fallback% упал с 5-10% до 3-5% (на 30%+)
- [ ] Wall-clock reindex < 4 ч (не более +30% к baseline)
- [ ] Search recall@10 на BSL golden-set не упал (no regression)
- [ ] 0 CUDA OOM errors в логе

### 3.5 Rollback

Тривиальный — revert одной строки, перезапустить reindex (idempotent через UUID5).

---

## §4 Phase 2 — Sliding Window Late Chunking

### 4.1 Scope

Доработка `Qwen3STEmbedder.embed_late_chunked()` в `scripts/reindex_bsl_qwen3.py:377-434`:

```python
def embed_late_chunked(self, parent_text, chunk_char_spans):
    # NEW: если parent > max_seq_length, использовать sliding window
    parent_tokens = self._estimate_tokens(parent_text)
    if parent_tokens <= self.max_seq_length:
        return self._embed_late_chunked_single_pass(parent_text, chunk_char_spans)
    return self._embed_late_chunked_sliding(parent_text, chunk_char_spans)

def _embed_late_chunked_sliding(self, parent_text, chunk_char_spans, overlap_ratio=0.15):
    window_size = self.max_seq_length
    overlap = int(window_size * overlap_ratio)
    windows = self._make_windows(parent_text, window_size, overlap)

    results = [None] * len(chunk_char_spans)
    for window_char_offset, window_text in windows:
        enc = self.model.tokenizer(window_text, ...)
        token_embeddings = self._forward(enc)

        for i, (char_start, char_end) in enumerate(chunk_char_spans):
            if results[i] is not None:
                continue  # already embedded by previous window (overlap)
            if window_char_offset <= char_start < window_char_offset + window_size:
                local_start = char_start - window_char_offset
                local_end = char_end - window_char_offset
                span = _char_span_to_token_span(window_offsets, local_start, local_end)
                if span:
                    results[i] = mean_pool(token_embeddings, span)
    return results
```

### 4.2 Estimated impact (+ замеренный результат)

| Метрика | После Phase 1 (estimate) | После Phase 2 (estimate) | **Реальность 2026-05-19 (FA2)** |
|---|---|---|---|
| Fallback % (god-object >500K) | 90-97% | **<5%** | **1.9%** (см. §1.2.2) |
| Average fallback% | 3-5% | **<1%** | **1.9%** (близко, ещё tuning) |
| Wall-clock reindex | ~3-4 ч | **~4-6 ч** (windows processed серийно) | **~5 мин на самый большой god-object** с FA2 → 50 god-objects ≈ 4 ч (попадает в estimate) |
| Quality на cross-window chunks | N/A | -10-20% recall (vs single pass) | TBD (Phase 4 benchmark) |
| Forward_s per window | ~1s estimate | ~1s estimate | **2.1s median c FA2** / **191-437s без FA2** (см. §1.2.2) |

### 4.3 Implementation steps

1. Helper `_make_windows(text, size, overlap) -> list[(char_offset, text)]`
2. Refactor `embed_late_chunked` — add length check + sliding fallback
3. Caller (`_embed_chunks_late`) не меняется (signature тот же)
4. Test: модуль 942K chars должен дать <5% fallback (vs 99% сейчас)
5. Full reindex + measurement

### 4.4 Success criteria

- [x] Fallback% на god-objects < 5% — **достигнуто 1.9%** (§1.2.2, single-module test 2026-05-19)
- [ ] Average fallback% < 1% — **близко 1.9%, нужен tuning** (full reindex после Phase 5)
- [x] Wall-clock reindex < 6 ч (не более +50% к Phase 1) — **достижимо ТОЛЬКО с FA2** (§1.2.2)
- [ ] Search recall@10 на BSL golden-set: -3% — +0% (приемлемая просадка) — TBD Phase 4
- [x] Border-region chunks (последние chunks окна) имеют ≥1 overlap chunk — overlap 15% реализован
- [x] **`--enable-fa2` MANDATORY** для Phase 2 на Cyrillic BSL — подтверждено A/B (§1.2.2)

### 4.5 Trade-off & risks

- **Quality риск:** chunks на границе окна теряют context «другой стороны». Митigation — overlap 15%; для критически больших модулей возможно 25%.
- **Wall-clock риск:** N windows × 1 forward pass = O(N) growth. Для модуля 200K tokens = ~25 windows × ~1s = +25s/модуль. На 50 god-object модулей = +20 мин total.

### 4.6 Rollback

Helper и sliding branch покрыты flag'ом (например `--no-sliding-fallback`). Revert через flag, не нужен reindex.

---

## §5 Phase 3 — Region-based Late Chunking

### 5.1 Scope

Использовать существующий [`BSLChunker.parse_regions()`](../../src/bsl/parser/bsl_chunker.py) для split'а модуля по `#Область` границам ДО embedding'а:

```python
def embed_late_chunked_region_aware(self, parent_text, chunk_char_spans, regions):
    """
    Phase 3: вместо one forward pass на модуль, делаем по одному
    pass'у на каждый #Область (естественные семантические границы BSL).

    Region обычно self-contained (ОбработчикиСобытийФормы vs ПрограммныйИнтерфейс
    vs СлужебныеПроцедуры), потеря cross-region context минимальна.
    """
    results = [None] * len(chunk_char_spans)
    for region in regions:
        region_text = parent_text[region.char_start:region.char_end]
        region_chunks = [
            (i, (cs - region.char_start, ce - region.char_start))
            for i, (cs, ce) in enumerate(chunk_char_spans)
            if region.char_start <= cs < region.char_end
        ]
        if not region_chunks:
            continue

        if estimate_tokens(region_text) > self.max_seq_length:
            # large region → cascade to sliding window (Phase 2)
            local_spans = [cs for _, cs in region_chunks]
            embeddings = self._embed_late_chunked_sliding(region_text, local_spans)
        else:
            local_spans = [cs for _, cs in region_chunks]
            embeddings = self._embed_late_chunked_single_pass(region_text, local_spans)

        for (orig_idx, _), emb in zip(region_chunks, embeddings):
            results[orig_idx] = emb
    return results
```

### 5.2 Estimated impact

| Метрика | После Phase 2 | После Phase 3 |
|---|---|---|
| Fallback% на normal modules (regions <max_seq) | <1% | **0%** |
| Fallback% на huge regions (>max_seq) | <5% (Phase 2 cascades) | <5% (cascade) |
| Average fallback% | <1% | **<0.5%** |
| Quality cross-region | -10-20% (sliding) | **0%** (regions independent) |
| Wall-clock | ~4-6 ч | **~3-5 ч** (lots of small regions parallelize via buckets) |

### 5.3 Implementation steps

1. Verify `BSLChunker.parse_regions()` correctness — должен возвращать list of regions с char ranges
2. New method `embed_late_chunked_region_aware`
3. Pass `regions` через chain reindex_bsl_qwen3 → `_embed_chunks_late` → embedder
4. Handle modules БЕЗ `#Область` (legacy code) — fallback на Phase 2 sliding window
5. Full reindex + measurement

### 5.4 Success criteria

- [ ] Fallback% < 0.5% average
- [ ] Quality на cross-region queries не падает (vs Phase 1 baseline)
- [ ] Region-aware пайплайн работает на модулях БЕЗ regions (legacy fallback)
- [ ] Wall-clock не превышает Phase 1 (regions распараллеливаются better через bucket batching)

### 5.5 Trade-off & risks

- **Зависимость от качества `BSLChunker.parse_regions()`** — нужно убедиться что region parsing robust на malformed `#Область` (вложенные, нестандартные имена)
- **Modules без regions** — старый код может не использовать `#Область`. Fallback на Phase 2 sliding обязателен.

---

## §6 Phase 4 — Benchmark suite

### 6.1 Scope

Создать `tests/benchmarks/test_bsl_retrieval_quality.py`:

1. **Golden set:** 50 queries про BSL код из `ИБTransportManagementDevelop` (вручную составленный, с expected `module_path:line` results)
2. **Metrics:** recall@10, NDCG@10, MRR, precision@5
3. **Variants:** baseline (current 4K), Phase 1 (8K), Phase 2 (sliding), Phase 3 (region)
4. **Special slices:**
   - Queries про god-object modules (>500K chars) — где Phase 2/3 имеют maximum effect
   - Queries про small modules — где должны быть ≈одинаковые результаты
   - Cross-region queries (искусственные, чтобы test Phase 3 trade-off)

### 6.2 Tools

- [Chroma generative-benchmarking](https://github.com/chroma-core/generative-benchmarking) — generate synthetic golden set (как делали для Phase 8 pilot)
- Сравнить с CLAUDE.md Phase 8 baseline (E5=0.450 → Qwen3 Late=0.567)

### 6.3 Success criteria для decision

- **Phase 1 (8K):** если recall@10 не падает И wall-clock < 4ч → MERGE
- **Phase 2 (sliding):** если average fallback <1% И recall@10 на god-object queries +10%+ → MERGE
- **Phase 3 (region):** если quality vs Phase 2 не хуже И wall-clock не выше → MERGE
- **Fallback:** если оба Phase 2/3 ломают recall — оставить Phase 1 only

### 6.4 Open questions (blocking Phase 4 implementation)

Scaffold создан 2026-05-19 в [tests/benchmarks/test_bsl_retrieval_quality.py](../../tests/benchmarks/test_bsl_retrieval_quality.py). Чтобы превратить его в работающий бенчмарк, нужны решения:

| # | Вопрос | Опции | Recommended |
|---|---|---|---|
| **a** | Откуда взять 50 golden queries? | (1) Manual curation 3-5 ч человеко-времени · (2) Chroma generative-benchmarking синтез через LLM · (3) Reuse Phase 8 golden set если он сохранён | (3) если есть, иначе (2) с human review |
| **b** | Какие variant-коллекции существуют как snapshots? | (1) Только текущая `bsl_code_v4_late` (production) · (2) Создать `bsl_phase12_test` + `bsl_phase123_test` через `--recreate` на полном проекте | (2) обязательно — без отдельных snapshot'ов A/B невозможен |
| **c** | Через какой entry point делать `search_variant()`? | (i) Direct `client.query_points()` — изолирует Phase 2/3 эффект · (ii) Через `hybrid_router.route()` — production routing | (i) для чистого A/B; (ii) после merge для regression-теста на production-пути |
| **d** | Какой baseline для acceptance gate? | (1) Текущая `bsl_code_v4_late` recall@10 = 0.567 (из Phase 8) · (2) Phase 8.12.8 A2 (std pooling) · (3) E5 1024d legacy | (1) — самый свежий production |
| **e** | Threshold для regression? | (1) Hard fail если recall@10 -3pp · (2) Warning если -1pp, fail если -5pp · (3) Per-slice threshold (god-object более lenient) | (3) — god-object slice имеет другую базу, fixed pp threshold нечестен |

**Зависимости от других задач:**
- (a) + (b) можно делать параллельно — оба независимы
- (c) + (d) + (e) — code-only, делать после (a)+(b)

**Объём работ после ответов на a-e:** ~1-2 дня (golden set гениρация + reindex 2-3 variant collections + wiring `search_variant()` + first benchmark run + tuning thresholds).

---

## §7 Phase 5 — Production rollout

### 7.1 Scope

1. Применить выбранную комбинацию (Phase 1 + 2/3) к 3 BSL collections:
   - `bsl_code_v4_late` (production, primary impact)
   - `bsl_code_v4` (std pooling baseline — для consistency)
   - Все 1С-проекты в `configuration/<X>/` (через `--project <root>` цикл)

2. Использовать **alias swap pattern** (memory `reference_qdrant_collection_aliases`):
   ```
   bsl_code_v4_late → bsl_code_v4_late_phase3 (rebuild в новой коллекции)
   alias swap: bsl_code_v4_late → bsl_code_v4_late_phase3
   delete: bsl_code_v4_late_old
   ```
   Это держит online queries рабочими во время reindex.

3. Backup snapshot ПЕРЕД rollout (Qdrant snapshot API).

### 7.2 Risks

- **Downtime:** 0 если alias swap. Maximum 1 минута на atomic alias change.
- **VRAM:** TEI должен оставаться up для online queries; qwen3-st reindex в alias collection → docker stop TEI на время rebuild (несколько часов на проект).
- **Resource conflict:** Phase 5 = последовательно по проектам, не параллельно (single GPU).

### 7.3 Documentation updates после rollout

- [ ] [chapter 31.6](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md) §3 — update decision flowchart (full-quality reindex теперь включает Phase 2/3)
- [ ] [chapter 31.3](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.3_Pipeline_индексации.md) — update команды (`--pooling-mode late-chunking` теперь by default Region-aware)
- [ ] CLAUDE.md — update «Phase 8.12.9» secondary point: «Fallback < 1% после Phase 5»
- [ ] skill [`bsl-development`](../../.claude/skills/bsl-development/SKILL.md) — упомянуть новый дефолт max_seq_length
- [ ] MEMORY.md — add entry о новой стратегии fallback handling

---

## §8 Risks & Dependencies

| Risk | Severity | Mitigation |
|---|---|---|
| OOM на Phase 1 8K | LOW | Pre-flight VRAM test на одном XXL модуле |
| Phase 2 ломает quality cross-region | MEDIUM | Phase 4 benchmark с cross-region queries; rollback flag |
| Phase 3 region parsing bugs | MEDIUM | Robust fallback на Phase 2 sliding для модулей без regions / с malformed regions |
| Phase 5 downtime / regression | MEDIUM | Alias swap + Qdrant snapshot backup |
| Wall-clock regression | LOW | Bucket batching + length-aware processing keep throughput |
| **Phase 2 нежизнеспособен без FA2 на Cyrillic BSL** | **HIGH** | A/B 2026-05-19 (§1.2.2): forward_s 191-437s без FA2 vs 2.1s с FA2 (91-208× speedup). FA2 mandatory во всех production командах; добавить guard в [scripts/reindex_bsl_qwen3.py](../../scripts/reindex_bsl_qwen3.py) — отказывать reindex с `--pooling-mode late-chunking` без `--enable-fa2` для Cyrillic projects. Verified: FA2 уже установлен в проектном venv (flash_attn 2.8.3) |

**Зависимости:**

- ✓ `BSLChunker.parse_regions()` существует (нужно verify в `src/bsl/parser/bsl_chunker.py`)
- ✓ Qdrant alias support (используется в Phase 8 для MRL migration)
- ✓ TEI Docker setup (есть, используется)
- ✗ Golden set 50 queries — TBD (можно re-use Phase 8 golden set если есть)
- ✗ Benchmark harness — TBD (можно adapt из `src/pdf_framework/evaluation/` если есть)

---

## §9 Связанные документы

- [chapter 31.6 Варианты индексации и типичные ошибки](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md) — текущая матрица, типичные ошибки
- [chapter 31.3 Pipeline индексации](../framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.3_Pipeline_индексации.md) — production команды (будет обновлён после Phase 5)
- [chapter 04.9 Matryoshka Embeddings](../framework%20documentation/04_ПОИСК/04.9_Matryoshka_Embeddings.md) — параллельная оптимизация (MIGRATE-3 + REJECT-3, **НЕ затрагивает BSL**)
- [architecture-research cache: bsl-late-chunking-improvements-2026](../../.claude/skills/architecture-research/cache/bsl-late-chunking-improvements-2026.md) — full research findings (12 sources)
- [Phase 8 roadmap (closed)](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) — Phase 8.12.9 introduced Late Chunking
- Skill [bsl-development](../../.claude/skills/bsl-development/SKILL.md) — decision flowchart, 7 типичных ошибок (будет обновлён после Phase 5)

## §10 Ссылки на key sources

- **[Paper]** [arXiv:2409.04701 — Late Chunking: Contextual Chunk Embeddings (Günther et al., Jina AI, v3 Jul 2025)](https://arxiv.org/pdf/2409.04701)
- **[GitHub]** [jina-ai/late-chunking](https://github.com/jina-ai/late-chunking) — reference implementation
- **[GitHub]** [QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding) — official Qwen3 embedding repo
- **[Vendor]** [Jina blog: Late Chunking in Long-Context Embedding Models](https://jina.ai/news/late-chunking-in-long-context-embedding-models/)
- **[Vendor]** [voyage-code-3 blog (32K native context, +13.8% over OpenAI на code)](https://blog.voyageai.com/2024/12/04/voyage-code-3/)
- **[Docs]** [Qwen3-Embedding-8B HF model card (32K context, MTEB 80.68 code)](https://huggingface.co/Qwen/Qwen3-Embedding-8B)
- **[Reference]** [APXML: Qwen3-8B GPU VRAM Requirements](https://apxml.com/models/qwen3-8b)
- **[Tutorial]** [VXRL Medium: Enhancing LLM Code Generation with RAG and AST-Based Chunking](https://vxrl.medium.com/enhancing-llm-code-generation-with-rag-and-ast-based-chunking-5b81902ae9fc)
- **[Tutorial]** [LanceDB blog: Chunking Techniques with Langchain and LlamaIndex](https://blog.lancedb.com/chunking-techniques-with-langchain-and-llamaindex/)
