---
name: post-indexing-analysis
description: Автоматический пост-анализ результатов индексации и сборки графа. Используй когда нужно проанализировать последний индексационный ран, получить отчёт по коллекции Qdrant, графу BSL/Neo4j/graph_embeddings, или обнаружить аномалии (dimension drift, HNSW corruption, dangling calls, orphan nodes). Триггеры '/analyze-run', 'проанализируй последнюю индексацию', 'отчёт по коллекции', 'analyze run', 'анализ графа', 'check call graph', 'analyze graph_embeddings'.
---

# Post-Indexing Analysis

## Когда использовать

| Запрос пользователя | Действие |
|---------------------|----------|
| «проанализируй последнюю индексацию» | `python scripts/analyze_run.py --mode indexing --run-id <последний из jsonl>` |
| «отчёт по коллекции framework_code_v1» | `python scripts/analyze_run.py --mode indexing --run-id <id> --collection framework_code_v1` |
| «проверь граф вызовов BSL» | `python scripts/analyze_run.py --mode graph --source sqlite` |
| «состояние graph_embeddings в Qdrant» | `python scripts/analyze_run.py --mode graph --source qdrant_graph` |
| «метрики Neo4j» | `python scripts/analyze_run.py --mode graph --source neo4j` |
| «где отчёт по последнему ран` | `data/reports/indexing/_latest_<collection>.md` |

## Архитектура

**Триггер**: Stop-хук [`post-indexing-analyzer.py`](../../hooks/post-indexing-analyzer.py) на каждый Claude-Stop читает tail `data/indexing-progress.jsonl`, находит новые `category=run_end` записи (по `run_id`, отсутствующему в `.claude/cache/post-indexing-analyzer-state.json`), и запускает `analyze_run.py` как **detached subprocess** для каждого нового ран'а.

**Анализатор**: [`scripts/analyze_run.py`](../../../scripts/analyze_run.py) → [`scripts/analyzers/`](../../../scripts/analyzers/) — два режима (`indexing`, `graph`), три графовых источника (`sqlite`, `neo4j`, `qdrant_graph`).

**Выход**:
- `data/reports/<mode>/<subject>_<YYYYMMDD_HHMMSS>.md` — основной отчёт
- `data/reports/<mode>/<subject>_<YYYYMMDD_HHMMSS>.json` — sidecar для diff vs prev
- `data/reports/<mode>/_latest_<subject>.md` — копия последнего (быстрый доступ)
- `data/reports/index.jsonl` — append-only реестр всех ран'ов

## Indexing report — что внутри

- **Run identity & CLI** — PID, embedder, batch size, pooling mode, recreate флаг
- **Run end summary** — files/chunks/symbols/embeddings_done из `run_end` payload
- **Stages & timing** — таблица всех `stage_end`, сортировка по duration
- **Discrete events** — `startup`, `file_scan_done`, `parse_error` и т.д.
- **Heartbeat gaps** — max idle_s (warn >60s — возможное зависание)
- **Collection state** — Qdrant introspection (alias-resolved physical name, dim, distance, quantization, on_disk, named_vectors)
- **Quality probes** (lightweight, ~10-30s):
  - L2 norm mean/std/min/max (drift detection — warn >25% vs prev)
  - Zero-vector count
  - Dimension consistency (collection dim vs sample vector len)
  - Self-recall@1 на 10 случайных точках (target ≥0.95; <0.95 = HNSW corruption или named-vector mismatch)
- **Diff vs previous run** — Δpoints, Δduration, norm drift, dimension swap detection

## Graph report — что внутри

**SQLite (`bsl_call_graph.db`)**:
- Таблицы: counts по `modules`, `symbols`, `calls`, `module_metadata`
- Symbols by `symbol_type` (function/procedure/variable)
- Top-15 symbols по incoming calls (наиболее вызываемые)
- Top-15 modules по symbol count (плотность)
- Schema integrity: orphan modules (без symbols), dangling calls (callee без matching symbol)

**Neo4j (bolt://localhost:7687)**:
- Total nodes/relationships, edges/node ratio
- Distribution по labels (`Module`, `Symbol`, `Object`, `Community`)
- Distribution по relationship types (`CALLS`, `BELONGS_TO`, `DECLARES`, `CONTAINS`)
- Top-15 nodes by degree (выявляет hubs, дубли по name)
- Orphan nodes (degree=0)

**Qdrant `graph_embeddings`**:
- Collection state (physical name, points, dim, status)
- Entity vs relation split (по payload)
- Entity types distribution (top-20)
- Top sources distribution (откуда entity извлечены)
- L2 norm summary (mean/std/min/max)

## Аномалии (auto-detection)

| Аномалия | Где детектится | Что значит |
|----------|---------------|------------|
| `run_end отсутствует` | tail JSONL | Индексер упал до `atexit` — heartbeat покажет где |
| `errors > 0` в run_end | `run_end` payload | Pipeline errors |
| `stage X завершился с ошибкой` | `stage_end.ok=false` | Stage threw exception |
| `idle_s > 60s` | heartbeat | Зависание в одной stage |
| `Qdrant introspection failed` | `get_collection` exception | Коллекция битая или Qdrant down |
| `Dimension mismatch` | sample vec len ≠ collection dim | Model swap не догнан |
| `Self recall@1 < 0.95` | search probe | HNSW corruption или named-vector mismatch |
| `L2 norm drift > 25%` | vs prev report | Model swap или renorm policy change |
| `Dangling calls` | SQLite call vs symbol join | Внешние API либо typo в BSL коде |
| `Orphan nodes` | Neo4j degree=0 | Изолированные модули/символы |

## Manual usage

```bash
# Последний indexing run (взять run_id из tail jsonl)
.venv\Scripts\python.exe scripts/analyze_run.py --mode indexing \
  --run-id index_framework-1779345729-bbcff4

