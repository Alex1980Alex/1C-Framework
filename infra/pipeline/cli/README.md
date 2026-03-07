# Pipeline CLI

Командный интерфейс для Development Pipeline - multi-agent системы разработки 1С.

## Документация

**📘 [PIPELINE-FULL-REFERENCE.md](PIPELINE-FULL-REFERENCE.md)** - Полный справочник по Development Pipeline

- Двухуровневая архитектура (субагенты + Python агенты)
- Детальное описание всех фаз (INIT → SPEC → DESIGN → IMPLEMENT → DEBUG → VERIFY)
- MCP инструменты для каждого агента
- Примеры использования и артефакты

## Установка

CLI является частью модуля `shared.pipeline`. Убедитесь, что зависимости установлены:

```bash
# Из корня проекта
pip install -e shared/pipeline
```

## Быстрый старт

```bash
# Запустить pipeline для проекта
python -m shared.pipeline.cli run --project GKSTCPLK-1872 --task "Добавить валидацию"

# Проверить статус
python -m shared.pipeline.cli status

# Список проектов
python -m shared.pipeline.cli list

# Настройки
python -m shared.pipeline.cli config show
```

## Команды

### `run` - Запуск Pipeline

Запускает multi-agent pipeline для выполнения задачи.

```bash
python -m shared.pipeline.cli run --project <name> --task "<description>" [options]
```

**Параметры:**

| Параметр | Сокращение | Описание | По умолчанию |
|----------|------------|----------|--------------|
| `--project` | `-p` | Имя или путь проекта | обязательный |
| `--task` | `-t` | Описание задачи | обязательный |
| `--parallel` | - | Макс. параллельных задач | 4 |
| `--timeout` | - | Таймаут в секундах | 3600 |
| `--no-checkpoint` | - | Отключить checkpoint'ы | false |
| `--dry-run` | - | Режим симуляции | false |

**Примеры:**

```bash
# Базовый запуск
python -m shared.pipeline.cli run -p GKSTCPLK-1872 -t "Добавить валидацию номенклатуры"

# С параметрами
python -m shared.pipeline.cli run \
  --project src/projects/configuration/251118_GKSTCPLK-1872 \
  --task "Исправить ошибку в документе ПоступлениеТоваров" \
  --timeout 7200

# Режим симуляции (без изменений)
python -m shared.pipeline.cli run -p GKSTCPLK-1996 -t "Тест" --dry-run
```

### `status` - Статус выполнения

Показывает текущий статус pipeline.

```bash
python -m shared.pipeline.cli status [--run-id <id>] [--watch]
```

**Параметры:**

| Параметр | Описание |
|----------|----------|
| `--run-id` | ID конкретного запуска |
| `--watch` | Режим отслеживания |

**Пример вывода:**

```
📊 Pipeline Status

Проект: GKSTCPLK-1872
Запущен: 2025-12-23 14:30:00
Текущая фаза: IMPLEMENTER (BUILD)

Фазы:
✅ PM-SPEC (INIT) - 2 min
✅ PM-SPEC (SPEC) - 5 min
✅ ARCHITECT (DESIGN) - 8 min
🔄 IMPLEMENTER (BUILD) - in progress
⏳ PM-SPEC (VERIFY) - pending

Артефакты:
📄 context.md (12 KB)
📄 spec.md (8 KB)
📄 design.md (15 KB)
```

### `list` - Список проектов и запусков

Показывает зарегистрированные проекты и историю.

```bash
python -m shared.pipeline.cli list [projects|runs|artifacts]
```

**Типы:**

| Тип | Описание |
|-----|----------|
| `projects` | Зарегистрированные проекты (по умолчанию) |
| `runs` | История последних запусков |
| `artifacts` | Артефакты проектов |

**Примеры:**

```bash
# Список проектов
python -m shared.pipeline.cli list
python -m shared.pipeline.cli list projects

# История запусков
python -m shared.pipeline.cli list runs

# Артефакты
python -m shared.pipeline.cli list artifacts
```

### `config` - Управление конфигурацией

Управление настройками pipeline.

```bash
python -m shared.pipeline.cli config <action> [options]
```

**Действия:**

| Действие | Описание |
|----------|----------|
| `show` | Показать конфигурацию |
| `init` | Инициализировать конфигурацию |
| `set <key> <value>` | Установить значение |
| `add-project` | Добавить проект |
| `remove-project <name>` | Удалить проект |

**Примеры:**

```bash
# Показать конфигурацию
python -m shared.pipeline.cli config show

# Инициализировать
python -m shared.pipeline.cli config init

# Установить значение
python -m shared.pipeline.cli config set default_project GKSTCPLK-1872
python -m shared.pipeline.cli config set max_parallel_tasks 4

# Добавить проект
python -m shared.pipeline.cli config add-project \
  --name GKSTCPLK-1996 \
  --path src/projects/configuration/251222_GKSTCPLK-1996 \
  --type configuration

# Удалить проект
python -m shared.pipeline.cli config remove-project GKSTCPLK-1996
```

**Доступные ключи:**

