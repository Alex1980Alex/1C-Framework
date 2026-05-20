---
name: framework-search
description: "Framework Self-Search — semantic поиск по самому фреймворку (Python код, hooks, skills, docs). ИСПОЛЬЗУЙ когда нужно найти место в коде фреймворка по смысловому описанию, а не по точному имени. Триггеры: 'найди в фреймворке', 'где в коде делается X', 'какие skills делают Y', 'индексировать фреймворк', 'index_framework', 'framework_code_v1'. НЕ для BSL кода (→ bsl-development), НЕ для PDF документов (→ search-pipeline-debug)."
---

# Framework Self-Search — semantic поиск по коду фреймворка

## Обзор

Подсистема индексации **самого фреймворка** (`C:\1С-Framework`) в отдельную Qdrant-коллекцию `framework_code_v1` через Qwen3-Embedding-8B (TEI HTTP backend). Параллельная инфраструктура к BSL retrieval (`bsl_code_v4_late`), переиспользует тот же TEI Docker.

**Источник:** Phase 8 §24/§25 roadmap — `docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md`
**Стадии:**
- Stage 1 ✅ — manual indexer + chunkers (commit `ae6ccebb`)
- Stage 2 ✅ — MCP server `framework-search-mcp` с lazy mtime check (4 tools, registered in `.mcp.json`)
- Stage 3 ✅ — file watcher daemon `scripts/watch_framework.py` (polling, 5s default)

## Когда использовать

- Поиск кода по смыслу: "fallback логика для embeddings" → найдёт `_tei_fallback()` в `qwen3_embedding.py`
- Discovery hooks/skills по описанию: "хук блокирующий запись без активации скилла" → найдёт `code-skill-enforcer.py`
- Refactoring impact analysis: где используется паттерн X
- Onboarding / Q&A по фреймворку

## НЕ для

- **BSL код** (`src/bsl/`, `configuration/`) → `bsl-development` skill + `bsl_code_v4_late` collection
- **PDF документов** (`data/pdfs/`) → `search-pipeline-debug` + `pdf_documents` collection
- **Точные lookup'ы по имени** (`grep "function_name"`) — там быстрее Grep/Glob

## Команда индексации

```bash
# Первый раз / полный reindex (~15-20 мин на TEI)
python scripts/index_framework.py --recreate

# Dry-run: посмотреть chunk distribution без embed/upsert
python scripts/index_framework.py --dry-run

# Smoke test на 50 chunks (~10 секунд)
python scripts/index_framework.py --limit 50 --recreate

# Incremental: переиндексировать конкретные файлы
python scripts/index_framework.py --paths src/foo.py docs/bar.md
```

## CLI аргументы

| Аргумент | Default | Назначение |
|----------|---------|------------|
| `--collection` | `framework_code_v1` | Имя Qdrant коллекции |
| `--qdrant-url` | `http://localhost:6333` | Qdrant endpoint |
| `--tei-url` | `http://localhost:8080` | TEI HTTP endpoint (`pdf-rag-tei` контейнер) |
| `--batch-size` | `16` | Chunks на TEI batch (sub-batched на 32 внутри) |
| `--recreate` | off | Drop and create коллекции |
| `--dry-run` | off | Только walk + chunk, без embed/upsert |
| `--limit N` | 0 | Cap на N chunks (для тестов) |
| `--paths …` | none | Restrict к конкретным файлам |
| `--verbose` / `-v` | off | DEBUG logging |

## Pre-flight check

```bash
# 1. TEI healthy
docker ps | grep pdf-rag-tei

# 2. Qdrant healthy
curl -s http://localhost:6333/collections | python -m json.tool | head -5

# 3. GPU свободен
nvidia-smi --query-gpu=memory.used,memory.free --format=csv
```

## Архитектура (Stage 1)

