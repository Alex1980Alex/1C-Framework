---
name: search-pipeline-debug
description: "Search Pipeline Debug — отладка и выбор стратегии поиска. ИСПОЛЬЗУЙ когда поиск не находит результаты, низкое качество поиска, нужно сравнить BM25 vs vector, отладить reranking, выбрать стратегию. Триггеры: 'поиск не находит', 'низкое качество поиска', 'отладка search', 'score debug', 'BM25 vs vector', 'reranking', 'какую стратегию', 'search strategy', 'hybrid search'. НЕ для индексации (→ indexing-pipeline)."
---

# Search Pipeline Debug

## Когда использовать
- "почему поиск не находит", "низкое качество поиска", "отладка search"
- "score debug", "BM25 vs vector", "reranking не работает"
- "какую стратегию выбрать", "как искать", "search strategy"
- Любые вопросы о поиске: использование, выбор, отладка

---

## Для пользователя — выбор стратегии

### Decision Tree

```
Что нужно?
├─ Точный термин/фраза          → bm25 (5 мс)
├─ Семантический смысл           → vector (400 мс)
├─ Лучшее качество               → hybrid (500 мс) ← РЕКОМЕНДУЕТСЯ
├─ Поиск в конкретном разделе    → section_first (50-100 мс)
├─ Разнообразие результатов      → mmr (500 мс)
├─ Сущности и связи              → graphrag_local (1-3 с)
├─ Тематический обзор            → graphrag_global (5-15 с)
├─ Автоматический выбор          → adaptive (авто)
└─ Не знаю                       → hybrid (default)
```

### 16 стратегий — полная таблица

| # | Стратегия | Скорость | Качество | Когда использовать |
|---|-----------|----------|----------|-------------------|
| 1 | `vector` | 400-500ms | Хорошее | Семантический поиск |
| 2 | `bm25` | **5 мс** | Среднее | Точные термины, ключевые слова |
| 3 | `hybrid` | ~500ms | **Лучшее** | По умолчанию (Vector + BM25 + Graph, RRF) |
| 4 | `graph` | Средняя | Хорошее | Поиск по графу знаний |
| 5 | `mmr` | 500-600ms | Хорошее | Diversity (λ = `--diversity 0.5`) |
| 6 | `two_stage` | Средняя | Высокое | Recall → FlashRank reranking |
| 7 | `adaptive` | Зависит | Высокое | Автоклассификация → выбор стратегии |
| 8 | `graphrag_local` | 1-3s | Высокое | Local community search |
| 9 | `graphrag_global` | 5-15s | Высокое | Global map-reduce по communities |
| 10 | `graphrag_light` | 600-900ms | Хорошее | LightRAG — 50x дешевле Full GraphRAG (Phase 38) |
| 11 | `graphrag_auto` | Зависит | Высокое | Авто-выбор Light vs Full GraphRAG (Phase 38) |
| 12 | `auto_merge` | Средняя | Хорошее | Parent-Child retrieval |
| 13 | `raptor` | Средняя | Хорошее | Иерархические суммаризации |
| 14 | `section_first` | 50-100ms | Высокое | BM25 по заголовкам → scoped hybrid |
| 15 | `visual` | Средняя | Хорошее | ColPali visual embeddings (Phase 55) |
| 16 | `web_search` | 1-3s | Зависит | Fallback на web при пустых локальных результатах (Phase 37) |

> **Примечание:** Self-RAG — это агент (`ask --stream`), а не стратегия поиска. Используйте `agent-orchestration` скилл.

### CLI примеры

```bash
# Быстрый поиск конкретного термина
python -m src.cli.main search "модуль внешнего соединения" --strategy bm25

# Лучшее качество (рекомендуется)
python -m src.cli.main search "роли и права доступа" --strategy hybrid

# Поиск по разделу документа
python -m src.cli.main search "справочники" --strategy section_first

# Разнообразие результатов
python -m src.cli.main search "настройка" --strategy mmr --diversity 0.7 -k 10

# Автовыбор стратегии
python -m src.cli.main search "сравните типы регистров" --strategy adaptive --verbose

# Концептуальный обзор
python -m src.cli.main search "архитектура платформы" --strategy graphrag_global
```

