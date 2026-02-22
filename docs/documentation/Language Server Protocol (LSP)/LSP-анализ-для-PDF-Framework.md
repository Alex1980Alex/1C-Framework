# LSP-анализ для PDF Vector & Graph Framework

> **Назначение**: Детальный маппинг всех возможностей Language Server Protocol 3.18 на конфигурационную поверхность проекта. Основа для дорожной карты, создания Skills и реализации LSP-сервера.
>
> **Дата**: 2026-02-22 | **LSP версия**: 3.18 | **Проект**: PDF Vector & Graph Framework

---

## 1. Введение

### 1.1. Цель документа

Этот документ отвечает на три вопроса:

1. **Что** — полная карта всех 80+ методов LSP и их применимость к проекту
2. **Как** — анализ передовых реализаций (pygls, bsl-language-server, lsp-ai, MCP-LSP мосты) с паттернами для заимствования
3. **Когда** — roadmap реализации LSP-сервера (5 фаз, приоритеты P0-P3)

### 1.2. Зачем LSP для PDF Framework

Проект имеет **обширную конфигурационную поверхность**:

| Метрика | Значение |
|---------|----------|
| Pydantic Settings классов | 40+ |
| Всего параметров | ~130+ |
| Literal-типы (enum) | 27 параметров |
| .env ключей | ~100+ |
| Search стратегий | 14 |
| MCP tools | 15 |
| REST API endpoints | 50+ |
| CLI команд | 15+ |

Без LSP-поддержки пользователь должен:
- Помнить все допустимые значения наизусть
- Открывать Python-код для проверки типов
- Обнаруживать ошибки только при запуске (runtime)
- Читать документацию отдельно от конфигурации

**С LSP**: автодополнение, валидация в реальном времени, документация при наведении — прямо в IDE.

---

## 2. Конфигурационная поверхность — детальная инвентаризация

### 2.1. Literal-типы (кандидаты для enum completion)

Каждый Literal-параметр — это enum, который LSP-сервер предложит через `textDocument/completion`.

| # | Класс | Параметр | Literal значения | Default | .env ключ |
|---|-------|----------|-----------------|---------|-----------|
| 1 | PDFSettings | loader | `pymupdf`, `pdfplumber`, `unstructured`, `docling`, `pymupdf4llm`, `smart`, `hybrid` | `pymupdf` | `PDF__LOADER` |
| 2 | PDFSettings | splitter | `recursive`, `semantic`, `by_heading`, `by_page`, `parent_child`, `structure_aware` | `recursive` | `PDF__SPLITTER` |
| 3 | DoclingSettings | ocr_engine | `easyocr`, `tesseract`, `rapidocr` | `rapidocr` | `DOCLING__OCR_ENGINE` |
| 4 | DoclingSettings | table_mode | `fast`, `accurate` | `accurate` | `DOCLING__TABLE_MODE` |
| 5 | SmartRouterSettings | fast_loader | `pymupdf`, `pymupdf4llm` | `pymupdf4llm` | `SMART_ROUTER__FAST_LOADER` |
| 6 | SmartRouterSettings | full_loader | `docling`, `unstructured` | `docling` | `SMART_ROUTER__FULL_LOADER` |
| 7 | HybridLoaderSettings | docling_table_mode | `fast`, `accurate` | `accurate` | `HYBRID_LOADER__DOCLING_TABLE_MODE` |
| 8 | EmbeddingSettings | provider | `openai`, `voyage`, `local`, `giga`, `jina` | `local` | `EMBEDDING__PROVIDER` |
| 9 | EmbeddingSettings | backend | `torch`, `onnx`, `openvino` | `torch` | `EMBEDDING__BACKEND` |
| 10 | VectorStoreSettings | provider | `chroma`, `qdrant`, `faiss`, `pgvector` | `chroma` | `VECTOR_STORE__PROVIDER` |
| 11 | VectorStoreSettings | distance_metric | `cosine`, `euclidean`, `dot` | `cosine` | `VECTOR_STORE__DISTANCE_METRIC` |
| 12 | SearchSettings | bm25_backend | `qdrant`, `fts5`, `both` | `qdrant` | `SEARCH__BM25_BACKEND` |
| 13 | SearchSettings | query_expansion_method | `llm`, `synonyms`, `hyde` | `llm` | `SEARCH__QUERY_EXPANSION_METHOD` |
| 14 | AgentSettings | reranker_type | `cross_encoder`, `llm`, `colbert` | `llm` | `AGENT__RERANKER_TYPE` |
| 15 | AgentSettings | checkpointer | `memory`, `postgres`, `sqlite` | `memory` | `AGENT__CHECKPOINTER` |
| 16 | ConversationSettings | memory_backend | `memory`, `sqlite` | `sqlite` | `CONVERSATION__MEMORY_BACKEND` |
| 17 | LayoutSettings | layout_provider | `unstructured`, `surya`, `docling`, `none` | `unstructured` | `LAYOUT__LAYOUT_PROVIDER` |
| 18 | LayoutSettings | layout_strategy | `hi_res`, `fast` | `hi_res` | `LAYOUT__LAYOUT_STRATEGY` |
| 19 | LayoutSettings | parse_template | `auto`, `generic`, `research_paper`, `user_manual` | `auto` | `LAYOUT__PARSE_TEMPLATE` |
| 20 | SuggestionSettings | method | `entity`, `frequency`, `llm`, `related` | `entity` | `SUGGESTIONS__METHOD` |
| 21 | GuardrailsSettings | pii_mode | `detect`, `redact`, `block` | `detect` | `GUARDRAILS__PII_MODE` |
| 22 | GuardrailsSettings | injection_mode | `log`, `warn`, `block` | `log` | `GUARDRAILS__INJECTION_MODE` |
| 23 | ObservabilitySettings | tracer | `jsonfile`, `langsmith`, `langfuse`, `none` | `jsonfile` | `OBSERVABILITY__TRACER` |
| 24 | GraphStoreSettings | provider | `neo4j`, `networkx` | `networkx` | `GRAPH_STORE__PROVIDER` |
| 25 | MCPServerSettings | transport | `stdio`, `sse` | `stdio` | `MCP_SERVER__TRANSPORT` |
| 26 | Settings | log_level | `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` | `LOG_LEVEL` |
| 27 | Settings | log_format | `text`, `json` | `text` | `LOG_FORMAT` |

**Итого**: 27 параметров × в среднем 3.7 значений = **~100 вариантов completion items**.

### 2.2. Числовые параметры с ограничениями (кандидаты для diagnostics)

