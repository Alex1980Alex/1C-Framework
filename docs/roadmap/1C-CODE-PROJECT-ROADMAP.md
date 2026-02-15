# Дорожная карта: 1C-Code Project — BSL Development Environment

## Цель

Создать Claude Code-powered среду для полного цикла разработки на 1С: редактирование BSL, генерация модулей, рефакторинг, code review, консультации по документации.

## Архитектура: Layered (Core + 2 Framework)

```
~/.claude/                          Core (ГОТОВ)
  hooks/    ralph, guards            Работает во ВСЕХ проектах
  skills/   factory, evaluation      Работает во ВСЕХ проектах
  settings.json                      + mcpServers для PDF Framework

D:\1С-Framework\.claude/            Framework A — PDF RAG (ГОТОВ)
  hooks/    research-task-detector, search-optimizer...
  skills/   1c-doc-research, tech-research, pdf-knowledge...
  src/mcp_server/                    MCP с 12 tools (knowledge backend)

D:\1C-Code\.claude/                 Framework B — BSL Development (НОВЫЙ)
  hooks/    bsl-code-validator, module-structure-guard, bsl-test-runner
  skills/   bsl-coding, 1c-architecture
  settings.json                      hooks + mcpServers (BSL + PDF Framework)
```

### Ключевой принцип

- **Core** (`~/.claude/`) — универсальная инфраструктура (Ralph Wiggum, guards, factory)
- **PDF Framework** — knowledge backend (проиндексированная документация 1С)
- **1C-Code** — domain-specific environment (BSL hooks, skills, MCP tools)

### Потоки данных

```
Разработчик: "Напиши обработчик проведения документа ПриходнаяНакладная"
    │
    ├── Core: ralph_activator → активирует автономный цикл (Factory/Phase)
    ├── Framework B: маршрутизатор → 1c-architecture skill
    │
    ├── MCP (PDF Framework): search_documents("проведение документа")
    │     → чанки из проиндексированной документации 1С
    ├── MCP (PDF Framework): ask_question("как работает проведение?")
    │     → RAG ответ с источниками и номерами страниц
    │
    ├── Claude генерирует .bsl код на основе знаний
    │
    ├── MCP (BSL LS): анализ кода → 180 диагностик
    ├── BSL LSP плагин → подсветка, автодополнение
    │
    ├── Framework B: bsl-test-runner → OneScript тесты
    └── Core: ralph_wiggum_stop → код написан? валидация? тесты?
```

---

## Фаза 0: Подготовка (prerequisites)

**Цель:** Убедиться что все зависимости доступны.