### API

```bash
curl -X POST http://localhost:8000/search/ \
    -H "Content-Type: application/json" \
    -d '{"query": "запрос", "strategy": "hybrid", "k": 10}'
```

### Section-First — двухуровневый поиск

1. BM25 по заголовкам (title=10x boost) → определяет доминирующий раздел
2. Hybrid search ограничен этим разделом

```bash
python -m src.cli.main search "справочники" --strategy section_first
# → определит раздел "5.8 Справочники" → scoped hybrid в этом разделе
```

### Turbo Pipeline (автоматический)

```
simple (90%):  BM25 early termination → 125 мс (31x ускорение)
moderate:      Hybrid + Reranking → 3-5 с
complex:       Decomposition + Multi-step → 10-30 с
```

---

## Internals — отладка и конфигурация

## Стратегии (классы)

| Стратегия | Класс | Латентность |
|-----------|-------|------------|
| `vector` | VectorSearchStrategy | 400-500ms |
| `bm25` | BM25SearchStrategy | 5-14ms |
| `hybrid` | HybridSearchStrategy | 500-700ms |
| `section_first` | SectionFirstPipeline | 200-400ms |
| `mmr` | MMRSearchStrategy | 500-600ms |
| `lightrag` | LightRAGStrategy | 600-900ms |
| `graphrag_global` | GraphRAGGlobalStrategy | 5-10s |

## RRF Fusion (hybrid)

```
score[chunk] = Σ (weight / (rrf_k + rank + 1))
```

Веса: `hybrid_vector_weight=0.5`, `bm25_weight=0.3`, `hybrid_graph_weight=0.2`, `rrf_k=60`

## Ключевые конфиг-параметры

```env
SEARCH__HYBRID_VECTOR_WEIGHT=0.5
SEARCH__BM25_WEIGHT=0.3
SEARCH__BM25_BACKEND=qdrant       # qdrant|fts5|both
SEARCH__BM25_TWO_PASS=false
AGENT__RERANKER_ENABLED=true
AGENT__RERANKER_TYPE=llm           # llm|cross_encoder|colbert
AGENT__SCORE_PREFILTER_THRESHOLD=0.1
```

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| 0 результатов | Пустой BM25 индекс | `GET /documents` → проверить chunk count |
| Низкие vector scores | Dimension mismatch | Проверить `EMBEDDING__MODEL` в .env (1024d для E5) |
| BM25 не находит | Лемматизация/язык | Проверить `bm25_language=russian`, попробовать OR-запрос |
| Reranker timeout | Z.AI proxy latency | Проверить `base_url`, уменьшить `reranker_top_k` |
| Section-first пустой | Неверный section_number | Дебажить `_extract_section_number()`, проверить `section_title` |

## Связанные скиллы

- `framework-config` — все .env переменные поиска
- `framework-cli` — все CLI команды search
- `framework-troubleshooting` — ошибки и performance


## Незадокументированные Search Strategies

- `graph_r_a_g_auto` (src\pdf_framework\search\strategies\graphrag_auto.py)
- `graph_r_a_g_local` (src\pdf_framework\search\strategies\graphrag_local.py)

## Файлы
- Менеджер: [manager.py](src/pdf_framework/search/manager.py)
- Стратегии: [strategies/](src/pdf_framework/search/strategies/)
- BM25: [bm25_store.py](src/pdf_framework/search/bm25_store.py)
- Пайплайны: [pipelines/](src/pdf_framework/search/pipelines/)
- Реранкинг: [reranking/](src/pdf_framework/search/reranking/)
- Конфиг: [search.py](src/pdf_framework/config/search.py)