| Ключ | Тип | Описание |
|------|-----|----------|
| `default_project` | string | Проект по умолчанию |
| `max_parallel_tasks` | int | Макс. параллельных задач |
| `timeout_seconds` | int | Таймаут выполнения |
| `auto_commit` | bool | Автокоммит изменений |
| `output_format` | string | Формат вывода (text/json/markdown) |
| `verbosity` | int | Уровень детализации (0-3) |

### `logs` - Просмотр логов

Просмотр логов выполнения pipeline.

```bash
python -m shared.pipeline.cli logs [--run-id <id>] [--follow] [--level <level>]
```

**Параметры:**

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--run-id` | ID запуска | последний |
| `--follow` | Следить за логами | false |
| `--level` | Уровень логов (debug/info/warning/error) | info |
| `--lines` | Количество строк | 50 |

## Глобальные параметры

Доступны для всех команд:

| Параметр | Сокращение | Описание |
|----------|------------|----------|
| `--config` | `-c` | Путь к конфигурации |
| `--format` | `-f` | Формат вывода (text/json/markdown) |
| `--verbose` | `-v` | Подробный вывод |
| `--quiet` | `-q` | Минимальный вывод |
| `--no-color` | - | Отключить цвета |
| `--help` | `-h` | Справка |
| `--version` | - | Версия |

## Конфигурация

CLI ищет конфигурацию в следующем порядке:

1. `--config` параметр командной строки
2. Переменная окружения `PIPELINE_CONFIG`
3. `.pipeline/config.json` в текущей директории
4. `~/.pipeline/config.json`

### Структура конфигурации

```json
{
  "project_root": ".",
  "artifacts_dir": "artifacts",
  "logs_dir": "logs",
  "default_project": "GKSTCPLK-1872",
  "max_parallel_tasks": 4,
  "timeout_seconds": 3600,
  "auto_commit": false,
  "output": {
    "format": "text",
    "verbosity": 1,
    "color": true,
    "unicode": true
  },
  "enabled_agents": [
    "pm-spec",
    "architect",
    "implementer",
    "bsl-debugger"
  ]
}
```

### Переменные окружения

| Переменная | Описание |
|------------|----------|
| `PIPELINE_CONFIG` | Путь к конфигурации |
| `PIPELINE_PROJECT` | Проект по умолчанию |
| `PIPELINE_ARTIFACTS_DIR` | Директория артефактов |
| `PIPELINE_LOG_LEVEL` | Уровень логов |
| `NO_COLOR` | Отключить цвета |

## Интеграция с Claude Code

### Полный Workflow в Claude Code (от начала до завершения)

Рекомендуемый порядок работы над проектом 1С в Claude Code:

#### Шаг 1: Создание папки проекта и загрузка конфигурации

```bash
# 1. Создать папку проекта:
src/projects/configuration/{YYMMDD}_{JIRA_TICKET}/

# 2. Создать папку для конфигурации:
src/projects/configuration/{YYMMDD}_{JIRA_TICKET}/src/

# 3. Выгрузить конфигурацию 1С в папку src/ (из EDT или Конфигуратора)
```

**В Claude Code:**
```
> Создай папку проекта для GKSTCPLK-2000
```

Claude создаст:
```
src/projects/configuration/260104_GKSTCPLK-2000/
├── src/                    # Конфигурация 1С (загружает пользователь, работает Claude)
└── docs/                   # Задача проекта и документация
    └── task.md             # Описание задачи (см. ниже)
```

**Задача проекта (docs/task.md):**
- Если пользователь **описал задачу в чате** → Claude создаст `docs/task.md` автоматически
- Если пользователь **загрузил файл задачи** → положить в `docs/task.md` вручную
- Формат: Markdown с описанием требований, критериев приёмки, ограничений

После выгрузки конфигурации структура будет:
```
src/projects/configuration/260104_GKSTCPLK-2000/
├── src/
│   ├── Configuration/      # Корень конфигурации
│   ├── CommonModules/      # Общие модули
│   ├── Catalogs/           # Справочники
│   ├── Documents/          # Документы
│   └── ...
└── docs/
    ├── task.md             # Описание задачи
    └── ...                 # Сгенерированная документация
```

**Пример docs/task.md:**
```markdown
# Задача: GKSTCPLK-2000

## Описание
Добавить валидацию справочника Номенклатура при записи.

## Требования
- Проверять заполненность поля "Артикул"
- Проверять уникальность наименования в группе
- Выводить понятные сообщения об ошибках

## Критерии приёмки
- [ ] Валидация срабатывает при записи
- [ ] Ошибки отображаются пользователю
- [ ] Код соответствует стандартам 1С

## Ограничения
- Не изменять существующую логику проведения документов
```

#### Шаг 2: Запуск Development Pipeline (автоматическая инициализация)

**Development Pipeline автоматически:**
- ✅ Активирует проект в Serena (LSP навигация)
- ✅ Индексирует код в 1c-docs-rag (семантический поиск)
- ✅ Подключает ast-grep для анализа BSL
- ✅ Настраивает unified-memory для контекста
- ✅ Регистрирует проект в конфигурации

**В Claude Code:**
```
> /pipeline 260104_GKSTCPLK-2000 "Добавить валидацию номенклатуры"
```

Или:
```bash
python -m shared.pipeline.cli run \
  -p 260104_GKSTCPLK-2000 \
  -t "Добавить валидацию номенклатуры"