| Параметр | Тип | Диапазон | Default | Валидация |
|----------|-----|----------|---------|-----------|
| `PDF__CHUNK_SIZE` | int | 100–5000 | 1000 | > min_chunk_size |
| `PDF__CHUNK_OVERLAP` | int | 0–chunk_size | 200 | < chunk_size |
| `PDF__MIN_CHUNK_SIZE` | int | 50–1000 | 200 | < chunk_size |
| `PDF__MAX_CHUNK_SIZE` | int | 500–10000 | 1500 | > chunk_size |
| `PDF__SEMANTIC_THRESHOLD` | float | 0.0–1.0 | 0.75 | — |
| `SEARCH__HYBRID_VECTOR_WEIGHT` | float | 0.0–1.0 | 0.5 | sum(weights) ≈ 1.0 |
| `SEARCH__BM25_WEIGHT` | float | 0.0–1.0 | 0.3 | sum(weights) ≈ 1.0 |
| `SEARCH__HYBRID_GRAPH_WEIGHT` | float | 0.0–1.0 | 0.2 | sum(weights) ≈ 1.0 |
| `SEARCH__HYBRID_RRF_K` | int | 1–1000 | 60 | — |
| `SEARCH__MMR_DIVERSITY_LAMBDA` | float | 0.0–1.0 | 0.5 | — |
| `AGENT__TEMPERATURE` | float | 0.0–2.0 | 0.0 | — |
| `AGENT__RERANKER_TOP_K` | int | 1–100 | 20 | > search_k |
| `AGENT__COST_BUDGET_PER_QUERY` | float | 0.01–10.0 | 0.10 | — |
| `EMBEDDING__DIMENSIONS` | int | 128–4096 | 1024 | match model |
| `EMBEDDING__BATCH_SIZE` | int | 1–512 | 64 | — |
| `GUARDRAILS__INJECTION_THRESHOLD` | float | 0.0–1.0 | 0.7 | — |
| `PARENT_CHILD__PARENT_CHUNK_SIZE` | int | 500–10000 | 2000 | > child_chunk_size |
| `PARENT_CHILD__CHILD_CHUNK_SIZE` | int | 100–2000 | 400 | < parent_chunk_size |

### 2.3. Зависимости между параметрами (кандидаты для cross-field diagnostics)

| # | Если... | То требуется... | Severity |
|---|---------|----------------|----------|
| 1 | `EMBEDDING__PROVIDER=openai` | `OPENAI_API_KEY` задан | Error |
| 2 | `EMBEDDING__PROVIDER=voyage` | `VOYAGE_API_KEY` задан | Error |
| 3 | `EMBEDDING__PROVIDER=jina` | `JINA_API_KEY` задан (или `EMBEDDING__JINA_API_KEY`) | Error |
| 4 | `VECTOR_STORE__PROVIDER=qdrant` | `VECTOR_STORE__QDRANT_URL` задан | Error |
| 5 | `VECTOR_STORE__PROVIDER=pgvector` | `VECTOR_STORE__PGVECTOR_DSN` задан | Error |
| 6 | `SEARCH__BM25_BACKEND=qdrant` | `VECTOR_STORE__PROVIDER=qdrant` | Error |
| 7 | `AGENT__RERANKER_TYPE=llm` | `ANTHROPIC_API_KEY` задан | Error |
| 8 | `AGENT__RERANKER_TYPE=cross_encoder` | `AGENT__RERANKER_MODEL` задан | Warning |
| 9 | `AGENT__RERANKER_TYPE=colbert` | `AGENT__COLBERT_MODEL` задан | Warning |
| 10 | `GRAPH_STORE__PROVIDER=neo4j` | `GRAPH_STORE__NEO4J_URI` + `NEO4J_USER` + `NEO4J_PASSWORD` | Error |
| 11 | `OBSERVABILITY__TRACER=langsmith` | `LANGSMITH_API_KEY` задан | Error |
| 12 | `OBSERVABILITY__TRACER=langfuse` | `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` | Error |
| 13 | `PARENT_CHILD__ENABLED=true` | `PDF__SPLITTER=parent_child` рекомендуется | Warning |
| 14 | `VISUAL_SEARCH__ENABLED=true` | ColPali модель доступна | Warning |
| 15 | `LAYOUT__LAYOUT_PROVIDER=surya` | surya package установлен | Warning |
| 16 | `PDF__LOADER=docling` | docling package установлен | Warning |
| 17 | `PDF__CHUNK_OVERLAP >= PDF__CHUNK_SIZE` | — | Error |
| 18 | `PARENT_CHILD__CHILD_CHUNK_SIZE >= PARENT_CHILD__PARENT_CHUNK_SIZE` | — | Error |
| 19 | sum(SEARCH weights) значительно != 1.0 | — | Warning |
| 20 | `AGENT__RERANKER_TOP_K < AGENT__SEARCH_K` | — | Warning |
| 21 | `EMBEDDING__DIMENSIONS` не совпадает с моделью | — | Warning |
| 22 | `QUEUE__ENABLED=true` | `QUEUE__REDIS_URL` задан | Error |
| 23 | `AUTH__ENABLED=true` | `AUTH__JWT_SECRET` задан | Error |

### 2.4. Секции конфигурации (для Document Symbols / Folding)

```
Root Settings
├── PDF (loader, splitter, chunk_size, ...)
│   ├── Docling (ocr_engine, table_mode, ...)
│   ├── SmartRouter (fast_loader, full_loader, ...)
│   └── HybridLoader (vision_model, coverage_threshold, ...)
├── Embedding (provider, model, backend, dimensions, ...)
├── VectorStore (provider, qdrant_url, distance_metric, ...)
├── Search (weights, bm25_backend, expansion, ...)
│   ├── ContextualRetrieval (model, batch_concurrency, ...)
│   └── TwoStage (stage1_k, stage2_rerank_k, ...)
├── Agent (model, temperature, reranker_type, ...)
│   ├── SelfRAG (grading_model, relevance_threshold, ...)
│   └── DeepResearch (max_sub_questions, ...)
├── GraphStore (provider, neo4j_uri, ...)
├── GraphRAG (leiden_resolution, community_levels, ...)
│   └── LightRAG (entity_top_k, relation_top_k, ...)
├── Observability (tracer, langsmith_enabled, ...)
│   ├── Cache (embedding_ttl, llm_ttl, ...)
│   ├── Feedback (few_shot_max_examples, ...)
│   ├── RAGAS (regression_threshold, ...)
│   └── AutoRAG (max_experiments, ...)
├── Features
│   ├── ParentChild (parent_chunk_size, child_chunk_size, ...)
│   ├── AdaptiveRAG (route_simple_strategy, ...)
│   ├── Conversation (memory_backend, max_history, ...)
│   ├── Layout (layout_provider, parse_template, ...)
│   ├── RAPTOR (max_levels, search_mode, ...)
│   ├── Suggestions (method, max_suggestions, ...)
│   ├── Guardrails (pii_mode, injection_mode, ...)
│   ├── HierarchicalSearch (section_first_enabled, ...)
│   └── VisualSearch (model_name, hybrid_weight_*, ...)
├── Infrastructure
│   ├── MCP (transport, ...)
│   ├── API (host, port, cors_origins, ...)
│   ├── Auth (jwt_secret, token_expire_hours, ...)
│   ├── UI (port, share, theme, ...)
│   ├── OpenAICompat (model_name, ...)
│   └── Queue (redis_url, max_jobs, ...)
└── External (web_search_enabled, tavily_api_key, ...)
```

---

## 3. Маппинг LSP → PDF Framework

### 3.1. P0 — Must Have (основная ценность)

#### 3.1.1. Completion (`textDocument/completion` + `completionItem/resolve`)

**Что делает LSP**: Автодополнение при наборе текста — предложения вариантов по контексту.

**Применение в проекте**:

| Контекст курсора | Что предлагается | CompletionItemKind |
|-------------------|-------------------|-------------------|
| Начало строки (пустая) | Все .env ключи верхнего уровня: `PDF__`, `EMBEDDING__`, `SEARCH__`, ... | Property |
| После `PDF__` | `LOADER`, `CHUNK_SIZE`, `SPLITTER`, ... | Property |
| После `=` для Literal-ключа | Допустимые enum-значения | EnumMember |
| После `=` для bool-ключа | `true`, `false` | Value |
| После `=` для path-ключа | Существующие директории | File/Folder |

**Триггеры**: `=` (после ключа), `_` (для вложенных), начало строки

