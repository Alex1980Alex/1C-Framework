# LLM Agent Memory Systems — ведущие практики (GitHub, 2026-07)

> Собрано 2026-07-05 для аудита главы 5_ПАМЯТЬ. Источники: mem0, Letta (MemGPT), Zep/Graphiti, LangMem
> (canonical-репо через WebFetch — ecosystem_scan 30-дневное окно их не ловит, freshness-gap).

## Сводка паттернов лидеров

### mem0 (mem0ai/mem0)
- **Single-pass ADD-only extraction** (алгоритм 2026-04): один LLM-вызов, БЕЗ UPDATE/DELETE в hot-path —
  конфликты снижаются аддитивным дизайном, а не rewrite'ом.
- **Multi-signal retrieval**: semantic + BM25 + entity-matching, скорятся параллельно и фьюзятся.
- **Entity linking**: сущности извлекаются, эмбеддятся и линкуются между воспоминаниями (retrieval boost);
  дедуп через entity resolution, а не merge записей.
- **Time-aware retrieval**: ранжирование правильного датированного экземпляра (current state vs past vs planned).
- **Уровни памяти**: user-level / session-level / agent-level.
- Agent-generated факты — first-class, если подтверждены действиями.

### Letta / MemGPT (letta-ai/letta, docs.letta.com)
- **Иерархия**: core memory blocks (рабочая, редактируемые лейблированные блоки human/persona) →
  archival (долгосрочная) → recall (история).
- **Self-editing memory**: агент сам редактирует свои блоки инструментами.
- **MemFS (V2)**: память как **git-tracked файловая система** + «agent dreaming» —
  фоновая консолидация в sleep-time (не в hot-path).
- Compaction для long-running executions.

### Zep / Graphiti (getzep/graphiti)
- **Би-темпоральная модель**: у факта окно валидности (когда стал истинным / когда супersед);
  устаревшие факты **инвалидируются, не удаляются** — полная темпоральная история.
- **Episodes как provenance**: сырые вводы = ground truth, каждый derived-факт трассируется к источнику.
- **Инкрементальность**: новые данные интегрируются сразу, без batch-recompute (контраст с GraphRAG).
- **Hybrid retrieval**: semantic + BM25 + graph traversal (без LLM-суммаризации на пути чтения).
- **Prescribed + learned ontology**: типы сущностей/рёбер задаются Pydantic-моделями, структура дорастает из данных.
- **Оценка на бенчмарках**: LoCoMo, LongMemEval — memory-качество меряется, не декларируется.

### LangMem (langchain-ai/langmem)
- **Hot-path vs background**: инструменты записи в диалоге + асинхронный memory manager
  (extract/consolidate/update вне потока разговора).
- **Storage agnosticism**: любой BaseStore (InMemory/Postgres).
- **Композиция примитивов** вместо монолита; prompt-оптимизация из памяти.

## Кросс-паттерны (что делают ВСЕ лидеры)
1. **Разделение hot-path (дёшево, additive) и background-консолидации** (mem0 ADD-only, Letta dreaming, LangMem manager).
2. **Инвалидация вместо удаления** + темпоральные окна (Graphiti bi-temporal; mem0 time-aware).
3. **Provenance**: derived-знание трассируется к сырому источнику (Graphiti episodes; наша аналогия — citations в курируемой памяти, ADR-011).
4. **Hybrid retrieval из ≥3 сигналов с фьюжном** (mem0, Graphiti; наш RRF k=60 — соответствует).
5. **Измеримость**: бенчмарки памяти (LongMemEval/LoCoMo) как gate, не вручную-заявленное качество (наш golden-set tune_memory_surfacing.py — частичный аналог).
6. **Git-tracked память** (Letta MemFS) — версии/аудит/rollback дёшево (наш wiki-слой docs/wiki + auto-git-save — близко).

## Применимость к нашему src/memory (первичная оценка)
- Соответствуем: hybrid RRF-фьюжн, confidence decay (Beta-posterior), карантин skill-learning, citations (ADR-011), event-log/audit.
- Пробелы-кандидаты: (а) нет би-темпоральной инвалидации (у нас archived=hard-exclude, но нет valid_from/valid_to);
  (б) консолидация/дедуп больше в hot-path хуков, чем в背景-каденсе; (в) нет memory-бенчмарка типа LongMemEval
  (golden-set — про surfacing, не про end-to-end память); (г) entity linking между записями отсутствует.