```

Pipeline выполнит:
1. **INIT** (PM-SPEC) - автоинициализация всех инструментов
2. **SPEC** (PM-SPEC) - анализ требований и создание спецификации
3. **DESIGN** (ARCHITECT) - проектирование решения
4. **IMPLEMENT** (IMPLEMENTER) - реализация кода
5. **DEBUG** (BSL-DEBUGGER) - отладка и исправление ошибок
6. **VERIFY** (PM-SPEC) - финальная верификация и приёмка

#### Шаг 3: Работа с Development Pipeline

**Вариант A: Через slash command (рекомендуется)**
```
> /pipeline GKSTCPLK-2000 "Добавить валидацию номенклатуры"
```

**Вариант B: Прямой вызов CLI**
```bash
python -m shared.pipeline.cli run \
  -p GKSTCPLK-2000 \
  -t "Добавить валидацию номенклатуры"
```

**Вариант C: Поэтапно (для контроля)**
```
> /analyze-1c-task GKSTCPLK-2000 "Добавить валидацию"  # Анализ задачи
> Покажи план реализации                               # Review плана
> Реализуй согласно плану                              # Выполнение
```

#### Шаг 4: Проверка результатов

```
> /pipeline-status                    # Статус выполнения
> Покажи изменённые файлы             # Git diff
> Запусти анализ ast-grep на ошибки   # Статический анализ BSL
```

#### Шаг 5: Документирование и коммит

```
> Сгенерируй документацию для изменённых модулей
> Сделай коммит с описанием задачи
```

### Оптимизированный Workflow (Рекомендация)

**Самый простой подход - всего 2 шага:**

```
┌─────────────────────────────────────────────────────────────────┐
│ ШАГ 1: ПОДГОТОВКА (ручной)                                      │
│                                                                 │
│   1. Создать папку: src/projects/configuration/YYMMDD_TICKET/  │
│   2. Выгрузить конфигурацию 1С в папку src/                    │
│   3. (опционально) Положить задачу в docs/task.md              │
│      ИЛИ описать задачу в чате - Claude создаст task.md        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ ШАГ 2: РАБОТА (автоматический)                                  │
│                                                                 │
│   > /pipeline TICKET "Описание задачи"                         │
│                                                                 │
│   Pipeline АВТОМАТИЧЕСКИ:                                       │
│   • Активирует Serena для LSP                                  │
│   • Индексирует код в RAG                                      │
│   • Подключает ast-grep анализ                                 │
│   • Выполняет задачу                                           │
│   • Генерирует документацию                                    │
│   • Делает коммит                                              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Для опытных пользователей - поэтапный контроль:**

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. ПОДГОТОВКА                                                   │
│    • Создать папку проекта + выгрузить конфигурацию            │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. АНАЛИЗ ЗАДАЧИ                                                │
│    • /analyze-1c-task или прямой запрос Claude                 │
│    • Поиск связанного кода через ast-grep и Serena             │
│    • Поиск правил и примеров в 1c-docs-rag                     │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. РЕАЛИЗАЦИЯ                                                   │
│    • Редактирование через Serena (символьные операции)         │
│    • ИЛИ через Edit tool (для точечных изменений)              │
│    • Проверка ast-grep после каждого изменения                 │
└─────────────────────────────────────────────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. ЗАВЕРШЕНИЕ                                                   │
│    • auto-documenter: генерация документации                   │
│    • Git commit с осмысленным сообщением                       │
│    • Сохранение контекста в unified-memory                     │
└─────────────────────────────────────────────────────────────────┘
```

### Пример сессии в Claude Code

**Простой вариант (2 шага):**

```
Пользователь: Создай папку проекта для GKSTCPLK-2000

Claude:
✅ Создана папка: src/projects/configuration/260104_GKSTCPLK-2000/
   ├── src/    # Выгрузите сюда конфигурацию 1С из EDT
   └── docs/

Пользователь: [Выгружает конфигурацию в папку src/]

Пользователь: /pipeline 260104_GKSTCPLK-2000 "Добавить валидацию справочника Номенклатура"

Claude (pipeline автоматически):
1. 🔧 Инициализация инструментов...
   ✅ Serena активирована
   ✅ Код проиндексирован в RAG (150 BSL файлов)
   ✅ ast-grep подключен

2. 📋 Анализ требований (PM-SPEC)...
   ✅ Задача проанализирована
   ✅ Найдены связанные модули

3. 🏗️ Проектирование (ARCHITECT)...
   ✅ План реализации создан

4. 💻 Реализация (IMPLEMENTER)...
   ✅ CommonModules/ВалидацияНоменклатуры/Module.bsl создан

5. ✅ Проверка (QA)...
   ✅ ast-grep: ошибок не найдено

