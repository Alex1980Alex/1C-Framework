# Phase 26: Turbo Search Pipeline

**Версия:** v0.17.0
**Статус:** РЕАЛИЗОВАНО
**Дата:** 2026-02-11

## Обзор

Каскадный поисковый пайплайн с early termination и rule-based классификацией запросов.
Основан на анализе 15 GitHub-решений (LlamaIndex, LangChain, Haystack, RAGFlow, fastRAG, Kotaemon и др.).

## Проблема

Спекулятивное выполнение (запуск стратегий параллельно с классификацией) протестировано и отвергнуто — классификация LLM (~1.3s) составляет лишь 10% общего времени. По закону Амдала, оптимизация 10%-компонента даёт максимум 11% ускорения.

Индустрия не использует спекулятивное выполнение для retrieval. Ни LlamaIndex, ни LangChain, ни Haystack не реализовали его. Вместо этого используются:
1. **Always-on fusion** — все стратегии параллельно + RRF
2. **Cascading with early termination** — выход на первом достаточно хорошем уровне
3. **Fast classification** — rule-based вместо LLM

## Архитектура

```
Query → Semantic Cache (5ms) → HIT? → Return
              │ MISS
              ▼
     Rule-based Classify (~0ms, 90% покрытие)
      ┌───────┼────────┬──────────┐
   simple  moderate  complex  thematic
      │       │        │         │
      ▼       │        │         │
 BM25 probe   │        │         │
 (15ms)       │        │         │
 score>0.7?   │        │         │
 ┌──┴──┐      │        │         │
YES    NO     │        │         │
 │     │      │        │         │
 ▼     ▼      ▼        ▼         ▼
RETURN Hybrid Hybrid  Parallel  GraphRAG
(125ms) no-RR  +RR   decomp    global
        (250ms)(3-5s) (5-8s)   (varies)
```

## Компоненты

### 1. Rule-based Fast Classifier

**Файл:** `src/pdf_framework/search/routing/classifier.py`
**Метод:** `classify_fast(query) -> QueryClassification | None`

Покрытие: **90%** запросов за **0ms** (вместо LLM 0.5-1.3s).

Правила (приоритет сверху вниз):
- **Thematic:** "обзор", "основные темы", "резюме", "краткое содержание"
- **Complex:** "сравни", "отличия", "перечисли все", "пошагово"
- **Simple:** "что такое X" (≤8 слов), запросы ≤3 слов
- **Moderate:** "как", "почему", "зачем", "каким образом"
- **None** → fallback на LLM Haiku

### 2. BM25 Early Termination

**Файл:** `src/pdf_framework/search/strategies/adaptive.py`
**Метод:** `_try_bm25_early()`

Для simple-запросов: сначала BM25 поиск (~15ms). Если top score ≥ 0.7 и найдено ≥ min(k, 2) результатов → возвращаем сразу, пропуская vector search, graph search и reranking.

### 3. Parallel Sub-Queries

**Файл:** `src/pdf_framework/search/strategies/adaptive.py`
**Метод:** `_execute_decomposed_search()`

Заменён последовательный `for`-цикл на `asyncio.gather(*tasks)` для параллельного выполнения подзапросов.

### 4. Parallel Multi-Query Expansion

**Файл:** `src/pdf_framework/search/manager.py`
**Метод:** `search()` (ветка `len(queries) > 1`)

Заменён последовательный `for`-цикл на `asyncio.gather(*tasks)` для параллельного выполнения расширенных запросов.

## Настройки

**Файл:** `src/pdf_framework/config.py` (`AdaptiveRAGSettings`)

| Параметр | Значение | Описание |
|----------|----------|----------|
| `fast_classify_enabled` | `True` | Rule-based pre-classifier |
| `bm25_early_termination` | `True` | BM25 fast path для simple |
| `bm25_early_threshold` | `0.7` | Min BM25 score для early return |
| `parallel_decomposition` | `True` | asyncio.gather для sub-queries |
| `parallel_expansion` | `True` | asyncio.gather для expanded queries |

## Результаты тестирования

### Реальный запрос: "Отчеты и обработки"

| Стратегия | Время | Ускорение |
|-----------|-------|-----------|
| **Turbo (BM25 early)** | **125ms** | **baseline** |
| BM25 only | 230ms | 0.5x |
| Hybrid (no rerank) | 7164ms | 0.017x |
| Hybrid + rerank | 3878ms | 0.032x |

**Turbo vs Hybrid+Rerank = 31x ускорение** при том же качестве результатов.

### Батч-тест (7 запросов)

| Тип | Запрос | Время | Стратегия |
|-----|--------|-------|-----------|
| Simple | что такое журнал документов | 134ms | bm25_early |
| Simple | регистр накопления | 191ms | bm25_early |
| Simple | справочник | 178ms | bm25_early |
| Moderate | как создать подчиненный справочник | 165ms | hybrid (cache) |
| Moderate | почему нужны регистры сведений | 10773ms | hybrid + rerank |
| Complex | сравни регистр сведений и регистр накопления | 20524ms | decomposed |
| Thematic | обзор главы про справочники | 194ms | graphrag_global |

### Покрытие fast classifier

Протестировано на 10 запросах: **90% покрытие** (9/10 классифицированы rule-based за 0ms).

## Файлы изменений

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/config.py` | +5 настроек turbo pipeline |
| `src/pdf_framework/search/routing/classifier.py` | +`classify_fast()`, обновлён `classify()` |
| `src/pdf_framework/search/strategies/adaptive.py` | +`_try_bm25_early()`, parallel sub-queries |
| `src/pdf_framework/search/manager.py` | parallel multi-query expansion |

## Источники

Основано на анализе 15 решений из GitHub:
1. LlamaIndex QueryFusionRetriever (46.9K stars) — asyncio.gather + RRF
2. LangChain EnsembleRetriever (126.5K stars) — weighted RRF
3. Haystack AsyncPipeline (24.2K stars) — DAG + DocumentJoiner
4. RAGFlow (73.2K stars) — DB-level fusion
5. fastRAG (1.8K stars) — cascading + early termination
6. Kotaemon (25K stars) — semantic routing cache
7. Canopy (1K stars) — embedding-based routing
8. Speculative Decoding pattern — rule-based + LLM fallback
9. JARVIS/HuggingGPT — parallel sub-tasks
10. ColBERT/RAGatouille — late interaction reranking
