---
name: bsl-development
description: "BSL Development — разработка на 1С:Предприятие. ИСПОЛЬЗУЙ когда пишешь BSL код, модули 1С, процедуры/функции, обработки проведения, формы. Триггеры: 'BSL', '1С код', 'модуль 1С', 'процедура BSL', 'конфигурация 1С', 'справочник', 'документ 1С', 'регистр', 'модуль объекта', 'модуль формы', 'общий модуль', 'обработка проведения', 'ПередЗаписью'. НЕ для запросов к данным (→ 1c-mcp-crud), НЕ для документации 1С (→ 1c-doc-research)."
---

# BSL Development — разработка на 1С:Предприятие

## Обзор

Скилл для работы с кодом на языке BSL (Built-in Scripting Language)
платформы 1С:Предприятие 8.3.27.

**Источник миграции:** `D:\1C-Enterprise_Framework` → `D:\1С-Framework`
**Фаза:** 44 (Infrastructure)

## Триггеры

- 'BSL', '1С код', 'модуль 1С', 'процедура BSL'
- 'конфигурация 1С', 'справочник', 'документ 1С', 'регистр'
- 'модуль объекта', 'модуль формы', 'общий модуль'
- 'отладка BSL', 'debug 1С', 'semantic search BSL'

## Доступные MCP-инструменты

| Инструмент | MCP сервер | Назначение |
|-----------|-----------|-----------|
| **Reasoning (ОБЯЗАТЕЛЬНЫЙ)** | `mcp-reasoner` | 3 BSL-стратегии: архитектура, документы, подсистемы |
| Семантический поиск | `bsl-semantic-search` | Поиск похожего кода (3,908+ модулей) |
| Автодокументация | `auto-documenter` | generate_documentation, autoreview, autotestplan |
| Отладка (OneScript, статика) | `bsl-debugger` | breakpoints, step, variables, evaluate — без live 1С |
| Live отладка (RDBG, Scenario B) | `1c-debug` | post-BP-fire handshake против running 1С: debug_set_breakpoint, debug_variables, debug_evaluate, debug_step (см. [16.7](../../docs/framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.7_Autonomous_Debug_Workflow.md)) |
| API платформы | `bsl-platform-context` | Типы, методы, свойства 1С:8.3.27 |
| AST-анализ | `ast-grep-mcp` | Tree-sitter парсинг BSL |
| LSP | `serena` | Symbol extraction, рефакторинг |

## Workflow

### 0. Архитектурный анализ (ОБЯЗАТЕЛЬНЫЙ для 1С кода)

Перед написанием/рефакторингом BSL кода — выбрать стратегию анализа:

| Контекст задачи | Стратегия | Глубина |
|----------------|-----------|---------|
| Архитектура модулей, SOLID, God Object | `bsl_architecture` | 8 уровней |
| Проведение, движения, регистры, производительность | `bsl_document_patterns` | 10 уровней |
| Подсистемы, RBAC, RLS, интеграция, зависимости | `bsl_subsystem_analysis` | 12 уровней |

```
mcp__reasoner__processThought(
  thought="Анализ архитектуры модуля ОбработкаДокументов",
  thoughtNumber=1,
  totalThoughts=5,
  nextThoughtNeeded=true,
  strategyType="bsl_architecture"
)
```



### 1. Анализ кода
```
mcp__ast-grep-mcp__ast_grep(pattern="Процедура $NAME($$$PARAMS)", language="bsl")
```
или
```
mcp__serena__find_symbol(name_path="...", relative_path="...")
```

### 2. Поиск похожего кода
```
mcp__bsl-semantic-search__search(query="обработка проведения документа", limit=5)
```

### 3. Контекст платформы 1С
```
mcp__bsl-platform-context__get_method_info(method_name="СправочникМенеджер.НайтиПоКоду")
```

### 4. Документация
```
mcp__auto-documenter__generate_documentation(file_path="...")
```

### 5. Code Review
```
mcp__auto-documenter__autoreview(file_path="...")
```

### 6. Отладка (при необходимости)
```
mcp__bsl-debugger__set_breakpoint(file="...", line=...)
mcp__bsl-debugger__step_over()
mcp__bsl-debugger__get_variables()
```

## Стандарты кода 1С

При написании BSL кода следовать стандартам:
- Имена процедур/функций: CamelCase
- Имена переменных: camelCase
- Отступы: табуляция
- Максимальная длина строки: 120 символов

## Примеры использования

### Поиск процедур проведения
```bsl
// Запрос к bsl-semantic-search
"обработка проведения документа движения регистры"
```

### Генерация документации модуля
```
Использовать auto-documenter с профилем #7 (lazy-mcp)
```

## Конфигурация (Phase 8.12.8 production switchover, 2026-04-30)