6. 📝 Завершение (REVIEWER)...
   ✅ Документация сгенерирована
   ✅ Коммит создан: feat(GKSTCPLK-2000): добавлена валидация Номенклатуры
```

**Детальный вариант (с контролем):**

```
Пользователь: Создай проект для GKSTCPLK-2000 и добавь валидацию справочника Номенклатура

Claude:
1. Создаю структуру проекта...
   ✅ src/projects/configuration/260104_GKSTCPLK-2000/

2. Активирую проект в Serena...
   ✅ mcp__serena__activate_project("260104_GKSTCPLK-2000")

3. Анализирую задачу...
   - Поиск существующих валидаций: ast-grep "ПроверитьЗаполнение"
   - Поиск правил: 1c-docs-rag "валидация справочник стандарты"

4. Создаю код валидации...
   ✅ CommonModules/Валидация/Module.bsl

5. Генерирую документацию...
   ✅ docs/CommonModules/Валидация.md

6. Коммит...
   ✅ git commit -m "feat(GKSTCPLK-2000): добавлена валидация Номенклатуры"
```

---

## 🗺️ ДОРОЖНАЯ КАРТА PIPELINE (Детальные фазы)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│              DEVELOPMENT PIPELINE - МУЛЬТИ-АГЕНТНАЯ СИСТЕМА                          │
│                                                                                      │
│  📋 ФАЗА 1: ПЛАНИРОВАНИЕ     🏗️ ФАЗА 2: РАЗРАБОТКА              ✅ ФАЗА 3: ЗАВЕРШЕНИЕ │
│  ─────────────────────── ───▶ ─────────────────────────────── ───▶ ──────────────────│
│  [INIT] → [SPEC]              [DESIGN] → [IMPLEMENT] → [DEBUG]        [VERIFY]       │
│     │         │                  │           │            │              │           │
│  PM-SPEC   PM-SPEC           ARCHITECT  IMPLEMENTER  BSL-DEBUGGER    PM-SPEC        │
│                                                                                      │
│  🚪 ТОЧКИ ВЫХОДА: --exit-after <stage>  │  📤 ВОЗОБНОВЛЕНИЕ: --resume-from <stage>  │
│  ⏸️ ПАУЗА: --stop-after <stage>         │  ▶️ ЗАПУСК: --start-from <stage>          │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 📋 ФАЗА 1: ПЛАНИРОВАНИЕ (INIT → SPEC)

**Цель:** Подготовить проект и сформировать спецификацию задачи.
**Агент:** PM-SPEC (Product Manager - Спецификация)

#### Этап 1.1: INIT (PM-SPEC Agent)

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔧 АКТИВАЦИЯ ИНСТРУМЕНТОВ                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. mcp__serena__activate_project(project_path)                │
│     └─▶ LSP навигация по коду                                  │
│                                                                 │
│  2. mcp__1c-docs-rag__index_bsl_project(project_path)          │
│     └─▶ Семантический поиск по BSL коду                        │
│                                                                 │
│  3. mcp__ast-grep-mcp__ast_grep(pattern, language="bsl")       │
│     └─▶ Статический анализ BSL                                 │
│                                                                 │
│  4. mcp__unified-memory__save_memory(context)                  │
│     └─▶ Сохранение контекста проекта                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Задачи PM-SPEC Agent (INIT):**
| # | Задача | Инструмент | Артефакт |
|---|--------|------------|----------|
| 1 | Создать структуру папок | `mkdir`, `Write` | `src/`, `docs/` |
| 2 | Активировать Serena | `mcp__serena__activate_project` | LSP ready |
| 3 | Индексировать код в RAG | `mcp__1c-docs-rag__index_bsl_project` | Index ready |
| 4 | Загрузить контекст | `mcp__unified-memory__get_context` | Context loaded |
| 5 | Создать task.md | `Write` | `docs/task.md` |

**Выходные артефакты:**
- `docs/task.md` — описание задачи
- `.pipeline/init.json` — метаданные инициализации

**⏸️ ТОЧКА ПАУЗЫ после INIT:**
```bash
> /pipeline TICKET "задача" --stop-after init
```

**🚪 ТОЧКА ВЫХОДА после INIT:**
```bash
> /pipeline TICKET "задача" --exit-after init
# Полное завершение pipeline (без продолжения)
# Для возобновления: --resume-from spec
```

---

#### Этап 1.2: SPEC (PM-SPEC Agent)

```
┌─────────────────────────────────────────────────────────────────┐
│ 📋 АНАЛИЗ ТРЕБОВАНИЙ                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. mcp__1c-docs-rag__search_docs("требования {задача}")       │
│     └─▶ Поиск похожих задач и паттернов                        │
│                                                                 │
│  2. mcp__ast-grep-mcp__ast_grep(pattern="связанный_код")       │
│     └─▶ Анализ существующего кода                              │
│                                                                 │
│  3. mcp__serena__find_symbol(name_path)                        │
│     └─▶ Поиск связанных символов                               │
│                                                                 │
│  4. mcp__bsl-platform-context__search(query)                   │
│     └─▶ API платформы 1С                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Задачи PM-SPEC Agent:**
| # | Задача | Инструмент | Артефакт |
|---|--------|------------|----------|
| 1 | Проанализировать задачу | `Read`, `1c-docs-rag` | Понимание требований |
| 2 | Найти связанный код | `ast-grep`, `serena` | Список файлов |
| 3 | Поиск стандартов 1С | `bsl-platform-context` | API справка |
| 4 | Сформировать спецификацию | `Write` | `docs/spec.md` |
| 5 | Определить критерии приёмки | `Write` | acceptance criteria |