| Задача | Команда/Действие | Статус |
|--------|-----------------|--------|
| Java Runtime (для BSL Language Server) | `java -version` (нужна JDK 17+) | |
| BSL Language Server JAR | Скачать с [GitHub releases](https://github.com/1c-syntax/bsl-language-server/releases) | |
| OneScript (опционально, для тестов) | Скачать с [oscript.io](https://oscript.io) | |
| Node.js (для BSL MCP Server) | `node -v` (нужна 18+) | |
| PDF Framework MCP сервер работает | `python -m src.mcp_server.server` из `D:\1С-Framework` | |

---

## Фаза 1: MCP-мост к знаниям 1С

**Цель:** Дать любому проекту доступ к проиндексированной документации 1С через MCP.

**Трудозатраты:** 5-10 минут

### Шаги

1. Добавить `mcpServers` в `C:\Users\AlexT\.claude\settings.json`:

```json
{
  "mcpServers": {
    "pdf-vector-graph": {
      "command": "D:\\1С-Framework\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "D:\\1С-Framework"
    }
  }
}
```

2. Проверить: в любом проекте Claude Code должен видеть 12 MCP tools:
   - `search_documents` — поиск по документации
   - `ask_question` — RAG-ответ с источниками
   - `graph_query` — запрос к графу знаний
   - `get_toc` — оглавление документа
   - и другие

### Результат

Все Claude Code проекты получают доступ к знаниям 1С:Предприятие 8.3.27 (1012 чанков, 218 страниц, 3166 сущностей графа).

---

## Фаза 2: Перенос 1c-doc-research в Core

**Цель:** Skill исследования 1С-документации доступен во всех проектах.

**Трудозатраты:** 10-15 минут

### Шаги

1. Скопировать skill:
   ```
   .claude/skills/1c-doc-research/ → ~/.claude/skills/1c-doc-research/
   ```

2. Обновить SKILL.md — убедиться что пути к cache используют `core_paths` или relative paths

3. Оставить копию в `.claude/skills/` как fallback (или удалить если не нужно)

### Результат

Skill `1c-doc-research` (5-фазный цикл, 8 категорий, приоритет источников) работает в любом проекте.

---

## Фаза 3: Каркас 1C-Code проекта

**Цель:** Создать `.claude/` структуру для проекта разработки 1С.

**Трудозатраты:** 1-2 часа

### Структура

```
D:\1C-Code\
  .claude/
    hooks/
      base/              # Fallback (копия из ~/.claude/hooks/base/)
      shared/            # Fallback (копия из ~/.claude/hooks/shared/)
    skills/
    cache/
    settings.json
  .bsl-language-server.json    # Конфигурация BSL Language Server
  src/                          # EDT-структура проекта 1С
```

### settings.json

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python D:\\1C-Code\\.claude\\hooks\\1c-task-router.py",
            "timeout": 5
          }
        ]
      }
    ]
  },
  "mcpServers": {
    "bsl-language-server": {
      "command": "npx",
      "args": ["-y", "phsin-mcp-bsl-ls"],
      "env": {
        "BSL_JAR": "D:\\tools\\bsl-language-server.jar",
        "BSL_CONFIG": "D:\\1C-Code\\.bsl-language-server.json",
        "BSL_MEMORY_MB": "4096"
      }
    }
  }
}
```

### .bsl-language-server.json

```json
{
  "language": "ru",
  "diagnostics": {
    "computeTrigger": "onSave",
    "skipSupport": "withSupportLocked"
  },
  "codeLens": {
    "showCognitiveComplexity": true,
    "showCyclomaticComplexity": true
  }
}
```

### Результат

Проект 1C-Code готов к работе: Core hooks подхватываются автоматически, MCP tools доступны (PDF Framework + BSL LS).

---

## Фаза 4: BSL MCP Server

**Цель:** Подключить BSL Language Server через MCP для валидации и форматирования кода.

**Трудозатраты:** 30 минут

### Шаги

1. Скачать BSL Language Server JAR:
   ```
   https://github.com/1c-syntax/bsl-language-server/releases
   → bsl-language-server-X.Y.Z-exec.jar → D:\tools\
   ```

2. Установить BSL MCP Server:
   ```bash
   npx -y phsin-mcp-bsl-ls
   ```

3. Проверить MCP tools:
   - `analyze_file` — анализ .bsl файла (180 диагностик)
   - `format_file` — форматирование кода
   - `analyze_directory` — пакетный анализ

### Доступные диагностики (топ по важности)

| Код | Диагностика | Severity |
|-----|------------|----------|
| `ParseError` | Синтаксические ошибки | Error |
| `UsingHardcodeNetworkAddress` | Хардкод IP-адресов | Vulnerability |
| `UsingModalWindows` | Модальные окна | Error |
| `EmptyCodeBlock` | Пустые блоки кода | Code Smell |
| `CognitiveComplexity` | Когнитивная сложность | Code Smell |
| `UnreachableCode` | Мертвый код | Error |
| `MethodSize` | Размер методов | Code Smell |
| `MissingTemporaryFileDeletion` | Утечка временных файлов | Error |

### Результат

Claude Code может валидировать BSL код в реальном времени через 180 диагностик BSL Language Server.

---

## Фаза 5: Skill bsl-coding

**Цель:** Skill с паттернами BSL-кода, шаблонами модулей, правилами code review.

**Трудозатраты:** 2-3 часа

### Структура

```
.claude/skills/bsl-coding/
  SKILL.md                    # Процедура + правила
  cache/
    _index.json
    module-patterns.md        # Паттерны модулей (общие, менеджера, объекта, формы)
    form-handlers.md          # Обработчики форм (ПриОткрытии, ПриИзменении...)
    query-patterns.md         # Паттерны запросов (СКД, динамические списки)
    transaction-patterns.md   # Транзакции, блокировки, проведение
    error-handling.md         # Обработка ошибок, попытка-исключение
    naming-conventions.md     # Соглашения об именах (стандарты 1С)
    antipatterns.md           # Типичные ошибки и как их избежать
  templates/
    common-module.bsl         # Шаблон общего модуля
    object-module.bsl         # Шаблон модуля объекта
    form-module.bsl           # Шаблон модуля формы
    manager-module.bsl        # Шаблон модуля менеджера