| Файл | Назначение |
|------|------------|
| `src/framework_search/chunker_base.py` | `Chunk` dataclass + UUID5 deterministic id (idempotent reindex) |
| `src/framework_search/python_chunker.py` | AST-based: функции/классы/методы; sliding-window fallback на parse error |
| `src/framework_search/markdown_chunker.py` | H1-H3 splits с heading-path; **code-fence aware** (` ``` ` блоки игнорируются для heading detection) |
| `src/framework_search/text_chunker.py` | Generic для json/yaml/configs/text |
| `src/framework_search/file_walker.py` | Glob+SKIP_PATTERNS+symlink escape protection (символлинки за пределы repo отбрасываются) |
| `src/framework_search/embedder.py` | TEI HTTP client с tenacity retry (4 attempts, exponential jitter) и sub-batching на `MAX_CLIENT_BATCH_SIZE=32` |
| `src/framework_search/indexer.py` | Pipeline orchestrator; **upsert-then-delete** ordering для idempotency без window потери данных |
| `src/framework_search/config.py` | Defaults: scope (включая/исключая), TEI/Qdrant URLs, MAX_CHUNK_CHARS=8000 |
| `scripts/index_framework.py` | CLI entry-point |

## Scope (что индексируется)

**Включено:** `src/`, `scripts/`, `.claude/hooks/`, `.claude/skills/`, `tools/`, `tests/`, `docs/{architecture,framework documentation,roadmap}/`, `.mcp/`, **`openspec/`** (добавлено 2026-05-20 §H roadmap_openspec_v2 — OpenSpec changes/archive/specs индексируются в ту же коллекцию для semantic-search через `mcp__framework-search__search_code(query, path_glob='openspec/changes/**')` без отдельной коллекции `openspec_changes_v1`), root configs (`CLAUDE.md`, `AGENTS.md`, `.mcp.json`, `pyproject.toml`)

**Исключено** (`SKIP_PATTERNS` в `config.py`):
- `__pycache__/`, `.venv/`, `node_modules/`, `.git/`, `dist/`, `build/`, кэши
- `data/`, `cache/`, `tmp/`, `logs/`
- `configuration/` (BSL projects идут в `bsl_code_v4_late`)
- `docs/documentation/{Lang Chain Docs,Claude Code Docs,Протокол контекста модели,Language Server Protocol}/` (импортированная сторонняя документация)
- Файлы > 512 KB (защита от monstro-md)

## Объёмы (snapshot 2026-04-30)

- **31 519 chunks из 2 130 файлов**
- Распределение: python 17 224 / markdown 13 419 / json 500 / typescript 266 / text 63 / javascript 47
- Время dry-run (chunk only): ~14 сек
- Время full reindex (embed+upsert): ~15-20 мин на RTX 3090 (TEI Docker)
- Размер коллекции: ~500 MB (31k × 4096d × float32)

## Поиск через Python API

```python
from qdrant_client import QdrantClient
from src.framework_search.embedder import FrameworkTEIEmbedder

client = QdrantClient(url="http://localhost:6333")
with FrameworkTEIEmbedder() as e:
    qv = e.embed_batch(["fallback логика для embedding"], is_query=True)[0]

results = client.query_points(
    collection_name="framework_code_v1",
    query=qv, limit=5, with_payload=True,
).points
for r in results:
    p = r.payload
    print(f"{r.score:.3f} {p['language']} {p['relative_path']}:{p['line_start']}")
```

## Поиск с фильтрами

```python
from qdrant_client.http import models

# Только Python функции
flt = models.Filter(must=[
    models.FieldCondition(key="language", match=models.MatchValue(value="python")),
    models.FieldCondition(key="chunk_type", match=models.MatchValue(value="function")),
])
results = client.query_points(
    collection_name="framework_code_v1",
    query=qv, query_filter=flt, limit=10, with_payload=True,
).points
```

## Payload schema

```json
{
  "relative_path": "src/foo/bar.py",
  "content": "def foo():\n    ...",
  "language": "python | markdown | json | javascript | typescript | text",
  "chunk_type": "function | class | module | section | config | text",
  "symbol_name": "ClassName.method_name | None",
  "line_start": 42,
  "line_end": 55,
  "mtime": 1714478400.0,
  "sha1": "abc123...def"
}
```

## Stage 2 — MCP Server (готово)

Файл: `tools/framework-search-mcp/server.py`. Stdio MCP, зарегистрирован в `.mcp.json` как `framework-search`.

**4 MCP tools:**

| Tool | Описание |
|------|----------|
| `mcp__framework-search__search_code(query, k=5, language?, path_glob?)` | Semantic поиск по описанию |
| `mcp__framework-search__find_similar(file_path, k=5)` | Похожий код по содержимому файла |
| `mcp__framework-search__index_status()` | Статистика коллекции + sample distributions |
| `mcp__framework-search__reindex_changed()` | Force lazy-check (без throttle) |

**Lazy mtime check:** перед каждым `search_code` сервер сравнивает on-disk mtime файлов с `payload.mtime` в Qdrant. Stale + новые файлы реиндексируются на лету. Cap: 50 файлов за проход. Throttle: не чаще 1× в 30 сек (`LAZY_CHECK_MIN_INTERVAL_SEC`).

**Запуск вручную (для отладки):**
```bash
python tools/framework-search-mcp/server.py --log-level DEBUG
```

## Stage 3 — File Watcher (готово)

Файл: `scripts/watch_framework.py`. **Polling-based** (зачем не watchdog — см. docstring): ноль новых deps, кроссплатформенно, нет риска dropped-events на bulk-операциях git.

**Параметры:**

| Аргумент | Default | Назначение |
|----------|---------|------------|
| `--poll-interval` | `5.0` | Секунд между сканами |
| `--debounce` | `2.0` | Пропускать файлы изменённые в последние N сек (ещё редактируются) |
| `--max-files-per-batch` | `100` | Cap на reindex за итерацию (защита от bulk git checkout) |
| `--quiet` | off | WARNING level only (для daemon-режима) |

**Запуск:**

```bash
# Foreground (Ctrl+C to stop)
python scripts/watch_framework.py

# Реже (10 сек интервал)
python scripts/watch_framework.py --poll-interval 10

# Daemon-style на Windows: через Task Scheduler или nssm
python scripts/watch_framework.py --quiet > watcher.log 2>&1 &
```

**Архитектура:** каждые 5 сек загружает snapshot `{relative_path: mtime}` из Qdrant payload (рефреш каждые 5 минут чтобы держать в памяти), сравнивает с on-disk mtime, формирует diff, дёргает `run_index(only_paths=changed)`. Идемпотентность через UUID5 chunk_id — повторный run просто перезаписывает.

**Дополняет Stage 2 lazy-check:** если watcher работает — `search_code` всегда найдёт свежие данные без задержки. Если watcher упал — lazy-check вытянет stale файлы при ближайшем запросе.

## Auto-indexing on git commit (3rd backup layer)

Активирована автоматическая инкрементальная индексация при `git commit` и `git merge`. Срабатывает в **detached background process** — коммит завершается мгновенно, reindex идёт параллельно.

**Активация (один раз на клон репозитория):**

```bash
git config core.hooksPath scripts/git_hooks
```

Это перенаправляет git hooks из `.git/hooks/` (per-clone) в версионируемый `scripts/git_hooks/` (всем clone'ам).

**Что происходит при коммите:**

1. `scripts/git_hooks/post-commit` срабатывает → передаёт управление `git lfs post-commit` (сохраняет существующее поведение)
2. Затем вызывает `scripts/git_post_commit_reindex.py --since-ref HEAD~1`
3. Helper читает `git diff --name-only HEAD~1..HEAD`, фильтрует через `EXT_TO_LANGUAGE` + `SKIP_PATTERNS`
4. Если изменений > 200 — skip (initial commit, bulk operations) → лог в `cache/framework_search_reindex.log`
5. Иначе спавнит `index_framework.py --paths <changed>` **detached** (Windows: `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`; POSIX: `setsid`)
6. Лог индексации идёт в `cache/framework_search_reindex.log`, терминал юзера остаётся чистым

**При merge** срабатывает `post-merge` со `--since-ref ORIG_HEAD` (диапазон merge'а).

**При checkout/branch-switch** reindex намеренно пропускается — diff может быть огромным; MCP lazy-check вытянет stale файлы при следующем `search_code`.

**Split на 2 pipeline:**

`git_post_commit_reindex.py` разделяет diff на две группы:
- `.bsl` под `configuration/<X>/` → **BSL pipeline** (`scripts/reindex_bsl_qwen3.py --paths --embedder qwen3-tei`) → коллекция `bsl_code_v4_late`. Cap файла: 4 MB. Группируются по project root (один spawn на проект).
- Остальное (`.py .md .json .ts .js .toml .yaml .ini`) → **framework pipeline** (`scripts/index_framework.py --paths`) → коллекция `framework_code_v1`. Cap: 512 KB.

Оба pipeline спавнятся detached, логи раздельные:
- `cache/framework_search_reindex.log` — framework reindex
- `cache/bsl_reindex.log` — BSL reindex

**BSL caveat:** Auto-reindex использует `qwen3-tei` (std pooling) вместо `qwen3-st` (Late Chunking) чтобы избежать GPU contention с уже работающим TEI. Quality impact ~5-10% на свежеправленных символах (различные pooling режимы). Раз в неделю/месяц рекомендуется ручной полный reindex по §23 для re-alignment всей коллекции на Late Chunking pooling.

**Отключить:**

```bash
git config --unset core.hooksPath
# Восстанавливает .git/hooks/ как источник (lfs hooks там же)
```

**Проверить лог:**

```bash
tail cache/framework_search_reindex.log
```

**Файлы:**

| Файл | Назначение |
|------|------------|
| `scripts/git_hooks/post-commit` | shell wrapper: lfs + reindex trigger |
| `scripts/git_hooks/post-merge` | shell wrapper: lfs + reindex trigger (ORIG_HEAD diff) |
| `scripts/git_hooks/post-checkout` | lfs only (skip reindex) |
| `scripts/git_hooks/pre-push` | lfs only |
| `scripts/git_post_commit_reindex.py` | Python helper: filter + detached spawn |

## Связанные skills

- `bsl-development` — параллельный pipeline для BSL кода (`bsl_code_v4_late`)
- `embedding-models` — детали Qwen3+TEI backend
- `qdrant-operations` — управление коллекциями
- `deployment` — TEI Docker compose `--profile tei`

## Файлы

- Pipeline: [src/framework_search/](src/framework_search/)
- CLI: [scripts/index_framework.py](scripts/index_framework.py)
- Roadmap: [docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md §24](docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md)