**Выходные артефакты:**
- `docs/spec.md` — спецификация требований
- `docs/related-code.md` — список связанного кода
- `.pipeline/spec.json` — метаданные спецификации

**⏸️ ТОЧКА ПАУЗЫ после SPEC:**
```bash
> /pipeline TICKET "задача" --stop-after spec
```

**▶️ ВОЗОБНОВЛЕНИЕ с ФАЗЫ 1:**
```bash
> /pipeline TICKET --resume-from spec
```

**🚪 ТОЧКА ВЫХОДА после SPEC:**
```bash
> /pipeline TICKET "задача" --exit-after spec
# Полное завершение pipeline (без продолжения)
# Для возобновления: --resume-from design
```

---

### 🏗️ ФАЗА 2: РАЗРАБОТКА (DESIGN → IMPLEMENT → DEBUG)

**Цель:** Спроектировать, реализовать и отладить решение.
**Агенты:** ARCHITECT, IMPLEMENTER, BSL-DEBUGGER

#### Этап 2.1: DESIGN (ARCHITECT Agent)

```
┌─────────────────────────────────────────────────────────────────┐
│ 🏗️ ПРОЕКТИРОВАНИЕ РЕШЕНИЯ                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. mcp__serena__get_symbols_overview(file_path)               │
│     └─▶ Обзор структуры модулей                                │
│                                                                 │
│  2. mcp__1c-docs-rag__search_docs("архитектура {паттерн}")     │
│     └─▶ Поиск архитектурных паттернов                          │
│                                                                 │
│  3. mcp__ast-grep-mcp__find_code_by_rule(yaml_rule)            │
│     └─▶ Поиск похожих реализаций                               │
│                                                                 │
│  4. mcp__sequential-thinking__sequentialthinking(thought)      │
│     └─▶ Структурированное проектирование                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Задачи ARCHITECT Agent:**
| # | Задача | Инструмент | Артефакт |
|---|--------|------------|----------|
| 1 | Изучить структуру кода | `serena`, `ast-grep` | Понимание архитектуры |
| 2 | Найти паттерны | `1c-docs-rag` | Референсные решения |
| 3 | Спроектировать решение | `sequential-thinking` | Архитектурный план |
| 4 | Определить изменения | `Write` | `docs/design.md` |
| 5 | Создать план реализации | `Write` | Список шагов |

**Выходные артефакты:**
- `docs/design.md` — архитектурное решение
- `docs/implementation-plan.md` — план реализации
- `.pipeline/design.json` — метаданные проектирования

**⏸️ ТОЧКА ПАУЗЫ после DESIGN:**
```bash
> /pipeline TICKET "задача" --stop-after design
```

---

#### Этап 2.2: IMPLEMENT (IMPLEMENTER Agent)

```
┌─────────────────────────────────────────────────────────────────┐
│ 💻 РЕАЛИЗАЦИЯ КОДА                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. mcp__serena__replace_symbol_body(name_path, body)          │
│     └─▶ Редактирование через LSP (рекомендуется)               │
│                                                                 │
│  2. Edit(file_path, old_string, new_string)                    │
│     └─▶ Точечное редактирование                                │
│                                                                 │
│  3. mcp__ast-grep-mcp__ast_grep(pattern, mode="replace")       │
│     └─▶ Массовые изменения по паттерну                         │
│                                                                 │
│  4. mcp__bsl-platform-context__info(name, type)                │
│     └─▶ Проверка API вызовов                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Задачи IMPLEMENTER Agent:**
| # | Задача | Инструмент | Артефакт |
|---|--------|------------|----------|
| 1 | Создать/изменить модули | `serena`, `Edit`, `Write` | BSL код |
| 2 | Добавить комментарии | `Edit` | Документированный код |
| 3 | Проверить синтаксис | `ast-grep` | Валидный код |
| 4 | Проверить API вызовы | `bsl-platform-context` | Корректные вызовы |
| 5 | Сохранить контекст | `unified-memory` | Контекст изменений |

**Выходные артефакты:**
- Изменённые `.bsl` файлы
- `docs/changes.md` — список изменений
- `.pipeline/implement.json` — метаданные реализации

**⏸️ ТОЧКА ПАУЗЫ после IMPLEMENT:**
```bash
> /pipeline TICKET "задача" --stop-after implement
```

**🚪 ТОЧКА ВЫХОДА после IMPLEMENT:**
```bash
> /pipeline TICKET "задача" --exit-after implement
# Полное завершение pipeline (без продолжения)
```

---

#### Этап 2.3: DEBUG (BSL-DEBUGGER Agent)