```

### SKILL.md содержание

- **Когда использовать**: написание/редактирование BSL, code review, рефакторинг
- **Триггеры**: "напиши модуль", "обработчик", "процедура", "функция", "запрос", "BSL"
- **Процедура**:
  1. Определить тип модуля (общий, менеджера, объекта, формы, команды)
  2. Проверить cache на паттерны для этого типа
  3. Консультация с документацией через MCP (search_documents)
  4. Генерация кода по шаблону + паттернам
  5. Валидация через BSL MCP Server
  6. Сохранение нового паттерна в cache (если уникальный)

### Категории знаний

1. **Модули**: общий, менеджера, объекта, формы, команды, сеанса, приложения
2. **Обработчики форм**: жизненный цикл, события элементов, команды
3. **Запросы**: язык запросов 1С, временные таблицы, пакетные запросы
4. **Транзакции**: явные/неявные, блокировки, deadlock prevention
5. **Проведение**: регистрация движений, контроль остатков, сторно
6. **Интеграция**: COM, HTTP, web-сервисы, обмен данными
7. **Антипаттерны**: God-модуль, N+1 запросы, блокировки в цикле

### Результат

Claude знает best practices BSL и генерирует код по стандартам 1С.

---

## Фаза 6: Skill 1c-architecture

**Цель:** Skill со знаниями об архитектуре конфигураций 1С, EDT-структуре, подсистемах.

**Трудозатраты:** 2-3 часа

### Структура

```
.claude/skills/1c-architecture/
  SKILL.md
  cache/
    _index.json
    edt-structure.md          # Структура EDT-проекта
    subsystems.md             # Подсистемы и их организация
    metadata-objects.md       # Типы объектов метаданных
    configuration-design.md   # Принципы проектирования конфигурации
    roles-and-rights.md       # Роли, права, RLS
    data-composition.md       # СКД (система компоновки данных)
    exchange-plans.md         # Планы обмена, распределённые ИБ