**Пример**:
```
Пользователь печатает:  EMBEDDING__PROVIDER=|
                                             ↓
LSP предлагает:  ┌──────────────────────────────────────────────┐
                 │ local     (default) intfloat/multilingual-e5  │
                 │ openai    text-embedding-3, requires API key   │
                 │ voyage    voyage-multilingual-2                │
                 │ giga      GigaChat embeddings                  │
                 │ jina      jina-embeddings-v3, late_chunking    │
                 └──────────────────────────────────────────────┘
```

**Реализация (pygls)**:
```python
@server.feature(TEXT_DOCUMENT_COMPLETION,
                CompletionOptions(trigger_characters=["=", "_"]))
async def completions(params: CompletionParams) -> CompletionList:
    doc = server.workspace.get_text_document(params.text_document.uri)
    line = doc.lines[params.position.line]

    if "=" in line:
        key = line.split("=")[0].strip()
        if key in SCHEMA and SCHEMA[key].literal_values:
            return CompletionList(items=[
                CompletionItem(
                    label=val,
                    kind=CompletionItemKind.EnumMember,
                    documentation=SCHEMA[key].value_docs.get(val, ""),
                    detail=f"default" if val == SCHEMA[key].default else "",
                )
                for val in SCHEMA[key].literal_values
            ])
    else:
        prefix = line.strip()
        return CompletionList(items=[
            CompletionItem(
                label=key,
                kind=CompletionItemKind.Property,
                documentation=SCHEMA[key].description,
                insert_text=f"{key}={SCHEMA[key].default}",
            )
            for key in SCHEMA if key.startswith(prefix)
        ])
```

#### 3.1.2. Diagnostics (`textDocument/publishDiagnostics`)

**Что делает LSP**: Подчёркивание ошибок, предупреждений и подсказок прямо в редакторе.

**Применение в проекте**:

| Severity | Что проверяется | Пример |
|----------|----------------|--------|
| Error (1) | Неизвестный .env ключ | `PDF__LOADR=hybrid` → "Unknown key PDF__LOADR. Did you mean PDF__LOADER?" |
| Error (1) | Невалидное Literal-значение | `PDF__LOADER=magic` → "Invalid value 'magic'. Allowed: pymupdf, pdfplumber, ..." |
| Error (1) | Неверный тип данных | `EMBEDDING__DIMENSIONS=abc` → "Expected int, got 'abc'" |
| Error (1) | Отсутствует зависимый ключ | `EMBEDDING__PROVIDER=openai` без `OPENAI_API_KEY` → "OPENAI_API_KEY required when EMBEDDING__PROVIDER=openai" |
| Error (1) | Нарушение ограничения | `PDF__CHUNK_OVERLAP=1500` при `PDF__CHUNK_SIZE=1000` → "chunk_overlap (1500) must be less than chunk_size (1000)" |
| Warning (2) | Сумма весов != 1.0 | vector_weight=0.5 + bm25_weight=0.4 + graph_weight=0.3 = 1.2 → "Hybrid weights sum to 1.2 (expected ~1.0)" |
| Warning (2) | Субоптимальная комбинация | `EMBEDDING__BACKEND=torch` на CPU → "Consider onnx or openvino backend for CPU deployment" |
| Warning (2) | Deprecated параметр | — |
| Information (3) | Рекомендация | "BM25 two-pass mode improves recall for Russian text" |
| Hint (4) | Значение = default | `LOG_LEVEL=INFO` → "This is the default value, line can be removed" |

**Диагностические теги**:
- `Unnecessary` (1) — параметр со значением по умолчанию
- `Deprecated` (2) — устаревший параметр

**Пример диагностики в редакторе**:
```env
PDF__LOADER=hybrid                    ✅ OK
EMBEDDING__PROVIDER=openai            🔴 Error: OPENAI_API_KEY is required
EMBEDDING__DIMENSIONS=abc             🔴 Error: Expected int, got 'abc'
SEARCH__HYBRID_VECTOR_WEIGHT=0.9
SEARCH__BM25_WEIGHT=0.8
SEARCH__HYBRID_GRAPH_WEIGHT=0.5       🟡 Warning: sum = 2.2 (expected ~1.0)
LOG_LEVEL=INFO                        💡 Hint: default value, can be omitted
VECTOR_STORE__PROVIDR=qdrant          🔴 Error: Unknown key. Did you mean PROVIDER?
```

#### 3.1.3. Hover (`textDocument/hover`)

**Что делает LSP**: Всплывающая подсказка при наведении мыши на элемент.

**Применение в проекте**:

| Наведение на... | Показывается |
|-----------------|-------------|
| .env ключ | Тип, default, описание, допустимые значения, зависимости |
| .env значение | Описание конкретного значения, его влияние на систему |
| Секцию (EMBEDDING__) | Описание группы, количество параметров, ссылка на документацию |
| Комментарий (# ...) | — (пропуск) |

**Пример hover для `AGENT__RERANKER_TYPE=llm`**:

```markdown
**AGENT__RERANKER_TYPE**

Тип реранкера для переупорядочивания результатов поиска.

| Свойство | Значение |
|----------|----------|
| Тип | `Literal["cross_encoder", "llm", "colbert"]` |
| Default | `"llm"` |
| Класс | `AgentSettings` |

**Значения:**
- `llm` — Реранкинг через Claude API. Точный, но платный (~$0.001/query, 1-3s)
- `cross_encoder` — Локальный BAAI/bge-reranker-v2-m3. Бесплатный, но медленный на CPU
- `colbert` — jinaai/jina-colbert-v2. Баланс качества и скорости

**Зависимости:**
- `llm` → требует `ANTHROPIC_API_KEY`
- `cross_encoder` → требует `AGENT__RERANKER_MODEL`
- `colbert` → требует `AGENT__COLBERT_MODEL`
```

#### 3.1.4. Document Symbols (`textDocument/documentSymbol`)

**Что делает LSP**: Структура документа в панели Outline / Breadcrumb.

**Применение в проекте**:

VS Code Outline для `.env` файла:
```
📦 PDF
  🔧 LOADER = hybrid
  🔧 CHUNK_SIZE = 1000
  🔧 SPLITTER = recursive
📦 EMBEDDING
  🔧 PROVIDER = local
  🔧 MODEL = intfloat/multilingual-e5-large
  🔧 BACKEND = torch
📦 VECTOR_STORE
  🔧 PROVIDER = qdrant
  🔧 QDRANT_URL = http://localhost:6333
📦 SEARCH
  🔧 HYBRID_VECTOR_WEIGHT = 0.4
  🔧 BM25_WEIGHT = 0.4
  ...
```

**SymbolKind маппинг**:
- Секции (PDF, EMBEDDING, ...) → `SymbolKind.Namespace` (3)
- Параметры → `SymbolKind.Property` (7)
- Комментарии-разделители → `SymbolKind.String` (15)

---

### 3.2. P1 — Should Have (расширенная ценность)

#### 3.2.1. Code Actions (`textDocument/codeAction` + `codeAction/resolve`)

| Действие | Триггер | CodeActionKind |
|----------|---------|---------------|
| Fix typo in key | Diagnostic "Unknown key, did you mean..." | `quickfix` |
| Fix invalid value | Diagnostic "Invalid value" | `quickfix` |
| Add missing dependency | Diagnostic "API key required" | `quickfix` |
| Normalize weights to 1.0 | Diagnostic "Weights sum != 1.0" | `quickfix` |
| Generate .env from template | Пустой файл / команда | `source` |
| Switch profile (dev/prod/test) | Команда | `source` |
| Remove default values | Все Hint diagnostics | `source.fixAll` |
| Migrate deprecated params | Diagnostic "Deprecated" | `refactor` |

**Пример Quick Fix**:
```
PDF__LOADER=magik        ← 🔴 Error: Unknown value
                         ← 💡 Quick Fix: Change to "pymupdf" (closest match)
                         ← 💡 Quick Fix: Change to "hybrid" (recommended)
```

#### 3.2.2. Code Lens (`textDocument/codeLens`)

| Позиция | Текст CodeLens | Действие |
|---------|---------------|----------|
| Строка `VECTOR_STORE__QDRANT_URL=...` | `▶ Test Connection` | Проверить доступность Qdrant |
| Строка `GRAPH_STORE__NEO4J_URI=...` | `▶ Test Connection` | Проверить доступность Neo4j |
| Строка `EMBEDDING__PROVIDER=local` | `📊 Model loaded: 1024 dims` | Статус модели |
| Строка `SEARCH__*_WEIGHT=...` | `∑ = 1.0 ✓` или `∑ = 1.2 ✗` | Сумма весов |
| Начало файла | `🔧 15 params / 3 errors / 1 warning` | Общая статистика |

#### 3.2.3. Inlay Hints (`textDocument/inlayHint`)

```env
PDF__CHUNK_SIZE=1000          : int     ← тип параметра (InlayHintKind.Type)
PDF__LOADER=hybrid            (default) ← пометка "это default" (InlayHintKind.Parameter)
EMBEDDING__DIMENSIONS=        1024      ← default значение для пустого параметра
SEARCH__HYBRID_VECTOR_WEIGHT= 0.5      ← default значение
```

#### 3.2.4. Folding Ranges (`textDocument/foldingRange`)

```env
# ═══════════ PDF ═══════════        ← FoldingRangeKind.region
PDF__LOADER=hybrid                    │
PDF__CHUNK_SIZE=1000                  │ foldable
PDF__SPLITTER=recursive               │
                                      ↓
# ═══════════ Embedding ═══════════  ← FoldingRangeKind.region
EMBEDDING__PROVIDER=local             │
EMBEDDING__MODEL=intfloat/...         │ foldable
EMBEDDING__BACKEND=torch              │
```

#### 3.2.5. Document Links (`textDocument/documentLink`)

| Паттерн | Действие |
|---------|----------|
| `VECTOR_STORE__QDRANT_URL=http://localhost:6333` | Кликабельная ссылка → открыть в браузере |
| `EMBEDDING__CACHE_DIR=data/cache/embeddings` | Кликабельный путь → открыть папку |
| `# See: https://docs.qdrant.io/...` | Кликабельная ссылка в комментарии |

#### 3.2.6. Semantic Tokens (`textDocument/semanticTokens/full`)

| Элемент | TokenType | TokenModifier | Цвет (пример) |
|---------|-----------|--------------|----------------|
| `PDF__LOADER` (ключ) | `property` | `definition` | Голубой |
| `hybrid` (Literal-значение) | `enum` | — | Зелёный |
| `1000` (число) | `number` | — | Оранжевый |
| `true`/`false` | `keyword` | — | Фиолетовый |
| `http://localhost:6333` (URL) | `string` | — | Коричневый |
| `data/cache/...` (путь) | `string` | — | Коричневый |
| `# Comment` | `comment` | — | Серый |
| `# ═══ Section ═══` | `namespace` | `declaration` | Жёлтый bold |
| Deprecated ключ | any | `deprecated` | Зачёркнутый |

#### 3.2.7. Definition / References

| Направление | Применение |
|-------------|-----------|
| `.env` ключ → Go to Definition | Открывает Python-файл `config/embedding.py` на строке `provider: Literal[...]` |
| `.env` ключ → Find References | Все использования `settings.embedding.provider` в Python-коде |
| `.env` значение → Go to Definition | Для стратегий: `hybrid` → `search/strategies/hybrid.py` |

---

### 3.3. P2 — Nice to Have

#### 3.3.1. Rename (`textDocument/rename`)

Переименование .env ключа → обновление `env_prefix` или field name в Pydantic. Сложно и рискованно — P3.

#### 3.3.2. Formatting (`textDocument/formatting`)

- Сортировка ключей по секциям
- Выравнивание `=` по столбцу
- Добавление пустых строк между секциями
- Удаление trailing whitespace

#### 3.3.3. Signature Help (`textDocument/signatureHelp`)

Применимо если добавим CLI-like команды в конфиг (DSL):
```
# search --strategy hybrid --k 5 --rerank true
```

#### 3.3.4. Selection Range (`textDocument/selectionRange`)

- Выделение значения → расширение до ключ=значение → расширение до секции → весь файл

---

### 3.4. N/A — Неприменимо

| Метод | Причина |
|-------|---------|
| `notebookDocument/*` (4 метода) | .env — не notebook |
| `textDocument/moniker` | Нет cross-project навигации |
| `textDocument/inlineCompletion` | Не AI-completion для кода |
| `textDocument/linkedEditingRange` | Нет парных тегов в .env |
| `textDocument/documentColor` | Нет цветов в .env |
| `textDocument/colorPresentation` | Нет цветов в .env |
| `textDocument/declaration` | .env — нет forward declarations |
| `textDocument/typeDefinition` | .env — нет типов для навигации |
| `textDocument/implementation` | .env — нет интерфейсов |
| `typeHierarchy/*` (3 метода) | .env — нет наследования типов |

---

## 4. Анализ реализаций

### 4.1. pygls 2.0.0 — базовый фреймворк

| Свойство | Значение |
|----------|----------|
| **GitHub** | [openlawlibrary/pygls](https://github.com/openlawlibrary/pygls) |
| **Версия** | 2.0.0 (октябрь 2025) |
| **Python** | 3.9–3.14 |
| **LSP** | 3.18 (через lsprotocol 2025.0.0) |
| **Транспорт** | stdio, TCP, WebSocket |

**Архитектура**:
```python
from pygls.server import LanguageServer
from lsprotocol import types

server = LanguageServer("name", "v1")

@server.feature(types.TEXT_DOCUMENT_COMPLETION)
async def completions(params: types.CompletionParams):
    ...

@server.feature(types.TEXT_DOCUMENT_HOVER)
async def hover(params: types.HoverParams):
    ...

server.start_io()  # stdio transport
```

**Плюсы**: Python (наш стек), asyncio (наш подход), LSP 3.18, хорошая документация, активная разработка.

**Минусы**: нет готовых .env парсеров, всё пишется с нуля.

**Паттерн для заимствования**: Decorator-based feature registration — точно как наш MCP server (`@mcp.tool()`).

### 4.2. yaml-language-server — JSON Schema подход

| Свойство | Значение |
|----------|----------|
| **GitHub** | [redhat-developer/yaml-language-server](https://github.com/redhat-developer/yaml-language-server) |
| **Язык** | TypeScript |
| **Ключевая идея** | JSON Schema → автоматические completion + validation + hover |

**Применимость**: Pydantic v2 имеет встроенный экспорт JSON Schema:
```python
from src.pdf_framework.config._base import Settings
schema = Settings.model_json_schema()
# → Полная JSON Schema всех параметров
```

Этот schema можно:
1. Использовать внутри LSP-сервера как источник данных
2. Экспортировать как `.schema.json` для yaml-language-server (если добавим YAML-конфиг)
3. Опубликовать в [SchemaStore](https://www.schemastore.org/) для автоматической поддержки во всех IDE

**Паттерн для заимствования**: Schema-driven validation — не хардкодим правила, а генерируем из Pydantic.

### 4.3. bsl-language-server — референсный 1C LSP

| Свойство | Значение |
|----------|----------|
| **GitHub** | [1c-syntax/bsl-language-server](https://github.com/1c-syntax/bsl-language-server) |
| **Версия** | 0.26.0-rc.1 (декабрь 2025) |
| **Язык** | Java |
| **Diagnostics** | 180+ правил |

**Реализованные LSP-features**:
- `textDocument/publishDiagnostics` — 180+ диагностических правил
- `textDocument/codeAction` — Quick Fixes привязанные к diagnostics
- `textDocument/formatting` — форматирование BSL-кода
- `textDocument/documentSymbol` — методы, переменные, регионы
- `textDocument/definition`, `references` — навигация
- `textDocument/hover` — документация при наведении
- `textDocument/foldingRange` — свертка #Region, If, процедур
- `textDocument/codeLens` — Cognitive/Cyclomatic Complexity
- `textDocument/semanticTokens` — полная семантическая токенизация BSL (v0.26)
- `callHierarchy` — граф вызовов

**Паттерны для заимствования**:
1. **DiagnosticSupplier pattern** — каждое правило в отдельном классе. У нас: каждая валидация .env → отдельный ValidationRule.
2. **CodeAction привязанные к Diagnostic** — codeAction.diagnostics[] ссылается на конкретную ошибку.
3. **Конфигурация через JSON** — `.bsl-language-server.json`. У нас: `.pdf-lsp.json` или секция в `.vscode/settings.json`.

**Уроки**: 180+ diagnostics — это **killer feature**. Именно diagnostics делают LSP-сервер незаменимым.

### 4.4. lsp-ai — AI-powered LSP

| Свойство | Значение |
|----------|----------|
| **GitHub** | [SilasMarvin/lsp-ai](https://github.com/SilasMarvin/lsp-ai) |
| **Язык** | Rust |
| **Бэкенды** | Ollama, OpenAI, Anthropic, Gemini, llama.cpp |

**Концепция**: LSP-сервер, который генерирует completions через LLM. Работает в любом редакторе с LSP.

**Применение к проекту**:
- **AI-powered config suggestions**: "Based on your document types and hardware, I recommend: `EMBEDDING__BACKEND=onnx`, `PDF__LOADER=hybrid`"
- **Explain error**: Diagnostic + LLM explanation: "This error occurs because Qdrant BM25 sparse vectors require Qdrant as the vector store provider"
- **"Optimize my config"** code action → AI анализирует текущий .env и предлагает оптимизации

**Паттерн для заимствования**: LSP + LLM = context-aware suggestions. Наш MCP-сервер уже имеет доступ к Claude — можно использовать для AI-powered hover/completion.

### 4.5. MCP-LSP мосты — синергия протоколов

Новая категория (2024–2025): проекты, соединяющие MCP и LSP.

| Проект | Язык | Направление | Ключевая идея |
|--------|------|-------------|---------------|
| [Tritlo/lsp-mcp](https://github.com/Tritlo/lsp-mcp) | Haskell | MCP → LSP | MCP-сервер обращается к LSP: hover, completion, codeAction, diagnostics |
| [Language-Server-MCP-Bridge](https://github.com/sehejjain/Language-Server-MCP-Bridge) | TypeScript | LSP → MCP | VS Code extension: LSP capabilities → MCP tools для Copilot |
| [jonrad/lsp-mcp](https://github.com/jonrad/lsp-mcp) | Node.js | MCP → LSP | MCP server → LSP client, lazy start серверов |
| [bug-ops/mcpls](https://github.com/bug-ops/mcpls) | Rust | Bidirectional | Universal bridge, LSP 3.17 compliant |
| [ktnyt/cclsp](https://github.com/ktnyt/cclsp) | TypeScript | MCP → LSP | Специализирован для Claude Code, robust position resolution |
| [oraios/serena](https://github.com/oraios/serena) | Python | MCP + LSP | LSP abstraction layer для coding agents, **спонсируется VS Code team** |

**Применение к проекту**:

Наш MCP-сервер (15 tools) + новый LSP-сервер = **двусторонний мост**:

```
Claude Code                    VS Code / IDE
    │                              │
    │ MCP (stdio)                  │ LSP (stdio)
    ▼                              ▼
┌──────────┐    bridge     ┌──────────────┐
│ MCP      │◄─────────────►│ LSP          │
│ Server   │               │ Server       │
│ (15+4    │               │ (pygls)      │
│  tools)  │               │              │
└──────────┘               └──────────────┘
    │                              │
    ▼                              ▼
┌────────────────────────────────────────┐
│ Pydantic Settings introspection        │
│ + Validation engine                    │
│ + Config dependency graph              │
└────────────────────────────────────────┘
```

**Новые MCP tools через bridge**:
- `config/validate` → вызывает LSP diagnostics engine
- `config/suggest` → вызывает LSP completion engine
- `config/explain` → вызывает LSP hover engine
- `config/profile` → переключение профилей конфигурации

### 4.6. super-glass-lsp — шаблон для CLI wrapping

| Свойство | Значение |
|----------|----------|
| **GitHub** | [tombh/super-glass-lsp](https://github.com/tombh/super-glass-lsp) |
| **Язык** | Python (pygls) |
| **Идея** | Обернуть любой CLI инструмент как LSP-сервер |

**Применение**: Наша CLI (`pdf-framework search --strategy hybrid`) → LSP diagnostics по результатам валидации конфигурации.

### 4.7. cli-lsp-client — daemon для Claude Code

| Свойство | Значение |
|----------|----------|
| **GitHub** | [eli0shin/cli-lsp-client](https://github.com/eli0shin/cli-lsp-client) |
| **Идея** | CLI daemon, потребляющий LSP diagnostics, работает без VS Code |

**Применение**: Автоматический мониторинг `.env` валидности в терминале и Claude Code.

---

## 5. Архитектура LSP-сервера для проекта

### 5.1. Компонентная модель

```
src/lsp_server/
├── __init__.py
├── server.py                    # pygls LanguageServer + feature registration
├── parsers/
│   ├── __init__.py
│   ├── env_parser.py            # .env файл → AST (ключ, значение, комментарий, секция)
│   └── yaml_parser.py           # (Phase E) YAML config parser
├── schema/
│   ├── __init__.py
│   ├── introspector.py          # Pydantic Settings → LSP schema (автоматически)
│   ├── dependency_graph.py      # Граф зависимостей между параметрами (23 правила)
│   └── validators.py            # Валидационные правила → Diagnostic[]
├── features/
│   ├── __init__.py
│   ├── completion.py            # textDocument/completion — enum + keys
│   ├── diagnostics.py           # textDocument/publishDiagnostics — validation
│   ├── hover.py                 # textDocument/hover — parameter docs
│   ├── symbols.py               # textDocument/documentSymbol — outline
│   ├── code_actions.py          # textDocument/codeAction — quick fixes
│   ├── code_lens.py             # textDocument/codeLens — test connection
│   ├── semantic_tokens.py       # textDocument/semanticTokens — highlighting
│   ├── folding.py               # textDocument/foldingRange — sections
│   ├── links.py                 # textDocument/documentLink — URLs, paths
│   └── inlay_hints.py           # textDocument/inlayHint — defaults, types
├── bridge/
│   ├── __init__.py
│   └── mcp_bridge.py            # LSP ↔ MCP: новые tools (validate, suggest, explain)
└── runtime/
    ├── __init__.py
    └── config_tester.py          # Runtime: проверка подключений (Qdrant, Neo4j, Redis)
```

### 5.2. Schema Introspection (ядро)

Центральный компонент — **автоматическое извлечение metadata из Pydantic**:

```python
# schema/introspector.py
import typing
from src.pdf_framework.config._base import Settings

@dataclass
class FieldSchema:
    env_key: str              # "EMBEDDING__PROVIDER"
    python_path: str          # "settings.embedding.provider"
    field_type: str           # "Literal" | "int" | "float" | "bool" | "str" | "Path"
    literal_values: list[str] # ["openai", "voyage", "local", "giga", "jina"]
    default: Any              # "local"
    description: str          # "Embedding provider to use"
    config_class: str         # "EmbeddingSettings"
    source_file: str          # "src/pdf_framework/config/embedding.py"
    source_line: int          # 42

def introspect_settings() -> dict[str, FieldSchema]:
    """Extract all fields from all Settings classes."""
    result = {}
    for section_name, section_field in Settings.model_fields.items():
        section_class = section_field.annotation
        prefix = section_class.model_config.get("env_prefix", "").upper()
        for field_name, field_info in section_class.model_fields.items():
            env_key = f"{prefix}{field_name.upper()}"
            annotation = field_info.annotation
            literal_values = []
            if typing.get_origin(annotation) is typing.Literal:
                literal_values = list(typing.get_args(annotation))
            result[env_key] = FieldSchema(
                env_key=env_key,
                python_path=f"settings.{section_name}.{field_name}",
                field_type=_type_name(annotation),
                literal_values=literal_values,
                default=field_info.default,
                description=field_info.description or "",
                config_class=section_class.__name__,
                source_file=inspect.getfile(section_class),
                source_line=_get_field_line(section_class, field_name),
            )
    return result
```

**Преимущество**: добавление нового параметра в Pydantic Settings → LSP автоматически его подхватит без изменения кода LSP-сервера.

### 5.3. MCP-LSP Bridge

```python
# bridge/mcp_bridge.py
# Новые MCP tools, использующие LSP engine внутри

async def validate_config(file_path: str) -> list[dict]:
    """MCP tool: валидация .env файла через LSP diagnostics engine."""
    content = Path(file_path).read_text()
    diagnostics = run_diagnostics(content, SCHEMA)
    return [
        {
            "line": d.range.start.line,
            "severity": d.severity.name,
            "message": d.message,
            "code": d.code,
        }
        for d in diagnostics
    ]

async def suggest_completion(key_prefix: str) -> list[dict]:
    """MCP tool: предложения для .env ключа через LSP completion engine."""
    ...

async def explain_parameter(env_key: str) -> dict:
    """MCP tool: документация параметра через LSP hover engine."""
    ...
```

---

## 6. Roadmap реализации

### Phase A: Foundation

**Deliverables**:
- pygls 2.0 сервер skeleton с initialize/shutdown
- .env парсер (key=value, комментарии, секции, пустые строки)
- Pydantic Settings introspection (все 40+ классов → schema)
- `textDocument/completion` для .env ключей и Literal значений
- `textDocument/publishDiagnostics`: неизвестный ключ, невалидное значение, неверный тип
- `textDocument/hover`: описание параметра, тип, default, допустимые значения
- VS Code extension wrapper (extension.ts + package.json)

**Зависимости**: `pygls>=2.0.0`, `lsprotocol>=2025.0.0`

**Метрики**: completion accuracy >95%, hover coverage 100% Literal params

### Phase B: Rich Diagnostics

**Deliverables**:
- Cross-field dependency validation (23 правила из раздела 2.3)
- Range validation для числовых параметров (раздел 2.2)
- DiagnosticTag: Unnecessary (default values), Deprecated
- `textDocument/documentSymbol` для .env структуры (секции → параметры)
- `textDocument/foldingRange` для секций
- `workspace/didChangeWatchedFiles` — отслеживание изменений .env
- `workspace/configuration` — LSP-серверные настройки

**Метрики**: 23/23 dependency rules covered, 0 false positives

### Phase C: Code Intelligence

**Deliverables**:
- `textDocument/codeAction`: quick fixes для всех Error/Warning diagnostics
- `textDocument/codeLens`: "Test connection", "Current value", "Weights sum"
- `textDocument/inlayHint`: default values, type annotations
- `textDocument/documentLink`: URLs, file paths
- `textDocument/semanticTokens`: полная токенизация .env
- `workspace/executeCommand`: test connection, switch profile

**Метрики**: code action для каждой diagnostic, <200ms response time

### Phase D: MCP Bridge + AI

**Deliverables**:
- MCP-LSP bridge: 4 новых MCP tools (validate, suggest, explain, profile)
- AI-powered suggestions (LLM-based config recommendations через Claude)
- `textDocument/definition`: .env key → Python source file:line
- `textDocument/references`: где параметр используется в Python-коде
- Runtime config testing через codeLens commands (Qdrant, Neo4j, Redis)

**Зависимости**: Phase C, существующий MCP server (`src/mcp_server/server.py`)

### Phase E: Advanced

**Deliverables**:
- YAML config support (альтернатива .env)
- JSON Schema export (`Settings.model_json_schema()` → `.schema.json`)
- `textDocument/formatting`: сортировка, выравнивание .env
- `textDocument/rename`: propagation в Python-код
- Call Hierarchy: граф зависимостей конфигурации
- VS Code extension: marketplace packaging
- CLI LSP daemon (cli-lsp-client pattern)
- Публикация JSON Schema в SchemaStore

---

## 7. Маппинг на Skills (триада Hooks + Skills + MCP)

### 7.1. Новые Skills

| Skill | Тип | Содержание | Phase |
|-------|-----|-----------|-------|
| `lsp-server` | Операционный | Архитектура LSP-сервера: pygls паттерны, feature registration, .env parsing, VS Code extension | A |
| `lsp-config-validation` | Операционный | Все 23+ validation rules, cross-field deps, diagnostic severity mapping, DiagnosticTag | B |
| `lsp-completion-schema` | Операционный | Pydantic introspection → completion items, trigger characters, CompletionItemKind mapping | A |
| `lsp-mcp-bridge` | Операционный | MCP-LSP интеграция: новые MCP tools, bidirectional protocol bridge | D |
| `lsp-ai-features` | Операционный | AI-powered config suggestions, LLM integration в LSP, context-aware recommendations | D |
| `vscode-extension-dev` | Среда | VS Code extension: packaging, activation events, language contribution, client configuration | E |

### 7.2. Обновляемые Skills

| Skill | Обновление |
|-------|-----------|
| `framework-config` | Добавить секцию "LSP Support" — как LSP помогает с конфигурацией |
| `pdf-knowledge` | Добавить MCP tools: `config/validate`, `config/suggest`, `config/explain`, `config/profile` |
| `claude-code-vscode` | Добавить секцию "PDF Framework LSP Extension" — установка, настройка |

### 7.3. Новые Hooks

| Hook | Event | Action |
|------|-------|--------|
| `config-validation-on-save` | .env file save | Run LSP diagnostics, report errors в output channel |
| `lsp-schema-refresh` | Python config class change | Regenerate introspection schema из Pydantic |

### 7.4. Новые MCP Tools

| Tool | Input | Output | Описание |
|------|-------|--------|----------|
| `config/validate` | `file_path: str` | `Diagnostic[]` | Валидация .env файла |
| `config/suggest` | `key_prefix: str, context: str` | `CompletionItem[]` | Предложения для параметра |
| `config/explain` | `env_key: str` | `HoverContent` | Документация параметра |
| `config/profile` | `profile_name: str` | `AppliedChanges` | Переключение профиля (dev/prod/test) |

---

## 8. Метрики успеха

| Метрика | Target | Как измерять |
|---------|--------|-------------|
| Completion accuracy | >95% | % правильных Literal-значений в suggestions |
| Diagnostic coverage (required) | 100% | Все 23 dependency rules покрыты |
| Diagnostic coverage (optional) | >80% | Range validation, compatibility checks |
| Hover coverage | 100% | Все .env ключи имеют hover-документацию |
| Time to first completion | <200ms | LSP response latency (p95) |
| False positive rate | <5% | Неправильные diagnostics / total diagnostics |
| Code action coverage | >90% | % Error/Warning diagnostics с quick fix |
| Schema auto-detection | 100% | Новые Pydantic поля подхватываются без изменения LSP |

---

## 9. Технические решения и trade-offs

### 9.1. Формат конфигурации: .env vs YAML vs JSON

| Формат | Плюсы | Минусы | Решение |
|--------|-------|--------|---------|
| `.env` | Уже используется, простой, docker-friendly | Плоский (flat), нет типов, нет вложенности | **Phase A-D**: основной формат |
| YAML | Иерархический, типизированный, yaml-language-server | Требует миграции, дублирование | **Phase E**: опционально |
| JSON | Schema-friendly, IDE-поддержка из коробки | Неудобен для ручного редактирования | JSON Schema export только |

### 9.2. Push vs Pull Diagnostics

| Модель | Плюсы | Минусы | Решение |
|--------|-------|--------|---------|
| Push (`publishDiagnostics`) | Простая реализация, real-time | Может генерировать лишние обновления | **Phase A**: начинаем с Push |
| Pull (`textDocument/diagnostic`) | Более эффективна, client-driven | Сложнее, не все клиенты поддерживают | По необходимости |

### 9.3. Document Sync Mode

| Режим | Плюсы | Минусы | Решение |
|-------|-------|--------|---------|
| Full sync | Простая реализация, no state bugs | Передача всего документа | **Full sync** — .env файлы маленькие (<100 строк) |
| Incremental sync | Эффективнее для больших файлов | Сложнее, edge cases | Не нужен для .env |

### 9.4. Schema Introspection: Static vs Dynamic

| Подход | Плюсы | Минусы | Решение |
|--------|-------|--------|---------|
| Static (build-time) | Быстро, нет runtime deps | Требует rebuild при изменении | — |
| Dynamic (runtime) | Всегда актуально | Медленный startup, Python dependency | — |
| **Hybrid** | Introspect при initialize, кеш, refresh при file change | Чуть сложнее | **Выбран** — баланс актуальности и производительности |

---

## 10. Приложение: Сводная таблица 80+ методов → применимость

| # | Метод LSP | Категория | Применимо? | Приоритет | Phase | Комментарий |
|---|-----------|-----------|:----------:|:---------:|:-----:|-------------|
| 1 | `initialize` | Lifecycle | ✅ | P0 | A | Capability negotiation |
| 2 | `initialized` | Lifecycle | ✅ | P0 | A | — |
| 3 | `shutdown` | Lifecycle | ✅ | P0 | A | — |
| 4 | `exit` | Lifecycle | ✅ | P0 | A | — |
| 5 | `$/cancelRequest` | Lifecycle | ✅ | P1 | B | Отмена долгих validation |
| 6 | `$/progress` | Lifecycle | ✅ | P2 | C | Progress bar для validation |
| 7 | `$/logTrace` | Lifecycle | ⚪ | P3 | E | Debug only |
| 8 | `$/setTrace` | Lifecycle | ⚪ | P3 | E | Debug only |
| 9 | `textDocument/didOpen` | Sync | ✅ | P0 | A | Начало отслеживания .env |
| 10 | `textDocument/didChange` | Sync | ✅ | P0 | A | Full sync |
| 11 | `textDocument/willSave` | Sync | ⚪ | P3 | E | — |
| 12 | `textDocument/willSaveWaitUntil` | Sync | ❌ | N/A | — | Не нужен для .env |
| 13 | `textDocument/didSave` | Sync | ✅ | P1 | B | Trigger full validation |
| 14 | `textDocument/didClose` | Sync | ✅ | P0 | A | Cleanup |
| 15 | `notebookDocument/didOpen` | Sync | ❌ | N/A | — | Не notebook |
| 16 | `notebookDocument/didChange` | Sync | ❌ | N/A | — | Не notebook |
| 17 | `notebookDocument/didSave` | Sync | ❌ | N/A | — | Не notebook |
| 18 | `notebookDocument/didClose` | Sync | ❌ | N/A | — | Не notebook |
| 19 | `textDocument/declaration` | Navigation | ❌ | N/A | — | Нет declarations в .env |
| 20 | `textDocument/definition` | Navigation | ✅ | P2 | D | .env key → Python source |
| 21 | `textDocument/typeDefinition` | Navigation | ❌ | N/A | — | — |
| 22 | `textDocument/implementation` | Navigation | ❌ | N/A | — | — |
| 23 | `textDocument/references` | Navigation | ✅ | P2 | D | Где key используется в Python |
| 24 | `textDocument/documentHighlight` | Navigation | ✅ | P2 | C | Подсветка одинаковых ключей |
| 25 | `textDocument/prepareCallHierarchy` | Hierarchy | ⚪ | P3 | E | Config dependency graph |
| 26 | `callHierarchy/incomingCalls` | Hierarchy | ⚪ | P3 | E | — |
| 27 | `callHierarchy/outgoingCalls` | Hierarchy | ⚪ | P3 | E | — |
| 28 | `textDocument/prepareTypeHierarchy` | Hierarchy | ❌ | N/A | — | — |
| 29 | `typeHierarchy/supertypes` | Hierarchy | ❌ | N/A | — | — |
| 30 | `typeHierarchy/subtypes` | Hierarchy | ❌ | N/A | — | — |
| 31 | `textDocument/documentSymbol` | Symbols | ✅ | P1 | B | Outline: секции + параметры |
| 32 | `workspace/symbol` | Symbols | ✅ | P2 | C | Поиск параметров по workspace |
| 33 | `workspaceSymbol/resolve` | Symbols | ⚪ | P3 | E | — |
| 34 | `textDocument/moniker` | Symbols | ❌ | N/A | — | — |
| 35 | `textDocument/hover` | Hover | ✅ | P0 | A | Документация при наведении |
| 36 | `textDocument/documentLink` | Links | ✅ | P2 | C | URLs, file paths |
| 37 | `documentLink/resolve` | Links | ⚪ | P3 | E | — |
| 38 | `semanticTokens/full` | Semantic | ✅ | P2 | C | .env syntax highlighting |
| 39 | `semanticTokens/full/delta` | Semantic | ⚪ | P3 | E | Инкрементальные обновления |
| 40 | `semanticTokens/range` | Semantic | ⚪ | P3 | E | — |
| 41 | `textDocument/inlineValue` | Semantic | ❌ | N/A | — | Debug only |
| 42 | `textDocument/inlayHint` | Semantic | ✅ | P2 | C | Default values, types |
| 43 | `inlayHint/resolve` | Semantic | ⚪ | P3 | E | — |
| 44 | `textDocument/codeLens` | CodeLens | ✅ | P2 | C | Test connection, weights sum |
| 45 | `codeLens/resolve` | CodeLens | ✅ | P2 | C | — |
| 46 | `textDocument/publishDiagnostics` | Diagnostics | ✅ | P0 | A | Валидация .env |
| 47 | `textDocument/diagnostic` | Diagnostics | ⚪ | P2 | D | Pull model (опционально) |
| 48 | `textDocument/foldingRange` | Folding | ✅ | P1 | B | Свертка секций .env |
| 49 | `textDocument/selectionRange` | Selection | ⚪ | P3 | E | Smart expand selection |
| 50 | `textDocument/formatting` | Formatting | ✅ | P2 | C | Сортировка, выравнивание |
| 51 | `textDocument/rangeFormatting` | Formatting | ⚪ | P3 | E | — |
| 52 | `textDocument/rangesFormatting` | Formatting | ❌ | N/A | — | — |
| 53 | `textDocument/onTypeFormatting` | Formatting | ⚪ | P3 | E | Auto-complete after = |
| 54 | `textDocument/linkedEditingRange` | Formatting | ❌ | N/A | — | Нет парных тегов |
| 55 | `textDocument/completion` | Completion | ✅ | P0 | A | Ключи + Literal значения |
| 56 | `completionItem/resolve` | Completion | ✅ | P0 | A | Lazy documentation |
| 57 | `textDocument/signatureHelp` | Completion | ⚪ | P3 | E | CLI command help |
| 58 | `textDocument/inlineCompletion` | Completion | ❌ | N/A | — | — |
| 59 | `textDocument/codeAction` | Actions | ✅ | P1 | C | Quick fix для diagnostics |
| 60 | `codeAction/resolve` | Actions | ✅ | P1 | C | — |
| 61 | `textDocument/rename` | Actions | ⚪ | P3 | E | Rename .env key |
| 62 | `textDocument/prepareRename` | Actions | ⚪ | P3 | E | — |
| 63 | `textDocument/documentColor` | Color | ❌ | N/A | — | — |
| 64 | `textDocument/colorPresentation` | Color | ❌ | N/A | — | — |
| 65 | `workspace/configuration` | Workspace | ✅ | P1 | B | LSP server settings |
| 66 | `workspace/didChangeConfiguration` | Workspace | ✅ | P1 | B | — |
| 67 | `workspace/workspaceFolders` | Workspace | ✅ | P0 | A | — |
| 68 | `workspace/didChangeWorkspaceFolders` | Workspace | ⚪ | P2 | C | — |
| 69 | `workspace/didChangeWatchedFiles` | Workspace | ✅ | P1 | B | .env file watching |
| 70 | `workspace/executeCommand` | Workspace | ✅ | P2 | C | Test, switch profile |
| 71 | `workspace/applyEdit` | Workspace | ✅ | P1 | C | Quick fix apply |
| 72 | `workspace/willCreateFiles` | FileOps | ❌ | N/A | — | — |
| 73 | `workspace/didCreateFiles` | FileOps | ⚪ | P3 | E | .env created |
| 74 | `workspace/willRenameFiles` | FileOps | ❌ | N/A | — | — |
| 75 | `workspace/didRenameFiles` | FileOps | ❌ | N/A | — | — |
| 76 | `workspace/willDeleteFiles` | FileOps | ❌ | N/A | — | — |
| 77 | `workspace/didDeleteFiles` | FileOps | ❌ | N/A | — | — |
| 78 | `workspace/semanticTokens/refresh` | Refresh | ✅ | P2 | C | — |
| 79 | `workspace/codeLens/refresh` | Refresh | ✅ | P2 | C | — |
| 80 | `workspace/inlayHint/refresh` | Refresh | ⚪ | P3 | E | — |
| 81 | `workspace/inlineValue/refresh` | Refresh | ❌ | N/A | — | — |
| 82 | `workspace/diagnostic/refresh` | Refresh | ✅ | P1 | B | — |
| 83 | `workspace/foldingRange/refresh` | Refresh | ⚪ | P3 | E | — |
| 84 | `workspace/textDocumentContent` | VirtualDocs | ⚪ | P3 | E | Generated .env view |
| 85 | `workspace/textDocumentContent/refresh` | VirtualDocs | ⚪ | P3 | E | — |
| 86 | `window/showMessage` | Window | ✅ | P1 | B | Validation results |
| 87 | `window/showMessageRequest` | Window | ✅ | P2 | C | Migration prompts |
| 88 | `window/showDocument` | Window | ✅ | P2 | C | Open documentation |
| 89 | `window/logMessage` | Window | ✅ | P0 | A | Debug logging |
| 90 | `window/workDoneProgress/create` | Window | ✅ | P2 | C | Long validation progress |
| 91 | `window/workDoneProgress/cancel` | Window | ⚪ | P3 | E | — |
| 92 | `client/registerCapability` | Client | ✅ | P1 | B | Dynamic registration |
| 93 | `client/unregisterCapability` | Client | ⚪ | P2 | C | — |
| 94 | `telemetry/event` | Telemetry | ⚪ | P3 | E | Usage analytics |

**Статистика**:
- ✅ Применимо: **44** метода
- ⚪ Опционально: **24** метода
- ❌ Неприменимо: **26** методов

**По приоритетам**:
- **P0** (Phase A): 12 методов — skeleton + completion + diagnostics + hover
- **P1** (Phase B-C): 14 методов — symbols + folding + code actions + config watching
- **P2** (Phase C-D): 18 методов — code lens + semantic tokens + links + MCP bridge
- **P3** (Phase E): 24 метода — rename, formatting, advanced features

---

## Ссылки

### Спецификация
- [LSP 3.18 Specification](https://microsoft.github.io/language-server-protocol/specifications/lsp/3.18/specification/)
- [LSP 3.18 GitHub](https://github.com/microsoft/language-server-protocol/blob/gh-pages/_specifications/lsp/3.18/specification.md)
- [LSP Home](https://microsoft.github.io/language-server-protocol/)

### Фреймворки
- [pygls 2.0](https://github.com/openlawlibrary/pygls) | [Docs](https://pygls.readthedocs.io/)
- [super-glass-lsp](https://github.com/tombh/super-glass-lsp) — pygls template

### Языковые серверы
- [bsl-language-server](https://github.com/1c-syntax/bsl-language-server) — 1C Enterprise
- [yaml-language-server](https://github.com/redhat-developer/yaml-language-server) — YAML + JSON Schema
- [lsp-ai](https://github.com/SilasMarvin/lsp-ai) — AI-powered LSP
- [python-lsp-server](https://github.com/python-lsp/python-lsp-server) — Python
- [jedi-language-server](https://github.com/pappasam/jedi-language-server) — Jedi + pygls

### MCP-LSP мосты
- [Tritlo/lsp-mcp](https://github.com/Tritlo/lsp-mcp) — MCP → LSP
- [Language-Server-MCP-Bridge](https://github.com/sehejjain/Language-Server-MCP-Bridge) — VS Code LSP → MCP
- [jonrad/lsp-mcp](https://github.com/jonrad/lsp-mcp) — Node.js bridge
- [bug-ops/mcpls](https://github.com/bug-ops/mcpls) — Rust universal bridge
- [ktnyt/cclsp](https://github.com/ktnyt/cclsp) — Claude Code + LSP
- [oraios/serena](https://github.com/oraios/serena) — LSP abstraction for agents
- [axivo/mcp-lsp](https://github.com/axivo/mcp-lsp) — Multi-language MCP-LSP

### Другое
- [cli-lsp-client](https://github.com/eli0shin/cli-lsp-client) — CLI LSP daemon
- [langserver.org](https://langserver.org/) — LSP implementation catalog
- [SchemaStore](https://www.schemastore.org/) — JSON Schema registry