```
┌─────────────────────────────────────────────────────────────────┐
│ 🐛 ОТЛАДКА BSL КОДА                                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. mcp__ast-grep-mcp__ast_grep(pattern="проблемный_код")       │
│     └─▶ Поиск потенциальных ошибок                              │
│                                                                 │
│  2. mcp__serena__find_referencing_symbols(name_path)            │
│     └─▶ Анализ зависимостей                                     │
│                                                                 │
│  3. mcp__bsl-platform-context__getMembers(typeName)             │
│     └─▶ Проверка корректности вызовов API                       │
│                                                                 │
│  4. mcp__1c-docs-rag__search_docs("ошибка {описание}")          │
│     └─▶ Поиск решений известных проблем                         │
│                                                                 │
│  5. mcp__sequential-thinking__sequentialthinking(debug_thought) │
│     └─▶ Пошаговый анализ проблемы                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Задачи BSL-DEBUGGER Agent:**
| # | Задача | Инструмент | Артефакт |
|---|--------|------------|----------|
| 1 | Найти потенциальные ошибки | `ast-grep` | Список проблем |
| 2 | Проанализировать зависимости | `serena` | Граф зависимостей |
| 3 | Проверить API вызовы | `bsl-platform-context` | Валидация API |
| 4 | Найти решения проблем | `1c-docs-rag` | Рекомендации |
| 5 | Исправить ошибки | `Edit`, `serena` | Исправленный код |
| 6 | Верифицировать исправления | `ast-grep` | Подтверждение |

**Выходные артефакты:**
- Исправленные `.bsl` файлы
- `docs/debug-report.md` — отчёт об отладке
- `.pipeline/debug.json` — метаданные отладки

**⏸️ ТОЧКА ПАУЗЫ после DEBUG:**
```bash
> /pipeline TICKET "задача" --stop-after debug
```

**🚪 ТОЧКА ВЫХОДА после DEBUG:**
```bash
> /pipeline TICKET "задача" --exit-after debug
# Завершить после отладки без верификации
```

**▶️ ВОЗОБНОВЛЕНИЕ с ФАЗЫ 2:**
```bash
> /pipeline TICKET --resume-from design
> /pipeline TICKET --resume-from implement
> /pipeline TICKET --resume-from debug
```

---

### ✅ ФАЗА 3: ЗАВЕРШЕНИЕ (VERIFY)

**Цель:** Верифицировать результат и завершить задачу.
**Агент:** PM-SPEC (Product Manager - Верификация)

#### Этап 3.1: VERIFY (PM-SPEC Agent)

```
┌─────────────────────────────────────────────────────────────────┐
│ ✅ ВЕРИФИКАЦИЯ И ЗАВЕРШЕНИЕ                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. mcp__ast-grep-mcp__ast_grep(pattern="антипаттерн")         │
│     └─▶ Финальная проверка кода                                │
│                                                                 │
│  2. mcp__1c-docs-rag__validate_solution(solution)              │
│     └─▶ Валидация против стандартов                            │
│                                                                 │
│  3. mcp__auto-documenter__generate_documentation(path)         │
│     └─▶ Генерация документации                                 │
│                                                                 │
│  4. mcp__auto-documenter__autoreview(path)                     │
│     └─▶ Автоматический code review                             │
│                                                                 │
│  5. mcp__unified-memory__save_memory(content, type="code")     │
│     └─▶ Сохранение результатов в память                        │
│                                                                 │
│  6. Bash("git add . && git commit -m '...'")                   │
│     └─▶ Коммит изменений                                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Задачи PM-SPEC Agent (VERIFY):**
| # | Задача | Инструмент | Артефакт |
|---|--------|------------|----------|
| 1 | Финальный анализ кода | `ast-grep` | Отчёт о качестве |
| 2 | Проверка против стандартов | `1c-docs-rag` | Валидация |
| 3 | Генерация документации | `auto-documenter` | `docs/*.md` |
| 4 | Автоматический review | `auto-documenter` | Review отчёт |
| 5 | Проверка критериев приёмки | `Read` | Acceptance check |
| 6 | Сохранить в память | `unified-memory` | Долгосрочный контекст |
| 7 | Git commit | `Bash` | Коммит |

**Выходные артефакты:**
- `docs/verify-report.md` — отчёт о верификации
- Сгенерированная документация в `docs/`
- Git commit с описанием изменений
- Контекст сохранён в `unified-memory`

**⏸️ ТОЧКА ПАУЗЫ после VERIFY:**
```bash
> /pipeline TICKET "задача" --stop-after verify
```

**🚪 ТОЧКА ВЫХОДА после VERIFY:**
```bash
> /pipeline TICKET "задача" --exit-after verify
# Завершить pipeline полностью
```

**▶️ ВОЗОБНОВЛЕНИЕ с ФАЗЫ 3:**
```bash
> /pipeline TICKET --resume-from verify
```

---

### 🎛️ УПРАВЛЕНИЕ PIPELINE

#### Команды запуска с определённой фазы