```

### Категории знаний

1. **EDT-проект**: структура каталогов, Configuration.xml, подключение к Git
2. **Подсистемы**: иерархия, командный интерфейс, зависимости
3. **Объекты метаданных**: справочники, документы, регистры, перечисления, обработки
4. **Проектирование**: нормализация данных, связи объектов, план счетов
5. **Безопасность**: роли, RLS (ограничения на уровне записей), профили
6. **Обмен**: планы обмена, XDTO, EnterpriseData
7. **СКД**: макеты, схемы, наборы данных, параметры

### Результат

Claude понимает архитектуру конфигураций 1С и может давать рекомендации по проектированию.

---

## Фаза 7: Domain hooks для BSL

**Цель:** Автоматизация через hooks специфичные для разработки на 1С.

**Трудозатраты:** 3-4 часа

### Hook 1: 1c-task-router.py (UserPromptSubmit)

Маршрутизатор задач, аналогичный `research-task-detector.py` в PDF Framework:

- Вопросы о 1С-объектах → skill `1c-doc-research` (Core)
- Задачи на написание BSL → skill `bsl-coding`
- Вопросы об архитектуре → skill `1c-architecture`
- Задачи на рефакторинг → workflow рефакторинга

### Hook 2: bsl-code-validator.py (PostToolUse/Write)

Срабатывает после записи `.bsl` файла:

1. Вызывает BSL MCP Server для анализа
2. Если есть Error-level диагностики → инжектирует предупреждение
3. Если есть Code Smell → инжектирует рекомендацию (не блокирует)

### Hook 3: bsl-test-reminder.py (PostToolUse/Write)

После записи `.bsl` файла напоминает о тестировании:

- Если написан/изменён модуль — напомнить про юнит-тесты
- Если написан обработчик проведения — напомнить про тест движений

### Результат

Автоматическая маршрутизация задач + валидация кода + напоминания о тестах.

---

## Фаза 8: Индексация дополнительной документации 1С

**Цель:** Расширить базу знаний за пределы Главы 5.

**Трудозатраты:** 1-2 часа (на каждый документ)

### Приоритетные документы для индексации

| Документ | Тема | Приоритет |
|----------|------|-----------|
| Глава 6 | Формы | Высокий |
| Глава 7 | Язык запросов | Высокий |
| Глава 3 | Встроенный язык (BSL) | Высокий |
| Глава 4 | Типы данных | Средний |
| Глава 8 | Система компоновки данных | Средний |
| Глава 9 | Механизмы обмена | Низкий |

### Процесс

1. Скачать PDF документации с its.1c.ru
2. Индексировать через MCP tool `index_pdf` или API
3. Hybrid Loader обработает (PyMuPDF4LLM + таблицы + Vision OCR)
4. Автоматическая сборка BM25 + sparse vectors + граф знаний
5. Обновить `1c-doc-research` skill cache с новыми темами

### Результат

Полная база знаний 1С:Предприятие 8.3.27 доступна для всех проектов через MCP.

---

## Сводная таблица

| Фаза | Цель | Трудозатраты | Зависимости |
|------|------|-------------|-------------|
| **0** | Prerequisites (Java, Node, OneScript) | 30 мин | — |
| **1** | MCP-мост к знаниям 1С | 5-10 мин | Фаза 0 |
| **2** | 1c-doc-research → Core | 10-15 мин | — |
| **3** | Каркас 1C-Code проекта | 1-2 часа | Фаза 1 |
| **4** | BSL MCP Server | 30 мин | Фаза 0, 3 |
| **5** | Skill bsl-coding | 2-3 часа | Фаза 3 |
| **6** | Skill 1c-architecture | 2-3 часа | Фаза 3 |
| **7** | Domain hooks для BSL | 3-4 часа | Фаза 3, 4, 5 |
| **8** | Индексация доп. документации | 1-2 часа/документ | Фаза 1 |

**Общий объём:** ~12-16 часов работы, разбитых на независимые фазы.

---

## Критический путь

```
Фаза 0 (prerequisites)
    ├── Фаза 1 (MCP-мост) ──── Фаза 8 (доп. документация)
    │       │
    │       └── Фаза 3 (каркас)
    │               ├── Фаза 4 (BSL MCP)
    │               ├── Фаза 5 (bsl-coding) ─┐
    │               └── Фаза 6 (1c-arch)     ├── Фаза 7 (hooks)
    │                                         │
    └── Фаза 2 (skill → Core)  ──────────────┘
```

Фазы 1-2 можно сделать параллельно. Фазы 5-6 можно делать параллельно. Фаза 8 независима и может выполняться в любой момент.

---

## Инструменты экосистемы

| Инструмент | Назначение | Интеграция |
|------------|-----------|------------|
| **BSL Language Server** | 180 диагностик, форматирование | MCP Server (`phsin-mcp-bsl-ls`) |
| **OneScript** | Запуск BSL вне 1С, unit-тесты | CLI (`oscript script.bsl`) |
| **SonarQube BSL** | 400+ правил, метрики качества | Локальный Docker (опционально) |
| **BSL LSP плагин** | Подсветка, автодополнение в VS Code | Уже включён (`bsl-lsp@1c-enterprise-lsps`) |
| **PDF Framework MCP** | Поиск по документации 1С | MCP Server (12 tools) |
| **1CFilesConverter** | Конвертация EDT ↔ Designer | CLI (опционально) |

---

## План Б

Если MCP-мост к PDF Framework окажется медленным (stdio latency):
- Индексировать 1С документацию повторно в отдельный Qdrant collection прямо в 1C-Code проекте
- Использовать lightweight MCP сервер с прямым доступом к Qdrant

Если BSL MCP Server (`phsin-mcp-bsl-ls`) не подойдёт:
- Вызывать BSL Language Server JAR напрямую через Bash hook:
  ```bash
  java -jar bsl-language-server.jar analyze -s ./src -r json
  ```
- Парсить JSON-результат в hook

---

## Связанные документы

- [Core/Framework Separation (ADR-006)](../architecture/core-framework-separation.md)
- [Triad Architecture](../architecture/triad-architecture.md)
- [Hooks Reference](../architecture/hooks-reference.md)
- [Skills Reference](../architecture/skills-reference.md)
- [Ralph Wiggum](../architecture/ralph-wiggum.md)
- [Architecture Overview](../architecture/overview.md)
