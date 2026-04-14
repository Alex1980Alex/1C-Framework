# Serena Audit — углублённый анализ эффективности в 1С-Framework

**Дата:** 2026-04-14
**Автор:** Claude Opus 4.6 (по запросу пользователя)
**Контекст:** Пользователь использовал Serena раньше, после изменений пайплайна перестал. Запрос — понять какие инструменты Serena реально уникальны и дают ощутимое преимущество.
**Статус:** Завершён. Приняты решения: (1) откатить Этап 0 из `implement-1c-task`, (2) рассмотреть смену `language: bsl` → `python` для Python-рефакторинга фреймворка.

---

## TL;DR

1. **Главная находка:** `.serena/project.yml` содержит `language: bsl`, но **BSL не входит в список языков, поддерживаемых Serena** (csharp/python/rust/java/typescript/go/cpp/ruby/php/elixir/swift/clojure/terraform/bash). **Все 13 LSP-based тулов Serena на этом проекте мертвы.**
2. **Подтверждение:** `.serena/cache/bsl/document_symbols_cache_v23-06-25.pkl` содержит ровно **1 проиндексированный файл** — и это `.py`, не `.bsl`. При 2027 BSL-файлах в проекте.
3. **Memories использовались в 1 проекте из 40** (2.5%). В том единственном проекте memories дублируют `ANALYSIS-REPORT.md`.
4. **`serena-index-checker.py` — фантом.** Хук упоминается в `/activate-project.md`, но файла нет в `.claude/hooks/`. Ранняя session-memory (2026-03-05) упоминает его как активный, но инфраструктура хуков была переработана, и этот хук выпилен.
5. **Вердикт:** на задачах 1С-BSL Serena даёт ~0 уникальной ценности. На задачах Python-рефакторинга фреймворка (337 файлов) — 20-30% выигрыш, **при условии смены конфига на `language: python`**.

---

## Контекст исследования

### Исходные артефакты
- `.claude/skills/implement-1c-task/SKILL.md` — в рамках предыдущей задачи был добавлен Этап 0 «Активация проекта в Serena» и скилл помечен v2.1.0 (9 этапов)
- `.claude/commands/implement-1c-task.md` — обновлена под 9 этапов
- `docs/framework documentation/01_ОБЗОР/01.2_Архитектура.md` — обновлён 1С Pipeline line

### Вопрос к проверке
Действительно ли Serena даёт ощутимую ценность в рабочем процессе реализации задач 1С, или Этап 0 — это ритуал без эффекта?

### Методология
Подход C (Value-per-tool audit): по каждому Serena-тулу отдельно — (a) что делает, (b) какая альтернатива есть в проекте, (c) unique value в диапазоне 0-2.

---

## Собранные факты (с доказательствами)

### Факт 1: `language: bsl` — невалидная конфигурация

**Источник:** `.serena/project.yml`

```yaml
# language of the project (csharp, python, rust, java, typescript, go, cpp, or ruby)
language: bsl
project_name: "1С-Framework"
```

**Serena-репозиторий содержит `adding_new_language_support_guide.md`** (в `tools/serena/.serena/memories/`) — это гайд как *добавить* новый язык. BSL LSP никто не добавлял (в `tools/serena/src/solidlsp/language_servers/` нет соответствующего файла).

**Физическое подтверждение отсутствия BSL LSP:**

```python
# content of .serena/cache/bsl/document_symbols_cache_v23-06-25.pkl
{
  'src/bsl/semantic_search/mcp.py-False': <...>
}
```

Кеш содержит **1 файл** за всё время существования проекта. И это **Python-файл**. Если бы BSL LSP работал, кеш должен был бы содержать тысячи записей (в проекте 2027 `.bsl` файлов).

### Факт 2: Memories coverage = 1/40 проектов

**Источник:** `Glob src/projects/configuration/*/.serena/memories/*.md`

