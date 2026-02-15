# Search Pipeline Debug

## Когда использовать
- "почему поиск не находит", "низкое качество поиска", "отладка search"
- "score debug", "BM25 vs vector", "reranking не работает"
- Любые проблемы с качеством/скоростью поиска

## Стратегии поиска

| Стратегия | Класс | Латентность | Когда использовать |
|-----------|-------|------------|-------------------|
| `vector` | VectorSearchStrategy | 400-500ms | Семантический поиск |
| `bm25` | BM25SearchStrategy | 5-14ms | Точные термины |
| `hybrid` | HybridSearchStrategy | 500-700ms | По умолчанию (RRF: dense+sparse) |
| `section_first` | SectionFirstPipeline | 200-400ms | Вопросы про конкретный раздел |
| `mmr` | MMRSearchStrategy | 500-600ms | Нужна разнообразность |
| `lightrag` | LightRAGStrategy | 600-900ms | Сущности и связи |
| `graphrag_global` | GraphRAGGlobalStrategy | 5-10s | Тематические обзоры |

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

## Файлы
- Менеджер: `src/pdf_framework/search/manager.py`
- Стратегии: `src/pdf_framework/search/strategies/`
- BM25: `src/pdf_framework/search/bm25_store.py`
- Пайплайны: `src/pdf_framework/search/pipelines/`
- Реранкинг: `src/pdf_framework/search/reranking/`
- Конфиг: `src/pdf_framework/config/search.py`
