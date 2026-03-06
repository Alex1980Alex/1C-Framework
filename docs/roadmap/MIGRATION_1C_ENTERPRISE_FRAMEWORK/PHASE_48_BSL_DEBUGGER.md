# Фаза 48: BSL Debugger

**Tier:** 2 — Основные сервисы
**Статус:** DONE
**Зависимости:** Фаза 44 (Infrastructure)
**Оценка:** ~3 часа

---

## Цель

Перенести интерактивный отладчик BSL-кода — Node.js MCP-сервер с 10 инструментами отладки через OneScript runtime.

---

## Компонент

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\bsl-debugger\` |
| **Цель** | `D:\1С-Framework\tools\bsl-debugger\` |
| **Runtime** | Node.js (TypeScript -> JS) |
| **LOC** | ~3,900 |
| **Версия** | v1.0.0 (Sprint 5.1 — 2025-12-24) |

---

## 10 Debug Tools

| # | Tool | Назначение |
|---|------|-----------|
| 1 | `bsl_analyze` | Статический анализ структуры кода |
| 2 | `bsl_debug_start` | Запуск debug-сессии |
| 3 | `bsl_debug_breakpoints` | Управление точками останова |
| 4 | `bsl_debug_step` | Пошаговое выполнение |
| 5 | `bsl_debug_variables` | Получение значений переменных |
| 6 | `bsl_debug_evaluate` | Вычисление выражений |
| 7 | `bsl_debug_stack` | Получение стека вызовов |
| 8 | `bsl_execute` | Выполнение BSL-кода |
| 9 | `bsl_debug_stop` | Остановка debug-сессии |
| 10 | `bsl_get_source` | Получение исходного кода с подсветкой |

---

## Архитектура

```
bsl-debugger/
├── package.json
├── tsconfig.json
├── src/
│   ├── index.ts              # MCP server entry point
│   ├── lexer.ts              # BSL Lexer (~450 LOC)
│   ├── parser.ts             # BSL Parser (~890 LOC)
│   ├── debug-engine.ts       # Debug Engine (~950 LOC)
│   ├── runtime.ts            # OneScript Runtime Integration (~736 LOC)
│   └── types.ts              # TypeScript type definitions
├── dist/                     # Compiled JS (entry: dist/index.js)
└── README.md
```

**Компоненты:**
- **Lexer** (450 LOC) — токенизация BSL-кода
- **Parser** (890 LOC) — AST-построение
- **Debug Engine** (950 LOC) — breakpoints, stepping, evaluation
- **Runtime** (736 LOC) — интеграция с OneScript

---

## Шаги

### 48.1 Скопировать компонент

```bash
cp -r D:/1C-Enterprise_Framework/bsl-debugger tools/bsl-debugger
rm -rf tools/bsl-debugger/node_modules
rm -rf tools/bsl-debugger/.git
```

### 48.2 Установить и собрать

```bash
cd tools/bsl-debugger
npm install
npm run build
```

**Критерий:** `dist/index.js` существует, 0 ошибок.

### 48.3 Зарегистрировать в .mcp.json

```json
"bsl-debugger": {
  "command": "node",
  "args": ["dist/index.js"],
  "cwd": "D:\\1С-Framework\\tools\\bsl-debugger",
  "env": { "NODE_ENV": "production" },
  "timeout": 60000
}
```

### 48.4 Тестирование

| Тест | Действие | Ожидаемый результат |
|------|----------|-------------------|
| Analyze | `bsl_analyze(code)` | Структура: процедуры, функции, переменные |
| Debug start | `bsl_debug_start(file)` | Session ID |
| Breakpoint | `bsl_debug_breakpoints(session, line)` | Breakpoint set |
| Step | `bsl_debug_step(session)` | Текущая позиция |
| Variables | `bsl_debug_variables(session)` | Список переменных с значениями |
| Evaluate | `bsl_debug_evaluate(session, expr)` | Результат выражения |
| Stack | `bsl_debug_stack(session)` | Call stack |
| Execute | `bsl_execute(code)` | Результат выполнения |
| Source | `bsl_get_source(file)` | Код с подсветкой |
| Stop | `bsl_debug_stop(session)` | Session terminated |

### 48.5 Создать skill

`.claude/skills/bsl-debugger/SKILL.md`:

```markdown
# BSL Debugger

## Триггеры
- 'отладка BSL', 'debug BSL', 'debug 1C'
- 'breakpoint', 'точка останова'
- 'переменные отладки', 'стек вызовов'
- 'выполнить BSL', 'execute BSL'

## Tools
1. bsl_analyze — статический анализ
2. bsl_debug_start — начать отладку
3. bsl_debug_breakpoints — точки останова
4. bsl_debug_step — пошагово
5. bsl_debug_variables — переменные
6. bsl_debug_evaluate — вычислить
7. bsl_debug_stack — стек
8. bsl_execute — выполнить код
9. bsl_debug_stop — остановить
10. bsl_get_source — исходник с подсветкой

## Workflow
1. bsl_analyze для понимания структуры
2. bsl_debug_start для начала сессии
3. bsl_debug_breakpoints для установки точек
4. bsl_debug_step + bsl_debug_variables для отладки
5. bsl_debug_stop для завершения
```

---

## Чеклист завершения

- [x] `tools/bsl-debugger/` содержит все файлы (dist/, package.json, README.md)
- [x] `npm install` — успех (pre-built dist/, no build needed)
- [x] `dist/index.js` существует
- [x] `.mcp.json` содержит `bsl-debugger`
- [x] Все 10 tools доступны из Claude Code (verified via MCP JSON-RPC)
- [x] `bsl_analyze` работает на тестовом BSL-коде (AST: functions, procedures, params, exports)
- [ ] `bsl_execute` выполняет простой BSL-скрипт (требует OneScript runtime `oscript`)
- [ ] Skill `bsl-debugger/SKILL.md` создан
- [ ] Git commit: `feat: Phase 48 — BSL Debugger migration`
