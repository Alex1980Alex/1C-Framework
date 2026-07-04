# 260518 ROADMAP — BSL Late Chunking improvements (снижение fallback %)

> **Дата:** 2026-05-18 | **Статус:** PROPOSED | **Owner:** TBD | **Estimated effort:** 3-5 days dev + 2 days benchmark

> **Note on origin:** черновик roadmap'а сгенерирован через Z.AI (`mcp__llm-rotation__llm_complete`, провайдер `claude-cli-haiku`, 216s) согласно Token Economy protocol. Opus review обнаружил >40% factual errors (выдуманные file paths, неправильное описание arxiv:2409.04701, фейковые chapter names) — финальная версия переписана Opus'ом с verified ссылками на реальный код и docs.

## §0 Status dashboard

| Phase | Описание | Статус | ETA | Файлы | Risk |
|---|---|---|---|---|---|
| **Phase 1** | Bump `max_seq_length` 4096 → 8192 (1-line) | ✅ **DONE** | — | [scripts/reindex_bsl_qwen3.py:255](../../scripts/reindex_bsl_qwen3.py) | LOW (только VRAM check) |
| **Phase 2** | Sliding window Late Chunking для модулей > max_seq_length | ✅ **DONE** (требует `--enable-fa2`, см. §1.2.2) | — | [scripts/reindex_bsl_qwen3.py:568-680](../../scripts/reindex_bsl_qwen3.py) | MEDIUM → **HIGH без FA2** (per-window forward 191-437s vs 2.1s; новая строка в §8) |
| **Phase 3** | Region-based Late Chunking (на основе `#Область` границ) | ⚠️ **IMPLEMENTED but FAILS QUALITY GATE** (medium recall -25pp vs baseline; §1.2.5) — use `--no-region-aware` in production | — | reindex + [src/bsl/parser/bsl_chunker.py](../../src/bsl/parser/bsl_chunker.py) | **HIGH** (quality regression confirmed Phase 4) |
| **Phase 4** | Benchmark suite + decision на основе recall@10 | ✅ **DONE** (§1.2.5; phase12 PASS, phase123 FAIL) | — | [tests/benchmarks/test_bsl_retrieval_quality.py](../../tests/benchmarks/test_bsl_retrieval_quality.py), [data/bsl_golden_set.json](../../data/bsl_golden_set.json) | LOW |
| **Phase 5** | Production rollout (alias swap to std_pool config, NOT Late Chunking) | ✅ **DONE 2026-05-20** | — | Alias `bsl_code_v4_late` → physical `bsl_code_v4_late_v2` (std pooling + FA2, 30 404 chunks). +30pp overall recall@10 confirmed post-swap | LOW (snapshot retained) |

**Триггер:** [chapter 31.6 §1](../framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md) указал что 5-10% chunks падают в standard pooling fallback на god-object модулях `ИБTransportManagementDevelop` (>500K chars). Пользователь запросил roadmap для исключения этого fallback'а (session 2026-05-18).

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

### 1.2.3 Overlap tuning A/B (2026-05-19, FA2 baseline)

После §1.2.2 — отдельный замер влияния `--sliding-overlap` (новый CLI флаг, добавлен 2026-05-19 в [scripts/reindex_bsl_qwen3.py](../../scripts/reindex_bsl_qwen3.py)) на тот же god-object `УправлениеДоступомСлужебный/Module.bsl`. Цель — снизить fallback% с 1.9% до <1% (§4.4 criterion).

| Метрика | overlap=0.15 (default) | overlap=0.25 | Δ |
|---|---|---|---|
| Wall-clock total | 381.5s | **414.4s** | +8.6% |
| Total sliding windows | 147 | 167 | +13.6% (доп. окна из увеличенного overlap) |
| forward_s median (FA2) | 2.10s | 2.12s | ≈ identical |
| forward_s mean | 2.06s | 2.05s | ≈ identical |
| Regions with any fallback | 10 | **3** | -70% |
| Fallback chunks (count) | 19 | **3** | -84% |
| **Fallback vs total chunks** | 19/1114 = **1.7%** | 3/1114 = **0.27%** | **HIT <1% target** |
| Chunks indexed | 1114 | 1114 | identical (deterministic) |

