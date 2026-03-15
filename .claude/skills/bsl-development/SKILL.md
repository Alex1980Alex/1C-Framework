---
name: bsl-development
description: "BSL Development — разработка на 1С:Предприятие. ИСПОЛЬЗУЙ когда пишешь BSL код, модули 1С, процедуры/функции, обработки проведения, формы. Триггеры: 'BSL', '1С код', 'модуль 1С', 'процедура BSL', 'конфигурация 1С', 'справочник', 'документ 1С', 'регистр', 'модуль объекта', 'модуль формы', 'общий модуль', 'обработка проведения', 'ПередЗаписью'. НЕ для запросов к данным (→ 1c-mcp-toolkit), НЕ для документации 1С (→ 1c-doc-research)."
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
| Отладка | `bsl-debugger` | breakpoints, step, variables, evaluate |
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

## Конфигурация

- **MCP профиль:** `.mcp/bsl.json`
- **Embeddings:** nomic-embed-text (768d)
- **Qdrant collection:** `bsl_code_v2`
- **SQLite fallback:** `cache/docs-mcp/hybrid_search.db` (FTS5, 12983 docs) — используется когда Qdrant недоступен

## Зависимости

- Фаза 45: BSL Semantic Search + SonarQube
- Фаза 46: MCP 1C Integration
- Фаза 47: Auto-Documenter
- Фаза 48: BSL Debugger
- Фаза 52: Serena LSP Integration
- Фаза 57: MCP Reasoner (3 BSL-стратегии)
