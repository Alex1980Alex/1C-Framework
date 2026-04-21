---
name: wiki-pipeline
description: PDF → Structured Wiki Pages pipeline (Hermes Phase 4). Экспорт graph entities в markdown wiki, incremental sync, reverse sync, поиск через HybridSearchService. Триггеры "wiki exporter", "export graph", "wiki pipeline", "reverse sync", "wiki_exporter", "incremental wiki", "docs/wiki/entities", "export_graph_to_wiki".
---

# wiki-pipeline — PDF → Structured Wiki Pages

Экспорт `GraphStore` (NetworkX/Neo4j) в `docs/wiki/entities/*.md` с wiki-links. Использует `MemoryCube.to_wiki_page()` (Phase 0), `HybridSearchService` (v1.3.3) для индексации, подписку на `IncrementalGraphUpdater` (Phase 6.5).

## Компоненты

| Класс | Файл | Назначение |
|-------|------|------------|
| `WikiExporter` | [src/pdf_framework/indexing/wiki_exporter.py:131](../../../src/pdf_framework/indexing/wiki_exporter.py#L131) | Graph entity → markdown через `MemoryCube.to_wiki_page()` |
| `ForwardSyncService` | [wiki_exporter.py:299](../../../src/pdf_framework/indexing/wiki_exporter.py#L299) | Catch-up sync по timestamp (`sync_since`) |
| `IncrementalWikiSync` | [wiki_exporter.py:392](../../../src/pdf_framework/indexing/wiki_exporter.py#L392) | Event-driven sync (подписка на `graph.*` через EventBus) + DLQ + metrics |
| `ReverseSyncService` | [wiki_exporter.py:487](../../../src/pdf_framework/indexing/wiki_exporter.py#L487) | Watchdog: Write в `docs/wiki/entities/*.md` → parse frontmatter → update graph |
| `WikiSearchIndexer` | [wiki_exporter.py:643](../../../src/pdf_framework/indexing/wiki_exporter.py#L643) | Индексация wiki-страниц через `HybridSearchService` (BM25+dense RRF) |

## CLI

[scripts/export_graph_to_wiki.py](../../../scripts/export_graph_to_wiki.py):

```bash
# Полный экспорт графа
python -m scripts.export_graph_to_wiki export-all --output-dir docs/wiki/entities

# Экспорт одной сущности
python -m scripts.export_graph_to_wiki export-entity <ENTITY_ID>

# Incremental sync daemon (подписка на events)
python -m scripts.export_graph_to_wiki sync-incremental

# Индексация wiki в HybridSearchService
python -m scripts.export_graph_to_wiki index-search --wiki-dir docs/wiki/entities

# Проверка консистентности wiki ↔ граф
python -m scripts.export_graph_to_wiki verify
```

Exit codes: `0` success, `1` partial failure, `2` total failure. Флаг `--dry-run` для проверки без записи.

## Шаблоны wiki-страниц

`docs/wiki/templates/`:
- [entity.md](../../../docs/wiki/templates/entity.md) — именованная сущность (Person, Organization, Concept)
- [concept.md](../../../docs/wiki/templates/concept.md) — абстрактное понятие/определение
- [procedure.md](../../../docs/wiki/templates/procedure.md) — процедура/how-to

Frontmatter (обязательно): `unified_id`, `source_pdf`, `confidence`, `created_at`, `type`.

## Интеграция с GraphRAG

[src/pdf_framework/search/strategies/graphrag_light.py:219](../../../src/pdf_framework/search/strategies/graphrag_light.py#L219): `LightRAGStrategy` возвращает `wiki_page_paths` в `SearchResponse.metadata` — ссылки на L3 canonical wiki-страницы, не только entity_id.

## Workflow

```
PDF → [existing Phase 38 LightRAG pipeline] → entity embeddings в Qdrant
                                    │
                                    ▼
                         GraphStore (NetworkX/Neo4j)
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
            WikiExporter.export()         IncrementalGraphUpdater events
                    │                               │
                    ▼                               ▼
         docs/wiki/entities/<id>.md    IncrementalWikiSync.on_event()
                    │                               │
                    ▼                               ▼
          WikiSearchIndexer.index_page() → HybridSearchService (BM25+dense)
                    │
                    ▼
          LightRAGStrategy возвращает wiki_page_paths
```

Reverse sync (L3 = canonical):
```
Write docs/wiki/entities/<id>.md → ReverseSyncService (watchdog)
                                         │
                                         ▼
                           parse frontmatter + body
                                         │
                                         ▼
                    change_detector.py (diff) → graph_store.update()
```

## Идемпотентность

Повторный `export-all` = upsert. `WikiExporter` сравнивает hash frontmatter+body перед записью, пропускает неизменённые страницы. `--overwrite` форсирует перезапись.

## Dead letter queue

`IncrementalWikiSync` держит failed events в памяти (configurable `max_dlq_size`). При рестарте daemon обрабатывает DLQ перед новыми событиями. Логи: `docs/wiki/log.md`.

## Troubleshooting

| Симптом | Причина | Действие |
|---------|---------|----------|
| `docs/wiki/entities/` пустой после `export-all` | GraphStore не инициализирован или пуст | Проверить `await store.initialize()`, запустить индексацию PDF |
| Битые `[[wiki-links]]` в draft | target не экспортирован | `export-entity <target_id>` + `docs-change-tracker` hook детектит |
| `wiki_pages_v1` не появилась | `index-search` не запускался | `python -m scripts.export_graph_to_wiki index-search` |
| Reverse sync не срабатывает | watchdog не подхватил изменения | Проверить что `ReverseSyncService.start()` вызван, fs events включены |
| DLQ растёт | persistent exception в `on_event` | Проверить log.md, исправить entity schema, clear DLQ |

## Eval

Регрессия: existing GraphRAG eval suite должен показывать те же или лучшие метрики precision/recall после wiki export. Бенчмарк:
```bash
python -m scripts.eval_graphrag --compare baseline wiki-enriched
```

## Связанные скиллы

| Скилл | Связь |
|-------|-------|
| `obsidian-vault` | Навигация по wiki через Obsidian, графовый вид |
| `graph-operations` | LightRAG/GraphRAG pipeline (источник entities) |
| `search-pipeline-debug` | Отладка `HybridSearchService` при проблемах с индексацией wiki |
| `memory-unified` | `MemoryCube.to_wiki_page()` / `from_wiki_page()` (Phase 0) |

## Тесты

[tests/unit/pdf_framework/indexing/test_wiki_exporter.py](../../../tests/unit/pdf_framework/indexing/test_wiki_exporter.py) — 17 тестов (WikiExporter, ForwardSync, IncrementalSync, ReverseSync, WikiSearchIndexer). Запуск: `pytest tests/unit/pdf_framework/indexing/test_wiki_exporter.py -q`.

## Spec

[openspec/changes/hermes-llm-wiki/specs/wiki-export-pipeline/spec.md](../../../openspec/changes/hermes-llm-wiki/specs/wiki-export-pipeline/spec.md) — 711 строк, полная спецификация требований (MUST/SHALL/SHOULD).
