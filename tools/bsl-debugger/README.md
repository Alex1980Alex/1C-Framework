# BSL-DEBUGGER MCP Server

> **Статус:** ✅ РЕАЛИЗОВАН (Sprint 5.1 - 2025-12-24)
> **Версия:** 1.0.0
> **Тип:** MCP Server для отладки BSL/1C кода

## Обзор

BSL-DEBUGGER - специализированный MCP сервер для отладки кода на языке 1С/BSL через OneScript runtime. Предоставляет 10 инструментов для интерактивной отладки, анализа структуры кода и выполнения BSL скриптов.

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        BSL-DEBUGGER                             │
│                                                                  │
│  ┌────────────┐      ┌──────────────────────────────────────┐  │
│  │  Claude    │─────►│         MCP Server                   │  │
│  │  Code      │      │  ┌────────────────────────────────┐  │  │
│  └────────────┘      │  │    Tools Layer (10 tools)      │  │  │
│                      │  │                                │  │  │
│                      │  │  1. bsl_analyze                │  │  │
│                      │  │  2. bsl_debug_start            │  │  │
│                      │  │  3. bsl_debug_breakpoints      │  │  │
│                      │  │  4. bsl_debug_step             │  │  │
│                      │  │  5. bsl_debug_variables        │  │  │
│                      │  │  6. bsl_debug_evaluate         │  │  │
│                      │  │  7. bsl_debug_stack            │  │  │
│                      │  │  8. bsl_execute                │  │  │
│                      │  │  9. bsl_debug_stop             │  │  │
│                      │  │  10. bsl_get_source            │  │  │
│                      │  └────────────────────────────────┘  │  │
│                      │                │                     │  │
│                      │  ┌─────────────┼─────────────────┐  │  │
│                      │  │             ▼                 │  │  │
│                      │  │     ┌───────────────┐         │  │  │
│                      │  │     │ Debug Engine   │         │  │  │
│                      │  │     │ - Breakpoints  │         │  │  │
│                      │  │     │ - Stepping     │         │  │  │
│                      │  │     │ - Evaluation   │         │  │  │
│                      │  │     └───────────────┘         │  │  │
│                      │  │             │                 │  │  │
│                      │  │             ▼                 │  │  │
│                      │  │     ┌───────────────┐         │  │  │
│                      │  │     │  OneScript    │         │  │  │
│                      │  │     │  Runtime      │         │  │  │
│                      │  │     └───────────────┘         │  │  │
│                      │  └──────────────────────────────┘  │  │
│                      └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Инструменты MCP

### 1. bsl_analyze
**Назначение:** Статический анализ структуры BSL кода

**Параметры:**
- `code` (string, optional): BSL код для анализа
- `file` (string, optional): Путь к .bsl или .os файлу

**Возвращает:**
```json
{
  "procedures": ["Процедура1", "Процедура2"],
  "functions": ["Функция1", "Функция2"],
  "variables": ["Переменная1", "Переменная2"],
  "exports": ["ЭкспортнаяФункция"],
  "structure": {...}
}
```

### 2. bsl_debug_start
**Назначение:** Запуск сессии отладки

**Параметры:**
- `code` (string): BSL код для отладки
- `file` (string, optional): Путь к файлу

**Возвращает:**
```json
{
  "sessionId": "debug-session-123",
  "breakpoints": [],
  "currentLine": 0,
  "status": "started"
}
```

### 3. bsl_debug_breakpoints
**Назначение:** Управление точками останова

**Параметры:**
- `sessionId` (string): ID сессии
- `action` (string): "set", "clear", "list"
- `line` (number, optional): Номер строки для set
- `condition` (string, optional): Условие для conditional breakpoint

**Возвращает:**
```json
{
  "breakpoints": [10, 25, 42],
  "message": "Breakpoints updated"
}
```

### 4. bsl_debug_step
**Назначение:** Пошаговое выполнение

**Параметры:**
- `sessionId` (string): ID сессии
- `action` (string): "stepOver", "stepIn", "stepOut", "continue"

**Возвращает:**
```json
{
  "currentLine": 25,
  "stackDepth": 2,
  "finished": false
}
```

### 5. bsl_debug_variables
**Назначение:** Получение значений переменных

**Параметры:**
- `sessionId` (string): ID сессии
- `scope` (string, optional): "local", "global", "all"

**Возвращает:**
```json
{
  "variables": [
    {"name": "Переменная1", "value": "Значение", "type": "String"},
    {"name": "Массив", "value": "[...]", "type": "Array"}
  ]
}
```

### 6. bsl_debug_evaluate
**Назначение:** Вычисление выражения

**Параметры:**
- `sessionId` (string): ID сессии
- `expression` (string): Выражение для вычисления

**Возвращает:**
```json
{
  "result": "Результат вычисления",
  "type": "String",
  "error": null
}
```

### 7. bsl_debug_stack
**Назначение:** Получение стека вызовов

**Параметры:**
- `sessionId` (string): ID сессии

**Возвращает:**
```json
{
  "frames": [
    {"function": "ОсновнаяФункция", "line": 10, "file": "module.bsl"},
    {"function": "Вспомогательная", "line": 25, "file": "module.bsl"}
  ]
}
```

### 8. bsl_execute
**Назначение:** Выполнение BSL кода

**Параметры:**
- `code` (string): BSL код для выполнения
- `file` (string, optional): Путь к файлу
- `args` (array, optional): Аргументы командной строки

**Возвращает:**
```json
{
  "success": true,
  "output": "Результат выполнения",
  "errors": "",
  "exitCode": 0,
  "duration": 150
}
```