| Команда | Описание |
|---------|----------|
| `/pipeline TICKET "задача"` | Полный цикл (все фазы) |
| `/pipeline TICKET --start-from init` | Начать с инициализации |
| `/pipeline TICKET --start-from spec` | Начать со спецификации |
| `/pipeline TICKET --start-from design` | Начать с проектирования |
| `/pipeline TICKET --start-from implement` | Начать с реализации |
| `/pipeline TICKET --start-from debug` | Начать с отладки |
| `/pipeline TICKET --start-from verify` | Начать с верификации |

#### Команды остановки (пауза)

| Команда | Описание |
|---------|----------|
| `/pipeline TICKET --stop-after init` | Остановить после инициализации |
| `/pipeline TICKET --stop-after spec` | Остановить после спецификации |
| `/pipeline TICKET --stop-after design` | Остановить после проектирования |
| `/pipeline TICKET --stop-after implement` | Остановить после реализации |
| `/pipeline TICKET --stop-after debug` | Остановить после отладки |
| `/pipeline TICKET --stop-after verify` | Остановить после верификации |

#### Команды выхода (полное завершение)

| Команда | Описание |
|---------|----------|
| `/pipeline TICKET --exit-after init` | ⏹️ Выйти после инициализации |
| `/pipeline TICKET --exit-after spec` | ⏹️ Выйти после спецификации |
| `/pipeline TICKET --exit-after design` | ⏹️ Выйти после проектирования |
| `/pipeline TICKET --exit-after implement` | ⏹️ Выйти после реализации |
| `/pipeline TICKET --exit-after debug` | ⏹️ Выйти после отладки |
| `/pipeline TICKET --exit-after verify` | ⏹️ Выйти после верификации |

> **Разница:**
> - `--stop-after` - пауза с возможностью возобновления
> - `--exit-after` - полное завершение pipeline

#### Команды возобновления

| Команда | Описание |
|---------|----------|
| `/pipeline TICKET --resume` | Продолжить с последней точки |
| `/pipeline TICKET --resume-from init` | Продолжить с инициализации |
| `/pipeline TICKET --resume-from spec` | Продолжить со спецификации |
| `/pipeline TICKET --resume-from design` | Продолжить с проектирования |
| `/pipeline TICKET --resume-from implement` | Продолжить с реализации |
| `/pipeline TICKET --resume-from debug` | Продолжить с отладки |
| `/pipeline TICKET --resume-from verify` | Продолжить с верификации |
| `/pipeline-status` | Проверить текущее состояние |

#### Интерактивный режим

```bash
> /pipeline TICKET "задача" --interactive

Pipeline запущен в интерактивном режиме.

[INIT] ✅ Завершён (PM-SPEC Agent)
  └─ Продолжить? (y/n/skip/exit): y

[SPEC] ✅ Завершён (PM-SPEC Agent)
  └─ Хотите отредактировать spec.md? (y/n): n
  └─ Продолжить? (y/n/skip/exit): y

[DESIGN] ✅ Завершён (ARCHITECT Agent)
  └─ Хотите отредактировать design.md? (y/n): y
  └─ [Редактирование...]
  └─ Продолжить? (y/n/skip/exit): y

[IMPLEMENT] ✅ Завершён (IMPLEMENTER Agent)
  └─ Продолжить? (y/n/skip/exit): y

[DEBUG] 🔄 В процессе... (BSL-DEBUGGER Agent)
  └─ [Анализ кода...]
  └─ Найдено 2 проблемы, исправлено
  └─ Продолжить? (y/n/skip/exit): y

[VERIFY] ⏳ Ожидает (PM-SPEC Agent)
```

> **Опции интерактивного режима:**
> - `y` - продолжить выполнение
> - `n` - остановить pipeline
> - `skip` - пропустить этот этап
> - `exit` - выйти с сохранением состояния

---

### Slash Commands

CLI интегрирован с Claude Code через slash commands:

| Команда | Описание |
|---------|----------|
| `/pipeline <project> <task>` | Запустить pipeline |
| `/pipeline-status` | Проверить статус |
| `/pipeline-list` | Список проектов |
| `/pipeline-config` | Управление конфигурацией |
| `/analyze-1c-task` | Анализ задачи 1С |

### Hooks

CLI автоматически обнаруживается через hook `pipeline-cli-trigger.py`:

```
Пользователь: запусти pipeline для GKSTCPLK-1872
[Hook обнаруживает команду и выводит рекомендации]
```

### Используемые MCP серверы

| Сервер | Назначение в workflow |
|--------|----------------------|
| `serena` | LSP для навигации и символьного редактирования |
| `1c-docs-rag` | Семантический поиск по документации и коду |
| `ast-grep-mcp` | Статический анализ BSL кода |
| `unified-memory` | Сохранение контекста между сессиями |
| `auto-documenter` | Генерация документации |
| `bsl-platform-context` | API платформы 1С |

## Структура модуля

```
shared/pipeline/cli/
├── __init__.py       # Module exports
├── __main__.py       # Entry point
├── main.py           # PipelineCLI class
├── commands.py       # Command implementations
├── config.py         # Configuration classes
├── output.py         # Output formatting
└── README.md         # This file
```

