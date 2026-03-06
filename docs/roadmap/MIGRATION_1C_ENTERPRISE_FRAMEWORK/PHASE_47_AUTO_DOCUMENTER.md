# Фаза 47: Auto-Documenter (Profile #7)

**Tier:** 2 — Основные сервисы
**Статус:** TODO
**Зависимости:** Фаза 44 (Infrastructure)
**Оценка:** ~5 часов
**Приоритет:** CRITICAL — ключевой компонент lazy-mcp профиля #7

---

## Цель

Полный перенос auto-documenter — Node.js MCP-сервера автоматической генерации документации для BSL-кода с tree-sitter парсингом и ротацией 5 AI-провайдеров.

---

## Компонент

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\autodocument\` |
| **Цель** | `D:\1С-Framework\tools\auto-documenter\` |
| **Runtime** | Node.js (TypeScript -> JS) |
| **Entry point** | `mcp-start.js` |
| **Timeout** | 180s (3 минуты) |
| **Memory** | 4096 MB (`NODE_OPTIONS --max-old-space-size=4096`) |
| **AI Provider** | Z.AI GLM-5 (primary), Gemini/Groq/Ollama (fallback) |
| **LOC** | ~8,000 |

---

## 5 MCP Tools

| Tool | Назначение | Вход | Выход |
|------|-----------|------|-------|
| `generate_documentation` | Генерация markdown документации для BSL-каталога | Путь к каталогу | `documentation.md` в каждой папке |
| `autotestplan` | Генерация тест-плана | Путь к каталогу | `testplan.md` |
| `autoreview` | Code review по стандартам 1С | Путь к каталогу | `review.md` |
| `generate_inline_docs` | JSDoc-стиль комментарии в исходниках | Путь к файлу | Модифицированный файл |
| `generate_dependency_graph` | Визуализация call graph | Путь к каталогу | Markdown с деревом вызовов |

---

## BSL-анализ (tree-sitter)

### Парсинг (bsl-treesitter-analyzer.ts)

100% точный AST-парсинг через tree-sitter-bsl WASM grammar:
- Процедуры и функции (с параметрами и значениями по умолчанию)
- Экспорты (ключевое слово `Экспорт` / `Export`)
- Регионы (`#Область` / `#КонецОбласти`)
- Переменные (`Перем`)
- Комментарии (однострочные `//` и блочные)

### 11 типов модулей (structure-1c-analyzer.ts)

| Тип модуля | Паттерн пути |
|-----------|-------------|
| FORM_MODULE | `/Forms/*/Ext/Form/Module.bsl` или `/Формы/*/Ext/Form/Module.bsl` |
| OBJECT_MODULE | `Ext/ObjectModule.bsl` |
| MANAGER_MODULE | `Ext/ManagerModule.bsl` |
| COMMAND_MODULE | `/Commands/*/Ext/CommandModule.bsl` |
| COMMON_MODULE | `/CommonModules/*/Ext/Module.bsl` |
| RECORDSET_MODULE | `Ext/RecordSetModule.bsl` |
| SESSION_MODULE | `SessionModule.bsl` |
| APPLICATION_MODULE | `ApplicationModule.bsl` |
| MANAGED_APPLICATION_MODULE | `ManagedApplicationModule.bsl` |
| EXTERNAL_CONNECTION_MODULE | `ExternalConnectionModule.bsl` |
| VALUE_MANAGER_MODULE | `Ext/ValueManagerModule.bsl` |

### 25+ типов метаданных

Справочники, Документы, РегистрыСведений, РегистрыНакопления, Обработки, Отчёты, ОбщиеМодули, ПланыОбмена, ПланыСчетов, ПланыВидовХарактеристик, БизнесПроцессы, Задачи и др.

### Call Graph (bsl-call-graph-analyzer.ts)

Классификация вызовов:
- `INTERNAL` — функции в том же модуле
- `COMMON_MODULE` — вызовы общих модулей
- `MANAGER` — менеджер справочника/документа
- `OBJECT_METHOD` — методы объекта
- `PLATFORM` — платформенные функции
- `CONSTRUCTOR` — `Новый` (New) конструкторы

Визуализация:
```
ГлавнаяПроцедура()
+-- ПодготовитьДанные()
|   L-- ПроверитьПараметры()
+-- ВыполнитьОбработку()
|   +-- ОбщийМодуль.Функция()
|   L-- ЗаписатьРезультат()
L-- ОповеститьПользователя()
```