Из 40 проектов в `src/projects/configuration/` только у **одного** (`260304_GKSTCPLK-2182`) есть `.serena/memories/`:

| Файл | Строк | Содержание | Уникальная ценность |
|---|---|---|---|
| `analysis-GKSTCPLK-2182.md` | 26 | Краткая сводка 4 точек модификации + корень бага | **0** (дубль ANALYSIS-REPORT.md) |
| `impl-GKSTCPLK-2182.md` | 15 | Список изменений по строкам | **0** (дубль git log + IMPLEMENTATION-PROGRESS) |
| `session-status-2026-03-05.md` | 43 | Состояние сессии на дату | **0** (устарело, упоминает несуществующие хуки) |
| `session-config-analysis-2026-03-05.md` | 48 | Конфиг-снапшот | **0** (устарело) |
| `troubleshooting-env-settings-*.md` | 39 | Env troubleshoot | **0** (не 1С-specific) |
| `howto-switch-to-glm5.md` | 44 | LLM rotation howto | **0** (не 1С-specific, должно быть в llm-rotation skill) |

**Из 215 строк memories — 0 строк уникальной информации.**

### Факт 3: `serena-index-checker.py` не существует

**Проверка:**
```bash
find .claude -name "serena-index-checker*"  →  (пусто)
grep "mcp__serena__.*" .claude/settings.json  →  (нет матчеров)
```

**Археологическая улика:** в `session-status-2026-03-05.md` упоминается список активных хуков из той эпохи:
```
### PostToolUse hooks
- skill-linker.py, bsl-impact-analysis.py, auto-parse-prd.py
- multi-pipeline-tracker.py
- code-analysis-ast-recorder.py
- serena-index-checker.py          ← когда-то существовал
- post-commit-completer.py
- git-commit-reminder.py
- documentation-blocker.py
```

Инфраструктура хуков переработана: из 15+ PostToolUse-хуков той эпохи в текущем `.claude/hooks/` остались лишь немногие, `serena-index-checker.py` выпилен вместе с остальными.

**Следствие:** `/activate-project.md` ссылается на несуществующий хук. Описанная там магия «claudeFallback → memory/git/index/memories» — **не работает**. Это мёртвая документация.

---

## Полный инвентарь ~40 тулов Serena

Источник: закомментированный список в `.serena/project.yml` (раздел `excluded_tools`).

### Категория A: LSP-dependent (символьные) — **13 тулов**

| Тул | Альтернатива в проекте | Работает на BSL? | Unique value |
|---|---|---|---|
| `find_symbol` | EDT-MCP `get_module_structure` + `get_symbol_info` | ❌ | **0** |
| `find_referencing_symbols` | EDT-MCP `find_references`, bsl-semantic-search | ❌ | **0** |
| `find_referencing_code_snippets` | Grep + bsl-semantic-search | ❌ | **0** |
| `get_symbols_overview` | EDT-MCP `get_module_structure` | ❌ | **0** |
| `replace_symbol_body` | EDT-MCP `write_module_source` (line-anchored) | ❌ | **0** |
| `insert_after_symbol` | EDT-MCP `write_module_source` с `insertAfterLine` | ❌ | **0** |
| `insert_before_symbol` | То же | ❌ | **0** |
| `restart_language_server` | — | ❌ | **0** |

**Всего: 0 unique value на BSL-задачах.** LSP мёртв.

### Категория B: Filesystem — **9 тулов (дубли нативных)**

| Тул | Альтернатива | Unique value |
|---|---|---|
| `list_dir` | `Glob`, `Bash ls` | **0** |
| `find_file` | `Glob` | **0** |
| `read_file` | `Read` | **0** |
| `create_text_file` | `Write` | **0** |
| `delete_lines` | `Edit` | **0** |
| `replace_lines` | `Edit` | **0** |
| `insert_at_line` | `Edit` | **0** |
| `search_for_pattern` | `Grep` | **0** |
| `execute_shell_command` | `Bash` | **0** |