## Примеры workflow

### Полный цикл разработки

```bash
# 1. Инициализировать конфигурацию
python -m shared.pipeline.cli config init

# 2. Добавить проект
python -m shared.pipeline.cli config add-project \
  --name GKSTCPLK-1872 \
  --path src/projects/configuration/251118_GKSTCPLK-1872

# 3. Запустить pipeline
python -m shared.pipeline.cli run \
  -p GKSTCPLK-1872 \
  -t "Добавить валидацию номенклатуры"

# 4. Следить за статусом
python -m shared.pipeline.cli status --watch

# 5. Просмотреть логи при ошибках
python -m shared.pipeline.cli logs --level error
```

### Автоматизация в скриптах

```bash
#!/bin/bash
# run-pipeline.sh

PROJECT="$1"
TASK="$2"

# Запустить pipeline
python -m shared.pipeline.cli run -p "$PROJECT" -t "$TASK" --no-checkpoint

# Проверить результат
if python -m shared.pipeline.cli status --format json | jq -e '.status == "completed"' > /dev/null; then
  echo "✅ Pipeline completed successfully"
  exit 0
else
  echo "❌ Pipeline failed"
  python -m shared.pipeline.cli logs --level error
  exit 1
fi
```

## Версионирование

- **1.0.0** - Initial release (Sprint 4.3)
- **2.0.0** - Orchestrator Enhancements P0-P3 (2026-01-08)

## 🚀 Optimizations v2.0.0

### Performance Improvements (P0-P3)

В версии 2.0.0 реализованы 4 критические оптимизации производительности:

| Optimization | Priority | Speedup | Description |
|--------------|----------|---------|-------------|
| **P0: Resume Capability** | CRITICAL | -50-70% time on retries | Prevents full pipeline restart on BSL errors |
| **P1: Checkpoint System** | HIGH | Recovery from crashes | Save/resume from any phase |
| **P2: Parallel Subtasks** | MEDIUM | +75% faster architect phase | Async parallel design (4 threads) |
| **P3: Pipeline DAG** | MEDIUM | +44% faster multi-module | Parallel module execution with DAG |

**Cumulative Effect:** ~60-80% total pipeline speedup

#### P0: Resume Instead of Restart

**Before (v1.0.0):**
```python
# On BSL error: Full restart from PM-SPEC
return self.run_pipeline()  # ❌ Wastes 5-10 minutes
```

**After (v2.0.0):**
```python
# On BSL error: Resume from implementation
implementation_success = self._run_implementer_phase(mode=AgentMode.RETRY)  # ✅
```

**Savings:** ~2000-5000 LLM tokens per retry

#### P1: Checkpoint System

```python
# Auto-save after each phase
orchestrator.save_checkpoint(PipelinePhase.SPECIFICATION)

# Resume from checkpoint
result = orchestrator.resume_from_checkpoint(PipelinePhase.IMPLEMENTATION)
```

**Features:**
- Artifact validation on load (prevents crashes from missing files)
- Resume from any phase
- ~1-5 MB disk overhead per checkpoint

#### P2: Parallel Architect Subtasks

**Before (v1.0.0):**
```python
# Sequential design
design_database()      # 0.4s
design_api()           # 0.4s
design_security()      # 0.4s
design_integrations()  # 0.4s
# Total: 1.6s
```

**After (v2.0.0):**
```python
# Parallel design (4 threads)
results = await asyncio.gather(
    design_database(),
    design_api(),
    design_security(),
    design_integrations(),
)
# Total: 0.4s (75% faster)
```

#### P3: Multi-Module Pipeline DAG

**Sequential (v1.0.0):**
```
Module1: PM→Arch→Impl→Verify  (6s)
Module2: PM→Arch→Impl→Verify  (6s)
Module3: PM→Arch→Impl→Verify  (6s)
Total: 18s
```

**Parallel (v2.0.0):**
```
Module1: PM→Arch→Impl→Verify
           ↓
Module2:    PM→Arch→Impl→Verify
                ↓
Module3:       PM→Arch→Impl→Verify
Total: 10s (44% faster)
```

### Testing

All optimizations validated with test suite:

```bash
# Run enhancement tests
python -m orchestrator.test_enhancements

# Results:
# [PASS] P0: Resume capability
# [PASS] P1: Checkpoint system
# [PASS] P2: Parallel subtasks (75% faster)
# [PASS] P3: Pipeline DAG (44% faster)
```

### Documentation

- **Implementation Report:** `docs/framework/refactoring/ORCHESTRATOR-ENHANCEMENTS-IMPLEMENTATION-REPORT.md`
- **Issues Explained:** `docs/framework/refactoring/orchestrator-issues-explained.md`
- **Test Script:** `development-pipeline/orchestrator/test_enhancements.py`

---

## См. также

- [ROADMAP.md](../../src/projects/development-pipeline-guide/ROADMAP.md) - План развития
- [Pipeline Documentation](.claude/commands/pipeline.md) - Slash command документация
- [Hooks README](.claude/hooks/pipeline/README.md) - Документация хуков