### Metadata XML (metadata-parser.ts)

- Парсинг 1С XML метаданных (формы, реквизиты, табличные части)
- Валидация Form.xml vs Module.bsl (quality score 0-100)
- Рекомендации best practices

---

## 5 AI-провайдеров с ротацией

| Провайдер | Стоимость | Скорость | Лимиты |
|-----------|----------|----------|--------|
| Google Gemini | Free (1,500/day) | Fast | ~1,533 модулей/день |
| Groq | Free (500k tokens/day) | Very Fast | Unlimited |
| Ollama | Free (Local) | Variable | Unlimited |
| xAI Grok | Paid | Medium | Unlimited |
| OpenRouter | Paid ($60-150/mo) | Medium | Unlimited |

**Стратегия ротации:**
- Primary: настраивается через `AUTODOC_PRIMARY_PROVIDER`
- Fallback: автоматическое переключение при ошибке/rate limit
- Cost tracking: бюджет и usage analytics встроены

---

## Исходная структура файлов

```
autodocument/
├── mcp-start.js                          # MCP server starter
├── package.json                          # npm dependencies
├── tsconfig.json                         # TypeScript config
├── jest.config.js                        # Test config
├── src/
│   ├── index.ts                          # MCP server definition
│   ├── prompt-config.ts                  # Centralized prompts
│   ├── analyzer/
│   │   ├── index.ts                      # File analyzer router
│   │   ├── bsl-treesitter-analyzer.ts    # Tree-sitter BSL parsing (~500 LOC)
│   │   ├── bsl-call-graph-analyzer.ts    # Call graph analysis (~400 LOC)
│   │   ├── structure-1c-analyzer.ts      # 1C metadata detection (~600 LOC)
│   │   └── bsl-integration.ts            # Integration layer
│   ├── tools/
│   │   ├── registry.ts                   # Tool registry
│   │   ├── aggregator.ts                 # Bottom-up processor
│   │   ├── base-tool.ts                  # Abstract base class
│   │   ├── documentation-tool.ts         # generate_documentation
│   │   ├── testplan-tool.ts              # autotestplan
│   │   ├── review-tool.ts               # autoreview
│   │   ├── inline-docs-tool.ts           # generate_inline_docs
│   │   └── dependency-graph-tool.ts      # generate_dependency_graph
│   ├── providers/
│   │   ├── provider-factory.ts           # Provider instantiation
│   │   ├── provider-rotation.ts          # 5-provider rotation
│   │   ├── ollama-utils.ts              # Ollama integration
│   │   └── local-llm-config.ts          # Local LLM setup
│   ├── metadata/
│   │   ├── metadata-parser.ts            # XML parsing
│   │   ├── metadata-types.ts             # TypeScript types
│   │   └── metadata-integration.ts       # Prompt enrichment
│   ├── prompts/
│   │   ├── bsl-context-prompts.ts        # BSL-specific context
│   │   └── bsl-review-prompts.ts         # 1C standards review
│   ├── cache/
│   │   ├── index.ts                      # Cache management
│   │   └── response-cache.ts             # AI response caching
│   ├── cli/
│   │   ├── index.ts                      # CLI entry point
│   │   └── commands/                     # generate, testplan, review, etc.
│   ├── browser/                          # Web UI for browsing docs
│   ├── benchmark/                        # Performance benchmarking
│   └── config/
│       └── config-loader.ts              # YAML/ENV config
├── build/                                # Compiled JavaScript
├── docs/
│   ├── architecture/
│   │   ├── BSL_ANALYZER.md              # 430+ line technical spec
│   │   ├── METADATA_ANALYZER.md
│   │   └── README.md
│   ├── guides/
│   │   ├── FREE_TIER_SETUP.md
│   │   ├── BSL_DEVELOPMENT_GUIDE.md
│   │   └── PROVIDER-CONFIGURATION.md
│   └── features/
│       └── FORM_XML_VALIDATION.md
└── test-autodoc/                         # Example BSL test files
```

---

## Шаги

### 47.1 Скопировать компонент

```bash
cp -r D:/1C-Enterprise_Framework/autodocument tools/auto-documenter
# Удалить ненужное
rm -rf tools/auto-documenter/node_modules
rm -rf tools/auto-documenter/.git
```