**Всего: 0 unique value.** Все покрываются нативными тулами Claude Code.

### Категория C: Memory — **4 тула**

| Тул | Альтернатива | Unique value |
|---|---|---|
| `write_memory` | Write в `docs/`, `MEMORY.md`, `memory-ai` MCP, `vector-memory` MCP | **1** (частично) |
| `read_memory` | Read из `docs/`, или MCP-тулы memory | **1** |
| `list_memories` | `Glob docs/*.md` | **1** |
| `delete_memory` | `rm` | **0** |

**Частичная уникальность:** memories в `.serena/memories/` гитигнорятся автоматически (`.serena/.gitignore` существует), изолированы от project docs и не засоряют git. Но:
- `C:\Users\AlexT\.claude\projects\D--1--Framework\memory\MEMORY.md` даёт ту же per-project auto-memory
- `memory-ai` MCP поддерживает поиск
- Фактическое использование = 0 (1 проект из 40, и там дубли)

### Категория D: Meta-cognitive (think-tools) — **3 тула**

| Тул | Функция | Альтернатива |
|---|---|---|
| `think_about_collected_information` | Пауза для оценки полноты данных | Prompt discipline |
| `think_about_task_adherence` | «Не ушёл ли я от задачи» | `task-protocol-enforcer`, `task-enforcer` |
| `think_about_whether_you_are_done` | «А точно ли всё сделал» | Checklist в SKILL.md, `skill-eval-enforcer` |

**Единственная категория с концептуальной уникальностью** — это не инструменты работы с кодом, а инструменты **дисциплины** (принудительная рефлексия через вызов тула).

**НО:** в проекте уже работают альтернативные дисциплинарные механизмы:
- `task-enforcer.py` блокирует Stop при pending задачах
- `code-review-enforcer.py` требует ревью после Write/Edit
- `skill-eval-enforcer.py` проверяет quality score скилла
- Checklists в конце SKILL.md

→ **Unique value: 0-1** (сильно зависит от того, считать ли think-tools дополнением или дублем существующих enforcer-хуков).

### Категория E: Config/Workflow — **9 тулов (admin)**

| Тул | Практическая ценность |
|---|---|
| `activate_project` | **1** (prerequisite) |
| `check_onboarding_performed` | **0** (одноразовая) |
| `onboarding` | **0** |
| `initial_instructions` | **0** (`initial_prompt: ""` пустой) |
| `prepare_for_new_conversation` | **0** |
| `switch_modes` | **0** (modes не используются) |
| `get_current_config` | **0** (debug) |
| `summarize_changes` | **0** (git log справляется) |
| `remove_project` | **0** |

---

## Сводная матрица

| Категория | Тулов | Работает? | Unique value total |
|---|---|---|---|
| A. LSP-symbols | 13 | ❌ (нет BSL LSP) | **0** |
| B. Filesystem | 9 | ✅ | **0** |
| C. Memory | 4 | ✅ | **1** (частично) |
| D. Think-tools | 3 | ✅ | **0-1** (частично) |
| E. Config/Admin | 9 | ✅ | **1** (activate_project) |
| **ИТОГО** | **~38** | — | **~2-3** |

**Из ~38 тулов — реально уникальную ценность на BSL-задачах даёт ~5-8% (2-3 тула), и все они частичные.**

---

## Сценарный анализ

### Сценарий X: Сменить `language: bsl` → `language: python`

**Что оживает:**
- LSP-тулы работают на **337 Python-файлах** (`src/pdf_framework/` 246, `src/memory/` 48, `src/bsl/**/*.py` 43)
- `find_symbol`, `find_referencing_symbols`, `get_symbols_overview` становятся реально функциональными
- `replace_symbol_body` делает анкерные правки устойчивые к сдвигу строк

**Что теряется:**
- На 2027 BSL-файлах Serena всё равно fallback text-search (было и так)

**Ожидаемый выигрыш:** 20-30% задач Python-рефакторинга фреймворка получают 2-5x ускорение.

