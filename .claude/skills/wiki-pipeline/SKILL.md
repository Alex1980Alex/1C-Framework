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
| `WikiPromoter` | [src/memory/librarian/wiki_promoter.py:21](../../../src/memory/librarian/wiki_promoter.py#L21) | L2→L5: скан `learned_patterns`, дедуп по cosine similarity, создание `docs/wiki/drafts/<slug>.md` через `MemoryCube.to_wiki_page()` + лог в `docs/wiki/log.md` |

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

# L2 → L5 promotion (learned_patterns → docs/wiki/drafts/)
python -m scripts.export_graph_to_wiki promote-patterns \
    [--min-confidence 0.8] [--min-usage 5] [--similarity-threshold 0.85]
```

Exit codes: `0` success, `1` partial failure (e.g. no eligible patterns), `2` total failure. Флаг `--dry-run` для export-команд (не для `promote-patterns`).

### Состояние L5 drafts/ (2026-05-14 после fix)

Pipeline активен. До closure session оба ингредиента уже существовали, но не стыковались:

- **Update side (работало):** [`src/memory/vector_memory/server.py:391 handle_apply_pattern`](../../../src/memory/vector_memory/server.py#L391) при каждом MCP-вызове `apply_pattern` инкрементирует поле `application_count` и обновляет `confidence` через bayesian-style delta (`+0.02` при success / `-0.01` при fail, clamp `[0,1]`).
- **Promote side (был сломан):** [`src/memory/librarian/wiki_promoter.py`](../../../src/memory/librarian/wiki_promoter.py) фильтровал `usage_count`, поле которого никто никогда не пишет. Field-name drift — закрыт в session 2026-05-14: WikiPromoter теперь фильтрует канонический `application_count` (constructor arg `usage_threshold` сохранён для back-compat).
- **Wire (добавлено):** [`session-memory-save.py:try_promote_patterns`](../../../.claude/hooks/session-memory-save.py) на Stop вызывает `python -m scripts.export_graph_to_wiki promote-patterns` (timeout 10s, swallows errors, `SESSION_MEMORY_NO_PROMOTE=1` отключает).

Корпус 2026-05-14: 44 точки в `learned_patterns`, 11 имеют `confidence=0.7` + `application_count=0`. До eligible не дотягивают (нужно одновременно `confidence>=0.8 AND application_count>=5`) — но теперь натурально дотянутся по мере MCP `apply_pattern` вызовов с success=true (через ~15 успешных применений у конкретного паттерна `confidence` пересечёт 0.8).

Smoke-test 2026-05-14 (синтетически бампанутый point с conf=0.85 + ac=5): CLI создал `docs/wiki/drafts/<slug>.md`, лог-entry в `docs/wiki/log.md`. Артефакт почищен после verification. См. roadmap [`260514_ROADMAP_WIKI_PROMOTION_GAP.md`](../../../docs/roadmap/260514_ROADMAP_WIKI_PROMOTION_GAP.md) для closure summary.

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
            WikiExporter.export()         IncrementalGraphUpdater.update()
                    │                               │
                    ▼                               ▼
         docs/wiki/entities/<id>.md    EventBus.publish("graph.*")
                                                    │
                                                    ▼
                                        IncrementalWikiSync._listen_loop()
                                                    │
                                                    ▼
                                         handle_event() → ForwardSync
                                                    │
                                                    ▼
                                         WikiSearchIndexer.index_page()
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

**Coverage matrix (53 тестов total, 52 pass + 1 skip; добавлено 26 тестов 2026-05-15):**

- [tests/unit/pdf_framework/indexing/test_wiki_exporter.py](../../../tests/unit/pdf_framework/indexing/test_wiki_exporter.py) — **27 тестов** (WikiExporter 7, sanitize_filename 4, ForwardSync 2, IncrementalSync 2, WikiSearchIndexer 2, ReverseSyncService 9, ReverseSyncRuntimeWatchdog 1 @pytest.mark.slow via `pytest.importorskip("watchdog")`)
- [tests/unit/memory/librarian/test_wiki_decay.py](../../../tests/unit/memory/librarian/test_wiki_decay.py) — **14 тестов** (TestDecayPoint 11: skip-paths + decay formula + clamps + timezone; TestDecayAll 3: counters aggregation + empty + termination)
- [tests/unit/pdf_framework/graph_store/test_networkx_get_relations.py](../../../tests/unit/pdf_framework/graph_store/test_networkx_get_relations.py) — **5 тестов** (outgoing only, empty for missing, properties preserve, no incoming)
- [tests/unit/scripts/test_archive_stale.py](../../../tests/unit/scripts/test_archive_stale.py) — **7 тестов** (qualify, fresh-skip, high-conf-skip, already-archived-skip, missing-frontmatter-skip, collision-suffix, dry-run)

Запуск: `pytest tests/unit/memory/librarian/ tests/unit/pdf_framework/graph_store/test_networkx_get_relations.py tests/unit/pdf_framework/indexing/test_wiki_exporter.py tests/unit/scripts/test_archive_stale.py -q` (slow skipped по default).

## Spec

[openspec/changes/hermes-llm-wiki/specs/wiki-export-pipeline/spec.md](../../../openspec/changes/hermes-llm-wiki/specs/wiki-export-pipeline/spec.md) — 766 строк, полная спецификация требований (MUST/SHALL/SHOULD).