### 9. bsl_debug_stop
**Назначение:** Завершение сессии отладки

**Параметры:**
- `sessionId` (string): ID сессии

**Возвращает:**
```json
{
  "message": "Debug session stopped",
  "sessionId": "debug-session-123"
}
```

### 10. bsl_get_source
**Назначение:** Получение исходного кода с подсветкой

**Параметры:**
- `file` (string): Путь к файлу
- `highlightLine` (number, optional): Строка для подсветки

**Возвращает:**
```json
{
  "source": "Функция Пример()\n\t// код\nКонецФункции",
  "lines": 3,
  "encoding": "utf-8"
}
```

## Установка

### Требования
- Node.js >= 18.0.0
- OneScript (опционально, для выполнения кода)
- npm >= 9.0.0

### Установка зависимостей

```bash
cd shared/mcp-servers/bsl-debugger
npm install
```

### Сборка

```bash
npm run build
```

## Конфигурация

### Добавление в .mcp.json

```json
{
  "mcpServers": {
    "bsl-debugger": {
      "command": "node",
      "args": [
        "D:\\1C-Enterprise_Framework\\shared\\mcp-servers\\bsl-debugger\\dist\\index.js"
      ],
      "env": {
        "NODE_ENV": "production"
      }
    }
  }
}
```

## Slash Commands

### `/debug-bsl <file>`

Запуск отладки BSL файла.

**Пример:**
```
/debug-bsl src/DataProcessors/Module.bsl
```

### `/analyze-bsl <file>`

Статический анализ BSL файла.

**Пример:**
```
/analyze-bsl src/CommonModules/MyModule.bsl
```

### `/execute-bsl <code>`

Выполнение BSL кода.

**Пример:**
```
/execute-bsl Сообщить("Привет, мир!");
```

## Примеры использования

### Пример 1: Поиск ошибки в коде

```
Пользователь: Почему падает этот код?
[код BSL с ошибкой]

Claude: Проанализирую код...
[использует bsl_analyze]
[запускает bsl_debug_start]
[устанавливает bsl_debug_breakpoints]
[выполняет bsl_debug_step]
[находит причину ошибки]

## 🔍 Диагностика

**Ошибка:** Индекс за границами массива
**Причина:** Массив пуст при обращении к индексу
**Исправление:** Добавить проверку перед обращением
```

### Пример 2: Интерактивная отладка

```
Пользователь: Отладь функцию РасчетСуммы

Claude:
1. [bsl_get_source] Получаю исходный код
2. [bsl_analyze] Анализирую структуру
3. [bsl_debug_start] Запускаю отладку
4. [bsl_debug_breakpoints] Ставлю breakpoint на строке 15
5. [bsl_debug_step] Шагаю по коду
6. [bsl_debug_variables] Проверяю значения переменных
7. [bsl_debug_evaluate] Вычисляю выражения
8. [bsl_debug_stop] Завершаю отладку
```

## Интеграция с Pipeline

BSL-DEBUGGER субагент автоматически активируется при:

1. **Обнаружении ошибок** в BSL коде
2. **Ключевых словах:** "отладь", "почему падает", "ошибка в"
3. **BSL файлах:** .bsl, .os расширения
4. **Запросах анализа:** "как работает", "почему не работает"

## Workflow субагента

```
┌──────────────┐
│   ANALYZE    │ Сбор контекста
└──────┬───────┘
       ▼
┌──────────────┐
│ HYPOTHESIZE  │ Формулирование гипотез
└──────┬───────┘
       ▼
┌──────────────┐
│    DEBUG     │ Интерактивная отладка
└──────┬───────┘
       ▼
┌──────────────┐
│   VERIFY     │ Верификация причины
└──────┬───────┘
       ▼
┌──────────────┐
│     FIX      │ Исправление
└──────┬───────┘
       ▼
┌──────────────┐
│  VALIDATE    │ Валидация исправления
└──────────────┘
```

## Технические детали

### Структура проекта

```
shared/mcp-servers/bsl-debugger/
├── dist/                 # Скомпилированные JS файлы
│   ├── index.js          # Главный MCP сервер
│   ├── engine/           # Движок отладки
│   ├── parser/           # BSL парсер и лексер
│   └── runtime/          # OneScript runtime интеграция
├── package.json          # Зависимости
└── README.md             # Этот файл
```

### Зависимости

```json
{
  "@modelcontextprotocol/sdk": "^1.0.0",
  "zod": "^3.22.0"
}
```

### Количество LOC

- **TypeScript исходники:** ~3894 LOC
- **Скомпилированный JavaScript:** ~3200 LOC
- **MCP инструментов:** 10
- **Компонентов:** 8 (lexer, parser, engine, runtime, и др.)

## Связанные документы

- **Спецификация субагента:** `src/projects/bsl-debugger-subagent/bsl-debugger-subagent.md`
- **Сравнение подходов:** `bsl-debugger-approaches-comparison.md`
- **DAP интеграция:** `mcp-bsl-dap-integration.md`
- **Отчёт по реализации:** `bsl-debugger-full-report.md`

## Статус реализации

| Компонент | Статус | LOC |
|-----------|--------|-----|
| MCP Server | ✅ | 868 |
| Lexer | ✅ | 450 |
| Parser | ✅ | 890 |
| Debug Engine | ✅ | 950 |
| Runtime Integration | ✅ | 736 |
| **ИТОГО** | **✅** | **~3894** |

**Дата реализации:** 2025-12-24
**Версия:** 1.0.0
**Лицензия:** MIT

---

**Автор:** Development Pipeline
**Версия документа:** 1.0
**Последнее обновление:** 2025-12-24