**Use-cases где Serena в Сценарии X реально помогает:**
| Задача | Serena | Grep/Edit | Выигрыш |
|---|---|---|---|
| Переименовать параметр `k` → `top_k` в стратегиях поиска | `find_referencing_symbols` + rename | Grep + Edit каждое | **Средний** |
| Найти все подклассы `BaseHook` | `find_referencing_symbols` | Grep `class.*BaseHook` | **Малый** |
| Заменить тело `_assign_page_numbers` | `replace_symbol_body` | Read → Edit по строкам | **Средний** |
| Переименовать функцию с учётом импортов | `find_referencing_symbols` | Grep + анализ | **Средний** |

### Сценарий Y: Оставить `language: bsl`

Serena даёт ~2% ценности (memories + think-tools), и те не используются на практике. **Чистая ценность ≈ 0.**

---

## Решения (приняты 2026-04-14)

### Решение 1: Откатить Этап 0 из `implement-1c-task`

**Обоснование:** Этап 0 был добавлен в ошибочном предположении что `serena-index-checker.py` существует и что Serena даёт ценность на BSL. Оба предположения оказались ложными.

**Действия:**
1. `.claude/skills/implement-1c-task/SKILL.md`: 9-этапный → 8-этапный, удалить секцию «Этап 0», вернуть таблицу инструментов к оригиналу, убрать Serena-строку из чеклиста. Версия → 2.1.1 с пометкой «rolled back Этап 0 after audit».
2. `.claude/commands/implement-1c-task.md`: убрать блок «Этап 0 обязателен», вернуть заголовок к 8-этапному.
3. `docs/framework documentation/01_ОБЗОР/01.2_Архитектура.md`: вернуть описание 1С Pipeline к состоянию без Этапа 0.

### Решение 2: Рассмотреть Сценарий X (опционально, не блокирует)

Сменить `.serena/project.yml` → `language: python` и добавить Serena как **опциональный** инструмент для Python-рефакторинга фреймворка. Это даст реальную ценность на 337 Python-файлах. Не делать автоматически — требует:
- Тест на одной реальной задаче рефакторинга
- Сравнение метрик (call count, токены) с Grep+Edit подходом
- Решение о добавлении в `framework-patterns` skill или отдельный `python-refactor-serena`

### Решение 3: Почистить устаревшую документацию

`/activate-project.md` ссылается на несуществующий хук `serena-index-checker`. Нужно либо:
- (a) удалить файл, либо
- (b) переписать без упоминания хука (оставить только `mcp__serena__activate_project` как примитив)

**Не блокирует**, но создаёт когнитивный шум и вводит в заблуждение при чтении.

### НЕ делаем

- ❌ Писать BSL LSP для Serena (3-5 дней работы, дубль EDT-MCP с худшим качеством)
- ❌ Добавлять enforcer-хук для жёсткой блокировки без activate_project (гейтить ценность которой нет)
- ❌ Полностью удалять Serena-инфраструктуру (`.serena/` папка, `tools/serena/`) — может пригодиться в Сценарии X

---

## Метрики для будущего ре-аудита

Если через 3-6 месяцев вернёмся к вопросу «нужна ли Serena?»:

| Метрика | Порог «оставить» | Порог «удалить» |
|---|---|---|
| Проекты с memories | >20% | <10% |
| Уникальных вызовов `write_memory` / месяц | >5 | <2 |
| Вызовы `find_symbol`/`find_referencing_symbols` в сессии | >3 | <1 |
| Git commits где Serena упомянута в pipeline | >10% | <5% |

---

## Ссылки

- Претензия на Этап 0: коммит с `docs(hermes)...` (ветка master, 2026-04-14)
- Предыдущий аудит (Подход C, быстрая версия): в контексте этой же сессии
- Serena upstream: `tools/serena/`
- BSL LSP гайд: `tools/serena/.serena/memories/adding_new_language_support_guide.md`