- **MCP профиль:** `.mcp/bsl.json`
- **Embeddings:** Qwen3-Embedding-8B (4096d, через Ollama `qwen3-embedding`)
- **Qdrant collection:** `bsl_code_v4_late` (Qwen3 + Late Chunking pooling, +26% recall vs E5 baseline на 50q expanded pilot)
- **Query instruction:** default web-retrieval template из HF model card (BSL-specific варианты дали -100%, см. roadmap §21.10 H1 ablation)
- **SQLite fallback:** `cache/docs-mcp/hybrid_search.db` (FTS5, 12983 docs) — когда Qdrant недоступен
- **Legacy collections:** `bsl_code_v3` (E5 1024d, drop pending Phase 8.11.3), `bsl_code_v2` (nomic 768d, deprecated), `bsl_code_v4` (Qwen3+std 4096d, research-baseline only — std pooling даёт -64% recall vs Late)

## Auto-reindex BSL при git commit (2026-04-30)

При активном `git config core.hooksPath scripts/git_hooks` автоматически срабатывает incremental reindex `bsl_code_v4_late` для изменённых `.bsl` файлов в `configuration/<X>/`.

**Команда incremental BSL reindex (используется хуком, можно вызвать вручную):**

```bash
python scripts/reindex_bsl_qwen3.py \
    --paths "<path-to-file1.bsl>" "<path-to-file2.bsl>" \
    --embedder qwen3-tei \
    --collection bsl_code_v4_late \
    --batch-size 32
```

**Особенности `--paths` режима:**
- Auto-detect project root из path (walk до `configuration/<X>/`)
- Все файлы должны быть в одном project root (иначе ERROR)
- `--recreate` запрещён (нельзя дропнуть production-коллекцию для incremental)
- Контекст-обогащение работает (если есть `cache/bsl_call_graph.db`)
- **Delete-stale**: после upsert удаляет chunks с тем же `module_path` но другими `chunk_id` — ловит удалённые/переименованные функции в файле
- Idempotent: повторный запуск на неизменном файле = same point_ids → overwrite, no-op

**Backend caveat:** `qwen3-tei` (std pooling) вместо `qwen3-st` (Late Chunking) — избегает GPU contention с TEI Docker (две копии Qwen3-8B FP16 = 32 GB на 24 GB RTX 3090). Trade-off: incremental chunks приземляются с std pooling, остальная коллекция — Late. Quality drop ~5-10% на свежих символах. Рекомендуется periodic full reindex по §23 roadmap для re-alignment.

**Лог:** `cache/bsl_reindex.log`

## Зависимости

- Фаза 45: BSL Semantic Search + SonarQube
- Фаза 46: MCP 1C Integration
- Фаза 47: Auto-Documenter
- Фаза 48: BSL Debugger
- Фаза 52: Serena LSP Integration
- Фаза 57: MCP Reasoner (3 BSL-стратегии)


## Незадокументированные bsl_tool

- `CallGraphStore` (src\bsl\call_graph\store.py)
- `BSLStyleProfile` (src\bsl\coding_assistant\style_extractor.py)
- `BSLStyleExtractor` (src\bsl\coding_assistant\style_extractor.py)
- `EvalResult` (src\bsl\evaluation\metrics.py)
- `ObjectInfo` (src\bsl\knowledge_graph\metadata_extractor.py)
- `MetadataExtractor` (src\bsl\knowledge_graph\metadata_extractor.py)
- `OAuth2BearerMiddleware` (src\bsl\mcp_server\http_server.py)
- `MCPHttpServer` (src\bsl\mcp_server\http_server.py)
- `MCPProxy` (src\bsl\mcp_server\mcp_server.py)
- `OneCClient` (src\bsl\mcp_server\onec_client.py)
- `BSLASTParser` (src\bsl\parser\bsl_ast_parser.py)
- `BSLChunk` (src\bsl\parser\bsl_chunker.py)
- `BSLChunker` (src\bsl\parser\bsl_chunker.py)
- `BSLContextEnricher` (src\bsl\parser\context_enricher.py)
- `SymbolType` (src\bsl\parser\models.py)
- `CompilationDirective` (src\bsl\parser\models.py)
- `ModuleType` (src\bsl\parser\models.py)
- `BSLParam` (src\bsl\parser\models.py)
- `BSLCall` (src\bsl\parser\models.py)
- `BSLSymbol` (src\bsl\parser\models.py)
- `BSLVariable` (src\bsl\parser\models.py)
- `BSLRegion` (src\bsl\parser\models.py)
- `BSLModule` (src\bsl\parser\models.py)
- `BSLSearchSettings` (src\bsl\semantic_search\config.py)
- `RouterResult` (src\bsl\semantic_search\hybrid_router.py)
- `SonarQubeConfig` (src\bsl\sonar\config_manager.py)
- `ConfigManager` (src\bsl\sonar\config_manager.py)
- `Issue` (src\bsl\sonar\report_generator.py)
- `AnalysisReport` (src\bsl\sonar\report_generator.py)
- `ReportGenerator` (src\bsl\sonar\report_generator.py)
- `BSLRule` (src\bsl\sonar\rules_manager.py)
- `RulesManager` (src\bsl\sonar\rules_manager.py)