### 47.2 Обновить mcp-start.js

Изменить пути и env:
- `cwd`: `D:\1С-Framework\tools\auto-documenter`
- Проверить `require()` пути к build/

### 47.3 Установить зависимости

```bash
cd tools/auto-documenter
npm install
```

**Ключевые зависимости:**
- `@modelcontextprotocol/sdk` — MCP protocol
- `tree-sitter` + `web-tree-sitter` + `tree-sitter-bsl` — AST parsing
- `openai` — LLM API client
- `xml2js` — XML parsing
- `commander` — CLI framework
- `js-yaml` — YAML config

### 47.4 Пересобрать TypeScript

```bash
cd tools/auto-documenter
npm run build
```

**Критерий:** `build/` содержит скомпилированный JS, 0 ошибок TypeScript.

### 47.5 Зарегистрировать в .mcp.json

```json
"auto-documenter": {
  "command": "node",
  "args": ["mcp-start.js"],
  "cwd": "D:\\1С-Framework\\tools\\auto-documenter",
  "env": {
    "NODE_OPTIONS": "--max-old-space-size=4096",
    "DEEP_REASONING_API_KEY": "${DEEP_REASONING_API_KEY}",
    "DEEP_REASONING_BASE_URL": "https://api.z.ai/api/anthropic",
    "DEEP_REASONING_MODEL": "glm-5"
  },
  "timeout": 180000
}
```

### 47.6-47.8 Тестирование

| Тест | Команда | Ожидаемый результат |
|------|---------|-------------------|
| generate_documentation | `mcp__auto-documenter__generate_documentation(path)` | `documentation.md` создан |
| autoreview | `mcp__auto-documenter__autoreview(path)` | `review.md` создан |
| autotestplan | `mcp__auto-documenter__autotestplan(path)` | `testplan.md` создан |

Тестовые BSL-файлы: `tools/auto-documenter/test-autodoc/`

### 47.9 Создать skill

`.claude/skills/auto-documenter/SKILL.md`:
- Триггеры: 'документация BSL', 'generate_documentation', 'autoreview', 'testplan', 'code review BSL'
- Описание 5 tools с параметрами
- Workflow: анализ -> документация -> review -> testplan

### 47.10 Проверить tree-sitter-bsl WASM

```bash
# Проверить наличие .wasm файла
ls tools/auto-documenter/node_modules/tree-sitter-bsl/*.wasm
```

Если отсутствует — скачать из npm или GitHub releases.

---

## Что адаптировать

| Файл | Изменение | Причина |
|------|-----------|---------|
| `mcp-start.js` | Обновить `cwd` и env пути | Новое расположение |
| `src/providers/provider-rotation.ts` | Опционально: добавить Z.AI как отдельный провайдер | Уже настроен через env |
| `.mcp.json` | Server entry с правильным cwd | Регистрация в Claude Code |
| `src/index.ts` | Проверить `calculate1COutputDir()` | Пути вывода |

## Что НЕ менять

- Tree-sitter парсер (самодостаточный, WASM)
- Tool registry и aggregator (стабильные, отлажены)
- Prompt templates (BSL-специфичные, 1C standards)
- CLI интерфейс (standalone usage)
- Cache система (response caching)
- Benchmark модуль

---

## Режимы работы

| Режим | Описание | Использование |
|-------|----------|---------------|
| **Bottom-up** | Сначала листовые каталоги, потом агрегация наверх | По умолчанию |
| **Incremental** | Только изменённые файлы | `--incremental` |
| **Watch** | Авто-генерация при изменении файлов | `--watch` |
| **Cache** | AI response caching | Автоматически |

---

## Чеклист завершения

- [ ] `tools/auto-documenter/` содержит все файлы
- [ ] `npm install` прошёл без ошибок
- [ ] `npm run build` — 0 TypeScript ошибок
- [ ] `node mcp-start.js` запускается
- [ ] Tree-sitter-bsl WASM grammar на месте
- [ ] `.mcp.json` содержит `auto-documenter`
- [ ] MCP tool `generate_documentation` работает на тестовом BSL
- [ ] MCP tool `autoreview` работает
- [ ] MCP tool `autotestplan` работает
- [ ] Skill `auto-documenter/SKILL.md` создан
- [ ] Git commit: `feat: Phase 47 — Auto-Documenter migration (Profile #7)`