# Указанная коллекция (override detection)
.venv\Scripts\python.exe scripts/analyze_run.py --mode indexing \
  --run-id <ID> --collection bsl_code_v4_late

# JSON-only output (для парсинга)
.venv\Scripts\python.exe scripts/analyze_run.py --mode indexing \
  --run-id <ID> --json-only

# BSL call graph (SQLite)
.venv\Scripts\python.exe scripts/analyze_run.py --mode graph \
  --source sqlite --db-path cache/bsl_call_graph.db

# Neo4j (с своими credentials)
.venv\Scripts\python.exe scripts/analyze_run.py --mode graph \
  --source neo4j --neo4j-uri bolt://localhost:7687 \
  --neo4j-user neo4j --neo4j-password <pw>

# Qdrant graph_embeddings
.venv\Scripts\python.exe scripts/analyze_run.py --mode graph \
  --source qdrant_graph --qdrant-collection graph_embeddings \
  --sample-size 500
```

## Hook behaviour

- **Cold-start** (первый запуск, нет state-файла): seed существующих run_ids без анализа, чтобы не залить отчётами всю историю. Эмитит дружелюбный init-message.
- **Normal flow**: tail JSONL → новые run_ends → детачит analyzer для каждого → emit `system_message` со списком запущенных + ссылкой на `_latest_<collection>.md`.
- **Dedup**: каждый run_id в `processed_run_ids` (FIFO cap 500). Повторный fire безопасен.
- **Cap**: max 5 analyzer'ов за один Stop (защита от dump'а после долгого batch индексирования).
- **Detached**: `subprocess.Popen` с `DETACHED_PROCESS | CREATE_NO_WINDOW` (Win) — хук возвращает за <2с, analyzer работает в фоне ~10-30с.

## Файлы
- Entry: [`scripts/analyze_run.py`](../../../scripts/analyze_run.py)
- Analyzers: [`scripts/analyzers/`](../../../scripts/analyzers/)
  - [`base.py`](../../../scripts/analyzers/base.py) — `AnalyzerBase`, `ReportSpec`
  - [`indexing.py`](../../../scripts/analyzers/indexing.py) — `IndexingAnalyzer`
  - [`graph.py`](../../../scripts/analyzers/graph.py) — `GraphAnalyzer` (3 source)
  - [`report_writer.py`](../../../scripts/analyzers/report_writer.py) — Markdown + JSON
- Hook: [`.claude/hooks/post-indexing-analyzer.py`](../../hooks/post-indexing-analyzer.py)
- Reports: `data/reports/{indexing,graph}/`
- State: `.claude/cache/post-indexing-analyzer-state.json`
- Source events: `data/indexing-progress.jsonl` (генерится `_progress.py`)
- Doc chapter: [`docs/framework documentation/38_AUTO_REPORTS/`](../../../docs/framework%20documentation/38_AUTO_REPORTS/)

## Related skills
- [`indexing-pipeline`](../indexing-pipeline/SKILL.md) — pipeline upstream
- [`qdrant-operations`](../qdrant-operations/SKILL.md) — collection alias resolution, MRL/SQ
- [`graph-operations`](../graph-operations/SKILL.md) — GraphRAG / LightRAG modes
- [`create-hook`](../create-hook/SKILL.md) — паттерн Stop-хука с state-файлом
