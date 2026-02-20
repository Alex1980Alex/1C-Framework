---
name: framework-cli
description: "CLI-команды PDF Framework. Триггеры: 'CLI', 'команда', 'command', 'pdf-framework', 'терминал', 'консоль', 'как запустить', 'python -m src.cli'. НЕ для REST API — используй framework-api."
---

# Framework CLI — все команды

## Когда использовать
- "какие команды есть", "как запустить поиск", "pdf-framework ..."
- "как индексировать через CLI", "команда для чата"
- Любые вопросы о терминальных командах

## Запуск

```bash
python -m src.cli.main --help
```

---

## Quick Reference (Top-5)

| Задача | Команда |
|--------|---------|
| Индексировать PDF | `python -m src.cli.main index "doc.pdf" --graph` |
| Поиск | `python -m src.cli.main search "запрос" --strategy hybrid` |
| RAG-вопрос | `python -m src.cli.main ask "вопрос?" --stream` |
| Чат | `python -m src.cli.main chat --strategy hybrid` |
| Запуск API сервера | `python -m src.cli.main server --port 8000` |

---

## Все команды

### search — Поиск документов

```bash
python -m src.cli.main search "ЗАПРОС" [ОПЦИИ]
```

| Опция | Описание | Default |
|-------|----------|---------|
| `--strategy`, `-s` | Стратегия: vector, bm25, hybrid, mmr, adaptive, graphrag_local, graphrag_global, section_first, raptor, auto_merge, two_stage | `vector` |
| `--top-k`, `-k` | Количество результатов | `5` |
| `--no-rerank` | Отключить reranking | `false` |
| `--language` | Фильтр по языку | — |
| `--doc-type` | Фильтр по типу документа | — |
| `--version` | Фильтр по версии | — |
| `--diversity` | MMR diversity (0.0-1.0) | `0.3` |
| `--expand-query` | HyDE query expansion | `false` |
| `--verbose`, `-v` | Подробный вывод | `false` |
| `--tenant` | Tenant ID | `default` |
| `--force-route` | Принудительная стратегия | — |

```bash
# Примеры
python -m src.cli.main search "конфигуратор" --strategy hybrid
python -m src.cli.main search "регистр" --strategy bm25 --language ru
python -m src.cli.main search "архитектура" --strategy adaptive --verbose
python -m src.cli.main search "настройка" --strategy mmr --diversity 0.7 -k 10
```

### ask — RAG-ответ на вопрос

```bash
python -m src.cli.main ask "ВОПРОС" [ОПЦИИ]
```

| Опция | Описание | Default |
|-------|----------|---------|
| `--strategy`, `-s` | Стратегия поиска | `hybrid` |
| `--no-self-rag` | Отключить Self-RAG | `false` |
| `--stream` | Потоковый вывод | `false` |
| `--verbose`, `-v` | Подробный вывод | `false` |

```bash
python -m src.cli.main ask "Что такое конфигуратор?" --stream
python -m src.cli.main ask "Сравните регистры" --strategy adaptive --verbose
```

### index — Индексация PDF

```bash
python -m src.cli.main index "ПУТЬ" [ОПЦИИ]
```

| Опция | Описание |
|-------|----------|
| `--graph` | Извлечь граф знаний (entities, relations) |
| `--communities` | Community detection (требует `--graph`) |
| `--parent-child` | Parent-child иерархия чанков |
| `--raptor` | RAPTOR tree (multi-level abstraction) |
| `--summarize` | Summary index |
| `--layout-aware` | Layout-aware parsing |
| `--extract-images` | Извлечь изображения + Vision OCR |
| `--extract-tables` | Извлечь таблицы |
| `--contextual` | Contextual Retrieval |
| `--recursive` | Рекурсивно обработать директорию |
| `--full-reindex` | Полная переиндексация (удалить старые данные) |
| `--tenant` | Tenant ID |

```bash
python -m src.cli.main index "document.pdf" --graph --communities
python -m src.cli.main index "docs/" --recursive --graph
python -m src.cli.main index "scan.pdf" --extract-images --layout-aware
```

### chat — Интерактивный чат

```bash
python -m src.cli.main chat [ОПЦИИ]
```

| Опция | Описание | Default |
|-------|----------|---------|
| `--strategy` | Стратегия поиска | `hybrid` |
| `--thread` | ID сессии (для продолжения) | auto |

```bash
python -m src.cli.main chat --strategy hybrid --thread session-1
```

### research — Deep Research

```bash
python -m src.cli.main research "ВОПРОС" [ОПЦИИ]
```

| Опция | Описание | Default |
|-------|----------|---------|
| `--max-rounds` | Макс. раундов исследования | `5` |

```bash
python -m src.cli.main research "Сравнительный анализ подходов к индексации"
```

### eval — Оценка качества

```bash
python -m src.cli.main eval [ОПЦИИ]
```

| Опция | Описание |
|-------|----------|
| `--dataset` | Путь к eval dataset (JSON/CSV) |
| `--strategy` | Стратегия для тестирования |
| `--evaluator` | Evaluator: `ragas` / `triad` / `basic` |

```bash
python -m src.cli.main eval --dataset "data/eval/benchmark.json"
python -m src.cli.main eval --dataset "data/eval/benchmark.json" --strategy hybrid --evaluator ragas
```

### autorag — AutoRAG оптимизация

```bash
python -m src.cli.main autorag --dataset "data/eval/benchmark.json" \
    --strategies vector,hybrid,bm25 --k-values 3,5,10
```

### server — Запуск REST API

```bash
python -m src.cli.main server [ОПЦИИ]
```

| Опция | Default |
|-------|---------|
| `--port` | `8000` |
| `--host` | `0.0.0.0` |
| `--reload` | `false` |
| `--workers` | `1` |

### ui — Запуск Web UI

```bash
python -m src.cli.main ui [ОПЦИИ]
```

| Опция | Default |
|-------|---------|
| `--port` | `7860` |
| `--share` | `false` |

### cache — Управление кешем

```bash
python -m src.cli.main cache stats
python -m src.cli.main cache clear --type all
python -m src.cli.main cache clear --type embedding
python -m src.cli.main cache clear --type llm
```

### tenant — Управление тенантами

```bash
python -m src.cli.main tenant create --id company-a
python -m src.cli.main tenant list
python -m src.cli.main tenant delete --id company-a
```

### auth — JWT токены

```bash
python -m src.cli.main auth token --tenant company-a --role admin
python -m src.cli.main auth token --tenant company-a --role viewer
```

### stats — Статистика

```bash
python -m src.cli.main stats
```

Выводит статистику vector store и graph store (документы, чанки, entities).

### suggest — Предложения запросов

```bash
python -m src.cli.main suggest --method entity
python -m src.cli.main suggest --query "конфигуратор" --method llm --top-k 5
```

---

## Связанные скиллы

- `framework-config` — все .env переменные для настройки
- `framework-api` — REST API endpoints (альтернатива CLI)
- `search-pipeline-debug` — отладка стратегий поиска
- `indexing-pipeline` — детали pipeline индексации


## Незадокументированные CLI Commands

- `feedback` (src/cli/main.py)

## Файлы

- CLI: [main.py](src/cli/main.py)