**Run IDs:** `phase12-fa2-260519` (overlap=0.15), `phase12-overlap25-260519` (overlap=0.25).

**Вывод:** `--sliding-overlap 0.25` рекомендуется как **новый default для production** Phase 2/3 на Cyrillic BSL. Закрывает §4.4 criterion `average fallback% < 1%`. Стоимость 8.6% wall-clock — приемлема (на 50 god-objects: ~5min → ~5.4min на самый большой модуль).

**Следующий шаг:** изменить `Qwen3STEmbedder.DEFAULT_SLIDING_OVERLAP_RATIO = 0.15` → `0.25` после Phase 4 benchmark (нельзя поднимать default без подтверждения что recall не падает; overlap-zone имеет потенциальное влияние на boundary chunks).

### 1.2.4 Full-scope A/B на 438 модулей (2026-05-20, CommonModules subset)

Прогон `scripts/reindex_bsl_qwen3.py` на полном `ИБTransportManagementDevelop/Конфигурация/src/CommonModules/` (438 файлов, включая 11 god-object'ов >500KB) в двух конфигурациях с одинаковым overlap=0.25 + FA2:

| Метрика | phase12 (P1+P2, region-aware **OFF**) | phase123 (P1+P2+P3, region-aware **ON, default**) | Δ |
|---|---|---|---|
| Files / Symbols / Chunks | 438 / 12 802 / 14 380 | 438 / 12 802 / 14 380 | identical (deterministic) |
| Wall-clock total | 64.9 min (3893s) | **59.5 min (3571s)** | **-8%** |
| Total sliding forward time | 3194s | **2332s** | **-27%** ⭐ |
| Sliding invocations (regions требующих sliding) | 214 | 256 | +20% (region grouping создаёт больше, но мельче) |
| Total sliding windows | 1607 | 1223 | -24% (меньше окон на регион) |
| forward_s median | 2.07s | 2.06s | ≈ identical |
| forward_s mean | 1.99s | 1.91s | -4% |
| forward_s max | 2.29s | 2.22s | -3% |
| Single_pass events (regions ≥2s) | 12 | (similar count, не критичный сигнал) | — |
| Fallback chunks (count) | 29 | 26 | -10% |
| Fallback groups (regions with any fallback) | 24 | 23 | — |
| **Fallback vs ALL indexed chunks** | **0.20%** (29/14380) | **0.18%** (26/14380) | both << 1% target ✅ |

**Run IDs:** `phase12-bench-260519`, `phase123-bench-260520`. Worst-case per module: phase12 — 5.9% (ОбновлениеИнформационнойБазыБИД, single chunk fallback из 17); phase123 — несколько 100% (1/1) entries для 1-chunk регионов где единственный chunk не влез — нормально, нивелируется тем что total denominator больше (14 380 chunks).

**Выводы:**

1. **Phase 3 (region-aware) — production winner.** Не только хитает quality criterion (0.18% fallback vs 0.20%), но и **экономит 27% GPU forward time** (3194s → 2332s) — критично при масштабировании на full `ИБTransportManagementDevelop` (2098 файлов → ~5ч с region-aware vs ~7ч без).
2. **§4.4 criterion `average fallback < 1%` — выполнен с большим запасом** для обоих вариантов. Region-aware ещё больше снижает уровень.
3. **§4.2 wall-clock estimate `~4-6h` для production reindex** — реалистичен с phase123 + FA2: ~5ч на 2098 файлов экстраполяционно.
4. **Защитник Phase 3 vs Phase 1+2 only:** wall-clock benefit перевешивает minor extra complexity (`_group_chunks_for_late(region_aware=True)` — уже реализован, ON by default).

**Что осталось до production rollout (Phase 5):**
- Phase 4 retrieval-quality benchmark (golden set готов scaffold-уровне, генератор написан, blocked на LLM API auth — см. session log 2026-05-20).
- После Phase 4 PASS — alias swap `bsl_code_v4_late` → `bsl_phase123_bench` (или новый full reindex production-scale).

### 1.2.5 Phase 4 quality benchmark (2026-05-20) — **ВАЖНО: reverses §1.2.4 default**

Запустили `pytest tests/benchmarks/test_bsl_retrieval_quality.py -v -s` против 3 коллекций (baseline = production `bsl_code_v4_late`, `phase12_bench` без region-aware, `phase123_bench` с region-aware) на manually-crafted 12-query golden set из CommonModules (8 small/medium, 1 god_object, mix). Search через прямой `client.query_points` + Qwen3 query prompt — без reranking, чистый dense retrieval.

| variant | small | medium | god_object | **overall** | NDCG@10 | MRR |
|---|---|---|---|---|---|---|
| baseline (current production, no FA2) | 0.200 | 0.750 | 1.000 | 0.583 | 0.334 | 0.253 |
| **phase12 (P1+P2 only + FA2 + overlap=0.25)** | **0.800** ⭐ | 0.750 | 1.000 | **0.833** ⭐ | **0.512** | **0.413** |
| phase123 (P1+P2+P3 region-aware + FA2 + overlap=0.25) | 0.800 | **0.500** ❌ | 1.000 | 0.750 | 0.430 | 0.331 |

**Acceptance gate result:** phase12 PASSES (no regression, +25pp overall). **phase123 FAILS** at medium slice: recall@10 0.750 → 0.500 = -25pp regression (fail threshold = -3pp per §6.4 spec).

**Driving findings:**

1. **Phase 1+2 (sliding + FA2 + overlap=0.25) — production-ready, big quality win.** +25pp overall recall@10, +60pp on small modules. Most of the gain is from FA2 (which forced full Late Chunking on every chunk rather than fallback to std pooling without FA2 — see §1.2.2/3 confirmation).
2. **Phase 3 region-aware hurts retrieval on medium modules.** The §4.5 quality risk warning («chunks на границе окна теряют context») materialized at scale: region grouping shrinks parent_text per forward pass, defeats Late Chunking's module-context advantage on multi-region medium modules. -25pp medium recall is unacceptable for production.
3. **§1.2.4 conclusion REVERSED:** 27% GPU forward-time savings from region-aware ≠ free lunch. Quality cost on medium slice outweighs wall-clock benefit.
4. **§4.4 success criteria — Phase 4 final check:** ✅ for phase12 (no regression vs baseline). ❌ for phase123 (medium-slice regression).

**Updated Phase 5 rollout target: `phase12` configuration** — `--pooling-mode late-chunking --enable-fa2 --sliding-overlap 0.25 --no-region-aware`. Default in `scripts/reindex_bsl_qwen3.py` should KEEP `region_aware=True` for backwards compat but production reindex commands MUST add `--no-region-aware` until Phase 3 issue is diagnosed.

**Open question for next session:** why region-aware degrades quality only on medium slice (not small or god_object)? Hypotheses: (a) god_objects need sliding anyway, so region splitting doesn't matter; (b) small modules are 1-region, no split happens; (c) medium modules have 3-10 regions of similar size, splitting creates fragmented embeddings. Investigation: per-query analysis of top-10 retrieved chunks comparing phase12 vs phase123 on the failing queries.

### 1.2.6 Phase 4 reproduction на 50 queries (2026-05-20 evening) — **CRITICAL REVERSAL of §1.2.5**

Расширенный golden set (50 queries вместо 12, ручная курация из CommonModules, 20 small / 20 medium / 10 god_object) переиграл бенчмарк с радикально иным результатом:

| variant | small | medium | god_object | overall |
|---|---|---|---|---|
| baseline (production `bsl_code_v4_late`, no FA2) | 0.400 | 0.700 | 0.700 | 0.580 |
| **phase12** (P1+P2+FA2+overlap=0.25, no region-aware) | **0.650** (+25pp) | **0.600** (-10pp ❌) | **0.500** (-20pp ❌❌) | 0.600 (+2pp) |
| phase123 (P1+P2+P3+FA2+overlap=0.25, region-aware ON) | **0.700** (+30pp) | 0.600 (-10pp ❌) | **0.400** (-30pp ❌❌❌) | 0.600 |

**Acceptance gate result — BOTH variants FAIL multiple slices:**
- phase12: medium FAIL (+10pp regression > 3pp threshold), god_object FAIL (+20pp > 5pp threshold)
- phase123: medium FAIL (+10pp), god_object FAIL (+30pp >> 5pp)

**Honest reading:**
1. **§1.2.5 (12 queries) was statistically underpowered.** Sample variance dominated the signal. phase12 looked +25pp overall, reality at 50 queries is +2pp.
2. **Phase 1/2/3 changes are NOT a clear win.** The big wins on small slice (likely from FA2 properly enabling Late Chunking vs baseline's std-pooling fallback) come at cost of medium/god_object regression.
3. **Phase 5 rollout BLOCKED.** Cannot swap production `bsl_code_v4_late` for phase12/phase123 — quality regression on the majority of real-world queries (medium+god_object > 60% of corpus).

**Confounding factors that need investigation before any rollout:**
- **Scope mismatch**: baseline has full `ИБTransportManagementDevelop` (54 800 chunks), variants have CommonModules-only (14 380). Even though queries target CommonModules, baseline competes against more chunks yet wins on medium/god_object → suggests variant embeddings ARE worse, not just unfair comparison.
- **FA2 numerical drift**: variants use FA2, baseline did not. Possible accumulated FP differences on long sequences.
- **Sliding window context fragmentation**: large modules get split into windows → boundary chunks lose "other-side" context.
- **`max_seq_length=8192` vs old 4096**: even chunks that fit in 4096 get different attention patterns at higher max length.

**Required follow-up (separate session, ~2-3 days):**
1. ~~Reindex baseline scope (CommonModules ONLY)~~ — addressed via cheap-path scope filter (see §1.2.7), confounder ruled out
2. Per-query analysis on the 20-30 failing queries: what does phase12 retrieve vs baseline? Is it relevant-but-wrong-line, or irrelevant?
3. Test Phase 1 alone (max_seq_length=8192 only, no overlap change, no region-aware) — isolate which change causes which delta
4. Consider whether the fallback% improvement (0.20% vs 5-10%) is worth the recall regression — maybe NOT for production retrieval workloads

**Updated Phase 5 status: BLOCKED indefinitely** until §1.2.6 questions resolved. Do not alias-swap based on §1.2.4 wall-clock or §1.2.5 quality data — both were validated only at small scale.

### 1.2.7 Cheap-path investigation (2026-05-20 night, same session) — scope confounder RULED OUT

After §1.2.6 the obvious next question was: is the regression real, or is it a scope artifact? baseline `bsl_code_v4_late` has 54 800 chunks (full `ИБTransportManagementDevelop`), variants have 14 380 (CommonModules only). Different corpora can't be compared directly.

**Cheap-path fix** (no GPU, ~5 min): patched `search_variant()` in [tests/benchmarks/test_bsl_retrieval_quality.py](../../tests/benchmarks/test_bsl_retrieval_quality.py) to apply a `module_path~"CommonModules"` Qdrant filter on every query. Filter is no-op on phase12/phase123 (already only CommonModules) but restricts baseline to the same effective scope.

| variant | small | medium | god_object | overall |
|---|---|---|---|---|
| baseline **WITH filter** | 0.350 (was 0.400 unfiltered) | 0.700 (same) | **0.800** (was 0.700) | 0.580 (same) |
| phase12 | 0.650 (+30pp) | 0.600 (-10pp) | 0.500 (**-30pp** worse with fair baseline) | 0.600 (+2pp) |
| phase123 | 0.700 (+35pp) | 0.600 (-10pp) | **0.400** (**-40pp** ❌❌❌) | 0.600 (+2pp) |

**Result:** filtering baseline to CommonModules INCREASED its god_object score (0.700 → 0.800) — i.e. removing non-CommonModules competing chunks made baseline EASIER to win for god_object queries. The variant regression vs fair baseline is therefore even WIDER than §1.2.6 reported. Variants are objectively worse for medium/god_object, NOT a scope artifact.

**Honest interpretation of why variants help small but hurt larger slices:**

1. **Small modules (1 chunk groups)**: FA2 + Late Chunking properly applied → chunk gets full module context → +30pp. Baseline often fell back to std pooling here (no FA2 means Late Chunking probe might overflow max_seq_length, no overlap means tighter sliding) → worse small-module embeddings.
2. **Medium modules (multi-region, multi-window)**: variant sliding window splits parent_text → each chunk loses "other-side" context. Baseline without sliding processes the whole thing in one truncated pass — for medium modules that *just barely fit*, baseline gets MORE context per chunk. -10pp regression.
3. **God-objects (many windows + region-aware = many groups)**: variants split the parent into 30+ windows; the chunk embedding accumulates over a few thousand tokens of contextual neighbours but loses the long-range structure. Baseline truncates to max_seq_length=4096 — fewer tokens but more cohesive context. -20-40pp.

**Implication for production**: the Phase 2 sliding window FIXES the «fallback to std pooling» quality issue (good — small slice +30pp confirms it), but introduces a NEW quality issue (context fragmentation in sliding). The §4.4 success criteria treated «fallback%» and «recall@10» as proxies for the same thing — they're NOT.

**Next-session investigation (still required):**
1. Per-query analysis: for the failing medium/god_object queries, what does variant retrieve at rank 1-5? Is the expected chunk at rank 11+ (silently dropped) or completely off-grid?
2. Phase 1 isolation reindex: max_seq_length=8192 alone (no FA2, no overlap, no region-aware) → does Phase 1 alone cause the regression, or only when combined with sliding/overlap/FA2?
3. Decision: roll back Phase 2 sliding (keep Phase 1 max_seq_length bump only), or accept quality regression as cost of fallback% reduction?

**Phase 5 status: still BLOCKED**, but root cause is now narrower — context fragmentation in sliding window, not scope artifact.

### 1.2.8 std_pool isolation — Phase 5 UNBLOCKED (2026-05-20 night)

Запустили std-pool reindex CommonModules (same scope as variants) с `--pooling-mode standard --enable-fa2` (без Late Chunking совсем). Wall-clock 39.9 min (`std_pool-isolation-260520`, 14 380 chunks, identical to phase12/123). Final 4-way benchmark:

| variant | small | medium | god_object | overall |
|---|---|---|---|---|
| baseline `bsl_code_v4_late` (production now, old config) | 0.350 | 0.700 | 0.800 | 0.580 |
| **std_pool `bsl_std_pool_bench`** (std pooling + FA2) | **0.850** 🚀 | **0.900** 🚀 | **0.900** 🚀 | **0.880** 🚀 |
| phase12 (P1+P2+FA2+overlap=0.25+no-region-aware) | 0.650 | 0.600 | 0.500 | 0.600 |
| phase123 (P1+P2+P3 region-aware ON) | 0.700 | 0.600 | 0.400 | 0.600 |

**std_pool DOMINATES every metric on every slice:**
- Δ vs production baseline: **+30pp overall**, +50pp small, +20pp medium, +10pp god_object
- Δ vs phase12 (current best LC variant): **+28pp overall**, +40pp god_object, +30pp medium, +20pp small

**This INVERTS the roadmap's foundational assumption.** Phase 8.12.9 introduction of Late Chunking was based on the «Jina arXiv:2409.04701 +64% recall» claim. That paper measured on long-document English/markdown corpora where parent context matters. **For BSL retrieval (Cyrillic identifiers + procedural code), std pooling per-chunk is dramatically better than sliding-window Late Chunking.**

**Root cause synthesis (combining §1.2.6 + §1.2.7 + §1.2.8):**

1. BSL chunks are SHORT and SELF-CONTAINED (typical procedure = 20-100 lines). They DON'T benefit from module-wide context the way English paragraph chunks benefit from document-wide context.
2. Late Chunking pools hidden states OVER a window of context. For a short BSL chunk, that pooling DILUTES the chunk's specific signal with surrounding noise. The chunk embedding becomes a generic "this is BSL code in this area" rather than "this procedure does X".
3. Sliding window splits this further on long modules — fragments the already-diluted context across multiple passes, each with different neighbours.
4. Standard pooling embeds each chunk INDEPENDENTLY with the model's full attention focused on just that chunk → cleaner, more discriminative embedding per chunk.

**This finding obsoletes §1.2.1-§1.2.7 production conclusions.** Phase 1/2/3 entire approach (extending max_seq_length to enable more Late Chunking) was solving the wrong problem.

### Phase 5 (production rollout) — UNBLOCKED, new target

**Decision: roll out std_pool, drop Late Chunking entirely.** Target config:

```bash
python scripts/reindex_bsl_qwen3.py \
    --project "ИБTransportManagementDevelop/Конфигурация/src" \
    --embedder qwen3-st \
    --pooling-mode standard \
    --enable-fa2 \
    --collection bsl_code_v4_late_v2 --recreate \
    --batch-size 32 --buffer-size 256
```

ETA: ~3-5h on full ИБTransport (2098 files) — std pooling without sliding is significantly faster than phase12/123 runs.

**Alias swap protocol** (per memory `reference_qdrant_collection_aliases`):
1. Snapshot `bsl_code_v4_late` (Qdrant snapshot API) — rollback insurance
2. Reindex full scope → `bsl_code_v4_late_v2`
3. Verify with benchmark (run on full ИБTransport scope, not just CommonModules — re-craft golden set or use existing)
4. Alias swap: `bsl_code_v4_late` → `bsl_code_v4_late_v2`
5. Drop old `bsl_code_v4_late_v1` after 7-14 days grace

**Need from user before Phase 5 launch:** explicit "go" on production swap + confirmation timing (5h GPU contention).

### 1.3 Почему `max_seq_length=4096`

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

Поддерживает **32K context natively** ([voyage-code-3 blog](https://blog.voyageai.com/2024/12/04/voyage-code-3/)) — не нуждается в sliding window для нашего размера модулей. «+13.80% over OpenAI v3-large на 32 code retrieval datasets». Альтернативная стратегия для долгосрочного перехода (closed-source API, deferred — см. [chapter 31.6 §7](../framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md)).

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

- [x] Fallback% на god-objects < 5% — **достигнуто 0.27%** (§1.2.3 с `--sliding-overlap 0.25`)
- [x] Average fallback% < 1% — **достигнуто 0.27%** на single-module test (§1.2.3); подтвердить full reindex'ом
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

- [ ] [chapter 31.6](../framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md) §3 — update decision flowchart (full-quality reindex теперь включает Phase 2/3)
- [ ] [chapter 31.3](../framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.3_Pipeline_индексации.md) — update команды (`--pooling-mode late-chunking` теперь by default Region-aware)
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

- [chapter 31.6 Варианты индексации и типичные ошибки](../framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md) — текущая матрица, типичные ошибки
- [chapter 31.3 Pipeline индексации](../framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.3_Pipeline_индексации.md) — production команды (будет обновлён после Phase 5)
- [chapter 04.9 Matryoshka Embeddings](../framework%20documentation/2_КОНТЕКСТ/2.2_ПОИСК/04.9_Matryoshka_Embeddings.md) — параллельная оптимизация (MIGRATE-3 + REJECT-3, **НЕ затрагивает BSL**)
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
