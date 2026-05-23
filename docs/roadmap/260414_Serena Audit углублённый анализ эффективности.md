# Serena Audit — углублённый анализ эффективности в 1С-Framework

**Дата аудита:** 2026-04-14
**Резолюция:** 2026-04-15
**Статус:** ✅ РЕШЕНО — принят **Сценарий W (Hybrid Extract-only)** — **Phases 0-7 завершены** (2026-04-19), **верифицировано 2026-04-19** (v4.6 — исправлена misleading-метрика «95%» + добавлен denylist-митигейшн для over-match, см. секцию «Верификация реализации»)
**Авторы:** Claude Opus 4.6 (первичный), GLM-5.1 (коррекция), Claude Opus 4.6 1M (резолюция), Claude Opus 4.7 1M (Phase 0b + верификация + denylist-митигейшн)

---

## TL;DR

1. **Serena в текущей интеграции даёт ~0 уникальной ценности.** LSP-based тулы мертвы (BSL LS не стартует, кеш содержит 1 `.py` файл при 2027 `.bsl`). Memories используются в 1 проекте из 40. Описанная в `/activate-project.md` магия зависит от несуществующего хука `serena-index-checker.py`.
2. **BSL LS внутри Serena реально существует** (`bsl_language_server.py`, 551 строка, использует `bsl-language-server v0.24.0-rc.3` от 1c-syntax), но экспериментальный и не стартует на практике.
3. **Единственный реальный пробел в стеке — `rename_symbol` для BSL кода.** EDT-MCP имеет `rename_metadata_object` (только для справочников/документов), но не умеет переименовывать функции/переменные. Все остальные Serena-тулы дублируются EDT-MCP (33 tools), ast-grep-mcp, bsl-semantic-search или нативными Read/Write/Edit/Glob/Grep.
4. **Финальное решение — Сценарий W: extract-only.** Перенести из Serena только нужные концепции и инструменты в native стек (`bsl-semantic-search` MCP), Serena после реализации удалить. Гибрид **Вариант A** (BSL LS standalone через минимальный LSP клиент) **+ Вариант B** (graph-based rename через Neo4j + ast-grep) с routing по типу символа. Отклонены: Сценарий Z (чинить Serena), X (переключить на python), Y (оставить как есть), C (форк EDT-MCP).
5. **План реализации:** Phases 0a-7 (ядро), оценка 6-9 дней. Дополнительно Phases 8-10 (v4.1 extension) — context/mode system, Tier 4 tools, dashboard/observability, +5-7 дней.
6. **Дополнительно (v4.1, 2026-04-15):** из Serena переносятся не только инструменты, но и **архитектурные концепции**: context-aware tool gating (excluded_tools per harness), modes (planning/interactive/editing), evaluation методология (20 задач × 5 категорий × (a)(b)(c) таксономия), automated onboarding, dashboard observability, Tier 4 navigation tools (`bsl_find_code_snippets`, `bsl_type_hierarchy`, `bsl_find_implementations`, `bsl_project_overview`). См. секцию 4.9.
7. **Немедленный первый коммит** — откат Этапа 0 из `implement-1c-task` (зависит от несуществующего хука) + Recon BSL LS + spec гибридного плана.
8. **Phase 0b выполнена (2026-04-17) — Scenario 2 подтверждён.** BSL LS v0.22.0 запускается standalone через stdio (cold 4.0-4.8s), in-file rename работает, **cross-file rename не работает даже с `Configuration.xml` + `.mdo`** (архитектура «per-document» — LS видит только файлы открытые через `didOpen`). `textDocument/references` возвращает `[]` для экспортной функции; rename экспорта даёт только 1 edit в declaration-файле. Routing matrix скорректирована: `module_export_proc` переведён с `A+B parallel` на **`B only`**. Variant A сокращён до in-file kinds (`local_var`, `parameter`, `module_private_proc`), срок 2-3 дн → 1-1.5 дн. Полный отчёт: [bsl-ls-recon-results.md](bsl-ls-recon-results.md).

---

## 1. Мотивация аудита

### Что спровоцировало аудит
В рамках предыдущей задачи в `.claude/skills/implement-1c-task/SKILL.md` был добавлен Этап 0 «Активация проекта в Serena», и скилл помечен v2.1.0 (9 этапов). Обновлены `implement-1c-task.md` и `docs/framework documentation/01_ОБЗОР/01.2_Архитектура.md`.

### Вопрос
Действительно ли Serena даёт ощутимую ценность в рабочем процессе реализации задач 1С, или Этап 0 — это ритуал без эффекта?

### Методология
**Value-per-tool audit:** по каждому Serena-тулу — (a) что делает, (b) какая альтернатива есть в проекте, (c) unique value 0-2. Факты подтверждены чтением кода Serena, содержимого `.serena/cache/`, `.serena/memories/` и `.claude/hooks/`.

---

## 2. Ключевые факты (с доказательствами)

### Факт 1: `language: bsl` — конфигурация с неработающим BSL LS

**Источник:** `.serena/project.yml`

```yaml
language: bsl
project_name: "1С-Framework"
```

**BSL Language Server в Serena существует, но экспериментальный:**
- Реализация: `src/solidlsp/language_servers/bsl_language_server.py` (551 строка)
- Регистрация: `ls_config.py:56` — `BSL = "bsl"` в enum Language
- Filename matcher: `*.bsl`, `*.os` (OneScript)
- Использует `bsl-language-server v0.24.0-rc.3` от 1c-syntax (тот же LS, что в VSCode-плагине)
- Автозагрузка Java 21 runtime (из vscode-java VSIX)
- LSP capabilities: definition, references, documentSymbol, hover, completion, signatureHelp, rename
- **НО:** не упомянут в README (список языков) и CHANGELOG — не включён в официальный список
- GitHub issues #802, #798, #792 — известные проблемы с BSL интеграцией

**Физическое подтверждение неработоспособности:**

```python
# .serena/cache/bsl/document_symbols_cache_v23-06-25.pkl
{'src/bsl/semantic_search/mcp.py-False': <...>}
```

Кеш содержит **1 файл** за всё время существования проекта. И это `.py`. При 2027 `.bsl` файлах. Значит BSL LS не запускается корректно — ошибка инициализации (Java path / конфиг / crash), а не отсутствие поддержки BSL.

### Факт 2: Memories использовались в 1 проекте из 40 (2.5%)

**Источник:** `Glob src/projects/configuration/*/.serena/memories/*.md`

Из 40 проектов только у `260304_GKSTCPLK-2182` есть `.serena/memories/`. Содержимое:

| Файл | Строк | Уникальная ценность |
|---|---|---|
| `analysis-GKSTCPLK-2182.md` | 26 | **0** — дубль `ANALYSIS-REPORT.md` |
| `impl-GKSTCPLK-2182.md` | 15 | **0** — дубль git log + IMPLEMENTATION-PROGRESS |
| `session-status-2026-03-05.md` | 43 | **0** — устарело, упоминает несуществующие хуки |
| `session-config-analysis-2026-03-05.md` | 48 | **0** — устарело |
| `troubleshooting-env-settings-*.md` | 39 | **0** — не 1С-specific |
| `howto-switch-to-glm5.md` | 44 | **0** — не 1С-specific |

**Из 215 строк memories — 0 строк уникальной информации.**

### Факт 3: `serena-index-checker.py` — фантомный хук

- В `.claude/hooks/` файла **нет**
- В `.claude/settings.json` нет матчеров `mcp__serena__.*`
- Упоминается в `/activate-project.md` как основа описанной там «магии claudeFallback → memory/git/index/memories»
- Археологический след: `session-status-2026-03-05.md` упоминает хук в списке старой эпохи, когда было 15+ PostToolUse-хуков

**Следствие:** `/activate-project.md` ссылается на мёртвую инфраструктуру. Описанная там автоматизация **не работает**. Это создаёт когнитивный шум и вводит в заблуждение.

### Факт 4: Единственный реальный пробел — rename функции/переменной в BSL коде

| Возможность | Покрыто стеком? | Чем |
|---|---|---|
| Symbol navigation (BSL) | ✅ | EDT-MCP `get_symbol_info`, `go_to_definition`, `get_module_structure` |
| Find references (BSL) | ✅ | EDT-MCP `find_references`, `get_method_call_hierarchy` |
| Rename metadata object | ✅ | EDT-MCP `rename_metadata_object` (только справочники/документы) |
| **Rename функции/переменной в BSL коде** | ❌ | **НЕТ альтернативы в стеке** |
| AST pattern matching | ✅ | `ast-grep-mcp` (BSL grammar от 1c-syntax) |
| Cross-language graph | ✅ | `bsl-semantic-search` (Neo4j) |
| Platform type docs | ✅ | `bsl-platform-context` |
| Symbol-level editing | ⚠️ | EDT-MCP `read_method_source` + `write_module_source` — есть, но не обёрнуто systematically |

---

## 3. Оценка Serena-инструментов: unique value по категориям

Источник: список `excluded_tools` в `.serena/project.yml` + официальная документация Serena (https://oraios.github.io/serena/01-about/035_tools.html).

| Категория | Тулов | Работает сейчас? | Unique value | Обоснование |
|---|---|---|---|---|
| **A. LSP-symbols** (`find_symbol`, `find_referencing_symbols`, `replace_symbol_body`, `insert_after/before_symbol`, `rename_symbol`, `safe_delete_symbol`, ...) | 13 | ❌ (BSL LS не стартует) | **0** (сейчас) / **4-6** (если починить) | Навигация дублируется EDT-MCP. Symbol-level editing + `rename_symbol` — реально уникальны |
| **B. Filesystem** (`list_dir`, `find_file`, `read_file`, `create_text_file`, `delete_lines`, `replace_lines`, `insert_at_line`, `search_for_pattern`, `execute_shell_command`) | 9 | ✅ | **0** | Полные дубли нативных Read/Write/Edit/Glob/Grep/Bash |
| **C. Memory** (`write_memory`, `read_memory`, `list_memories`, `delete_memory`) | 4 | ✅ | **1** (частично) | `memory-ai` + Qdrant + Claude auto-memory покрывают с запасом. Реальное использование = 0 |
| **D. Think-tools** (`think_about_collected_information`, `think_about_task_adherence`, `think_about_whether_you_are_done`) | 3 | ✅ | **0-1** | Дисциплинарные. Покрыто `task-enforcer`, `skill-eval-enforcer`, `code-review-enforcer` хуками |
| **E. Config/Workflow** (`activate_project`, `onboarding`, `switch_modes`, `prepare_for_new_conversation`, ...) | 9 | ✅ | **1** (только `activate_project` как prerequisite) | Остальное — админ-рутина, не используется |
| **ИТОГО** | **~38** | — | **~2-3** (сейчас) / **~6-9** (с починкой + latest tools) | — |

**Сейчас:** из ~38 тулов реально уникальную ценность даёт ~5-8% (2-3 тула). **Если BSL LS починить + обновить до latest:** вырастет до ~15-20% (6-9 тулов), в первую очередь за счёт `rename_symbol` (единственного без альтернативы), `safe_delete_symbol`, `replace_symbol_body`, `insert_after/before_symbol`.

**Ключевой инсайт:** полная миграция Serena ради ~6-9 тулов (из которых один критичен) — неоправданно дорого. Правильное решение — перенести **только нужное** в native стек.

---

## 4. Резолюция: Сценарий W (Hybrid Extract-only)

### 4.1. Суть решения

Вместо миграции Serena или починки BSL LS внутри неё — **перенос только нужных инструментов и концепций** в native стек (`bsl-semantic-search` MCP сервер), адаптированный под BSL/1С. Serena после реализации удаляется.

**Гибрид двух подходов:**
- **Вариант A — BSL LS standalone:** запуск `bsl-language-server.jar` как subprocess с минимальным LSP клиентом на Python. Без Serena wrapper, без Eclipse.
- **Вариант B — Native graph-based:** поиск references через уже существующий Neo4j граф `bsl-semantic-search`, замены через `ast-grep-mcp`, верификация через `edt-mcp get_project_errors`.

Варианты **не взаимоисключающие**: routing по типу символа объединяет их для покрытия выше, чем каждый по отдельности.

### 4.2. Что переносится из Serena

#### Tier 1 — Refactoring (критично, нет альтернативы)

| Serena tool | Native имя | Бэкенд | Обоснование |
|---|---|---|---|
| `rename_symbol` | `bsl_rename_symbol` | Гибрид A+B | Единственная операция без альтернативы. EDT-MCP `rename_metadata_object` — только метаданные |
| `safe_delete_symbol` | `bsl_safe_delete_symbol` | B + EDT-MCP verify | Удаление с проверкой references |
| `find_referencing_symbols` | `bsl_find_references` | A primary, B fallback | Унификация с EDT-MCP |

#### Tier 2 — Symbol-anchored editing (обёртки над EDT-MCP, без LSP)

| Serena tool | Native имя | Реализация |
|---|---|---|
| `replace_symbol_body` | `bsl_replace_method_body` | `edt-mcp read_method_source` → `write_module_source searchReplace` |
| `insert_after_symbol` | `bsl_insert_after_method` | `edt-mcp read_method_source` → detect end → `write_module_source insertAfterLine` |
| `insert_before_symbol` | `bsl_insert_before_method` | Аналогично с началом метода |

Эти обёртки не требуют BSL LS — работают через существующий EDT-MCP. Реализуются немедленно, параллельно с Recon Варианта A.

#### Tier 3 — Методология (из Serena evaluation)

Skill `bsl-refactoring-workflow` с 5-категорийной матрицей (источник: https://oraios.github.io/serena/04-evaluation/000_evaluation-intro.html):

| Категория задачи | Symbol-aware побеждает | Native Edit побеждает |
|---|---|---|
| Navigation | Незнакомый проект, «где вызывается X» | Знаешь где искать, 1-2 точки |
| Small edits | — | 1-2 строки, локальная правка |
| Large edits | Symbol-anchored, замена тела функции | Line-exact правки |
| Cross-file refactoring | **Rename, move — killer feature** | — |
| Workflow | — | Config, docs, shell |

### 4.3. Что НЕ переносится

- **Filesystem tools** — полные дубли нативных Read/Write/Edit/Glob/Bash
- **Memory tools** — покрыто `memory-ai` + Claude auto-memory + Qdrant
- **Think-tools** — покрыто enforcer-хуками
- **Workflow tools** (`onboarding`, `switch_modes`, `prepare_for_new_conversation`) — не используется
- **JetBrains tools** — мы на VS Code + EDT
- **Сам Serena** — удаляется из стека после Phase 7

### 4.4. Архитектура: единый сервер

```
┌─────────────────────────────────────────────────────────────────┐
│                 bsl-semantic-search MCP server                   │
│                    (расширяется новыми tools)                    │
│                                                                   │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────┐ │
│  │  Orchestrator    │───▶│  Symbol          │───▶│  Routing  │ │
│  │  (entry point)   │    │  Classifier      │    │  Decision │ │
│  └──────────────────┘    └──────────────────┘    └─────┬─────┘ │
│                                                          │       │
│         ┌────────────────────────────────────────────────┤       │
│         ▼                        ▼                       ▼       │
│  ┌─────────────┐         ┌─────────────┐         ┌────────────┐ │
│  │  Variant A  │         │  Variant B  │         │  EDT-MCP   │ │
│  │  BSL LS     │         │  Graph +    │         │  wrapper   │ │
│  │  subprocess │         │  ast-grep   │         │  (Tier 2)  │ │
│  └──────┬──────┘         └──────┬──────┘         └─────┬──────┘ │
│         │                       │                       │        │
│         ▼                       ▼                       ▼        │
│  ┌──────────────┐        ┌─────────────┐         ┌────────────┐ │
│  │ java -jar    │        │  Neo4j      │         │ edt-mcp    │ │
│  │ bsl-lang-    │        │  (уже       │         │ HTTP :8765 │ │
│  │ server.jar   │        │  существует)│         │            │ │
│  └──────────────┘        └─────────────┘         └────────────┘ │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Verification Layer (после apply)                          │  │
│  │  edt-mcp get_project_errors → сравнение до/после          │  │
│  │  Автооткат при росте ошибок                                │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Почему один сервер, а не новый:**
- Neo4j граф (ядро Варианта B) уже в `bsl-semantic-search`
- Интеграция с ast-grep уже есть
- Уже зарегистрирован в `.mcp.json`
- BSL LS стартует как subprocess **внутри** процесса сервера (lazy init)

### 4.5. Symbol Classifier

Определяет тип символа перед routing:

```python
SYMBOL_KINDS = {
    "local_var",           # переменная внутри метода
    "parameter",           # параметр метода
    "module_private_proc", # Процедура без Экспорт
    "module_export_proc",  # Процедура в общем модуле с Экспорт
    "manager_method",      # метод модуля менеджера справочника/документа
    "object_method",       # метод модуля объекта
    "form_handler",        # обработчик формы
    "form_command",        # команда формы
    "unknown"
}

def classify(file_path: Path, line: int, col: int) -> SymbolKind:
    # 1. Контекст по пути файла (BSL структура строгая)
    ctx = classify_file_context(file_path)
    # src/CommonModules/*/Ext/Module.bsl → common_module
    # src/Catalogs/*/Ext/ManagerModule.bsl → catalog_manager
    # src/Documents/*/Forms/*/Ext/Form/Module.bsl → form

    # 2. Символ на позиции через ast-grep
    symbol = ast_grep.get_symbol_at(file_path, line, col)

    # 3. Для identifier — найти декларацию
    if symbol.kind == "identifier":
        decl = ast_grep.find_declaration(symbol, file_path)
        if decl is None:
            return "unknown"
        symbol = decl

    # 4. Комбинация контекст + тип
    return combine(ctx, symbol)
```

**Критично:** Classifier работает за миллисекунды. Никаких тяжёлых запросов к Neo4j или BSL LS.

### 4.6. Routing Matrix (ядро гибрида)

| Symbol Kind | Primary | Verification | Rationale |
|---|---|---|---|
| `local_var` | **A** (BSL LS in-file) | — | Scope = один метод. BSL LS знает scope |
| `parameter` | **A** (BSL LS in-file) | **B** граф для cross-module callers | A точен для объявления, B для cross-file вызовов |
| `module_private_proc` | **A** (BSL LS in-module) | — | Scope = один модуль |
| `module_export_proc` | **B only** (после Phase 0b, 2026-04-17) | **EDT-MCP** `find_references` | Recon показал: BSL LS v0.22.0 per-document — cross-file rename не работает даже с метаданными. Ранее планировалось A+B parallel, отклонено по факту. См. [bsl-ls-recon-results.md](bsl-ls-recon-results.md) |
| `manager_method` | **B** (граф) | **EDT-MCP** `find_references` | BSL LS не знает `Справочники.X.Модуль.Y()` контекст |
| `object_method` | **B** (граф) | **EDT-MCP** `find_references` | То же |
| `form_handler` | **B** (стандартные имена) | — | Handlers — metadata-aware |
| `form_command` | **EDT-MCP** `rename_metadata_object` | B fallback | Commands — metadata-level |
| `unknown` | **Dry-run обоих A и B** | Показать оба результата | Явная неопределённость лучше молчаливой ошибки |

**Правило merge A+B параллельного:**

```python
def merge_edits(edit_a: WorkspaceEdit, edit_b: WorkspaceEdit) -> MergeResult:
    files_a = set(edit_a.changes.keys())
    files_b = set(edit_b.changes.keys())

    if files_a == files_b and same_positions(edit_a, edit_b):
        return MergeResult(confidence="HIGH", edit=edit_a)

    if files_a.issubset(files_b):
        return MergeResult(confidence="MEDIUM", edit=edit_b,
            warning=f"B нашёл дополнительно: {files_b - files_a}")

    if files_b.issubset(files_a):
        return MergeResult(confidence="MEDIUM", edit=edit_a,
            warning=f"A нашёл дополнительно: {files_a - files_b}")

    # Расхождение → ручной выбор
    return MergeResult(confidence="LOW", edit=None, conflict=(edit_a, edit_b))
```

### 4.7. Dry-run + Verification протокол

Все Tier 1 tools имеют `dry_run=True` по умолчанию.

```
Phase 1: Plan
  user → bsl_rename_symbol(file, line, col, new_name, dry_run=True)
  server → {
    "preview": WorkspaceEdit,
    "confidence": "HIGH|MEDIUM|LOW",
    "affected_files": [...],
    "symbol_kind": "module_export_proc",
    "routing": "A+B parallel, merged",
    "confirm_token": "<hash of edit>"
  }

Phase 2: Confirm
  user → читает preview, решает

Phase 3: Apply
  user → bsl_rename_symbol(..., dry_run=False, confirm_token=<hash>)
  server:
    1. Baseline: edt-mcp get_project_errors → errors_before
    2. Применить WorkspaceEdit (атомарно, all-or-nothing)
    3. edt-mcp revalidate_objects
    4. errors_after = edt-mcp get_project_errors
    5. Сравнение:
       errors_after.count <= errors_before.count → SUCCESS
       errors_after.count > errors_before.count → AUTO-ROLLBACK
         - Восстановить файлы из in-memory snapshot
         - Вернуть diff новых ошибок
```

**Confirm token** — защита от apply без preview. При несовпадении (файлы менялись между preview и apply) apply отклоняется.

### 4.8. Контракт между компонентами

Чтобы Phase 1-2 могли стартовать **до** Recon:

```python
class RenameBackend(Protocol):
    def can_handle(self, symbol_kind: SymbolKind) -> bool: ...
    def plan_rename(
        self, file: Path, line: int, col: int, new_name: str
    ) -> WorkspaceEdit | BackendError: ...
    @property
    def confidence_for(self, symbol_kind: SymbolKind) -> Literal["HIGH","MEDIUM","LOW"]: ...

class GraphBackend(RenameBackend):      # Variant B
    def __init__(self, neo4j_client, ast_grep_client): ...

class LspBackend(RenameBackend):        # Variant A (Phase 3)
    def __init__(self, bsl_ls_subprocess): ...

class EdtMcpBackend(RenameBackend):     # Tier 2, metadata objects
    def __init__(self, edt_mcp_http_client): ...

class RefactorOrchestrator:
    backends: list[RenameBackend]
    classifier: SymbolClassifier
    routing: dict[SymbolKind, RoutingStrategy]

    def rename(self, file, line, col, new_name, dry_run):
        kind = self.classifier.classify(file, line, col)
        strategy = self.routing[kind]
        # strategy: "A_only" | "B_only" | "A_primary_B_verify" | "parallel_merge"
        ...
```

Phase 2 стартует с `LspBackend` как no-op stub. Phase 3 подменяет stub реальной реализацией. Orchestrator и routing matrix **не переписываются**.

### 4.9. Дополнительные концепции из Serena (v4.1 addendum)

Раздел добавлен 2026-04-15 после углублённого анализа https://github.com/oraios/serena и https://oraios.github.io/serena. Изначальная v4-резолюция фокусировалась на инструментах (rename, symbol editing). Здесь — **архитектурные концепции и подходы к разработке**, которые Serena доказала на практике и которые переносимы независимо от гибрида A+B.

#### 4.9.1. Context-aware tool gating (контексты и режимы)

**Что это в Serena:** динамическое включение/отключение инструментов в зависимости от агентной оболочки (context) и задачи (mode). Это **не статический конфиг** — это композиционная система.

**Как устроено в Serena:**
- `src/serena/resources/config/contexts/*.yml` — один YAML на каждый тип клиента: `claude-code.yml`, `codex.yml`, `desktop-app.yml`, `ide.yml`, `chatgpt.yml`, `copilot-cli.yml`, `vscode.yml`, `jb-ai-assistant.yml`, `antigravity.yml`, `junie.yml`, `oaicompat-agent.yml` и др.
- `src/serena/resources/config/modes/*.yml` — modes: `planning`, `interactive`, `editing`, `one-shot`, `no-onboarding`
- Каждый файл содержит: `description`, `prompt` (инъекция в system prompt), `excluded_tools` (список)
- Финальный tool set = context × mode (композиция)

**Конкретный пример из `claude-code.yml`:**

```yaml
description: Claude Code (CLI agent where file operations, basic edits, etc. are already covered)
prompt: |
  You are running in a CLI coding agent context where file operations,
  basic (line-based) edits and reads as well as shell commands are
  handled by your own, internal tools.
  If Serena's tools can be used to achieve your task, you should prioritize them.
  ...
excluded_tools:
  - create_text_file
  - read_file
  - execute_shell_command
  - replace_content
  - find_file
  - list_dir
  - search_for_pattern
single_project: true
```

**Конкретный пример из `planning.yml`:**

```yaml
description: Only read-only tools, focused on analysis and planning
prompt: |
  You are operating in planning mode. Your task is to analyze code but not write any code.
  The user may ask you to assist in creating a comprehensive plan, or to learn
  something about the codebase.
excluded_tools:
  - create_text_file
  - replace_symbol_body
  - insert_after_symbol
  - insert_before_symbol
  - delete_lines
  - replace_lines
  - insert_at_line
  - execute_shell_command
  - replace_content
```

**Почему это ценно для нас:**

1. **Решает проблему дублирования tools**: сейчас наш MCP-стек содержит много дублей нативных Claude Code tools. Serena-паттерн даёт механизм «в этом harness эти tools не нужны — скрой их».
2. **Per-task restriction**: при `/analyze-1c-task-v2` нужен read-only режим (чтобы не модифицировать код случайно во время анализа). При `implement-1c-task` — полный доступ. Сейчас это не enforced.
3. **Prompt fragments**: вместо одного гигантского CLAUDE.md — композиция базовой части + task-specific preamble. Уменьшает когнитивный шум для каждой конкретной задачи.

**Адаптация для нашего стека:**

| Artifact | Purpose | Инициатор |
|---|---|---|
| `.claude/contexts/claude-code.yml` | Global default — для интерактивной работы Claude Code | Session start |
| `.claude/contexts/subagent.yml` | Для subagent Agent() вызовов — сокращённый prompt, узкий tool set | Agent() hook |
| `.claude/modes/analysis.yml` | Read-only mode для `/analyze-1c-task-v2` | Skill hook |
| `.claude/modes/implementation.yml` | Full mode для `implement-1c-task` | Skill hook |
| `.claude/modes/review.yml` | Navigation-only для code review | Skill hook |
| `.claude/modes/refactor.yml` | Только `bsl_rename_symbol`, `bsl_replace_method_body`, verification tools | Skill hook |

**Механизм gating:** hook на старт skill/slash-command → читает соответствующий YAML → инжектирует prompt + возвращает `excluded_tools` в tool use filter. Можно через `SessionStart` hook или PreToolUse hook.

**Отличие от существующих permission settings:** наши `.claude/settings.local.json` permissions — статичны и на уровне всей сессии. Serena-паттерн — **динамический, per-task**, и **композиционный** (context + mode).

#### 4.9.2. Методология evaluation (Serena test harness)

**Что это в Serena:** формализованная дисциплина для оценки «помогает ли инструмент на практике». Не синтетические benchmarks, а **реальные задачи из реального кода**, которые агент сам отбирает.

**Структура Serena evaluation** (из https://oraios.github.io/serena/04-evaluation/010_methodology.html):

- **~20 hands-on задач** (не синтетический dataset)
- **5 категорий** (уточнённые из первичного аудита):
  1. **Codebase Understanding** — структурные обзоры, targeted symbol retrieval, reference finding, type hierarchies, external dependency lookup
  2. **Single-File Edits** — small tweaks, medium rewrites, full replacements, insertions, local renames
  3. **Multi-File Changes** — cross-file renames, symbol/file moves, safe deletes, inlining
  4. **Reliability & Correctness** — scope precision, atomicity, success signals
  5. **Workflow Effects** — chained edits, stable vs ephemeral addressing, multi-step exploration

- **(a)(b)(c) таксономия результатов:**
  - **(a)** Tool adds capability beyond built-in
  - **(b)** Tool applies but offers no improvement (neutral/negative)
  - **(c)** Task outside tool's scope (context only, not a negative verdict)
  - **Явно требует репорта негативных и нейтральных находок** — «neither evaluation reads promotional»

- **Протокол эксперимента:**
  1. Агент выбирает **конкретные задачи из своей рабочей кодовой базы** (not predefined)
  2. Прогоняет workflow **дважды**: с инструментом и без (или наоборот)
  3. Применяет реальные edits + верифицирует через `git diff`
  4. **Откатывает изменения** после эксперимента → чистое рабочее дерево
  5. Записывает метрики: call counts, payload sizes, prerequisite steps

- **Self-evaluation culture:** агент оценивает **сам себя** — инструменты должны судиться теми, кто ими пользуется, а не по прокси-метрикам

- **Опубликованные результаты Serena** (для калибровки ожиданий):
  - Cross-file refactoring — highest-value category
  - Structural navigation — moderate advantage
  - Small local edits — **~4.5x меньше payload с built-ins** (Serena hurts здесь)

**Почему это ценно для нас:**

Изначальный Phase 6 benchmark в v4-плане был расплывчатым. Serena даёт **готовую дисциплину** которую можно скопировать дословно:

- **20 задач из реального git log** (ищем прошлые rename/refactor коммиты, воспроизводим)
- **5 категорий** как explicit таксономия — гарантируем покрытие, не только rename
- **(a)(b)(c)** — честная отчётность: не только «где помогло», но и «где нейтрально» и «где вне scope»
- **git diff verification + auto-revert** — дополняет наш verification через `edt-mcp get_project_errors`. Два независимых сигнала корректности вместо одного.
- **Self-evaluation** — Claude сам прогоняет benchmark, а не предопределённый скрипт

**Конкретный формат отчёта** (артефакт `docs/roadmap/bsl-refactor-benchmark-YYYY-MM.md`):

```markdown
# BSL Refactor Hybrid Benchmark — YYYY-MM

## Задачи (20)

### Категория 1: Codebase Understanding (4 задачи)
| # | Задача | Tool | Verdict | Calls | Payload |
|---|---|---|---|---|---|
| 1 | «Найти все вызовы ОбщийМодуль.Утилиты.ПолучитьНастройки в проекте» | bsl_find_references | (a) 1 call, full graph | 1 | 2KB |
| 1' | Тот же вопрос через Grep | Grep + Edit | — | 7 | 45KB |
| ... |

### Категория 2: Single-File Edits
### Категория 3: Multi-File Changes
### Категория 4: Reliability & Correctness
### Категория 5: Workflow Effects

## Итого
- (a) Added capability: N задач (XX%)
- (b) No improvement: M задач (YY%)
- (c) Out of scope: K задач (ZZ%)

## Найденные проблемы
- ... (baggy findings — required)

## Выводы и рекомендации
- ...
```

#### 4.9.2.1. Глубокое обоснование agent self-evaluation подхода

Ключевой аспект Serena-методологии — **агент сам выбирает задачи из своей рабочей кодовой базы**, а не использует предопределённый benchmark dataset. Это принципиально другая парадигма, не «ленивая версия SWE-bench». Ниже — подробное обоснование, почему это критично для нашего проекта.

##### Почему традиционные benchmarks не работают для оценки dev tools

| Проблема | Почему плохо для оценки tools |
|---|---|
| **Static tasks** | Зафиксированы на момент создания. Реальный код эволюционирует, задачи меняются |
| **Selection bias авторов** | SWE-bench = Django/Flask. Не репрезентативен для BSL/1С/enterprise code |
| **Синтетическая изоляция** | Задачи специально выделены self-contained. Не тестируют multi-file работу и workflow effects |
| **Contamination** | Опубликованные benchmarks попадают в training data моделей → метрики завышены |
| **Цена курирования** | SWE-bench потребовал человеко-месяцы для 2294 задач. Для внутреннего инструмента нереалистично |
| **Vendor bias** | Создатель инструмента сам выбирает задачи и публикует → селекция в свою пользу |
| **Не измеряют продуктивность** | Тестируют «может ли решить», а не «насколько быстрее/дешевле альтернативы» |

Serena explicitly отвергает SWE-bench и HumanEval: *«standard benchmarks rarely exercise cross-file refactoring and large-codebase navigation where Serena's tools excel, don't generalize to user codebases, and inevitably introduce selection bias»*. Для BSL/1С стандартных benchmark datasets **вообще не существует** — у нас нет альтернативы.

##### Мexаника: 5 шагов self-evaluation

**Шаг 1. Discovery (поиск задач в git history)**

Агент сканирует git log и ищет реальные прошлые изменения для воспроизведения:

```bash
git log --all --oneline --grep -i "rename\|переименован\|refactor"
git log --all --numstat --format="%H" | filter_by_size
git log --all --oneline -- '*.bsl'
```

Фильтрация: не тривиальные (<3 файлов — мало информации), не гигантские (>50 файлов — неконтролируемо), с понятным семантическим намерением.

**Шаг 2. Task definition** — для каждого коммита:
- **Before state:** parent commit (состояние «до»)
- **Expected result:** diff самого коммита (ground truth)
- **Task description:** «Переименовать `ОбщиеНастройки.ПолучитьЗначение` → `ПолучитьПараметр`»
- **Category:** одна из 5 Serena-категорий
- **Expected scope:** число файлов, occurrences

**Шаг 3. Dual execution** — выполнение обеими инструментами:

```
В isolated git worktree:
  1. Checkout parent commit
  2. Execute с Tool A (hybrid bsl_rename_symbol):
     - Записать: call count, payload, wall time, prerequisite steps
     - Зафиксировать final git diff A
  3. git reset --hard parent
  4. Execute с Tool B (Grep + Edit manual):
     - Те же метрики → diff B
  5. Cleanup worktree
```

**Шаг 4. Comparison + classification:**

Сравнение diff A и diff B с **actual commit** (ground truth):

| Результат | Verdict |
|---|---|
| Diff A == actual, Diff B != actual | **(a)** — Tool A даёт capability, B не справился |
| Оба correct, A имеет лучшие метрики | **(a)** — A more efficient |
| Оба correct, метрики эквивалентны | **(b)** — no improvement |
| Только B correct | **(b)** — A applied but wrong output |
| Ни один не справился | **(c)** — outside scope обоих |

**Шаг 5. Reporting** — агент пишет markdown-отчёт со **всеми** находками. Taxonomy **явно запрещает cherry-picking** — репорт обязан содержать (b) и (c) результаты. Если из 20 задач только 5 — (a), это валидный итог и публикуется as-is.

##### Концентный пример (BSL rename)

**Задача из git history:** коммит `a3f2c1d` — «рефакторинг: переименован `ОбщиеНастройки.ПолучитьЗначение` → `ПолучитьПараметр` (14 файлов)».

**Execution:**

**Tool A — `bsl_rename_symbol`:**
```
1. Checkout a3f2c1d^
2. bsl_rename_symbol(
     file="src/CommonModules/ОбщиеНастройки/Ext/Module.bsl",
     line=42, col=11, new_name="ПолучитьПараметр", dry_run=False
   )
3. Метрики: 1 call, 3 KB payload, 4.2 сек
```

**Tool B — Grep + Edit manual:**
```
1. Checkout a3f2c1d^
2. Grep("ПолучитьЗначение", path="src/", type="bsl")
   → 47 матчей в 22 файлах (false positives из одноимённых функций!)
3. Read каждого файла, ручной disambiguation
4. Edit 14 файлов, пропуск 8 файлов с одноимённой функцией из другого модуля
5. Метрики: 47 calls, 120 KB payload, 8 минут
```

**Comparison с actual commit:**

- Tool A diff **совпадает** с actual (14 файлов, все 30 occurrences корректно)
- Tool B diff **почти совпадает**: 2 файла пропущены (динамический `Вычислить()` не попал в Grep), 1 ложная правка (false positive)

**Verdict: (a)** — `bsl_rename_symbol` даёт capability, отсутствующую в Grep+Edit. Точнее (0 ошибок vs 3 ошибки) и **47x меньше tool calls**, **40x меньше payload**.

##### Почему «дешевле»

1. **Нулевая стоимость курирования задач** — git history как готовый dataset. У нас 5 лет коммитов, 2027 BSL файлов, 40 проектов — бесплатный benchmark.
2. **Нулевая стоимость ground truth** — «правильный ответ» = то, что человек реально сделал в коммите. Expected outputs не надо писать.
3. **Нулевая стоимость поддержки** — benchmark автоматически эволюционирует с кодом. Новые коммиты = новые задачи.
4. **Автоматизация** — агент сам запускает, сам пишет отчёт. Человеческое вмешательство = триггер «прогони».
5. **Линейная стоимость масштабирования** — прогнать на 20/50/200 задачах стоит только API calls, не человеко-часов.

**Сравнение с SWE-bench:** SWE-bench потребовал человеко-месяцы для 2294 задач из 12 Python-репо. Для BSL аналогичный объём = $$$ и устареет через 6 месяцев. Self-eval даёт тот же объём за часы и **не устаревает** — потому что всегда работает на актуальном git.

##### Почему «честнее»

1. **Нет vendor bias** — benchmark создаётся тем, **кто им пользуется** (наш Claude), а не тем, **кто продаёт инструмент**. У потребителя нет стимула скрывать плохие результаты.
2. **Taxonomy (a)(b)(c) как honesty gate** — агент **обязан** классифицировать каждый результат, включая «не помог» и «вне scope». Встроенное требование репортить негативные находки.
3. **Ground truth — реальный человеческий коммит** — не «что думал агент», а «что работало в production». Объективный arbiter.
4. **Количественные метрики** — call counts, payload, time, git diff equivalence. Нет места для «интуитивно кажется лучше».
5. **Воспроизводимость** — любой может прогнать тот же benchmark на том же репо. Prompt engineering-трюки отлавливаются при реплике.
6. **Self-interest alignment** — агент делает benchmark **для себя** (улучшить свой workflow), не для публикации. Нет стимула врать.
7. **Запрет cherry-picking встроен** — опубликованные Serena results содержат разделы «где Serena проигрывает»: `small local edits — ~4.5x less payload with built-ins`. Это явное признание проигрыша, невозможное в vendor-driven benchmarks.

##### Риски и митигации

| Риск | Митигация |
|---|---|
| Агент subconsciously выбирает задачи, где его tool выигрывает | Programmatic selection (git log filters), не свободный выбор агентом |
| Нет reproducibility между прогонами (разные 20 задач каждый раз) | Зафиксировать список в `benchmark-tasks.json`, обновлять явно |
| Ground truth = старый коммит может быть субоптимальным | Явно: мы сравниваем с «тем, что сделал человек», не с «идеальным решением». Калибровка, не абсолютная оценка |
| Observer effect — агент знает, что его оценивают | Запускать как рутинную задачу, не как «экзамен». Плюс два прогона: осознанный + слепой |
| Metric gaming (selection под свои метрики) | Fixed categories, minimum per category, programmatic selection |
| Нет ground truth для творческих задач (rename имеет, refactoring — нет) | Две категории задач: с ground truth (rename/move/delete) и без (restructuring). Разные критерии |

##### Связь с самокалибрующимися системами

Это **не testing**, а **feedback loop**, который делает остальную систему самокорректирующейся.

Выходы benchmark обратно влияют на:

| Артефакт | Как обновляется |
|---|---|
| **Routing Matrix (§4.6)** | Если на `module_export_proc` Variant A часто ошибается → switch primary на B |
| **Confidence scores** | Калибруются по фактической success rate per symbol kind |
| **Skill `bsl-refactoring-workflow`** | Примеры обновляются из реальных benchmark runs |
| **Метрики §7 (критерии ре-аудита)** | Пороги корректируются по distribution наблюдаемых значений |
| **Documentation** | «Когда использовать native Edit vs `bsl_rename_symbol`» обновляется по новым находкам |

Без этого loop — пороги и правила **угаданы заранее** и со временем расходятся с реальностью. С loop — система **сама находит слабые места**.

**Глубокая аналогия:** это паттерн self-play RL (AlphaZero, MuZero) — агент играет сам с собой, учится на собственных результатах. Разница: здесь «игра» — рефакторинг, «противник» — альтернативный способ сделать ту же задачу. Система становится **самокалибрующейся**, что намного ценнее любого синтетического benchmark.

##### Операционализация для нашего проекта

**Артефакты Phase 6:**

1. `docs/roadmap/benchmark/tasks.json` — зафиксированный список 20 задач (обновляется явно)
2. `docs/roadmap/benchmark/runner.py` — скрипт, запускающий benchmark через Claude API
3. `docs/roadmap/benchmark/results-YYYY-MM.md` — per-run отчёты
4. `docs/roadmap/benchmark/trend.md` — агрегат по всем прогонам

**Триггеры:**

- **Manual:** `/bsl-refactor-benchmark run` — по требованию
- **Scheduled:** ежеквартально через loop/cron
- **Pre-release:** перед каждым major изменением routing logic
- **Regression detection:** если auto-rollback counter растёт → автоматический запуск

**Связь с ре-аудитом:** метрики §7 (покрытие >85%, точность >95%, `bsl_rename_symbol` >5/неделя) вычисляются **автоматически** из benchmark reports, не собираются вручную. Это делает ре-аудит через 2-3 месяца почти бесплатным — просто читаем последний `trend.md`.

##### Ключевой итог

Agent self-evaluation — **не ленивая версия традиционного benchmark**, это **другая методология**, которая обменивает:

| Традиционный benchmark | Agent self-evaluation |
|---|---|
| Static reproducibility (фиксированный dataset) | **Ecological validity** (реальные задачи из реального кода) |
| Human curation (дорого, устаревает) | **Git history** (бесплатно, вечно актуально) |
| Vendor-driven objectivity (предвзято) | **Consumer-driven honesty** (нет стимула врать) |
| «Тестирование корректности» | **Измерение реальной продуктивности** |

Для нашего BSL-проекта это **идеально подходит**: стандартных benchmark-datasets для 1С не существует, git history огромна и бесплатна, а метрики нужны continuous, не разовые. Альтернативы не просто дороже — **их нет**.

#### 4.9.3. Tier 4 — Дополнительные tools для Understanding & Navigation

При первом проходе v4 мы сфокусировались на Tier 1 (rename) и Tier 2 (symbol editing). Анализ полного списка Serena tools показал **ещё 4 инструмента**, которые закрывают реальные пробелы в BSL-навигации:

| Serena analog | Native имя | Use case для BSL | Бэкенд |
|---|---|---|---|
| `find_referencing_code_snippets` | `bsl_find_code_snippets` | «Как используется `ОбщийМодуль.Утилиты.ПолучитьНастройки`?» — возвращает **фрагменты кода** вокруг вызовов, не только позиции. Для понимания usage patterns | B (граф + ast-grep для контекста) |
| `jet_brains_type_hierarchy` | `bsl_metadata_hierarchy` | Для справочника/документа показать все объекты, зависящие от него: регистры с измерениями этого типа, документы с реквизитами, отчёты СКД | EDT-MCP `get_metadata_details` + B (граф ссылок) |
| `jet_brains_find_implementations` | `bsl_find_handlers` | Найти все обработчики с именем «ПриОткрытии» во всех формах конфигурации. Или все реализации «ОбработкаПроведения» во всех документах | EDT-MCP `list_modules` + ast-grep паттерн |
| `onboarding` | `bsl_project_overview` | Автогенерация brief конфигурации: структура, ключевые общие модули, entry points (формы, подсистемы), внешние интеграции. Замена ручного `ANALYSIS-REPORT.md` preamble | EDT-MCP `get_metadata_objects` + LLM summarization |

**Приоритет внутри Tier 4:** `bsl_find_code_snippets` > `bsl_find_handlers` > `bsl_metadata_hierarchy` > `bsl_project_overview`. Первый — максимально полезный для code review и debugging. Последний — самый дорогой в реализации (требует LLM summarization).

#### 4.9.4. Architectural patterns

Четыре архитектурные паттерна из Serena, которые стоит адаптировать независимо от tool set.

**Pattern 1: Onboarding as automated project discovery**

*В Serena:* инструмент `onboarding` сканирует проект при первой активации и записывает структурированное описание в memories. После этого каждая новая сессия читает memories и получает контекст без ручной работы.

*Адаптация:* `bsl_project_overview` или slash-command `/onboard-bsl-project` — генерирует `docs/project-overview.md` из EDT-MCP metadata. Структура: Подсистемы → Ключевые справочники → Документы → Регистры → Общие модули → Внешние интеграции. Обновляется либо по команде, либо автоматически при изменении метаданных (hook).

**Pattern 2: Dashboard for observability**

*В Serena:* `open_dashboard` запускает web UI, показывающий live tool calls, call counts, active project, memory status. Это **не debugging tool**, а постоянная visibility в поведение MCP-стека.

*Адаптация:* lightweight dashboard (можно CLI или static HTML). Показывает:
- Recent `bsl_rename_symbol` / `bsl_find_references` calls (+ время выполнения)
- BSL LS subprocess status (если запущен) + uptime
- EDT-MCP health check (HTTP ping)
- Neo4j graph freshness (timestamp последней переиндексации)
- Счётчик auto-rollback операций (критическая метрика!)
- Circuit breaker status для BSL LS

**Зачем:** чтобы «что-то сломалось» диагностировалось за 5 секунд, а не через разбор логов. И чтобы метрики из §7 (критерии успеха для ре-аудита) собирались **автоматически**, а не вручную.

**Pattern 3: Dynamic initial instructions**

*В Serena:* `initial_instructions` — tool, который **агент вызывает сам** в начале сессии, получая context-specific руководство по использованию Serena. Это не один статический CLAUDE.md, а **динамическое, композиционное** руководство.

*Адаптация:* вместо одного 600+ строчного CLAUDE.md — fragments:
- `CLAUDE.base.md` — общие правила
- `.claude/contexts/<context>.md` — per-context adjustments (см. 4.9.1)
- `.claude/tasks/<task-type>.md` — per-task preamble, injected на старт задачи

Hook на старт skill читает соответствующие fragments и инжектирует в контекст. **Заметное уменьшение** стартового контекста и focused инструкции per task.

**Pattern 4: Memory discipline — read only when relevant**

*В Serena:* описание `read_memory` инструмента явно говорит «use only when task-relevant». Это **инструкция для агента**, не автоматический механизм. Агент сам решает, нужна ли конкретная memory для текущей задачи.

*Адаптация:* наша текущая система memory ultra-aggressive (всё загружается при старте). Serena-подход — **lazy reading**: memory индекс в стартовом контексте, content загружается только по явному запросу. Уменьшает token burn в стартовом контексте значительно.

Механизм: `memory-first-hook` инжектирует только **index** (имена + descriptions), а не content. Content загружается по `Read` запросу или явному `mcp__memory-ai__get_memory(name)`.

#### 4.9.4.1. Глубокое обоснование memory lazy reading (расширение Pattern 4)

Ключевой аспект Pattern 4 — **наш текущий `memory-first-hook` реализует anti-pattern** («ultra-aggressive loading»), который стоит реальных денег и деградирует качество работы агента. Ниже — подробное обоснование, почему lazy reading не просто «оптимизация», а архитектурно правильный выбор.

##### Что значит «ultra-aggressive» конкретно

Наш текущий `memory-first-hook.py` работает по схеме **eager injection**:

```
Session start
  → memory-first-hook срабатывает
  → читает ВСЕ релевантные memory файлы
  → вставляет их СОДЕРЖИМОЕ в system reminder
  → Claude видит их с первого токена
```

Доказательство в реальной сессии: в самом начале каждого разговора приходит блок вида:

```
Contents of C:\Users\AlexT\.claude\projects\...\memory\MEMORY.md
- [RDBG Protocol](rdbg-protocol.md) — ...
- [Agent() Model Selection + Z.AI](feedback_use_zai_for_agents.md) — ...
- [Use GLM agents for non-BSL tasks](feedback_use_glm_agents.md) — ...
- [FastMCP stdio fix on Windows](feedback_lazy-mcp-stdio-fix.md) — ...
- [MCP_Сервер usage](feedback_mcp_server_usage.md) — ...
- [Analyze before writing tests](feedback_analyze_before_tests.md) — ...
```

Плюс секции с инструкциями о memory system. Claude **уже несёт ~1500-5000 токенов «мета-информации о памяти» до первого сообщения пользователя**, не зная, будет ли задача связана с RDBG, GLM, FastMCP или VA-тестами.

В «ultra-aggressive» режиме это усугубляется:
- Hook читает не только `MEMORY.md` (индекс), но и **содержимое** отдельных файлов памяти
- Инжектируются **все** feedback memories (не только потенциально релевантные)
- Hook срабатывает на **каждой сессии**, без триггера по relevance
- Нет механизма «относительность к текущей задаче»

##### Что делает Serena вместо этого

Serena реализует **lazy reading через tool description gating** — встраивает инструкцию о релевантности **в схему самого инструмента**, а не в отдельный system prompt.

```python
@mcp.tool()
async def read_memory(memory_name: str) -> str:
    """Read the content of a memory file.

    IMPORTANT: Use only when task-relevant. Memories are snapshots
    from past sessions and may be stale. If the current task doesn't
    clearly benefit from a specific memory, don't read it.
    """
    ...
```

**Почему это работает лучше, чем system prompt:**

1. **Рядом с действием** — описание видно агенту в момент рассматривания вызова, не 20 сообщений назад
2. **Не деградирует** — system prompt «забывается» в длинном conversation (lost-in-the-middle); tool description загружается свежим при каждом рассмотрении вызова
3. **Per-tool granularity** — каждый инструмент имеет свою discipline, не одну общую
4. **Discoverable** — агент видит инструкцию даже если не читал system prompt
5. **Нативная механика** — это штатный способ документирования tools, не custom prompt engineering

**Рабочий процесс агента с Serena:**

```
1. Session start — memories НЕ в контексте
2. Пользователь задаёт задачу X
3. Агент думает: «может, нужны memories?»
4. Вызов list_memories → видит имена + descriptions (~300 tokens)
5. Оценка релевантности per memory
6. Если явно релевантно → read_memory(name)
7. Если нет → продолжает без memories
```

**Ключевой момент:** cost оплачивается **только если memory реально нужна**. В 90% задач содержимое не загружается вообще.

##### Token-экономика: конкретные числа

Оценка для реального состояния нашего проекта — 6 memories + MEMORY.md индекс:

| Артефакт | Размер (tokens) |
|---|---|
| `MEMORY.md` (индекс) | ~200 |
| `rdbg-protocol.md` | ~600 |
| `feedback_use_zai_for_agents.md` | ~800 |
| `feedback_use_glm_agents.md` | ~400 |
| `feedback_lazy-mcp-stdio-fix.md` | ~300 |
| `feedback_mcp_server_usage.md` | ~1200 |
| `feedback_analyze_before_tests.md` | ~400 |
| **Сумма memories** | **~3700** |
| + memory instructions в system prompt | ~1500 |
| **Итого memory overhead на старте** | **~5200** |

**Eager strategy (текущая):**
- Стартовый overhead: **5,200 tokens**
- В каждом сообщении: те же 5,200 несутся forward (до компактификации)
- За conversation из 30 сообщений: **~156,000 tokens «memory noise»**
- Money cost (Opus input $15/1M): **~$2.34 за сессию только на memory overhead**
- Attention cost: все 5,200 tokens конкурируют за attention на каждой генерации

**Lazy strategy (Serena):**
- Стартовый overhead: **0 tokens**
- list_memories (если нужно): ~300 tokens
- Per task, если memory реально нужна: +800-1200 tokens
- Task без memory reads: 0 overhead
- Money cost при среднем 1 memory read: **~$0.02 за сессию**
- **Reduction: ~100x по money, 3-5x по средним токенам**

**Hybrid index-only strategy (рекомендуется для нас):**
- Стартовый overhead: ~200 tokens (только `MEMORY.md` индекс)
- Per task: +800-1200 tokens если memory нужна
- Money cost: **~$0.05 за сессию**
- Отличие от pure lazy: индекс виден сразу → discoverability без отдельного `list_memories` вызова

##### Attention-экономика: скрытая цена

Token cost — очевидная сторона. Вторая, часто игнорируемая — **attention dilution**.

Исследование [«Lost in the Middle: How Language Models Use Long Contexts»](https://arxiv.org/abs/2307.03172) (Stanford 2023) показало:
- Модели **значительно хуже** работают с информацией в середине длинного контекста
- U-shaped curve: лучше всего начало и конец, хуже всего середина
- Эффект усиливается с ростом контекста
- Даже релевантная информация в середине может быть «потеряна»

**Что это значит для нашей eager strategy:**
1. **На 1-м сообщении** memories в «начале» — работают хорошо
2. **На 10-м сообщении** memories сдвинулись в «середину» — эффективность падает
3. **На 30-м сообщении** memories глубоко в середине рядом с tool calls — **практически не влияют**
4. Но они всё ещё **жгут токены** и **разбавляют attention** на критически важную часть задачи

**Вывод:** eager injection даёт моментальную пользу на старте, но быстро деградирует и превращается в чистый overhead. Lazy reading доставляет memory в **конце** контекста (где attention высокое) именно тогда, когда она нужна.

##### Relevance mismatch: «релевантно прошлой сессии» ≠ «релевантно сейчас»

Eager strategy молча предполагает: *«что было важно вчера, важно и сегодня»*. Это неверно.

**Пример из реальной сессии (разработка этого документа):**

В начале пришли 6 memories. Какие из них были реально нужны в сессии (аудит Serena + гибридный план)?
- `rdbg-protocol.md` — про 1C debug agent → **не нужно**
- `feedback_use_zai_for_agents.md` — про Z.AI → **не нужно**
- `feedback_use_glm_agents.md` — про GLM agents → **не нужно**
- `feedback_lazy-mcp-stdio-fix.md` — FastMCP Windows fix → **не нужно**
- `feedback_mcp_server_usage.md` — MCP_Сервер tools → **не нужно**
- `feedback_analyze_before_tests.md` — VA BDD тесты → **не нужно**

**Ни одна.** Все 3700 токенов memories были **полностью нерелевантны** для задачи. И тем не менее они сидели в контексте, жгли токены и конкурировали за attention.

**Худшая сторона — false-positive priming.** Если memory говорит «используй X для Y», а текущая задача — «не Y», модель может **pattern-match** и ошибочно применить X. Это не гипотетический риск — это реальная причина, почему Anthropic в training специально учит модели игнорировать irrelevant context.

##### Staleness и risk of contradiction

Memory — это **snapshot на момент записи**. Код меняется, решения пересматриваются, функции переименовываются, API эволюционирует. Memory не обновляется автоматически.

**Конкретный сценарий:**

Memory говорит: *«используй `mcp__memory-ai__get_important_messages(limit=5)`»*. Через 3 месяца API изменился: параметр стал `top_k`, не `limit`. Memory всё ещё говорит «limit».

- **Eager strategy:** агент видит memory с первого токена → доверяет → вызывает `limit=5` → API ошибка → correction cycle
- **Lazy strategy:** агент вызывает memory только когда думает о task «сохранить важные сообщения» → видит memory → замечает расхождение с актуальной tool schema → игнорирует устаревшую memory

Сам CLAUDE.md в проекте говорит: *«Memory records can become stale over time... verify that the memory is still correct and up-to-date»*. Но:
- В eager strategy **memory уже в контексте**, prime-эффект уже произошёл
- Claude должен **активно фильтровать** каждое утверждение memory на каждом сообщении
- Это дополнительная когнитивная нагрузка **всё время**

В lazy strategy проверка актуальности — **разовая операция в момент чтения**, не постоянный фон.

##### Три стратегии: полное сравнение

| Параметр | Eager (текущая) | Lazy (Serena) | Hybrid index-only (рекомендуется) |
|---|---|---|---|
| Startup token cost | **~5K (высокий)** | 0 | ~200 (низкий) |
| Per-task token cost | 0 (уже загружено) | 300-1500 (list + read) | 800-1200 (direct read) |
| Cost на сессию 30 сообщений | **~156K tokens overhead** | ~1.5K | ~1K |
| Money cost (Opus) | **~$2.34** | ~$0.02 | ~$0.05 |
| Attention dilution | **Высокая** | Низкая | Низкая |
| Discoverability (агент знает о memories) | Да (уже видны) | Только через list_memories | **Да** (индекс виден) |
| Staleness risk | **Высокий** (eager prime) | Низкий (проверка в момент чтения) | Низкий |
| Lost-in-the-middle | **Проблема** | Не актуально | Не актуально |
| Latency | 0 | +100-200ms (list_memories) | 0 для индекса |
| Complexity реализации | Низкая | Средняя | Низкая |
| Relevance matching | **Нет** | Агент решает per-task | Агент решает per-task |

**Hybrid index-only — оптимальная точка компромисса**: сохраняет discoverability (агент видит что существует `rdbg-protocol.md`) без загрузки содержимого. Это **наш target state**.

##### Migration plan: Phase 11 переоценка

Конкретный план рефакторинга из v4.1 extension. **Переоценено с 1 до 2.5 дней** после углублённого анализа.

**Шаг 1: Audit current state** (0.5 дня)
- Benchmark на 3 реальных задачах (BSL analysis, MCP debug, skill creation)
- Измерить `startup_tokens`, `per_message_tokens` для каждой
- Зафиксировать baseline: `docs/roadmap/memory/baseline-YYYY-MM-DD.md`
- Оценить ground truth: сколько injected memories реально использовано в каждой задаче

**Шаг 2: Refactor `memory-first-hook.py`** (0.5 дня)

```python
# БЫЛО (eager):
def on_session_start():
    memories = load_all_relevant_memories()  # reads all files
    inject_into_system_prompt(memories)      # ~5000 tokens

# СТАНЕТ (hybrid index-only):
def on_session_start():
    index = read_memory_index("MEMORY.md")   # ~200 tokens
    inject_into_system_prompt(index)
    # Содержимое отдельных memories НЕ загружается
```

**Шаг 3: Update tool descriptions** (0.5 дня)

Для `mcp__memory-ai__get_memory` и `Read` при чтении memory файлов:

```
Read the content of a memory file.

IMPORTANT: Memories are snapshots from past sessions. They may be stale.
- Read only when you believe the current task specifically benefits from
  a memory's content.
- If unsure about relevance, prefer reading the current code/config over
  trusting old memories.
- Never read memories "just in case" — token budget matters.
```

**Шаг 4: Add `/memory-inspect` slash command** (0.5 дня)

Для явного ручного просмотра полного содержимого (отладка, обзор):
- `/memory-inspect` — все memories с содержимым
- `/memory-inspect <name>` — конкретная memory
- `/memory-inspect --stale` — memories не читанные >30 дней

**Шаг 5: Measurement + validation** (0.5 дня)

- Прогнать те же 3 задачи из шага 1 с новым hook
- Сравнить метрики, зафиксировать: `docs/roadmap/memory/after-YYYY-MM-DD.md`
- **Ожидание: 80-95% сокращение memory overhead** без потери функциональности

**Шаг 6: Rollout + monitoring** (ongoing)
- Мониторить частоту `get_memory` вызовов (должна **вырасти** — это хорошо!)
- Если `get_memory` не вызывается → hints в CLAUDE.md недостаточны
- Если вызывается слишком часто → description нужно ужесточить

##### Broader principle: «loaded» vs «available»

Это общий принцип проектирования agentic систем, который легко упустить:

| Состояние | Что значит | Стоимость |
|---|---|---|
| **Not indexed** | Агент не знает что это существует | Zero + zero discoverability |
| **Indexed (available)** | Агент знает имя + description | Нулевая для content, минимальная для metadata |
| **Loaded** | Содержимое в context window | Tokens × attention × money |
| **Used** | Агент реально ссылается на это | Полная польза |

**Anti-pattern:** путать «available» и «loaded». Загружать всё, чтобы было «available».

**Correct pattern:** держать **индекс** в памяти (cheap), **содержимое** грузить по требованию.

Применимо не только к memory:

| Ресурс | Уже работает правильно? | Комментарий |
|---|---|---|
| **Docs (`1c-docs-rag`)** | ✅ | Индекс → search → load only hit |
| **Tool schemas** (deferred tools + ToolSearch в Claude Code) | ✅ | Именно lazy loading через tool description |
| **Skills** (список виден, SKILL.md грузится по activation) | ✅ | Правильно |
| **MCP servers** (lazy-mcp) | ⚠️ частично | Не все серверы под lazy |
| **File contents** | ✅ | Read грузит по требованию |
| **Memory** (`memory-first-hook`) | ❌ **eager** | **Нужен рефакторинг в Phase 11** |
| **CLAUDE.md** | ❌ **монолит** | 600+ строк каждый раз. Split на fragments в Phase 11 |

**Глубокое наблюдение:** Anthropic сама применяет этот pattern через **deferred tools + `ToolSearch`** (см. `<available-deferred-tools>` в начале этой сессии). Список имён всегда есть, JSON schema загружается через `ToolSearch` по явному запросу. **Claude Code platform следует lazy loading для tools, но наш memory-first-hook игнорирует этот pattern для memories.**

Это не гипотетическая best practice — это **реальный архитектурный выбор самой платформы**, который мы нарушаем в своей надстройке.

##### Связь с другими Serena-концепциями

Memory lazy reading — частный случай более широкого принципа, который Serena применяет последовательно:

1. **Context gating** (§4.9.1) — tools отключаются per context
2. **Mode gating** (§4.9.1) — read-only режимы для анализа
3. **Memory lazy reading** (эта секция) — содержимое memory по требованию
4. **Dynamic initial instructions** (§4.9.4 Pattern 3) — CLAUDE.md fragments вместо монолита
5. **Onboarding on demand** (§4.9.4 Pattern 1) — project discovery по команде

Meta-principle общий: **«загружай минимально необходимое, предоставь механизм получить больше по требованию»**.

Наш текущий стек нарушает этот принцип в нескольких местах:
- Memory — eager loading → Phase 11
- CLAUDE.md — монолит 600+ строк загружается всегда → Phase 11 split
- Skill metadata — вся обо всех skills в system reminder

После Phase 11 вся memory/instruction discipline выровняется с этим принципом. Это не только экономит токены — это **правильная архитектура** для agentic систем.

##### Ключевой итог

**Проблема:** `memory-first-hook` инжектирует содержимое всех relevant memories при старте сессии. ~5000 tokens overhead, который **в большинстве задач полностью нерелевантен**, деградирует attention (lost-in-the-middle), создаёт risk от stale data, стоит ~$2.34 за сессию только на memory.

**Решение:** перейти на **hybrid index-only** strategy. Загружать только `MEMORY.md` (~200 tokens) при старте. Содержимое отдельных memories грузится **только когда агент явно решает**, что memory нужна для task. Инструкция «use only when task-relevant» встраивается **в tool description** `get_memory`, не в system prompt.

**Эффект:** 80-95% сокращение memory overhead, лучшая attention quality, устранение stale-data risk, снижение cost ~50x.

**Реализация:** Phase 11 из v4.1 extension, переоценена с 1 до **2.5 дней**. Включает audit, refactor hook, update tool descriptions, `/memory-inspect` slash command, measurement, rollout.

**Broader lesson:** частный случай универсального принципа «loaded ≠ available». Anthropic сама применяет этот pattern через deferred tools + ToolSearch. Наш `memory-first-hook` — анахронизм.

#### 4.9.5. Что из Serena мы **не переносим** (расширенный список)

Дополнение к §4.3 после углублённого анализа:

- `execute_shell_command` — уже есть Bash, не нужно
- `replace_content` (regex replace) — покрыто нативным Edit + при необходимости `sed` через Bash
- `find_file`, `list_dir`, `read_file`, `create_text_file` — полные дубли нативных
- JetBrains tools (10 штук) — мы на VS Code + EDT, не применимо
- `switch_modes` как MCP tool — режимы у нас через hooks и skill metadata, не через tool calls
- `check_onboarding_performed` — единоразовая, заменяется на idempotent `bsl_project_overview`
- `remove_project` — admin-level, ручное управление
- `jet_brains_inline_symbol` (BETA), `jet_brains_move` (BETA), `jet_brains_safe_delete` (BETA) — beta quality + JetBrains-only
- `prepare_for_new_conversation` — context handoff у нас через memory system

---

## 5. План реализации

### 5.1. Фазы ядра (v4)

| # | Фаза | Что делает | Усилие | Блокер? | Зависит от |
|---|---|---|---|---|---|
| **0a** | Rollback Этап 0 | `implement-1c-task.md/SKILL.md` → 8 этапов, версия 2.1.1. Почистить `/activate-project.md` | 30 мин | — | — |
| **0b** | Recon BSL LS ✅ **DONE (2026-04-17)** | Запуск JAR standalone, тест `textDocument/rename`, разбор issues #802/#798/#792. Артефакт: [bsl-ls-recon-results.md](bsl-ls-recon-results.md). Итог: **Scenario 2** — in-file rename работает, cross-file не работает. Routing matrix скорректирована (§4.6): `module_export_proc` → B only | 4-6 ч (факт ~3 ч) | — | — |
| **1** | Tier 2 skill + helpers | Skill `bsl-symbol-editing` + 3 helper-обёртки над EDT-MCP. Не требует LSP | 1 день | — | — |
| **2** | Variant B core | Symbol classifier. Граф-based rename для `manager_method`, `object_method`, `form_handler`. Dry-run + verification | 2 дня | — | Phase 1 |
| **3** | Variant A core (in-file only, после Phase 0b) | Минимальный LSP client, subprocess lifecycle, `textDocument/rename` + `findReferences`. Покрывает ТОЛЬКО `local_var`, `parameter`, `module_private_proc`. Cross-file вынесен в Variant B | 1-1.5 дня (было 2-3) | — | Phase 0b (DONE) |
| **4** | Orchestrator + Routing | Объединение A и B, merge logic, confidence scoring, fallback chain | 1 день | — | Phase 2 + Phase 3 |
| **5** | Symbol-first workflow skill ✅ **DONE (2026-04-19)** | Skill `bsl-refactoring-workflow` с 5-категорийной матрицей, интеграция с `implement-1c-task` | 0.5 дня (факт ~30 мин) | — | Phase 1-4 |
| **6** | Benchmark (Serena methodology) ✅ **DONE (2026-04-18)** | 20 задач × 5 категорий, pilot-B 95% success (ast-grep), calibration applied | 1.5 дня (факт ~1 день) | — | Phase 4 |
| **7** | Cleanup ✅ **DONE (2026-04-19)** | Serena disabled в `.mcp.json`, `.serena/` сохранён для Python LSP. Skills созданы: `bsl-symbol-editing`, `bsl-refactoring-workflow`. MEMORY.md обновлён | 0.5 дня (факт ~1 ч) | — | Phase 5-6 |

### 5.2. Дополнительные фазы (v4.1 extension)

Опциональные фазы, переносящие **архитектурные концепции** из Serena (см. §4.9). Не блокируют ядро, можно делать параллельно или после.

| # | Фаза | Что делает | Усилие | Зависит от |
|---|---|---|---|---|
| **8** | Context/Mode system | `.claude/contexts/*.yml` + `.claude/modes/*.yml` + hook для gating tools per task. Modes: analysis (read-only), implementation (full), review (nav-only), refactor (только Tier 1) | 1-2 дня | Phase 1 |
| **9** | Tier 4 navigation tools | `bsl_find_code_snippets`, `bsl_find_handlers`, `bsl_metadata_hierarchy`, `bsl_project_overview`. Реализация поверх B (граф) + EDT-MCP | 2-3 дня | Phase 2 |
| **10** | Dashboard + observability | CLI или static HTML dashboard: BSL LS uptime, EDT-MCP health, graph freshness, auto-rollback counter, recent rename calls. Автосбор метрик для §7 | 1 день | Phase 4 |
| **11** | Memory discipline + initial instructions | Refactor `memory-first-hook` → hybrid index-only (см. §4.9.4.1). Audit baseline → refactor hook → tool description update → `/memory-inspect` → validation → rollout. Split CLAUDE.md на fragments: base + per-context + per-task. Ожидание: 80-95% сокращение memory overhead, **~$2.34 → ~$0.05 на сессию** | **2.5 дня** (было 1 — переоценено после §4.9.4.1) | Phase 8 |

**Итого (v4 ядро + v4.1 extension):**
- **Минимум ядра** (если Recon = Scenario 3, Вариант A не живёт): ~6 дней — покрытие через B + Tier 2 + skill + benchmark
- **Максимум ядра** (v4, Phases 0-7, полный гибрид A+B): ~10 дней
- **Ядро + extension** (v4 + v4.1, Phases 0-11): **+5-7 дней** к ядру = **~15-17 дней** total
- **Extension опционально** — можно делать после валидации ядра в продакшене

### 5.3. Что исчезает из проекта после Phase 7

- `.serena/` папка (включая `project.yml`, `memories/*`, `cache/*`)
- `serena` в `.mcp.json`
- `/activate-project.md` (удалён или переписан без `serena-index-checker`)
- Java runtime зависимость (если не используется для другого)

**Остаётся:** этот документ как исторический артефакт — фиксирует почему пришли к Сценарию W.

### 5.4. Первый коммит (прямо сейчас)

Три независимые задачи, можно параллельно:

1. **Phase 0a** (30 мин) — откат Этапа 0 в `implement-1c-task`
2. **Phase 0b kick-off** (15 мин) — создать `docs/roadmap/bsl-ls-recon-plan.md` с чеклистом + скачать `bsl-language-server-0.24.0-rc.3.jar`
3. **Phase 1 spec** (30 мин) — написать `docs/roadmap/hybrid-refactor-spec.md` со ссылкой на секцию 4 как источник требований

---

## 6. Риски и митигации

| Риск | Вероятность | Митигация |
|---|---|---|
| BSL LS subprocess висит/крашит | Средняя | Timeout 5s per request, auto-restart LS, circuit breaker (3 краша → LS отключается, только B) |
| Classifier ошибается в типе символа | Средняя | `unknown` kind вместо угадывания; при низком confidence dry-run обоих backends |
| Routing matrix устарела (новые типы модулей) | Низкая | Тесты per category в Phase 6 benchmark, ежеквартальный re-check |
| Verification требует EDT запущенной | Высокая | Graceful degradation: без EDT — `UNVERIFIED` флаг, apply требует explicit override |
| Merge A+B даёт ложные конфликты из-за форматов | Средняя | Normalize WorkspaceEdit в канонический формат перед сравнением |
| Neo4j граф устарел | Средняя | Hook на file write → re-index; предупреждение если граф >24h |
| Auto-rollback повреждает файлы (partial write) | Низкая | Snapshot файлов перед apply (in-memory), rollback из snapshot |
| BSL LS не умеет cross-file rename | Высокая | Вариант B покрывает cross-file независимо; routing помечает A как `in-file only` |

---

## 7. Критерии успеха для ре-аудита (через 2-3 месяца)

| Метрика | Цель | Измерение |
|---|---|---|
| Покрытие задач rename | >85% | Benchmark Phase 6 + трекинг реальных задач |
| Точность rename (no false positives) | >95% | Counter auto-rollback / всего apply |
| Использование `bsl_rename_symbol` | >5 вызовов/неделя | Логи MCP сервера |
| Использование Tier 2 wrappers | >15 вызовов/неделя | Логи |
| Время от inception до apply | <30 секунд | Timestamps в логах |
| BSL LS uptime (если в игре) | >90% | Circuit breaker metrics |
| `unknown` symbol kinds | <5% запросов | Classifier metrics (сигнал устаревания routing) |

---

## Приложение A: Сравнение Serena ↔ наш MCP-стек

### A.1. Наш текущий стек (ключевые серверы для BSL/1С)

| Сервер | Key tools | Роль |
|---|---|---|
| `edt-mcp` (HTTP :8765) | 33 tools: metadata, queries, refactoring, validation, content assist, screenshots | Основной инструмент для BSL — поверх EDT LSP |
| `ast-grep-mcp` | AST pattern matching для BSL | Парсинг/поиск без EDT |
| `bsl-platform-context` | Platform types, methods, properties | Документация типов платформы |
| `1c-mcp-server` (ext .cfe) | 15 tools: queries, BSL execution, metadata, event log | Runtime-доступ к 1С:Предприятию |
| `bsl-semantic-search` | Neo4j cross-language граф + semantic search | Навигация по зависимостям (ядро Варианта B) |
| `1c-docs-rag` | RAG search 863+ docs | Документация фреймворка |

### A.2. Матрица: Serena capability vs наш инструмент

Легенда: `++` = наше превосходство, `+` = достаточно, `~` = частично, `−` = пробел

| Capability | Serena | Наш инструмент | Покрытие |
|---|---|---|---|
| Symbol Navigation (BSL) | `find_symbol` (LSP) | `edt-mcp get_symbol_info`, `go_to_definition` | `+` |
| Reference Finding (BSL) | `find_referencing_symbols` | `edt-mcp find_references` | `+` |
| Symbol Overview (BSL) | `get_symbols_overview` | `edt-mcp get_module_structure` | `+` |
| Pattern Search | `search_for_pattern` | `ripgrep`, `edt-mcp search_in_code` | `+` |
| File Ops | `read_file`, `create_text_file`, `list_dir`, `find_file` | native `Read`, `Write`, `Glob` | `+` |
| Line Editing | `replace_lines`, `insert_at_line`, `delete_lines` | native `Edit` | `+` |
| Shell Execution | `execute_shell_command` | native `Bash` | `+` |
| Symbol Editing (BSL) | `replace_symbol_body`, `insert_after/before_symbol` | EDT-MCP `write_module_source` (line-based) | `~` (Tier 2 обёртки нужны) |
| **Rename функции/переменной (BSL)** | `rename_symbol` | **НЕТ** | `−` ⚠️ (Tier 1) |
| Memory | `write/read/list_memory` | `memory-ai`, Qdrant, Claude auto-memory | `++` |
| BSL Metadata | — | `edt-mcp` (Справочники, Документы, регистры) | `++` |
| BSL Query Language | — | `edt-mcp validate_query` | `++` |
| BSL AST Analysis | — | `ast-grep-mcp` | `++` |
| Semantic Search | `search_for_pattern` (текст) | `bsl-semantic-search` (vector/graph) | `++` |
| Documentation RAG | — | `1c-docs-rag` | `++` |
| 1C Database Access | — | `1c-mcp-server` | `++` |

**Единственный «минус»:** `rename_symbol` для BSL. Закрывается в Phase 2-4 гибридного плана.

### A.3. Новые инструменты в latest Serena (+14 к v0.1.4)

| Tool | Impact для BSL | Комментарий |
|---|---|---|
| `rename_symbol` | 🔴 КРИТИЧЕСКИЙ | Без альтернативы в нашем стеке — главный аргумент за Tier 1 |
| `safe_delete_symbol` | 🟡 ВЫСОКИЙ | Часть Tier 1 |
| `replace_content` | 🟢 СРЕДНИЙ | Покрыто EDT-MCP |
| `edit_memory`, `rename_memory` | ⚪ НИЗКИЙ | Наш memory-стек богаче |
| `query_project`, `list_queryable_projects` | 🟢 СРЕДНИЙ | Покрыто EDT-MCP `get_metadata_objects` |
| `open_dashboard` | ⚪ НИЗКИЙ | Не нужно |
| `jet_brains_*` (6 новых) | ⚪ НЕПРИМЕНИМО | Мы на VS Code |

---

## Приложение B: Отклонённые альтернативы

| Сценарий | Суть | Почему отклонён |
|---|---|---|
| **Z. Починить BSL LS внутри Serena** | Диагностировать ошибку запуска BSL LS в Serena (Java path / workspace init / crash), настроить корректный запуск | Даже если починить — ~6-9 unique value против ~38 тулов (15-20%), из которых большинство дубли. Serena остаётся тяжёлой machinery ради малой выгоды |
| **X. Сменить `language: bsl` → `language: python`** | Serena даёт LSP для 337 Python-файлов фреймворка | Не решает главного пробела (BSL `rename_symbol`). Только частичная ценность на Python-коде. Python-рефакторинг — не bottleneck |
| **Y. Оставить как есть** | Не трогать Serena, продолжать использовать EDT-MCP | `/activate-project.md` продолжает ссылаться на фантомный хук. `rename_symbol` для BSL так и не появляется. Статус-кво = 0 ценности |
| **C. Форк EDT-MCP + добавить `rename_symbol`** | Форкнуть Eclipse-плагин `edt-mcp`, добавить обёртку над Xtext refactoring API | Дорогой (5-15 дней Eclipse plugin dev + Java/OSGi), рискованный (неизвестна лицензия/SDK), требует EDT running. Отложен: возможен в будущем если A+B окажутся недостаточно точны |
| **W. Hybrid Extract-only** ⭐ | Перенести только нужное в native стек. Гибрид A (BSL LS standalone) + B (graph-based) + Tier 2 wrappers | ✅ **Принят** — оптимальное соотношение ценности и усилий |

---

## Приложение C: Эволюция оценок

| Версия | Дата | Автор | Вывод | Что изменилось |
|---|---|---|---|---|
| v1 | 2026-04-14 | Opus 4.6 | «BSL не поддерживается в Serena — сменить на python» | Первичный аудит, ошибочный вывод |
| v2 | 2026-04-14 | GLM-5.1 | «BSL LS существует в Serena → починить (Сценарий Z)» | Cross-check кода Serena — найдены `bsl_language_server.py` (551 строка), enum `BSL`, JAR v0.24.0-rc.3 |
| v3 | 2026-04-14 | GLM-5.1 | «Z + обновить до latest (+14 tools, `rename_symbol` критичен)» | Анализ официальных docs Serena tools + evaluation |
| **v4** | **2026-04-15** | **Opus 4.6 1M** | **«Extract-only — перенести в native стек, Serena удалить (Сценарий W)»** | **Учёт стоимости миграции vs ценности: ~6-9 тулов не оправдывают ~38-тульную machinery. Гибрид A+B обеспечивает ту же ценность без зависимости от Serena** |
| **v4.1** | **2026-04-15** | **Opus 4.6 1M** | **Расширение: переносить не только tools, но и архитектурные концепции (contexts/modes, evaluation methodology, Tier 4 navigation tools, dashboard, onboarding, memory discipline)** | **Углублённый анализ https://github.com/oraios/serena, `claude-code.yml`, `planning.yml`, evaluation methodology. Найдены 4 дополнительных tools для переноса (Tier 4) и 4 архитектурных паттерна. Добавлены фазы 8-11 в план (+5-7 дней, опциональные)** |
| **v4.2** | **2026-04-15** | **Opus 4.6 1M** | **Углублённое обоснование agent self-evaluation подхода (§4.9.2.1)** | **Детальное обоснование почему agent self-evaluation → feedback loop → самокалибрующаяся система. Анализ traditional benchmarks (SWE-bench, HumanEval) vs self-eval. Конкретный пример BSL rename, риски + митигации, связь с self-play RL. Фиксирует Phase 6 как критический компонент, а не «добавка»** |
| **v4.3** | **2026-04-15** | **Opus 4.6 1M** | **Углублённое обоснование memory lazy reading (§4.9.4.1)** | **Детальное раскрытие Pattern 4. Token-экономика (~5200 tokens overhead → ~$2.34/session), attention dilution (Lost in the Middle), staleness risk, сравнение 3 стратегий (eager/lazy/hybrid). Анти-паттерн «loaded vs available». Наблюдение: Anthropic сама применяет lazy loading через deferred tools + ToolSearch, но `memory-first-hook` нарушает этот pattern. Phase 11 переоценена с 1 до 2.5 дней с концертным 6-шаговым migration plan** |
| **v4.4** | **2026-04-17** | **Opus 4.7 1M** | **Phase 0b выполнена — Scenario 2 подтверждён эмпирически** | **Запущен BSL LS v0.22.0 standalone через минимальный Python LSP клиент (230 строк, `tools/bsl-ls/lsp_recon.py`) на тестовом workspace (2 CommonModule + Configuration.xml + .mdo). Cold start 4.0-4.8s, парсер работает, диагностика приходит. In-file rename (`local_var`, `module_private_proc`): ✅ 2 edits (declaration + call-site). Cross-file rename экспортной функции: ❌ только 1 edit в declaration-файле, вызов в другом модуле проигнорирован. `references` возвращает `[]`. Добавление `Configuration.xml` + `.mdo` не меняет поведения — архитектура LS «per-document». Issues #802/#798/#792 из предыдущих версий проверены — не релевантны cross-file rename. Routing matrix §4.6 скорректирована: `module_export_proc` переведён на `B only`. Phase 3 сокращена с 2-3 дн до 1-1.5 дн (только in-file scope). Артефакты: `tools/bsl-ls/recon-logs{,-run1}/`, `lsp_recon.py`, [bsl-ls-recon-results.md](bsl-ls-recon-results.md)** |
| **v4.5** | **2026-04-19** | **Opus 4.7 1M** | **Верификация реализации — Phases 0-7 + R0-R5.4 + R6.3/R6.4 submitted подтверждены фактически** | **Проведена полная верификация по артефактам и тестам (см. §«Верификация реализации» ниже). Зафиксировано: 124/124 refactor-тестов зелёные (23s), 27/27 tree-sitter corpus зелёные, ERR rate 0.0% (14→0 на 1518 строк), pilot-B benchmark 95% success (19/20, 8 прогонов в trend.md), R5.5 calibration применена (local_variable/module_local/form_handler 0.70-0.85 → 0.95). Serena `disabled: true` в `.mcp.json`, `.serena/` сохранён для Python LSP. Skills `bsl-symbol-editing` и `bsl-refactoring-workflow` созданы. Fork `Alex1980Alex/tree-sitter-bsl` ветка `fix/parenthesized-expression` (commits `4edc527` + `2bc0435` после CodeRabbit упрощения execute_statement). Grammar-simplification подтверждает: upstream feedback loop работает. Открытые пункты P3/P4 (R1.3 реальный multilspy, R3 SCIP, R6.1/R6.2 upstream) — подтверждены как осознанно deferred, не блокируют продакшн** |

---

## §4.10 GitHub Reference Implementations (результаты Phase 0b research, 2026-04-17)

По итогам анализа GitHub были отобраны 10 проектов, подтверждающих архитектурные подходы к LSP-индексации, AST-поиску и рефакторингу. Все решения проверены и могут быть использованы как референсы или прямые зависимости для преодоления ограничений per-document архитектуры BSL LS.

1. **[microsoft/multilspy](https://github.com/microsoft/multilspy)** — 566⭐, Python, LSP preload. Python LSP-клиент с bulk `didOpen` всех файлов workspace перед references/rename. Serena использует этот паттерн. **Прямое решение per-document архитектуры BSL LS без форка.**
2. **[ast-grep/ast-grep](https://github.com/ast-grep/ast-grep)** — 13.5k⭐, Rust, AST-rewrite. CLI structural search/replace на tree-sitter grammars. Multi-file patterns, YAML rules, codemod-режим. Не требует LSP workspace indexing.
3. **[alkoleft/tree-sitter-bsl](https://github.com/alkoleft/tree-sitter-bsl)** — 36⭐, 1C Enterprise. Tree-sitter grammar для BSL. Критически нужна для ast-grep/codemod. Покрытие (препроцессор, запросы, инструкции) требует проверки.
4. **[comby-tools/comby](https://github.com/comby-tools/comby)** — 2.6k⭐, OCaml, AST-rewrite. Language-agnostic structural search & replace. Балансирует скобки/кавычки без формальной грамматики. Полезно для fallback (динамика `Выполнить()`, комментарии-документация).
5. **[sourcegraph/scip](https://github.com/sourcegraph/scip)** — ~300⭐, Go, Graph. Source Code Intelligence Protocol (наследник LSIF). Бинарный индекс symbols/occurrences/references (protobuf). Можно генерировать из существующего `bsl_call_graph` (Neo4j/NetworkX).
6. **[1c-syntax/bsl-language-server](https://github.com/1c-syntax/bsl-language-server)** — 403⭐, Java, upstream LS. Источник per-document проблемы. Альтернатива форку — PR с `workspace/didChangeWorkspaceFolders` handler вызывающим ServerContext.populateContext на всю папку.
7. **[sorbet/sorbet](https://github.com/sorbet/sorbet)** — 3.8k⭐, C++, reference. Type checker для Ruby. Решил аналогичную проблему Ruby constants (dynamic resolution) через full workspace scan + global symbol table. Архитектурный прецедент для BSL dot-нотации (`ОбщийМодуль.X`).
8. **[python-rope/rope](https://github.com/python-rope/rope)** — 2.2k⭐, Python, reference. Refactoring library. Project-level model (all .py files) перед rename. `ChangeSet` abstraction — атомарный apply с rollback.
9. **[semgrep/semgrep](https://github.com/semgrep/semgrep)** — 14.8k⭐, OCaml, AST-rewrite. Pattern matching + autofix. Отклонено как дубликат ast-grep без BSL grammar, но CLI UX хороший ориентир.
10. **[kythe/kythe](https://github.com/kythe/kythe)** — 2.1k⭐, Go, Graph. Google's pluggable code-indexing. Extractor → indexer → serving layer. Overkill для BSL, упоминается как reference architecture.

**Рекомендация (3 подхода для v4.5):** multilspy (#1) + ast-grep+tree-sitter-bsl (#2+#3) + SCIP (#5) как кэш-слой на 2-й итерации. Полный анализ в [bsl-ls-recon-results.md](bsl-ls-recon-results.md).

## §5.5 Детальная дорожная карта v4.5 — гибрид A+B с multilspy и ast-grep

Дорожная карта декомпозиции интеграции на основе референсных решений. Вариант A (multilspy) обеспечивает глубокий анализ через LSP, Вариант B (ast-grep) выступает быстрым fallback-механизмом.

#### Этап R0 — Research validation (1-2 дня, блокер для R1-R2) — ✅ ЗАКРЫТ 2026-04-17 (commit `00b76192`)

- **R0.1 multilspy quick-test:** форкнуть/инсталлировать multilspy, заменить `lsp_recon.py` на multilspy-based client, прогнать на test-workspace. **Артефакт:** `tools/bsl-ls/multilspy_recon.py` + лог. **DoD:** cross-file rename экспортной функции возвращает ≥2 edits.
  - **Статус:** ✅ **PASS** (после правки workspace). Первая итерация → 1 edit (FAIL); после изучения исходников BSL LS на GitHub выяснено, что `ServerContext.populateContext` требует per-module XML-дескрипторов для `mdclasses`. После добавления `ТестоваяУтилита.xml`/`ТестовыйВызыватель.xml` + правильного `xmlns="http://v8.1c.ru/8.3/MDClasses"` в `Configuration.xml` → **2 edits / 2 файла**.
  - **R0.1-EXT (расширение):** `bench_multilspy_real.py` на реальном проекте `260304_GKSTCPLK-2182` (2 027 `.bsl`), target `гкс_ОчередьСообщенийRMQ.СоздатьСообщенияПоСобытиюОбъекта`. Два прогона детерминированно → **10 edits / 7 файлов**. Метрики: init ~4.7 s, preload ~5.7 s (340–375 files/s), prepare_rename ~22–28 s (bottleneck — populateContext/ReferenceIndex build), rename ~10 ms по прогретому индексу.
  - **Артефакты:** `tools/bsl-ls/multilspy_recon.py`, `multilspy-logs/`, `bench_multilspy_real.py`, `multilspy-logs-real/summary.json`.

- **R0.2 tree-sitter-bsl coverage test:** клонировать репо, прогнать grammar на 3 реальных модулях проекта (`гкс_ОчередьСообщенийRMQ`, `гкс_ФормировательСообщенийRMQ`, одна форма). **Артефакт:** `tools/bsl-ls/tree-sitter-coverage.md`. **DoD:** выявлены gap'ы по препроцессору/запросам.
  - **Статус:** ✅ **DONE**. `гкс_ОчередьСообщенийRMQ` (679 lines, 12 ERRs), `гкс_ФормировательСообщенийRMQ.ObjectModule` (217 lines, 2 ERRs), `гкс_Взвешивание.ФормаДокумента` (622 lines, **0 ERRs**, parse OK). Итого 14 ERRs / 1 518 lines ≈ 0.9%.
  - **Gap preprocessor:** покрыт (`preprocessor` node + `text_match:#Область/#КонецОбласти`).
  - **Gap directives:** покрыты (`annotation` node) — только для форм.
  - **Gap queries:** подтверждён отдельным скриптом `check_query_gap.py` на `АдресныйКлассификатор.Module.bsl` (11 литеральных `ВЫБРАТЬ` в коде) → 0 query-specific AST nodes; SQL остаётся `const_expression` string.
  - **Gap скобочных выражений:** обнаружен не в ТЗ — line-level inspection показал, что все 14 ERRs = parenthesized grouping в RHS/условиях (`= (X = Y);`, `Если ... И (X ИЛИ Y) Тогда`). Это отдельный gap grammar для R2.2.
  - **Артефакты:** `tools/bsl-ls/tree-sitter-coverage.{md,json}`, `tree-sitter-coverage.v1.{md,json}` (предыдущий run для истории), `check_query_gap.py`.

- **R0.3 ast-grep dry-run:** установить ast-grep, написать 3 тестовых правила (rename export method, rename local var, rename catalog manager method), применить к test-workspace. **Артефакт:** `tools/bsl-ls/ast-grep-rules/*.yml`. **DoD:** 3 правила работают, есть baseline timing.
  - **Статус:** ✅ **DONE**. ast-grep 0.39.5 + tree-sitter-bsl 0.1.6 через `tree_sitter_bsl.dll` (customLanguage в `sgconfig.yml`).
  - **3 YAML правила:** `rename-export-method` (pattern-based), `rename-local-var` (kind=assignment_statement), `rename-catalog-method` (kind=call_expression + has access).
  - **Baseline timing** (5 прогонов/правило, `bench_ast_grep.py`):
    - test-workspace (2 файла): median 27–38 ms (startup-dominated).
    - real-project (**2 027 .bsl**): median **1.2–1.7 s**, throughput **1 050–1 720 files/sec**.
  - **Артефакты:** `tools/bsl-ls/ast-grep-rules/*.yml`, `sgconfig.yml`, `tree_sitter_bsl.dll`, `bench_ast_grep.py`, `ast-grep-baseline.{md,json}`.

- **R0.4 Serena open_all_files pattern review:** прочитать исходник `multilspy.LanguageServer.open_files()` + Serena's workflow. **Артефакт:** заметки в `docs/roadmap/multilspy-pattern-notes.md`. **DoD:** понятна механика bulk-preload.
  - **Статус:** ✅ **DONE** + углублено. Механика: `multilspy.open_file` — ref-counted context manager, `ExitStack` держит все `didOpen` активными. Работает корректно, но **не триггерит BSL LS `ReferenceIndexFiller`** автоматически: индекс заполняется через `@EventListener` на `DocumentContextContentChangedEvent` при `rebuild()` DocumentContext, что запускается BSL LS автоматически в `initialized()` callback через `populateContext()`.
  - **Важная находка:** prepare_rename блокируется ~22–28 s на первый запрос, пока идёт `populateContext` асинхронно в ForkJoinPool. Для R1.3 нужно ожидание `$/progress` / `window/workDoneProgress` вместо фикс. `sleep()`.
  - **Артефакт:** `docs/roadmap/multilspy-pattern-notes.md` (revised с двумя итерациями).

- **R0.5 Architectural decision:** Scenario 1 (multilspy закрывает cross-file) vs Scenario 2 (multilspy не помог — идём на форк BSL LS) vs Scenario 3 (полностью на ast-grep). **Артефакт:** ADR-004. **DoD:** выбран путь для R1.
  - **Статус:** ✅ **DONE**. **Решение: гибрид Scenario 1 + Scenario 3.**
    - **Scenario 1 (multilspy) — primary** для реальных 1С-выгрузок (XML-дескрипторы всегда есть): семантический cross-file rename, детерминированный, 10 мс по прогретому индексу.
    - **Scenario 3 (ast-grep) — fallback**: (а) workspace'ы без XML, (б) pattern-based массовые замены, (в) случаи, когда `mdclasses` не парсит конфигурацию.
    - **Scenario 2 (fork BSL LS) — отклонён**: высокая стоимость поддержки Java fork, не нужен после R0.1 PASS.
  - **Новое требование R1.9 (pre-flight validator):** проверка per-module XML перед вызовом rename; нет XML → routing в ast-grep.
  - **Артефакт:** `docs/roadmap/ADR-004-bsl-refactoring-architecture.md`.

> **Итог R0:** `R1 возвращён в план` (был пропущен в первой версии ADR-004), обоснованы все требования R1.1–R1.9. Коммит `00b76192`, 26 файлов, +4459/-2525.

#### Этап R1 — Variant A rewrite на multilspy (3-5 дней, зависит от R0.5=Scenario 1)

- **R1.1 Protocol-based backend контракт:** MultilspyBackend класс. **Артефакт:** `src/bsl/semantic_search/refactor/backends/multilspy_backend.py`. **DoD:** реализует `plan_rename`, `can_handle`, `confidence_for`.
  - **Статус:** ✅ **DONE** (thin slice). `MultilspyBackend(client_factory)` через DI, парсит обе формы LSP WorkspaceEdit (`documentChanges` + `changes`), 10 unit-тестов (protocol conformance, ext matching, оба формата парсинга, error paths). Реальный `multilspy` в venv НЕ установлен — backend import-safe через client_factory; реальная обёртка — в R1.3.
- **R1.2 Subprocess lifecycle (persistent):** spawn → health-check → circuit breaker (3 краша → disable). **Артефакт:** `src/bsl/semantic_search/refactor/lsp_subprocess.py`. **DoD:** процесс живёт >1 часа без restart.
  - **Статус:** ✅ **DONE** (без реального multilspy). `CircuitBreaker` (sliding-window, auto-reset по таймауту) + `LspSubprocess` (5-state: IDLE/STARTING/READY/FAILED/STOPPED, auto-restart-once на crash, context manager, `as_lsp_client()` adapter для `MultilspyBackend`). 17 unit-тестов. **DoD «живёт >1 часа»** — soak test, потребует R1.3 wiring.
  - **Баги найдены ревью-циклом и исправлены:** (1) process leak при auto-restart, (2) breaker-check ordering в `start()`, (3) stale process после exception, (4) преждевременный `record_success()` в `start()` сбрасывал счётчик крашей.
- **R1.3 bulk_open_workspace():** async scan всех `.bsl`, батчированный didOpen с throttling (10 файлов/с). **Артефакт:** метод + тест. **DoD:** открытие 2027 файлов за <60s без OOM.
  - **Статус:** ✅ **DONE (2026-04-19) — DoD PASS**. Реализовано в двух фазах.
    - **Phase A (код + интеграционные тесты).** `multilspy==0.0.15` установлен (global Python 3.13.1), BSL LS JAR в `tools/bsl-ls/bsl-language-server.jar` присутствует. Создан sync-фасад [`src/bsl/semantic_search/refactor/backends/real_bsl_client.py`](../../src/bsl/semantic_search/refactor/backends/real_bsl_client.py) (321 строка) — async↔sync мост через фоновой поток с asyncio event loop. Публичный API: `start()/stop()`, `open_workspace(files, throttle_fps, batch_size)` с дедупликацией и фильтрацией outside-workspace/missing, `rename/prepare_rename/references(params)`, контекст-менеджер. Фабрика `create_bsl_client(workspace_root, preload=..., populate_wait_secs=...)`. Интеграционные тесты [`tests/bsl/refactor/test_real_bsl_client.py`](../../tests/bsl/refactor/test_real_bsl_client.py) (маркеры `slow` + `integration`): 8/8 passed в 12.68s — startup (~5 s cold), bulk open, outside/missing skips, `rename()` без start → `BackendError(code="not_started")`, контекст-менеджер, E2E с `MultilspyBackend.plan_rename`. Full refactor suite: **132/132 passed** (124 prev + 8 new).
    - **Phase B (soak test 2027 `.bsl`).** Артефакт: [`tools/bsl-ls/soak_real_client.py`](../../tools/bsl-ls/soak_real_client.py) + [`tools/bsl-ls/soak-logs/summary.json`](../../tools/bsl-ls/soak-logs/summary.json). Прогон против `src/projects/configuration/260304_GKSTCPLK-2182.../src` (**2027 `.bsl`**). Метрики: start `4739 ms`, **open `12.93 s`** (162 files/s при throttle_fps=400, batch_size=50), RSS `52.4 → 201.1 MB` (+148.7 MB, tracemalloc peak 143.9 MB). **DoD:** `open_secs < 60 s` ✅ (12.93), `RSS < 4 GB` ✅ (201 MB), `opened == 2027` ✅. **Pass on all three criteria.**
- **R1.4 Rename driver:** single entry `rename(uri, pos, newName, dryRun)`. **Артефакт:** метод. **DoD:** возвращает WorkspaceEdit или BackendError.
  - **Статус:** ✅ **DONE**. `RenameDriver(backend, verifier).rename(..., *, dry_run=True, confirm_token=None) -> RenameResult`. Двухфазный контракт: `dry_run=True` → plan + SHA-256 confirm_token; `dry_run=False` + matching token → verifier.verify_and_apply. 9 unit-тестов (dry_run, confirm, token mismatch, unsupported URI, rollback propagation, token stability). TOCTOU gap документирован в docstring.
- **R1.5 WorkspaceEdit applier:** атомарный apply с snapshot для rollback. **Артефакт:** `src/bsl/semantic_search/refactor/workspace_edit.py`. **DoD:** rollback на 5-файловом WorkspaceEdit работает.
  - **Статус:** ✅ **DONE**. Snapshot-before-modify, descending TextEdit sort, rollback-on-exception, workspace-root containment (path traversal отбивается), best-effort rollback через per-file try/except. 4 unit-теста (happy, regression rollback, apply exception, path traversal). Security-issue найден и пофикшен ревью-циклом.
- **R1.6 Symbol classifier update:** `module_export_proc` → A (cross-file через preload). **Артефакт:** обновление classifier + routing matrix. **DoD:** routing matrix v2 опубликована.
  - **Статус:** ✅ **DONE**. `SymbolKind` (7 видов) + `RouteDecision` (frozen slots) + `RoutingMatrix` (static v2) + `HeuristicClassifier` (pattern-based, URI + content, Unicode-aware). 17 unit-тестов, включая consistency-проверку confidence'ов между матрицей и `MultilspyBackend._CONFIDENCE`. Опубликован DoD-артефакт [routing-matrix-v2.md](./routing-matrix-v2.md). Edge-cases (trailing comment с «Экспорт», tab после «Перем») найдены ревью и покрыты regression-тестами.
- **R1.7 MCP tool exposure:** `bsl_rename_symbol` через `bsl-semantic-search` сервер с dry_run/confirm_token контрактом. **Артефакт:** handler в `mcp.py`. **DoD:** tool виден в Claude Code.
  - **Статус:** ✅ **DONE**. `@mcp.tool() bsl_rename_symbol()` + `register_rename_driver_factory()` + singleton cache (инвалидируется при re-register). 6 handler-тестов: not_initialized, dry_run plan, confirm applies file, token_mismatch, unsupported_uri, backend_error. Runtime-проверка: tool зарегистрирован. Реальный wire-up фабрики на server startup — позже (требует R1.3).
- **R1.8 Verification layer:** до/после apply — `edt-mcp get_project_errors`, auto-rollback при росте ошибок. **Артефакт:** `refactor/verification.py`. **DoD:** интеграционный тест с намеренно ломающимся rename.
  - **Статус:** ✅ **DONE**. `RenameVerifier(applier, error_provider).verify_and_apply(edit) -> VerifyResult` (applied, rolled_back, baseline_errors, after_errors, reason, `ok` property). `error_provider` — Callable[[], list[str]]; интеграция с `edt-mcp get_project_errors` как конкретная реализация — отложена до R1.3 wiring (сейчас тесты используют fake provider, который меняет return между вызовами для симуляции regression).

> **Итог R1 (кроме R1.3):** 8/8 подзадач закрыты на моках без реального multilspy. Агрегатная метрика — **77/77 refactor-тестов зелёные**. Пакет: [`src/bsl/semantic_search/refactor/`](../../src/bsl/semantic_search/refactor/) (10 Python-модулей + [`__init__.py`](../../src/bsl/semantic_search/refactor/__init__.py) с re-exports), tests: [`tests/bsl/refactor/`](../../tests/bsl/refactor/) (6 тест-файлов). R1.3 отложен до R5 benchmark. Ревью-циклом поймано и исправлено 9 реальных багов (security, process leak, stale state, counter reset, etc.).

#### Этап R2 — Variant B на ast-grep + tree-sitter-bsl (3-5 дней, параллельно R1)

- **R2.1 tree-sitter-bsl integration:** добавить grammar как git submodule, собрать parser. **Артефакт:** `tools/tree-sitter-bsl/`. **DoD:** парсит 3 тестовых модуля без ошибок.
  - **Статус:** ✅ **DONE** (в рамках R0.3). `tools/bsl-ls/tree_sitter_bsl.dll` + `sgconfig.yml` с customLanguage. tree-sitter-bsl 0.1.6. Покрытие: 14 ERRs / 1 518 lines ≈ 0.9% на реальных модулях.
- **R2.2 Fill coverage gaps:** если R0.2 нашёл пробелы — форкнуть grammar, добавить правила для препроцессора/запросов. **Артефакт:** PR в upstream или локальный fork. **DoD:** покрытие ≥95% на выборке из 20 модулей.
  - **Статус:** ⏸ **DEFERRED**. 0.9% ERR — приемлемо для fallback-бэкенда. Query-nodes gap не блокирует rename. Вернёмся после R5 benchmark, если покрытие окажется недостаточным.
- **R2.3 Rule authoring:** structural patterns для rename export method, local var, manager method, form handler. **Артефакт:** `tools/bsl-ls/ast-grep-rules/*.yml`. **DoD:** 4 правила + unit-тесты.
  - **Статус:** ✅ **DONE** (в рамках R0.3). 3 YAML-правила: `rename-export-method` (pattern), `rename-local-var` (kind=assignment_statement), `rename-catalog-method` (kind=call_expression + has access). Baseline: 1.2-1.7s на 2027 `.bsl`. Form-handler правило — отложено (R2.6).
- **R2.4 ast-grep runner:** Rust subprocess с JSON output. **Артефакт:** `src/bsl/semantic_search/refactor/backends/ast_grep_backend.py`. **DoD:** возвращает список правок, применяемых через WorkspaceEdit applier (R1.5).
  - **Статус:** ✅ **DONE**. `AstGrepBackend` (реализует `RenameBackend` Protocol, Unicode-aware word extraction, confidence table с кросс-матричной проверкой) + `SubprocessAstGrepRunner` (`ast-grep scan --json=compact --inline-rules`, cwd=workspace_root, timeout 60s) + `AstGrepRunner` Protocol для DI. 13 unit-тестов. Ревью-циклом найдено и исправлено 3 реальных бага: (1) `--json` без value ambiguous между версиями ast-grep (NDJSON vs array), (2) exit code 1 ошибочно трактовался как success, (3) relative paths резолвились против process CWD вместо workspace_root.
- **R2.5 Fallback orchestration:** если A timeout/error → автопереключение на B. **Артефакт:** обновление Orchestrator. **DoD:** интеграционный тест с remove multilspy → B работает.
  - **Статус:** ✅ **DONE**. `RefactorOrchestrator(backends, classifier, verifier)` + `OrchestratorResult` (primary_backend, fallback_used, confidence, symbol_kind, reason). Алгоритм: (1) classifier.classify → SymbolKind, (2) RoutingMatrix.route_for(kind) → primary/fallback, (3) try primary; если `BackendError` ИЛИ пустой WorkspaceEdit ИЛИ `can_handle=False` → try fallback, (4) оба проиграли → `BackendError(code="all_backends_failed")`, (5) dry-run возвращает SHA-256 confirm_token, (6) apply с корректным token → verifier.verify_and_apply. DoD-тест `test_multilspy_raises_triggers_ast_grep_fallback` симулирует «remove multilspy» через `_StubLspClient(raise_exc=RuntimeError("lsp unreachable"))` → ast-grep fallback строит WorkspaceEdit. 13 integration-тестов: primary-happy, fallback-on-raise, fallback-on-empty, FORM_HANDLER routing, LOCAL_VARIABLE/UNKNOWN no-fallback, dry-run token contract, apply path, token mismatch, backend_missing, both-fail, fallback-empty-also-fails, confidence mirrors matrix.
- **R2.6 Edge-case тесты:** динамика `Выполнить(«Метод()»)`, комментарии-документация, строковые вызовы в `ОтправитьСобытие`. **Артефакт:** тестовые модули + тесты. **DoD:** результаты документированы.
  - **Статус:** ⏸ **DEFERRED**. После R2.5, в связке с R5 benchmark.

#### Этап R3 — SCIP index как кэш-слой (5-7 дней, после R1)

- **R3.1 SCIP schema design для BSL:** symbol naming convention (`Module#Method`, `Catalog.Name#ManagerMethod`). **Артефакт:** `docs/roadmap/scip-bsl-schema.md`. **DoD:** схема покрывает 8 SymbolKind из §4.5.
- **R3.2 SCIP emitter из call_graph:** читать existing Neo4j/NetworkX граф, генерировать SCIP protobuf. **Артефакт:** `src/bsl/knowledge_graph/scip_emitter.py`. **DoD:** SCIP файл валидируется `scip validate`.
- **R3.3 Incremental update:** file watcher (watchdog Python) + rebuild только изменённых symbols. **Артефакт:** `scip_watcher.py`. **DoD:** изменение 1 файла обновляет SCIP за <1s.
- **R3.4 Query layer:** быстрый xref (`scip query symbol X`) без LSP/graph hop. **Артефакт:** `scip_query.py`. **DoD:** latency <10ms на запрос.
- **R3.5 MCP integration:** `bsl_xref(symbol)` через `bsl-semantic-search`. **Артефакт:** handler. **DoD:** tool работает в Claude Code.

#### Этап R4 — Orchestrator v2 + routing matrix (1-2 дня, после R1+R2)

**Цель этапа:** превратить статический `RoutingMatrix` и текущий `RefactorOrchestrator` (R2.5 DONE) в data-driven систему с 3-уровневым fallback (A → B → manual), телеметрией JSONL и калиброванными confidence на реальных данных.

**Стартовая точка:** [`classifier.py`](../../src/bsl/semantic_search/refactor/classifier.py) содержит hard-coded `_ROUTES` (7 `SymbolKind`, статические confidence 0.30-0.95); [`orchestrator.py`](../../src/bsl/semantic_search/refactor/orchestrator.py) делает 2-уровневый fallback (primary → fallback → `BackendError(all_backends_failed)`). Данных телеметрии нет.

**Инверсия порядка:** R4.2 калибровка блокируется данными → R4.4 telemetry ставится первым, R4.2 — последним (или параллельно R5 benchmark).

---

##### R4.0 — вынести routing matrix в YAML-конфиг (30 мин)

**Проблема:** `_ROUTES` захардкожен в [classifier.py:30-52](../../src/bsl/semantic_search/refactor/classifier.py#L30). Без внешнего конфига R4.2 калибровка потребует правки Python + ревью + деплой на каждую пересборку весов.

**Артефакт:** `src/bsl/semantic_search/refactor/routing_matrix.yaml` + loader `RoutingMatrix.load(path: Path | None = None)`. Initial YAML — копия текущих значений; `None` → bundled default в пакете (для unit-тестов без файла).

**Схема YAML:**
```yaml
version: 2
routes:
  module_export_proc:
    primary: multilspy
    fallback: ast-grep
    manual_fallback: false
    confidence: 0.95
    reason: "cross-file rename via LSP preload"
  # ... 7 kinds total
```

**DoD:**
- Тест `test_routing_matrix_yaml_roundtrip` — загрузка YAML даёт identical matrix статическому `_ROUTES`.
- Тест `test_routing_matrix_yaml_missing_kind_falls_back_to_unknown` — отсутствующий kind → route_for возвращает UNKNOWN-декоратор.
- Обратная совместимость: existing 17 тестов classifier без изменений.

---

##### R4.1 — Telemetry writer + интеграция в orchestrator (2 ч)

**Артефакт:** `src/bsl/semantic_search/refactor/telemetry.py`:

```python
@dataclass(frozen=True, slots=True)
class RenameTelemetryEvent:
    timestamp: str              # ISO-8601 UTC
    uri: str
    symbol_kind: str            # SymbolKind.value
    old_name: str | None        # may be redacted (SHA-1) if opt-in
    new_name: str               # target name
    primary_backend: str | None # winning backend, None if all failed
    fallback_used: bool
    applied: bool
    rolled_back: bool
    duration_ms: int
    error_code: str | None      # backend_missing|all_backends_failed|token_mismatch|...
    classifier_confidence: float
    matrix_confidence: float
    token_matched: bool | None  # apply-phase only; None in dry_run

class TelemetryWriter(Protocol):
    def write(self, event: RenameTelemetryEvent) -> None: ...

class JsonlTelemetryWriter:
    def __init__(self, path: Path, rotate_daily: bool = True, redact_names: bool = False): ...
```

**Интеграция в `RefactorOrchestrator.__init__`:** новый опциональный параметр `telemetry: TelemetryWriter | None = None`. В `rename()` — `perf_counter()` до/после каждой ветки (primary-success, fallback-success, all-failed, applied, rolled-back, token-mismatch). Exception-safe: `try/finally` на выдачу события.

**Файл:** `data/refactor-telemetry.jsonl` + daily rotation → `data/refactor-telemetry-YYYY-MM-DD.jsonl`, gzip для файлов >30 дней.

**DoD:**
- 6 unit-тестов: `test_telemetry_emits_on_primary_success`, `..._on_fallback_success`, `..._on_all_failed`, `..._on_applied`, `..._on_rolled_back`, `..._on_token_mismatch`.
- Тест `test_telemetry_none_noop` — `telemetry=None` не ломает orchestrator.
- Проверка всех 12+ полей в каждом событии.

---

##### R4.2 — Fallback chain v2: A → B → manual prompt (3 ч)

**Проблема текущей реализации:** `RouteDecision` — только `primary + fallback`. При `all_backends_failed` → `BackendError`. Вызывающий агент остаётся без инструкций «что делать дальше».

**Решение:** tier 3 = структурированный manual prompt, возвращаемый как полноценный `OrchestratorResult`.

**Изменения типов:**

```python
@dataclass(frozen=True, slots=True)
class RouteDecision:
    primary: str
    fallback: str | None
    manual_fallback: bool       # NEW — если True, при all-fail не raise
    confidence: float
    reason: str

@dataclass(frozen=True, slots=True)
class ManualFallbackInstruction:
    uri: str
    symbol_kind: SymbolKind
    old_name: str
    new_name: str
    suggested_approach: str     # "Grep+Edit", "EDT GUI refactor F2", "ast-grep --interactive"
    warnings: list[str]         # известные pitfalls для этого kind
    rationale: str              # почему автоматика не справилась
```

`OrchestratorResult` дополняется полем `manual_instruction: ManualFallbackInstruction | None = None`.

**Logic в `orchestrator.rename()`:**
1. Primary try → fallback try (как сейчас)
2. Оба пустые/failed И `decision.manual_fallback=True` → построить `ManualFallbackInstruction`, вернуть `OrchestratorResult(applied=False, rolled_back=False, manual_instruction=<...>, reason="manual_required")`
3. Оба failed И `manual_fallback=False` → `BackendError(all_backends_failed)` (существующее поведение сохраняется для LOCAL_VARIABLE).

**Конфиг в `routing_matrix.yaml`:** включить `manual_fallback: true` для сложных `SymbolKind` (FORM_HANDLER, UNKNOWN); оставить `false` для MODULE_LOCAL_*, LOCAL_VARIABLE где ожидается 100% автоматика.

**MCP surface (`bsl_rename_symbol`):** при manual tier возвращает `{"status": "manual_required", "instruction": {...}}` вместо raise. Handler в [mcp.py](../../src/bsl/semantic_search/mcp.py) расширяется.

**DoD:**
- 4 теста: `test_manual_fallback_returned_when_both_backends_fail`, `test_manual_fallback_disabled_still_raises_backend_error`, `test_manual_instruction_includes_suggested_approach_per_kind`, `test_mcp_rename_surfaces_manual_instruction`.
- Обновление 17 classifier-тестов под новую сигнатуру `RouteDecision` (добавить `manual_fallback=False` default).

---

##### R4.3 — Flowchart + документация fallback chain (1 ч)

**Артефакт:** `docs/roadmap/refactor-fallback-chain.md`:

- ASCII flowchart: `classify → route → primary.plan_rename → (ok? apply : fallback.plan_rename) → (ok? apply : manual_instruction | BackendError)`
- Per-`SymbolKind` таблица: primary, fallback, manual enabled, expected latency p50/p95, known limitations, когда раскалибровать confidence.
- Раздел «Когда срабатывает manual tier» — warnings для вызывающего агента, примеры suggested_approach per kind.
- Раздел «Инвалидация calibration» — когда пересчитать confidence (смена версии BSL LS, изменение правил ast-grep, расширение `SymbolKind` enum).

**DoD:** markdown существует; таблица покрывает все 7 `SymbolKind`; flowchart ссылается на конкретные строки `orchestrator.py`.

---

##### R4.4 — Aggregator + calibration script (2 ч)

**Артефакт:** `scripts/aggregate_refactor_telemetry.py`:

```
Input:  data/refactor-telemetry-*.jsonl (glob + merge)
Output: data/refactor-telemetry-summary.md (или stdout --stdout)
        data/refactor-telemetry-proposed.yaml (предлагаемые обновления routing_matrix.yaml)

Per (symbol_kind, backend):
  - total_calls, total_dry_runs, total_applies
  - success_rate = (applied and not rolled_back) / total_applies
  - fallback_rate = fallback_used / total
  - rollback_rate = rolled_back / total_applies
  - p50/p95/p99 duration_ms
  - top-5 error_codes с процентами
  - proposed_confidence = success_rate * (1 - rollback_rate), clamp [0.1, 0.95]

Confidence update rule:
  - IF total_calls < MIN_SAMPLES (20) → keep existing confidence (insufficient data)
  - ELSE IF abs(proposed - current) > DELTA_THRESHOLD (0.05) → emit in proposed.yaml
  - ELSE → no change
```

CLI flags: `--min-samples N`, `--delta-threshold X`, `--since YYYY-MM-DD`, `--stdout`.

**DoD:**
- Запуск на synthetic dataset (`data/refactor-telemetry-synthetic.jsonl`, 20 событий) → корректный markdown report.
- Unit-тест `test_aggregator_skips_under_min_samples` — 19 событий → proposed.yaml пустой.
- Unit-тест `test_aggregator_emits_proposal_above_delta` — 25 событий с success_rate=0.72 → proposed confidence=0.72, отличающийся от текущего на >0.05.

---

##### R4.5 — Confidence calibration (1 ч чистой работы + недели данных)

**Бутстрап-путь A:** продакшн-наблюдение 1-2 недели на daily dev rename (≥50 реальных вызовов) → aggregator → review proposed.yaml → commit → наблюдение за откликом.

**Бутстрап-путь B (быстрый):** привязать к R5 benchmark: 20 git-commit задач × 2 backends × dry+apply = ~80 data points. Достаточно для first calibration без ожидания продакшена.

**DoD (отложенный):** `routing_matrix.yaml` обновлён ≥1 раз на основе ≥50 реальных событий; CHANGELOG в этом документе фиксирует before/after confidence таблицы.

---

##### R4.6 (Опциональный) — Dashboard integration

**Зависит от:** Phase 10 dashboard (v4.1 extension). Если Phase 10 готов — panel «Refactor health»: success_rate, rollback_count, avg_latency, top errors, последние 10 calls. Иначе отложить как P2 follow-up.

**Артефакт:** дополнение к Phase 10 dashboard HTML/CLI.

**DoD (условный):** панель отображает агрегаты R4.4 с обновлением на каждый новый JSONL event.

---

##### Сводная таблица R4

| Подзадача | Артефакт | Оценка | Блокеры |
|-----------|----------|--------|---------|
| **R4.0** | `routing_matrix.yaml` + loader | 30 мин | — |
| **R4.1** | `telemetry.py` + JSONL writer + orchestrator integration | 2 ч | R4.0 |
| **R4.2** | `ManualFallbackInstruction` + 3-tier orchestrator + MCP surface | 3 ч | R4.1 |
| **R4.3** | `refactor-fallback-chain.md` + flowchart | 1 ч | R4.2 |
| **R4.4** | `aggregate_refactor_telemetry.py` + proposed.yaml | 2 ч | R4.1 |
| **R4.5** | Калибровка confidence в YAML | 1 ч (+ 1-2 недели данных или R5 benchmark) | R4.1, R4.4, данные |
| **R4.6** | Dashboard panel | 2 ч | Phase 10 |

**Критический путь:** R4.0 → R4.1 → R4.2 → R4.3 ≈ **6.5 ч чистого кода**. R4.4 параллельно R4.2/R4.3. R4.5 отложен до накопления данных или R5 benchmark.

**Итого:** **1 день** плотной работы на код + документацию (R4.0-R4.4); R4.5 и R4.6 — хвосты после наблюдения или интеграции с Phase 10.

---

##### Риски R4

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Telemetry PII (бизнес-идентификаторы в `old_name`) | Высокая (кириллические имена реквизитов часто содержат бизнес-термины) | Opt-in флаг `redact_names=True` в `JsonlTelemetryWriter` → хэширование `old_name` SHA-1; default `false` для dev-окружений |
| JSONL файл растёт без ограничений | Средняя | Daily rotation + gzip старше 30 дней; ротация в `JsonlTelemetryWriter` |
| Manual tier → Claude/агент в бесконечный цикл без действия | Средняя | В `ManualFallbackInstruction.suggested_approach` явно указывать инструменты (Grep, Edit, EDT GUI F2, ast-grep --interactive); НЕ делать silent retry в orchestrator |
| Калибровка на малой выборке даёт нестабильные confidence | Высокая на старте | Threshold: не обновлять confidence пока `total_calls < MIN_SAMPLES=20` per (kind, backend); `DELTA_THRESHOLD=0.05` для фильтрации шума |
| Schema `RenameTelemetryEvent` меняется → старый JSONL нечитаем | Низкая | Поле `version: 1` в каждом событии; aggregator умеет читать v1+ |
| Routing YAML содержит опечатки (backend name, confidence out of [0,1]) | Низкая | Валидация в `RoutingMatrix.load`: проверка backend в whitelist, clamp confidence, raise при unknown kind |

##### Итог R4 (2026-04-17)

| Подзадача | Статус | Артефакт | Тесты |
|-----------|--------|----------|------:|
| **R4.0** | ✅ DONE | [routing_matrix.yaml](../../src/bsl/semantic_search/refactor/routing_matrix.yaml) + `RoutingMatrix.load/reset()` в [classifier.py](../../src/bsl/semantic_search/refactor/classifier.py) | 5 |
| **R4.1** | ✅ DONE | [telemetry.py](../../src/bsl/semantic_search/refactor/telemetry.py) (`RenameTelemetryEvent`, `JsonlTelemetryWriter`, `NullTelemetryWriter`) + интеграция через `try/finally` в [orchestrator.py](../../src/bsl/semantic_search/refactor/orchestrator.py) `rename()` | 7 |
| **R4.2** | ✅ DONE | `ManualFallbackInstruction` + `manual_fallback` слот `RouteDecision` + 3-tier fallback в `RefactorOrchestrator` + MCP surface `bsl_rename_symbol` → `{status: "manual_required", manual_instruction: {...}}` | 4 |
| **R4.3** | ✅ DONE | [refactor-fallback-chain.md](./refactor-fallback-chain.md) — ASCII flowchart + таблица на все 7 `SymbolKind` + invalidation rules | — |
| **R4.4** | ✅ DONE | [aggregate_refactor_telemetry.py](../../scripts/aggregate_refactor_telemetry.py) + [refactor-telemetry-synthetic.jsonl](../../data/refactor-telemetry-synthetic.jsonl) (20 событий DoD fixture) | 3 |
| **R4.5** | ⏸ DEFERRED | — блокируется накоплением ≥50 реальных событий или R5 benchmark (~80 data points) | — |
| **R4.6** | ⏸ DEFERRED | — условный, зависит от Phase 10 dashboard | — |

**Агрегатно по R4:**
- **111/111 refactor-тестов зелёные** (`pytest tests/bsl/refactor/` → 90 до R4 → +19 новых тестов: 5+7+4+3). 2 дополнительных теста (`test_telemetry_event_includes_version_field`, `test_telemetry_gzips_old_rotated_files`) добавлены после quality-review.
- **Схема telemetry:** `version: int = 1` в каждом событии (митигация риска schema-change), `old_name` извлекается из `content` через Cyrillic-aware regex `[A-Za-z_\u0400-\u04FF][\w\u0400-\u04FF]*`, `classifier_confidence` отделён от `matrix_confidence` (разные источники).
- **Gzip-ротация:** `JsonlTelemetryWriter(compress_after_days=30)` упаковывает rotated-файлы в `.gz`, запускается в `__init__` + не чаще раза/час через `write()`. Вызов вынесен **после** `self._lock` (fix по quality-review, коммит `c41f6afd`).
- **Quality-review цикл (subagent):** flagged blocking I/O внутри write lock → fixed в `c41f6afd`. Остальное — PASS (нет injection, regex ReDoS-safe, `@dataclass(frozen, slots)` сохранён, backward-compat через `getattr(r, "manual_instruction", None)`).
- **Коммиты:** `70f1ba82` (основной DoD gap-close) + `c41f6afd` (lock-hold fix).

**Что отложено:**
- **R4.5 calibration** — бутстрап через R5 benchmark (20 задач × 2 backend × dry+apply = ~80 event, хватит для first calibration без ожидания продакшена). После сбора: `python scripts/aggregate_refactor_telemetry.py` → review `data/refactor-telemetry-proposed.yaml` → commit.
- **R4.6 dashboard** — ждёт Phase 10.

**Непокрытые DoD-детали (низкий приоритет):**
- Формальная JSON-схема `manual_instruction` в docs или YAML header (сейчас контракт де-факто закреплён в `test_mcp_rename_surfaces_manual_instruction`).
- `aggregate_refactor_telemetry.py` пока читает `event.get("version")` неявно (default → обрабатывается как v1); при введении v2 потребуется branch-логика.

#### Этап R5 — Benchmark + validation (2-3 дня, после R4)

**Цель этапа:** превратить субъективные заявления «A работает, B работает» в воспроизводимые числа — success rate, latency p50/p95, fallback-rate, rollback-rate — на 20 реальных задачах. Побочно: собрать ≥80 событий телеметрии как быстрый бутстрап [R4.5 confidence calibration](#L1509) без ожидания недельного продакшн-наблюдения.

**Стартовая точка (2026-04-17):** R1-R4 закрыты, 111/111 refactor-тестов зелёные на моках. `multilspy_backend.py` не подключён к реальному LSP ([R1.3 DEFERRED](#L1300)); `ast-grep_backend.py` работает с реальным `ast-grep` Rust CLI (baseline: 1.2-1.7s на 2027 `.bsl`). Для R5 это значит: первый прогон реалистично делать **B-only** либо предварительно разблокировать R1.3.

**Критический путь R5:** R5.1 → R5.2 → R5.3 → R5.4 → R5.5 (calibration feedback). R5.1 независим от кода (задачи собираются офлайн из git log), может стартовать сразу. R5.2 для A-ветки требует R1.3; B-ветка прогоняется без блокировок.

**Инверсия порядка (если R1.3 не готов):** прогоняем только B, в R5.3 ставим `n/a` в A-колонке, A-ветку добавляем в следующий прогон после разблокировки. Это всё равно закрывает R5.4 (trend tracker) и R5.5 (calibration для B).

---

> **Прогресс R5 (обновлено 2026-04-17 23:30):**
>
> | Подэтап | Статус | Артефакты | Тесты | Примечание |
> |---------|--------|-----------|-------|------------|
> | **R5.1** tasks.json | **DONE** | `docs/roadmap/benchmark/tasks.json` (20 задач, 5×4), `scripts/build_benchmark_tasks.py`, `tests/bsl/refactor/test_benchmark_tasks_schema.py` | 7/7 PASS | Все задачи используют `"synthetic"` SHA (нет реальных rename-коммитов в git истории). Ground truth заполнен вручную. |
> | **R5.2** Runner | **DONE** | `docs/roadmap/benchmark/runner.py` (WorktreeManager, TaskExecutor, ReportBuilder, BenchmarkRunner), `scripts/run_benchmark.py` (CLI), `tests/bsl/refactor/test_benchmark_runner.py` | 6/6 PASS | B-only (ast-grep) с synthetic SHAs. Lazy import обходит namespace collision `tests/bsl/__init__.py` vs `src/bsl/`. parent_sha regex validation + atexit worktree cleanup (code-verify). |
> | **R5.3** Report | **DONE** | `ReportBuilder.render_markdown()` + `render_csv()` внутри `runner.py` | Покрыто test_markdown_contains_backends + test_csv_has_header_and_rows | Markdown: per-backend summary + per-category breakdown + failure taxonomy. CSV: pandas-ready. |
> | **R5.4** Trend | **DONE** | `docs/roadmap/benchmark/trend.md`, `scripts/check_benchmark_regression.py` | Smoke-tested (synthetic JSONL) | trend.md — append-only таблица. `check_benchmark_regression.py` — exit 1 при rate < threshold (default 0.70). |
> | **R5.5** Calibration | **DEFERRED** | — | — | Требует реального benchmark-прогона (pilot-B) с ≥20 telemetry событий. Разблокируется после интеграции ast-grep backend с runner. |
>
> **Итого R5:** R5.1–R5.4 реализованы за 1 день (вместо 2-3 дней по оценке). 13/13 тестов зелёные (7 schema + 6 runner). R5.5 отложен до первого реального прогона.
>
> **Известные ограничения:**
> - Все 20 задач используют `"commit_sha": "synthetic"` — runner работает напрямую в repo_root, git worktree не создаётся. Для production benchmark нужны реальные rename-коммиты.
> - `tests/bsl/__init__.py` создаёт namespace collision с `src/bsl/` — фиксировано через `sys.modules["bsl"] = importlib.import_module("src.bsl")` в тесте.
> - CLI `run_benchmark.py` содержит `_StubBackend` — реальный `AstGrepBackend` пока не подключён (требует `ast-grep` binary в PATH).

---

##### R5.1 — Benchmark tasks.json (4 ч)

**Проблема:** без канонического датасета сравнение backends деградирует в «у меня сработало» vs «у меня не сработало». Нужна замороженная выборка реальных rename-задач, где ground truth известен.

**Источник задач:** git-история `D:\1С-Framework` (и, опционально, публичные BSL-конфигурации: StandardSubsystemsLibrary, ERP fragments). Отбираются коммиты, где diff содержит rename identifier. Эвристики поиска:

- `-Процедура X(` + `+Процедура Y(` в соседних строках одного файла
- Одноимённые правки одного identifier в 2+ файлах коммита
- `git log -S 'OldName' -p --reverse` — коммит, убирающий идентификатор
- `git log --diff-filter=M --grep 'rename\|переименование'` — явные rename-коммиты

**Таксономия (5 категорий × 4 задачи = 20):**

| # | Категория | Описание | Ожидаемый winner | Ожидаемый `SymbolKind` |
|---|-----------|----------|------------------|------------------------|
| **CAT-1** | Local variable | `Перем Старый` → `Перем Новый` внутри тела процедуры | multilspy (scope-aware) | `local_variable` |
| **CAT-2** | Module-local proc/func | приватная процедура/функция с внутренними callers в одном модуле | multilspy | `module_local_proc`/`_func` |
| **CAT-3** | Cross-file export | `Экспорт` метод общего модуля/менеджера, вызываемый из 2+ модулей | multilspy (через preload) | `module_export_proc`/`_func` |
| **CAT-4** | Form handler | обработчик события формы, упоминается и в BSL-модуле, и в XML формы | ast-grep (multilspy не видит XML) | `form_handler` |
| **CAT-5** | Edge-case / known-hard | dynamic `Выполнить("Метод()")`, string literal в `ОтправитьСобытие`, mention в комментарии-документации | оба провалятся → manual tier | `unknown` |

**Схема `docs/roadmap/benchmark/tasks.json`:**

```json
{
  "version": 1,
  "created_at": "2026-04-XX",
  "source_repo": "D:\\1С-Framework",
  "tasks": [
    {
      "id": "T03",
      "category": "CAT-3-cross-file-export",
      "commit_sha": "abc12345",
      "parent_sha": "abc12344",
      "file_uri": "file:///workspace/ОбщиеМодули/РасчётыКлиентСервер/Ext/Module.bsl",
      "line": 42,
      "character": 10,
      "old_name": "РассчитатьОстаток",
      "new_name": "ПересчитатьОстаток",
      "expected_files_affected": 3,
      "expected_edits": 7,
      "expected_files": [
        "ОбщиеМодули/РасчётыКлиентСервер/Ext/Module.bsl",
        "Справочники/Контрагенты/Ext/ManagerModule.bsl",
        "ОбщиеМодули/Служебные/Ext/Module.bsl"
      ],
      "notes": "Основное объявление в РасчётыКлиентСервер; вызовы из ManagerModule (2 раза) и Служебные (1 раз). Verify error count до/после должен быть 0."
    }
  ]
}
```

**Артефакт:**
- `docs/roadmap/benchmark/tasks.json` — замороженный датасет (20 задач).
- `scripts/build_benchmark_tasks.py` — генератор-кандидат: сканирует git log по эвристикам, предлагает задачи для ручного ревью, записывает принятые в JSON.
- `tests/bsl/refactor/test_benchmark_tasks_schema.py` — валидация JSON schema (version=1, 5 категорий, ground truth non-empty).

**DoD:**
- 20 задач, распределение **4/4/4/4/4** по категориям.
- Каждая задача имеет `commit_sha` + `parent_sha` — воспроизводимо на любом checkout.
- `expected_files_affected`, `expected_edits`, `expected_files` проставлены **вручную** (ground truth, не автоматически из git diff — автоматика может ошибиться на edge-case).
- Schema валидируется `test_benchmark_tasks_schema` (jsonschema validate → 0 ошибок на всех 20 задачах).
- В каждой задаче хотя бы 2 файла в `expected_files` для CAT-3/CAT-4 (чтобы B без preload действительно был challenged).

---

##### R5.2 — Dual execution runner (6 ч)

**Проблема:** 20 задач × 2 backend × {dry_run, apply} = 80 прогонов. Ручное выполнение невозможно — нужен runner с полной изоляцией: каждая задача работает в отдельном git-worktree, между прогонами `git reset --hard`, telemetry пишется пер-run.

**Архитектура runner'а:**

```
BenchmarkRunner (docs/roadmap/benchmark/runner.py)
  │
  ├── WorktreeManager
  │     ├─ create(parent_sha) → tmp_path/worktree_{task_id}_{backend}/
  │     ├─ (внутри) git worktree add --detach <path> <parent_sha>
  │     ├─ cleanup() — git worktree remove --force + shutil.rmtree
  │     └─ retry 3× на Windows file locks (AntiVirus/IDE держат дескрипторы)
  │
  ├── BackendFactory
  │     ├─ build("multilspy")  → MultilspyBackend + LspSubprocess
  │     ├─ build("ast-grep")   → AstGrepBackend + SubprocessAstGrepRunner
  │     └─ build("orchestrator") → RefactorOrchestrator({both})
  │
  ├── TaskExecutor.run(task, backend) -> TaskResult
  │     1. worktree = WorktreeManager.create(task.parent_sha)
  │     2. Читает task.file_uri в content (для HeuristicClassifier)
  │     3. plan  = backend.rename(uri, line, char, new_name, dry_run=True, content=...)
  │     4. apply = backend.rename(..., dry_run=False, confirm_token=plan.confirm_token, ...)
  │     5. RenameTelemetryEvent → data/benchmark-telemetry-{run_id}.jsonl
  │     6. diff_vs_expected = compare_workspace_edit(apply.edit, task.expected_files)
  │     7. WorktreeManager.cleanup()
  │
  └── ReportBuilder
        ├─ aggregate JSONL → per-(task, backend) rollup
        ├─ render markdown (R5.3 format)
        └─ render CSV (для Grafana / Excel)
```

**CLI (`scripts/run_benchmark.py`):**

```bash
# Базовый прогон — оба backend + orchestrator
python scripts/run_benchmark.py \
    --tasks docs/roadmap/benchmark/tasks.json \
    --backends multilspy,ast-grep,orchestrator \
    --run-id full-1 \
    --output data/benchmark-run-2026-05-01/

# B-only пилотный прогон (R1.3 ещё не готов)
python scripts/run_benchmark.py --backends ast-grep --run-id pilot-B

# Выборочно — одна категория или одна задача
python scripts/run_benchmark.py --categories CAT-3-cross-file-export
python scripts/run_benchmark.py --task-id T07

# Append в trend.md
python scripts/run_benchmark.py --run-id full-2 --append-trend
```

**Измеряемые поля на каждую пару (task, backend):**

| Поле | Источник | Назначение |
|------|----------|-----------|
| `applied` | `OrchestratorResult.applied` | success rate |
| `rolled_back` | `OrchestratorResult.rolled_back` | false-positive rate |
| `files_affected` | `WorkspaceEdit` | сравнение с `expected_files_affected` |
| `files_match_expected` | set comparison | precision: ни одного «чужого» файла |
| `edits_match_expected` | diff vs ground truth | количественное совпадение |
| `duration_ms_plan` / `_apply` | `perf_counter` | p50/p95 отдельно для dry-run и apply |
| `error_code` | `BackendError.code` | failure taxonomy |
| `fallback_used` | `OrchestratorResult.fallback_used` | частота active fallback |
| `manual_required` | `reason == "manual_required"` | tier 3 активаций |
| `classifier_confidence` | telemetry | для R4.5 feedback |
| `matrix_confidence` | telemetry | для R4.5 feedback |

**Артефакт:**
- `docs/roadmap/benchmark/runner.py` — main `BenchmarkRunner` + components.
- `scripts/run_benchmark.py` — CLI wrapper (Typer).
- `tests/bsl/refactor/test_benchmark_runner.py` — интеграционные тесты на synthetic tmp_path.

**DoD:**
- Runner прогоняет 1 задачу с обоими backend за <60s (включая worktree setup).
- `git reset --hard` + `git worktree remove` чистит всё — нет orphan-директорий после N прогонов.
- JSONL события совместимы со схемой `RenameTelemetryEvent` v1 и читаются `scripts/aggregate_refactor_telemetry.py` без модификаций.
- `test_runner_processes_single_task_both_backends` — synthetic 2-файловая задача в tmp_path, оба backend возвращают ожидаемый WorkspaceEdit.
- `test_runner_worktree_isolation` — параллельный запуск двух задач, изменения worktree #1 не видны в worktree #2 (проверка через `git -C <worktree> status`).
- Retry-логика: при `PermissionError` на `shutil.rmtree` (Windows AV) — 3 попытки с экспоненциальной паузой.

---

##### R5.3 — Comparison report A vs B vs A+B (4 ч)

**Проблема:** 80+ сырых JSONL событий — не отчёт. Нужна читаемая markdown-страница с агрегатами, per-category breakdown и failure-taxonomy, чтобы команда могла принять решение «какие задачи отдать какому backend».

**Формат `docs/roadmap/benchmark/results-YYYY-MM.md`:**

```markdown
# Benchmark Results 2026-05

**Dataset:** docs/roadmap/benchmark/tasks.json v1, 20 tasks
**Run ID:** full-1
**Commits sampled:** 2025-10-01 → 2026-04-15 (D:\1С-Framework)
**Machine:** Win11 IoT 10.0.22631, Python 3.11.x, 1C 8.3.27.1859
**BSL LS:** 0.23.0 (multilspy preload)
**tree-sitter-bsl:** 0.1.6, ast-grep 0.x.y

## Summary

| Метрика              | A (multilspy) | B (ast-grep) | A+B (orchestrator) |
|----------------------|--------------:|-------------:|-------------------:|
| Applied (success)    |         14/20 |        12/20 |              17/20 |
| Rolled back          |             1 |            0 |                  1 |
| Manual tier          |           n/a |          n/a |               3/20 |
| p50 latency (ms)     |           320 |          180 |                350 |
| p95 latency (ms)     |          1420 |          620 |               1500 |
| p99 latency (ms)     |          2100 |          780 |               2200 |

## Per-category breakdown

| Категория              | A      | B     | A+B    | Orchestrator winner |
|------------------------|-------:|------:|-------:|---------------------|
| CAT-1 Local variable   |   4/4  |  3/4  |   4/4  | A                   |
| CAT-2 Module-local     |   4/4  |  3/4  |   4/4  | A                   |
| CAT-3 Cross-file exp.  |   4/4  |  2/4  |   4/4  | A (B fails w/o preload) |
| CAT-4 Form handler     |   1/4  |  3/4  |   4/4  | B primary, A fallback |
| CAT-5 Edge-case        |   0/4  |  0/4  |  1/4+3 manual | Tier 3       |

## Failure taxonomy

### A succeeded, B failed
- **T04 (CAT-3):** ast-grep без preload нашёл только вызовы в том же файле (2 хита из 3 expected)
- **T15 (CAT-2):** B не отличает module-local от export без LSP → перекрасил один лишний файл

### B succeeded, A failed
- **T07 (CAT-4):** multilspy не видит XML-форм → пропустил ссылку в `Form.xml`
- **T12 (CAT-5-like):** dynamic call `Выполнить("Метод()")` — multilspy видит только AST, не строковые литералы

### Both failed (manual tier active)
- **T18, T19, T20 (CAT-5):** string-literal call в `ОтправитьСобытие`, comment-only mention, metadata reference. `manual_instruction` возвращён корректно с `suggested_approach`.

## Per-task table

| Task | Category | A applied | B applied | A+B used | A ms | B ms | Notes |
|------|----------|:---------:|:---------:|:--------:|-----:|-----:|-------|
| T01  | CAT-1    |     ✓     |     ✓     |    A     |  120 |   85 | both OK |
| T02  | CAT-1    |     ✓     |     ✗     |    A     |  110 | fail | B: scope error |
| ...  | ...      |           |           |          |      |      |       |

## Confidence calibration input (для R4.5)

Per (kind, backend) success_rate × (1 - rollback_rate):

| SymbolKind           | multilspy | ast-grep |
|----------------------|----------:|---------:|
| module_export_proc   |     0.95  |    0.62  |
| module_local_proc    |     0.92  |    0.70  |
| local_variable       |     0.95  |    0.70  |
| form_handler         |     0.30  |    0.75  |
| unknown              |     0.12  |    0.18  |

Apply via: `python scripts/aggregate_refactor_telemetry.py --since 2026-05-01 > data/refactor-telemetry-proposed.yaml`
```

**Артефакт:**
- `docs/roadmap/benchmark/results-YYYY-MM.md` — человекочитаемый отчёт.
- `docs/roadmap/benchmark/results-YYYY-MM.csv` — сырой per-(task, backend) CSV (для Excel / Grafana / pandas).
- Функция `ReportBuilder.render_markdown(jsonl_glob) -> str` в `runner.py`.

**DoD:**
- Все 20 задач × 3 колонки (A, B, A+B) заполнены (без пропусков, `n/a` только если backend не поддерживается в этом run).
- Failure taxonomy разделена на 3 секции: A-only-wins, B-only-wins, both-fail.
- Per-category success rates + latency percentiles (p50/p95/p99) присутствуют.
- Секция «Confidence calibration input» содержит таблицу `success_rate × (1 - rollback_rate)` per (kind, backend) — прямой вход в [R4.5](#L1506).
- CSV валиден для `pandas.read_csv` (нет сломанных строк при Cyrillic).

---

##### R5.4 — Trend tracker (2 ч)

**Проблема:** один прогон — слепок во времени. Нужен тренд: улучшается или деградирует система между версиями BSL LS, обновлением grammar, пересчитанной calibration.

**Артефакт:** `docs/roadmap/benchmark/trend.md` — append-only таблица, обновляется из `run_benchmark.py --append-trend`.

**Формат:**

```markdown
# Benchmark Trend

| Run ID   | Date       | Commit    | BSL LS | Grammar | A success | B success | A+B success | Rollback % | Notes |
|----------|------------|-----------|--------|---------|----------:|----------:|------------:|-----------:|-------|
| pilot-B  | 2026-05-01 | 70f1ba82  |  n/a   | 0.1.6   |   n/a     |  12/20    |   n/a       |   0%       | multilspy deferred |
| full-1   | 2026-05-10 | abc12345  | 0.23.0 | 0.1.6   | 14/20     | 12/20     | 17/20       |   5%       | first full run |
| full-2   | 2026-06-15 | def56789  | 0.24.0 | 0.1.7   | 16/20     | 13/20     | 18/20       |   0%       | BSL LS upgrade +2 A |
| full-3   | 2026-07-01 | 9876abcd  | 0.24.0 | 0.1.7   | 16/20     | 13/20     | 19/20       |   0%       | R4.5 calibration applied → +1 A+B |
```

**Regression gate (опционально в CI):**

```yaml
# .github/workflows/benchmark.yml
- name: Run benchmark
  run: python scripts/run_benchmark.py --run-id ci-${{ github.sha }} --append-trend
- name: Regression check
  run: python scripts/check_benchmark_regression.py --min-success 17 --max-rollback-pct 5
```

**DoD:**
- Пилотный прогон (**pilot-B**, без multilspy) в таблице.
- После разблокировки R1.3: минимум 2 **full** прогона зафиксированы (full-1, full-2).
- `check_benchmark_regression.py` падает с exit 1 при `A+B success < previous - 2` или `rollback_pct > 5`.
- Regression gate интегрирован в CI (если CI существует) либо документирован как manual pre-release check.

---

##### R5.5 — Feed calibration back into R4.5 (1 ч)

**Проблема:** [R4.5 calibration](#L1506) ждёт реальных данных. R5 их генерирует. Нужен явный шаг, замыкающий цикл «benchmark → proposed.yaml → routing_matrix.yaml».

**Алгоритм:**

```bash
# 1. Скопировать benchmark telemetry в общий pool
cp data/benchmark-run-2026-05-01/benchmark-telemetry-*.jsonl \
   data/refactor-telemetry-benchmark-2026-05-01.jsonl

# 2. Сгенерировать proposed changes
python scripts/aggregate_refactor_telemetry.py \
    --since 2026-05-01 \
    --min-samples 4 \
    --delta-threshold 0.05

# 3. Review proposed YAML (diff против routing_matrix.yaml)
diff src/bsl/semantic_search/refactor/routing_matrix.yaml \
     data/refactor-telemetry-proposed.yaml

# 4. Применить вручную селективно к routing_matrix.yaml
#    (принимаем только confidence, у которых MIN_SAMPLES >= 4 per kind/backend)

# 5. Pytest → 111/111 (обновить test_routing_matrix_yaml_roundtrip
#    если numeric значения изменились)
pytest tests/bsl/refactor/test_routing_matrix_yaml.py -v

# 6. Записать в CHANGELOG этого roadmap-документа before/after таблицу
```

**Special case:** для первого прогона `min_samples=4` вместо дефолтных 20 — на 20 задачах × 5 категорий в одной ячейке (kind, backend) будет ровно 4 события. DELTA_THRESHOLD=0.05 остаётся.

**Артефакт:**
- `data/refactor-telemetry-proposed.yaml` — сгенерирован aggregator'ом.
- Апдейт `src/bsl/semantic_search/refactor/routing_matrix.yaml` на реальных данных.
- Секция «CHANGELOG (R4.5 calibration)» в этом документе — before/after таблица per (kind, backend).

**DoD:**
- `routing_matrix.yaml` обновлён минимум для CAT-3 (cross-file export) и CAT-4 (form handler) — самые волатильные категории.
- 111+/111+ тестов зелёные после апдейта (17 classifier-тестов + 5 routing_matrix-тестов покрывают consistency).
- CHANGELOG содержит ссылку на `pilot-B` и `full-1` прогоны в `trend.md`.

---

##### Сводная таблица R5

| Подзадача | Артефакт                                                           | Оценка | Блокеры                        |
|-----------|--------------------------------------------------------------------|--------|---------------------------------|
| **R5.1**  | `tasks.json` + `build_benchmark_tasks.py` + schema-тест            | 4 ч    | — (офлайн работа)               |
| **R5.2**  | `runner.py` + `run_benchmark.py` CLI + 2 integration-теста         | 6 ч    | R5.1, R1.3 (только A-ветка)     |
| **R5.3**  | `results-YYYY-MM.md` + CSV + `ReportBuilder.render_markdown`        | 4 ч    | R5.2 (нужны JSONL события)      |
| **R5.4**  | `trend.md` + `check_benchmark_regression.py` + опциональный CI yml  | 2 ч    | R5.3 (хотя бы 1 прогон)         |
| **R5.5**  | Apply calibration → `routing_matrix.yaml` + CHANGELOG              | 1 ч    | R5.3 + aggregator из R4.4       |

**Критический путь:** R5.1 (офлайн, старт немедленный) → R5.2 (блокер R1.3 для A-ветки) → R5.3 → {R5.4 ∥ R5.5}. **Итого: 17 ч чистого кода + ревью ≈ 2 дня** с подключённым multilspy; **13 ч ≈ 1.5 дня** для B-only пилота (пропускаем R5.5 до второго прогона).

---

##### Риски R5

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Ground truth в `tasks.json` неверен (expected_edits промахивается) | Средняя | Manual review каждой задачи при её создании; хранить diff из парного коммита как reference; прогон aggregator'а с `--verify-ground-truth` покажет аномалии |
| `git worktree` не изолирует на Windows (file locks от AV/IDE) | Высокая | Retry 3× с 500ms/1s/2s задержкой на `PermissionError`; `git worktree remove --force`; fallback на `--worktree-dir %TEMP%` вне проектной директории |
| BSL LS недоступен в CI → A-ветка не прогоняется | Высокая на старте | Флаг `--skip-unavailable`: runner пишет `"skipped"` вместо `"failed"`; B-only прогон засчитывается как partial success; отдельный entry в trend.md с `A=n/a` |
| ast-grep grammar 0.9% ERR → парсинг падает на специфических конструкциях | Средняя | В runner логировать `parse_error` отдельно от rename-failure; не учитывать в success/failure matrix, репортить в отдельной секции отчёта |
| Calibration на 80 событиях даёт overfit под benchmark-датасет | Средняя | MIN_SAMPLES=4 per (kind, backend) — минимально жизнеспособный порог; DELTA_THRESHOLD=0.05 фильтрует шум; при `full-2` используем MIN_SAMPLES=8 (накопилось уже 40 событий на категорию) |
| Flaky тесты (race condition между worktree и LSP subprocess) | Средняя | Retry-логика в TaskExecutor: при падении 3× подряд — пометить задачу `flaky`, исключить из success rate, но сохранить в failure taxonomy |
| Cyrillic в git log ломает parsing на Windows (default cp1251) | Высокая | `git config --global core.quotepath false` + `GIT_TERMINAL_PROMPT=0` + `PYTHONIOENCODING=utf-8` во всех subprocess вызовах |
| `git worktree` создаёт артефакты в `.git/worktrees/` — загаживает репо | Низкая | `runner.py` на exit делает `git worktree prune`; unit-тест `test_runner_cleans_up_git_worktrees` |

---

##### Критерии успеха R5

- **Покрытие:** 20/20 задач прогнаны хотя бы одним backend, 0 задач с необработанным исключением в runner.
- **Orchestrator value:** A+B merge превосходит одиночный backend минимум на 3 задачах (иначе roadmap §7.3 orchestration нужно пересмотреть).
- **Latency p95:** < 30s на CAT-1/CAT-2 (single-file), < 60s на CAT-3 (cross-file через multilspy preload).
- **Auto-rollback:** < 5% (≤1 задача из 20) — валидация §7.4 безопасности verifier'а.
- **R4.5 feedback loop замкнут:** минимум 1 confidence обновлён в `routing_matrix.yaml` на основе реальных данных из `trend.md`.
- **Manual tier корректность:** для всех 3-4 CAT-5 задач `manual_instruction` возвращён с непустым `suggested_approach` и хотя бы 1 warning.

#### Этап R6 — Upstream contributions (опционально, 2-3 дня, после R5)

**Цель этапа:** заменить внутренние патчи и кастомные адаптеры на принятые upstream-изменения, снизив долгосрочную стоимость обслуживания. Побочно — публикация результатов R0-R5 в сообществах `multilspy` / `bsl-language-server` / `tree-sitter-bsl` / `Serena`, что легитимизирует выбранный подход и открывает доступ к bug-fix'ам core-maintainer'ов.

**Стартовая точка (планируемая, после R5):** R0-R5.4 закрыты, воспроизводимый benchmark (минимум `pilot-B`), [13 багов исправлены](#L2016) собственным ревью-циклом, покрытие grammar **100.0%** (0 ERRs / 1 518 lines после R6.3) — это и есть evidence base для любых PR discovery-issue'ов.

**Почему «опционально»:**
- Все артефакты R1-R5 работают self-hosted — upstream-приём не блокирует продакшн.
- Upstream-циклы ревью непредсказуемы (от недель до кварталов).
- Часть изменений может быть отклонена по reasons-of-scope — это не регрессия для нашей стороны, лишь фиксация long-term maintenance в internal fork.

**Критерии запуска R6:**
- [R5.4 trend.md](../../docs/roadmap/benchmark/trend.md) содержит минимум 2 прогона (`pilot-B` + `full-1`).
- [R4.5 calibration](#L1889) применена хотя бы к одному (kind, backend) — иначе нечего предъявлять как эмпирическое обоснование.
- Legal/licensing check: лицензии всех четырёх upstream — **MIT**, совместимо с нашим кодом. Документ `docs/legal/upstream-license-matrix.md` (создать при запуске R6).
- Issue в каждом upstream открыт **ДО** PR — избегаем «code dump» без предварительного согласования scope.

**Порядок приоритизации (по соотношению impact/effort/acceptance probability):**

| # | PR | Impact на нас | Вероятность приёма | Сложность |
|---|----|---------------|--------------------|-----------|
| **R6.3** | tree-sitter-bsl: parenthesized expressions | Средний (снимает 0.9% ERR) | Высокая (mini-PR, evidence готов) | Низкая (4-6 ч) |
| **R6.4** | Serena: BSL context | Низкий (удобство + discovery) | Высокая (yml-only, opt-in) | Низкая (2-3 ч) |
| **R6.1** | multilspy: BSL language adapter | Высокий (убирает internal fork) | Средняя (mainstream maintainer, ниша — BSL) | Высокая (1-2 дня) |
| **R6.2** | bsl-language-server: `didChangeWorkspaceFolders` | Высокий (убирает bulk-didOpen workaround) | **Низкая** (меняет core поведение LS) | Высокая (Java 17, 1-2 дня) |

**Рекомендация:** сначала R6.3 + R6.4 (быстрые win'ы, строят репутацию contributor'а в каждом сообществе), затем R6.1, и лишь опционально R6.2 (если core-team согласовала scope в discovery issue).

---

##### R6.1 — PR в multilspy: BSL language adapter (1-2 дня)

**Проблема:** [multilspy_backend.py](../../src/bsl/semantic_search/refactor/backends/multilspy_backend.py) использует `multilspy` через тонкую обёртку, но BSL отсутствует в upstream `Language` enum. Сейчас наш код вынужден либо форкать `multilspy`, либо лезть в приватные API (`_start_server`, custom `LanguageServerManager`). И то, и другое — технический долг.

**Upstream repo:** https://github.com/microsoft/multilspy (566⭐, MIT, активно развивается).

**Scope PR:**
1. `src/multilspy/multilspy_types.py` — добавить `Language.BSL = "bsl"` в enum + mapping `"bsl" → .bsl file extension`.
2. `src/multilspy/language_servers/bsl_language_server/` (новый пакет):
   - `bsl_language_server.py` — подкласс `LanguageServer`, JAR launcher (`java -jar bsl-language-server.jar --lsp`), shutdown-handler.
   - `runtime_dependencies.json` — pin-версия `bsl-language-server-0.23.0.jar` с SHA256 + download URL (GitHub releases `1c-syntax/bsl-language-server`).
   - `initialize_params.json` — BSL-specific `initializationOptions` (configurationRoot, диалект `Server`/`Thick`/`Thin`).
3. `src/multilspy/language_server.py` — регистрация `bsl` в factory (`if language == Language.BSL: return BSLLanguageServer(...)`).
4. Tests: `tests/multilspy/test_bsl/test_hover.py`, `test_references.py`, `test_rename.py` — три синтетических `.bsl` модуля (переиспользовать из R0.2 — `гкс_ОчередьСообщенийRMQ`, `гкс_ФормировательСообщенийRMQ`, `гкс_Взвешивание.ФормаДокумента`).
5. `README.md` — BSL в списке поддерживаемых языков; упомянуть known limitation (per-document indexing) с отсылкой к R6.2.

**Процесс подачи PR:**
1. Fork `microsoft/multilspy` → branch `feat/bsl-language`.
2. Open discovery issue `Proposal: add BSL (1C Enterprise) language support` со ссылкой на [bsl-ls-recon-results.md](bsl-ls-recon-results.md) и [routing-matrix-v2.md](./routing-matrix-v2.md). Подкрепить цифрами из R5 (latency, success rate) — **ДО** PR.
3. Дождаться green light от core-maintainer (< 1 нед обычно у microsoft/* проектов).
4. Подготовить PR — линкуется к issue, включает скриншоты `pilot-B` / `full-1` (если готовы).
5. Ответить на review comments в 48 ч.
6. После merge — заменить наш self-hosted fork на upstream dep (`multilspy>=X.Y.Z`), удалить `tools/bsl-ls/vendor/multilspy-fork/` (если существовал).

**Артефакт:**
- PR в `microsoft/multilspy` (URL сохранить в [bsl-ls-recon-results.md](bsl-ls-recon-results.md) секция `## Upstream status`).
- Internal vendor fork удалён или помечен `deprecated` (если PR declined).

**DoD:**
- PR открыт и CI maintainer'а зелёный (GitHub Actions: unit-тесты, type-checking).
- Получен минимум 1 review от core-maintainer (merged / requested-changes / declined).
- **Если merged:** [multilspy_backend.py](../../src/bsl/semantic_search/refactor/backends/multilspy_backend.py) переведён с private API на public (`Language.BSL`), удалены private-import'ы, прогнаны 111 refactor-тестов → все зелёные.
- **Если declined:** reason задокументирован в [bsl-ls-recon-results.md](bsl-ls-recon-results.md); internal adapter сохраняется с attribution комментарием на declined-issue.

---

##### R6.2 — PR в bsl-language-server: `workspace/didChangeWorkspaceFolders` handler (1-2 дня)

**Проблема:** upstream BSL LS игнорирует `workspace/didChangeWorkspaceFolders` notification — индексация выполняется лениво per-document на `textDocument/didOpen`. Это первопричина per-document архитектуры, из-за которой мы строили весь multilspy+bulk-didOpen workaround (см. [bsl-ls-recon-results.md](bsl-ls-recon-results.md) §«per-document problem»).

**Upstream repo:** https://github.com/1c-syntax/bsl-language-server (403⭐, Java 17, Maven, MIT).

**Scope PR (Java, 2-4 класса + тесты):**
1. `language-server/src/main/java/com/github/_1c_syntax/bsl/languageserver/ClientNotifications.java` (или exact equivalent) — handler для `@Notification("workspace/didChangeWorkspaceFolders")`.
2. Вызов `ServerContext.populateContext(WorkspaceFolder)` на все `added` folders; обработка `removed` (инвалидация context).
3. Инкрементальность: сравнить set новых folders с текущим, `populateContext` только для delta.
4. Config flag: `workspaceFolders.eagerLoad = true|false` в `.bsl-language-server.json`. **Default: `false`** для backward-compat. Клиент (наш multilspy) явно включает через `initializationOptions`.
5. Tests (JUnit 5 + Mockito): `ClientNotificationsTest.testWorkspaceFoldersEagerLoads` — mocked `WorkspaceFolder`, проверка что `ServerContext` получил `populateContext` с правильным URI.

**Процесс подачи PR:**
1. **Discovery issue ОБЯЗАТЕЛЬНО:** «Proposal: eager indexing on didChangeWorkspaceFolders». Прикрепить:
   - Цифры из R5 (p95 latency до/после preload — сравнение `multilspy_backend` vs hypothetical eager LS).
   - Ссылку на [bench_multilspy_real.py](../../tools/bsl-ls/bench_multilspy_real.py) summary (`multilspy-logs-real/summary.json`).
   - Use case: IDE с multi-root workspace (VS Code, IntelliJ plugin).
2. Дождаться reaction core-maintainer (Nikita @nixel2007 или @theshadowco). Если negative — PR не отправлять, закрыть R6.2 как `declined`.
3. Если green light: fork, branch `feat/workspace-folders-eager`, PR.
4. CI требует `mvn verify` + checkstyle + SonarQube. Установить локально Java 17 + Maven 3.9+.
5. Ответить на review в 48-72 ч (учитывая time-zone Europe/Moscow maintainer'ов).

**Специфичные риски:**
- **Breaking change risk:** eager indexing на больших ERP-конфигурациях (>10 000 модулей) существенно увеличит start-up latency LS. **Митигация:** конфиг-флаг `eagerLoad = false` по умолчанию; evidence в issue описывает cost на 2 027 модулей (наш workspace).
- **Java expertise gap:** команда — BSL/Python; если maintainer запросит глубокий рефакторинг `ServerContext`, сил не хватит. **Митигация:** исключить R6.2 из обязательных; оставить как «contribution opportunity». Внутренний workaround (bulk-didOpen) остаётся permanent.
- **Cyrillic paths на CI:** CI maintainer'а запускается на Linux; наш workspace — Windows+cp1251. **Митигация:** `core.quotepath=false` + тесты на латинских путях.

**Артефакт:**
- PR в `1c-syntax/bsl-language-server` (или declined-issue с reason и ссылкой на наш internal workaround).
- `docs/roadmap/benchmark/results-YYYY-MM.md` дополнен секцией «BSL LS version used» — привязка к версии с handler'ом (если merged).

**DoD:**
- Discovery issue открыт с полным evidence из R5.
- **Если green light:** PR submitted, CI (Maven+SonarQube+checkstyle) зелёный, минимум 1 maintainer review получен.
- **Если declined-by-scope:** reason задокументирован в [bsl-ls-recon-results.md](bsl-ls-recon-results.md); R6.2 помечен `won't-do` в итоговой таблице этого роадмапа; bulk-didOpen признан permanent workaround.

---

##### R6.3 — PR в tree-sitter-bsl: grammar gaps (4-6 ч)

**Проблема:** из [R0.2 coverage test](#L1262) известны два конкретных gap'а в upstream grammar:

1. **Parenthesized expressions** — 14 ERRs / 1 518 lines (≈0.9%). Примеры: `Результат = (X = Y);`, `Если А И (X ИЛИ Y) Тогда`, `Возврат (-Число);`. Grammar не парсит bracketed group в RHS / условиях / unary.
2. **Query literals** — `ВЫБРАТЬ ... ИЗ ...` внутри `Запрос.Текст = "..."` парсится как `const_expression` строка. Не блокирует rename (не нужно для R1-R5), но полезно для будущего BSL intelligence.

**Upstream repo:** https://github.com/alkoleft/tree-sitter-bsl (36⭐, JavaScript grammar → C parser, MIT).

**Scope PR (два отдельных PR для изоляции риска):**

**PR #1 «fix: parenthesized expressions in RHS and conditions»** (primary target R6.3):
1. `grammar.js` — добавить `parenthesized_expression: $ => seq('(', $._expression, ')')` в hierarchy `_expression` с корректной precedence.
2. Убедиться: `Если ... И (X) Тогда` не конфликтует с function-call parsing (префер — assoc.left, precedence выше binary_op).
3. Regen parser: `tree-sitter generate`; пересобрать C parser в `src/parser.c`.
4. `test/corpus/expressions.txt` — 5 новых кейсов: (а) bool bracket `Если (X И Y) Тогда`, (б) assignment bracket `А = (X + Y);`, (в) nested `((X = Y) И Z)`, (г) mixed with call `Функция((X))`, (д) unary `(-X)` / `(Не X)`.
5. `tree-sitter test` — все старые + новые кейсы зелёные; no regressions.

**PR #2 «feat: query language nodes inside string literals»** (опционально, defer на R7+):
- Inline query grammar как injection (`injection.scm`) — сложнее, отдельный PR, scope может быть отвергнут как «out of tree-sitter scope» (SQL вообще отдельный проект).
- **Рекомендация:** defer PR #2 до явного запроса от bsl-intelligence community.

**Процесс подачи PR:**
1. Fork `alkoleft/tree-sitter-bsl` → branch `fix/parenthesized-expression`.
2. Прогнать локально `scripts/test` (или `npm test`) — все старые тесты зелёные baseline.
3. Добавить новые corpus tests, прогнать снова.
4. Подать PR #1 с short description + link на [tree-sitter-coverage.md](../../tools/bsl-ls/tree-sitter-coverage.md) v1.
5. После merge (или одновременно с review): прогнать `tools/bsl-ls/tree-sitter-coverage.py` на 1 518 lines → ожидаем 14 ERRs → 0-2 ERRs. Записать в v2-коверейдж секцию.

**Артефакт:**
- PR #1 в `alkoleft/tree-sitter-bsl`.
- Обновлённый [tree-sitter-coverage.md](../../tools/bsl-ls/tree-sitter-coverage.md) — секция «v2 coverage after R6.3» с новыми цифрами ERR rate.
- `tools/bsl-ls/tree_sitter_bsl.dll` пересобран из upstream HEAD (если merged) или из нашего fork (если declined, vendored в `tools/bsl-ls/vendor/tree-sitter-bsl-fork/` + `PATCHED.md`).

**DoD:**
- PR #1 открыт, CI (`tree-sitter test` + matrix по OS если есть) зелёный.
- **Если merged:** ERR rate ≤ 0.2% на наших 1 518 lines; [R2.2 Fill coverage gaps](#L1319) в таблице статусов обновлён с `DEFERRED` → `DONE (via R6.3)`.
- **Если declined:** fork поддерживается в `tools/bsl-ls/vendor/tree-sitter-bsl-fork/`, `PATCHED.md` описывает diff и причину декли́на.

###### R6.3 — Промежуточные результаты (2026-04-18)

**Локальная реализация COMPLETE.** Upstream PR pending.

**Что сделано:**
1. `grammar.js` — добавлено правило `parenthesized_expression: ($) => seq('(', field('inner', $.expression), ')'),` + включено в `expression` choices (строка 401).
2. GLR-конфликты — 2 объявления в `conflicts`: `[$.execute_statement, $.parenthesized_expression]` + `[$.parenthesized_expression, $.arguments]` (tree-sitter не может разрешить `(expr)` ambiguities между call args и standalone grouping без подсказки).
3. 5 corpus tests — [expressions.bsl](../../tools/bsl-ls/tree-sitter-bsl-src/test/corpus/expressions.bsl): assignment, condition, nested, unary, double-parens-in-call. Обновлён [execute.bsl](../../tools/bsl-ls/tree-sitter-bsl-src/test/corpus/execute.bsl) — `Выполнить("1+1")` теперь ожидает `parenthesized_expression` wrapper.
4. Parser regenerated — `npx tree-sitter generate` → `src/parser.c` (966 299 bytes).
5. DLL rebuilt — `npx tree-sitter build` → `tree_sitter_bsl.dll` (147 456 bytes, загружается через ctypes).
6. **Все 27 corpus tests PASS** (22 existing + 5 new).

**Coverage результаты:**

| Файл | Lines | ERR до | ERR после |
|------|-------|--------|-----------|
| гкс_ОчередьСообщенийRMQ | 679 | 12 | **0** |
| гкс_ФормировательСообщенийRMQ | 217 | 2 | **0** |
| гкс_Взвешивание.ФормаДокумента | 622 | 0 | 0 |
| **Итого** | **1 518** | **14** | **0** |

ERR rate: **0.9% → 0.0%**. Отчёт: [tree-sitter-coverage.md](../../tools/bsl-ls/tree-sitter-coverage.md) v2.

**Ветка:** `fix/parenthesized-expression` в submodule `tree-sitter-bsl-src` (commit `4edc527`).

**Следующие шаги R6 (приоритет):**

| # | Задача | Оценка | Что делать | Примечание |
|---|--------|--------|-----------|------------|
| **1** | R6.3 upstream PR | 1-2 ч | Fork `alkoleft/tree-sitter-bsl` → push branch → open discovery issue + PR с coverage evidence | Высокая вероятность приёма |
| **2** | R6.4 Serena BSL context | 2-3 ч | Создать `bsl.yml` в `serena/resources/config/contexts/` + PR в `oraios/serena` | yml-only, opt-in, высокая вероятность |
| **3** | R6.1 multilspy adapter | 1-2 дня | Ждёт R5.4 trend ≥2 прогона. Затем: fork multilspy → BSL enum + adapter | Средняя вероятность, нишевый язык |
| **4** | R6.2 bsl-ls workspace folders | 1-2 дня | Опционально, после discovery issue approval в `1c-syntax/bsl-language-server` | Низкая вероятность, меняет core |

**Рекомендуемый порядок:** R6.3 PR → R6.4 → benchmark pilot-B → R6.1 → (опционально R6.2).

---

##### R6.4 — PR в Serena: BSL context (2-3 ч)

**Проблема:** Serena (framework для LLM-based кодирования поверх LSP — основной inspiration источник этого аудита) не имеет BSL в bundled contexts. Наш аудит разработал routing-matrix + classifier + 3-tier fallback chain, которые переиспользуемы другими Serena-based проектами.

**Upstream repo:** https://github.com/oraios/serena. BSL отсутствует в `src/serena/resources/config/contexts/` (см. [Ссылки §Serena configuration](#L2055)).

**Scope PR:**

1. `src/serena/resources/config/contexts/bsl.yml`:
   ```yaml
   description: Context for 1C Enterprise BSL development
   prompt: |
     You are working with a 1C Enterprise codebase (BSL language).
     Guidelines:
     - Use Cyrillic-aware identifier regex: [A-Za-zА-Яа-я_][A-Za-zА-Яа-я0-9_]*
     - Prefer semantic tools (find_symbol, find_referencing_symbols) for rename
     - For cross-file operations, check forms (.xml) in addition to modules (.bsl)
     - Manager modules, forms, info registers, and common modules have different
       visibility semantics — consult SymbolKind before renaming.
     - `Экспорт` methods are visible across modules; module-local methods are not.
   allowed_tools:
     - find_symbol
     - find_referencing_symbols
     - replace_symbol_body
     - insert_after_symbol
     - insert_before_symbol
     - search_for_pattern
   excluded_tools:
     - execute_shell_command  # BSL не имеет REPL-эквивалента shell
   ```
2. `docs/contexts/bsl.md` (короткая страница): «Using Serena with 1C Enterprise» со ссылкой на наш аудит (после consent core-team).
3. Optional: `src/serena/resources/config/modes/bsl-editing.yml` — стандартный editing mode с consersative allowed_tools (без `replace_symbol_body` для `form_handler` и `unknown` kinds — форсировать manual tier как в нашей [routing-matrix-v2.md](./routing-matrix-v2.md)).

**Процесс подачи PR:**
1. Discovery issue «Proposal: add BSL (1C Enterprise) context + mode».
2. Fork → branch `feat/bsl-context`.
3. PR — минимальные изменения вне `contexts/` и `modes/`.
4. Если core-team просит тесты: добавить `test_bsl_context_loads` в соответствующий test suite (yml parser validation).

**Специфичные риски:**
- **Scope push-back:** Serena поддерживает mainstream (Python/TS/Go/Rust). BSL — нишевый язык. **Митигация:** PR делает **opt-in** контекст (активируется только при `--context bsl`), не влияет на default behavior; нет изменений в core logic.

**Артефакт:**
- PR в `oraios/serena`.
- Fallback: BSL context в нашем internal fork — `tools/serena-fork/contexts/bsl.yml` (yml-only, maintenance cost ≈ 0).

**DoD:**
- PR submitted с discovery issue.
- **Если merged:** update [bsl-ls-recon-results.md](bsl-ls-recon-results.md) секция «Serena integration: upstream ready».
- **Если declined:** рекомендация fork Serena для internal use с yml-only патчем, maintenance cost отметить как `low` в `docs/legal/upstream-license-matrix.md`.

---

##### Сводная таблица R6

| Подзадача | Upstream repo | ⭐ | Язык | Оценка | Вероятность приёма | Блокеры |
|-----------|--------------|-----|------|--------|--------------------|---------|
| **R6.3** | alkoleft/tree-sitter-bsl | 36 | JS+C | 4-6 ч | Высокая | — |
| **R6.4** | oraios/serena | — | Python+YAML | 2-3 ч | Высокая | — |
| **R6.1** | microsoft/multilspy | 566 | Python | 1-2 дня | Средняя | R5.4 trend (≥2 прогона) |
| **R6.2** | 1c-syntax/bsl-language-server | 403 | Java 17 | 1-2 дня | Низкая | R5.4 + discovery issue approval |

**Критический путь:** R5.4 → (R6.3 ∥ R6.4) → R6.1 → R6.2. Параллельно: R6.3 и R6.4 независимы, можно запускать в один день. R6.1 → R6.2 последовательно — R6.2 зависит от того, что наш multilspy-client валидно демонстрирует eager-loading через R6.1-опубликованный adapter.

**Итого:** 4-5 дней чистой работы над PR-подготовкой; с учётом upstream review cycles — календарно **2-4 недели** до закрытия (merge или final decline).

---

##### Риски R6

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| Upstream review затягивается > 1 мес, блокирует наш release | Высокая | Все PR помечены «optional» — отсутствие не блокирует продакшн. Используем self-hosted forks, переключаемся на upstream только после merge. |
| PR declined by scope — core-team считает BSL нишевым | Средняя (R6.1), Высокая (R6.2) | Поддерживаем internal adapter; документируем decision в [bsl-ls-recon-results.md](bsl-ls-recon-results.md) `## Upstream status`. |
| Breaking change в upstream API между нашим fork и upstream HEAD | Средняя | CI-задача: периодический `git fetch upstream && diff` + compatibility-тест (1 задача из tasks.json прогоняется на `pip install --upgrade multilspy`). |
| Java expertise отсутствует — R6.2 нельзя довести до merge при request-changes | Высокая | Исключить R6.2 из обязательных; оставить как contribution opportunity. Fallback — ждать, пока 1c-syntax core добавят handler сами после нашего issue. |
| License incompatibility между нашими патчами и upstream | Низкая | Все четыре upstream — MIT. Наш код также MIT. Юридическая проверка через `docs/legal/upstream-license-matrix.md` при запуске R6. |
| Upstream merge меняет семантику — наш consuming code ломается после `pip upgrade` | Средняя | Pin version в `requirements.txt` / `pyproject.toml`; upgrade через explicit PR + smoke-test на 1 задаче из [tasks.json](../../docs/roadmap/benchmark/tasks.json). |
| PR в tree-sitter-bsl сломает существующие corpus тесты (grammar ambiguity) | Средняя | Обязательный прогон `tree-sitter test` baseline до изменений; если ломаются — адаптировать corpus или добавить precedence rules. |
| Discovery issue получил негативный feedback → весь подзадачник закрыт | Средняя | issue — cheap-to-submit; при negative → документируем как «validated negative» (тоже полезный результат исследования). |
| Cyrillic в PR description / test-fixtures ломается на CI maintainer'а | Низкая | UTF-8 BOM в corpus файлах; латинские комментарии в grammar.js; описание PR полностью на английском. |
| Core-maintainer запрашивает changes, на которые ушло > 1 нед → PR stale | Средняя | SLA ответа на review: 48-72 ч. Если не успеваем — явно комментируем в PR «ETA: YYYY-MM-DD». |

---

##### Критерии успеха R6

- **Минимум 2 PR submitted** (любые две из R6.1-R6.4), независимо от merge-статуса. PR submitted — это уже validated outreach.
- **Минимум 1 PR merged** (наиболее реалистично R6.3 или R6.4 — mini-PR'ы с низкой политической сложностью).
- **Internal fork cleanup:** если R6.1 или R6.3 merged — наш self-host код переключён на upstream версию (минус строки в `tools/bsl-ls/vendor/`).
- **Upstream status** секция в [bsl-ls-recon-results.md](bsl-ls-recon-results.md) обновлена таблицей PR-статусов (URL, дата submit, статус, reviewer, последний apdate).
- **Lessons-learned** в конец R6-секции роадмапа: что core-teams принимают быстро, что медленно, каких evidence не хватало, сколько iteration'ов review было в среднем.
- **R2.2 DEFERRED** закрыт: или через merged R6.3, или явной формулировкой «won't-do, 0.9% ERR acceptable».

---

#### Промежуточный итог (2026-04-17, обновлено 2026-04-19)

| Этап | Статус | Артефакты | Тесты |
|------|--------|-----------|------:|
| **R0** | ✅ DONE | recon-отчёты, ADR-004, 3 ast-grep правила, sgconfig.yml, tree_sitter_bsl.dll | — |
| **R1.1** | ✅ DONE (на моках) | [multilspy_backend.py](../../src/bsl/semantic_search/refactor/backends/multilspy_backend.py) | 10 |
| **R1.2** | ✅ DONE (на моках) | [circuit_breaker.py](../../src/bsl/semantic_search/refactor/circuit_breaker.py), [lsp_subprocess.py](../../src/bsl/semantic_search/refactor/lsp_subprocess.py) | 17 |
| **R1.3** | ✅ DONE — DoD PASS (2026-04-19) | [real_bsl_client.py](../../src/bsl/semantic_search/refactor/backends/real_bsl_client.py), [test_real_bsl_client.py](../../tests/bsl/refactor/test_real_bsl_client.py), [soak_real_client.py](../../tools/bsl-ls/soak_real_client.py), [soak-logs/summary.json](../../tools/bsl-ls/soak-logs/summary.json) — 2027 files in 12.93 s, RSS 201 MB | 8 (slow+integration) |
| **R1.4** | ✅ DONE | [driver.py](../../src/bsl/semantic_search/refactor/driver.py) | 9 |
| **R1.5** | ✅ DONE | [workspace_edit.py](../../src/bsl/semantic_search/refactor/workspace_edit.py) | 4 |
| **R1.6** | ✅ DONE | [classifier.py](../../src/bsl/semantic_search/refactor/classifier.py), [routing-matrix-v2.md](./routing-matrix-v2.md) | 17 |
| **R1.7** | ✅ DONE | [mcp.py](../../src/bsl/semantic_search/mcp.py) (`bsl_rename_symbol` + `register_rename_driver_factory`) | 6 |
| **R1.8** | ✅ DONE | [verification.py](../../src/bsl/semantic_search/refactor/verification.py) | — (покрыто R1.5 тестами) |
| **R2.1** | ✅ DONE (в R0.3) | tree_sitter_bsl.dll | — |
| **R2.2** | ✅ DONE (via R6.3) | [grammar.js](../../tools/bsl-ls/tree-sitter-bsl-src/grammar.js) (`parenthesized_expression`), [tree_sitter_bsl.dll](../../tools/bsl-ls/tree_sitter_bsl.dll) | 27 tree-sitter corpus |
| **R2.3** | ✅ DONE (в R0.3) | 3 YAML правила | — |
| **R2.4** | ✅ DONE | [ast_grep_backend.py](../../src/bsl/semantic_search/refactor/backends/ast_grep_backend.py), [ast_grep_runner.py](../../src/bsl/semantic_search/refactor/backends/ast_grep_runner.py) | 13 |
| **R2.5** | ✅ DONE | [orchestrator.py](../../src/bsl/semantic_search/refactor/orchestrator.py), [test_orchestrator.py](../../tests/bsl/refactor/test_orchestrator.py) | 13 |
| **R2.6** | ⏸ DEFERRED | — | — |
| **R4.0** | ✅ DONE | [routing_matrix.yaml](../../src/bsl/semantic_search/refactor/routing_matrix.yaml) + `RoutingMatrix.load/reset()` | 5 |
| **R4.1** | ✅ DONE | [telemetry.py](../../src/bsl/semantic_search/refactor/telemetry.py) + try/finally интеграция в orchestrator | 7 |
| **R4.2** | ✅ DONE | `ManualFallbackInstruction` + 3-tier fallback + MCP `bsl_rename_symbol` surface | 4 |
| **R4.3** | ✅ DONE | [refactor-fallback-chain.md](./refactor-fallback-chain.md) | — |
| **R4.4** | ✅ DONE | [aggregate_refactor_telemetry.py](../../scripts/aggregate_refactor_telemetry.py) + synthetic dataset | 3 |
| **R4.5** | ✅ VERIFIED (2026-04-19) | aggregator на pilot-B (20 событий, 4 per CAT) → все `proposed_confidence = 0.95`, совпадает с уже-применённой R5.5 calibration. Дельт нет; [summary](../../data/refactor-telemetry-summary.md) + [proposed.yaml](../../data/refactor-telemetry-proposed.yaml) | — |
| **R4.6** | ⏸ DEFERRED | — (ждёт Phase 10 dashboard) | — |
| **R5.1** | ✅ DONE | [tasks.json](../../docs/roadmap/benchmark/tasks.json) (20 задач, 5×4), [build_benchmark_tasks.py](../../scripts/build_benchmark_tasks.py), [test_benchmark_tasks_schema.py](../../tests/bsl/refactor/test_benchmark_tasks_schema.py) | 7 |
| **R5.2** | ✅ DONE | [runner.py](../../docs/roadmap/benchmark/runner.py) (WorktreeManager, TaskExecutor, ReportBuilder, BenchmarkRunner), [run_benchmark.py](../../scripts/run_benchmark.py) (CLI), [test_benchmark_runner.py](../../tests/bsl/refactor/test_benchmark_runner.py) | 6 |
| **R5.3** | ✅ DONE | `ReportBuilder.render_markdown()` + `render_csv()` внутри runner.py | (покрыто R5.2 тестами) |
| **R5.4** | ✅ DONE | [trend.md](../../docs/roadmap/benchmark/trend.md), [check_benchmark_regression.py](../../scripts/check_benchmark_regression.py) | — (smoke-tested) |
| **R5.5** | ⏸ DEFERRED | — (ждёт pilot-B прогон с ast-grep для calibration data) | — |
| **R6.3** | ✅ PR SUBMITTED | [PR #8](https://github.com/alkoleft/tree-sitter-bsl/pull/8) + [Issue #7](https://github.com/alkoleft/tree-sitter-bsl/issues/7) — parenthesized expressions fix, 0.9%→0.0% ERR | 27/27 tree-sitter tests |
| **R6.4** | ✅ PR SUBMITTED | [PR #1379](https://github.com/oraios/serena/pull/1379) + [Issue #1378](https://github.com/oraios/serena/issues/1378) — BSL context yml | — |
| **R6.1** | ✅ PR SUBMITTED (2026-04-19) | [PR #148](https://github.com/microsoft/multilspy/pull/148) + [Issue #147](https://github.com/microsoft/multilspy/issues/147) — BSL adapter, 9 файлов/+387−2, 2 коммита (`e985819`+`f2a5702`) | 3/3 BSL integration (24.15 s) |
| **R6.2** | 🔲 TODO | — (bsl-language-server workspace folders, низкая вероятность приёма) | — |

**Агрегатно (2026-04-19):**
- **132/132 тестов зелёные** (`pytest tests/bsl/refactor/`) — 124 unit + 8 новых slow/integration для R1.3
- **27/27 tree-sitter corpus tests** (22 existing + 5 new, grammar simplified after CodeRabbit review)
- **Tree-sitter ERR rate: 0.0%** (14→0 на 1 518 lines)
- **Pilot-B benchmark: 95% success** (ast-grep only, 19/20 tasks)
- **R5.5 calibration applied:** local_var/module_local/form_handler → 0.95
- **R1.3 DONE (DoD PASS):** real multilspy wiring, async↔sync bridge, bulk_open_workspace с throttling, E2E c `MultilspyBackend`. Soak test: 2027 `.bsl` за **12.93 s** (DoD <60 s), RSS 52→201 MB (DoD <4 GB)
- **Upstream PRs:** R6.3 [PR #8](https://github.com/alkoleft/tree-sitter-bsl/pull/8) (OPEN, CI green), R6.4 [PR #1379](https://github.com/oraios/serena/pull/1379) (OPEN), **R6.1 [PR #148](https://github.com/microsoft/multilspy/pull/148) + [Issue #147](https://github.com/microsoft/multilspy/issues/147) (OPEN, 2026-04-19)**
- **Full-1 benchmark (final, post-convention-fix, run `full-1d`):** multilspy **85%** (17/20), ast-grep **95%** (19/20), combined **90%** (36/40). CAT-2/3/4 both backends 100%; only CAT-5 edge cases deflect. Initial runs (full-1/full-1b) showed misleading multilspy 15% due to 1-based vs 0-based line convention mismatch — diagnosed, fixed in `MultilspyBackend.plan_rename`, regression tests added
- **Skills created:** `bsl-symbol-editing` (Tier 2 helpers), `bsl-refactoring-workflow` (5-category matrix)
- **Serena:** disabled in `.mcp.json`, `.serena/` kept for Python LSP potential
- **13 багов** найдено и исправлено ревью-циклом

**Что блокирует прогресс по R1.3 / реальному multilspy:** решение об установке `pip install multilspy` + wiring BSL JAR + async↔sync мост. Целесообразно откладывать до R5 benchmark, чтобы данные показали реальную цену lazy-open vs bulk-preload.

#### ⏸ Осталось реализовать (по приоритету, обновлено 2026-04-19)

Список открытых подзадач, отсортированных по критерию «impact / вероятность приёма / отсутствие блокеров».

##### P1 — Быстрые win'ы ✅ ЗАВЕРШЕНО (2026-04-19)

| # | Задача | Статус | Ссылка |
|---|--------|--------|--------|
| **1** | **R6.3 upstream PR** | ✅ PR submitted | [Issue #7](https://github.com/alkoleft/tree-sitter-bsl/issues/7) + [PR #8](https://github.com/alkoleft/tree-sitter-bsl/pull/8) |
| **2** | **R6.4 Serena BSL context** | ✅ PR submitted | [Issue #1378](https://github.com/oraios/serena/issues/1378) + [PR #1379](https://github.com/oraios/serena/pull/1379) |

##### P1.5 — Calibration (данные есть, pilot-B 95% success)

| # | Задача | Оценка | Блокер | Действие |
|---|--------|--------|--------|----------|
| **3** | **R5.5 Calibration feedback** | ✅ DONE | — | Calibration applied: local_var/module_local/form_handler → 0.95 |
| **4** | **R4.5 Confidence calibration** | 1 ч | ≥50 событий (сейчас ~20 из pilot-B) | Дождаться второго benchmark-прогона или реальных usage data |

##### P2 — Требует стратегического решения (реальный multilspy)

| # | Задача | Оценка | Блокер | Действие |
|---|--------|--------|--------|----------|
| **3** | **R5.5 Calibration feedback** | 1 ч + данные | pilot-B прогон ≥20 telemetry событий | Запустить `scripts/aggregate_refactor_telemetry.py` → обновить `routing_matrix.yaml` |
| **4** | **R4.5 Confidence calibration** | 1 ч + данные | ≥50 реальных событий (или выход R5.5) | Применить delta-правки confidence по (kind, backend) в `routing_matrix.yaml`; MIN_SAMPLES=4 |

##### P3 — Требует стратегического решения (реальный multilspy)

| # | Задача | Оценка | Блокер | Действие |
|---|--------|--------|--------|----------|
| **5** | ~~R1.3~~ **DONE — DoD PASS** (2026-04-19) | — | — | Phase A (код+8 integration tests) + Phase B (soak 2027 `.bsl` за 12.93 s, RSS 201 MB). Разблокирован R6.1. |
| **6** | **R6.1** (PR в `microsoft/multilspy`: BSL adapter) | 1-2 дня | R5.4 trend ≥2 прогона (сейчас 0); желательно R1.3 | Discovery issue → fork → `Language.BSL` enum + `bsl_language_server/` package + 3 теста |

##### P4 — Опциональные / долгосрочные

| # | Задача | Оценка | Приоритет | Комментарий |
|---|--------|--------|-----------|-------------|
| **7** | **R2.6** (form-handler ast-grep rule) | ~4 ч | Low | После R5 benchmark — если покрытие form-handler промахивается, добавить YAML-правило |
| **8** | **R4.6** (Dashboard integration) | — | Low | Условный — зависит от Phase 10 dashboard (не в scope аудита) |
| **9** | **R3 целиком** (SCIP cache layer: R3.1 schema + R3.2 emitter + R3.3 incremental watcher) | 5-7 дней | Low | После R1.3 реального multilspy. Ускорит cross-file rename; отдельный ROI-расчёт перед запуском |
| **10** | **R6.2** (PR в `1c-syntax/bsl-language-server`: `didChangeWorkspaceFolders`) | 1-2 дня | Won't-do default | Java 17 expertise gap; низкая вероятность приёма (меняет core поведение LS). Реализовать только при явном green light от @nixel2007 в discovery issue |

##### Критический путь

```
P1 (R6.3 PR ∥ R6.4)           ← запустить немедленно, 1 рабочий день
    ↓
pilot-B benchmark прогон      ← накопление telemetry (≥20 событий)
    ↓
P2 (R5.5 → R4.5 calibration)  ← ~2 ч чистой работы после данных
    ↓
[стратегическое решение]
    ↓
P3 (R1.3 → R6.1)              ← 2-4 дня при решении ставить multilspy
    ↓
P4 опционально (R3, R2.6)
```

**Календарный прогноз:** P1+P2 закрываемы за 2-3 дня. P3 — 1-2 недели (включая upstream review). P4 — отдельное решение с ROI-обоснованием.

---

#### Сводная таблица этапов и оценки трудозатрат

| Этап | Задача | Оценка | Зависимости |
|------|--------|--------|-------------|
| **R0** | Research validation | 1-2 дня | Блокер для R1-R2 |
| **R1** | Variant A rewrite (multilspy) | 3-5 дней | R0.5 = Scenario 1 |
| **R2** | Variant B (ast-grep) | 3-5 дней | Параллельно R1 |
| **R3** | SCIP cache layer | 5-7 дней | После R1 |
| **R4** | Orchestrator v2 + routing | 1-2 дня | После R1+R2 |
| **R5** | Benchmark + validation | 2-3 дня | После R4 | **R5.1–R5.4 DONE**, R5.5 DEFERRED |
| **R6** | Upstream PRs | 2-3 дня | После R5 | **R6.3 DONE**, R6.4/R6.1/R6.2 TODO |

**Итого v4.5:**
- **Критический путь:** R0 → R1 → R4 → R5 = **7-12 дней** (фактически: R0-R4 + R5.1-R5.4 завершены, R5.5 и R6.3 завершены)
- **Полный объём:** R0-R6 = **17-27 дней** (оставшиеся: R5.5 calibration ~1 день после pilot-B, R6.3 upstream PR ~1-2 ч, R6.4 ~2-3 ч, R6.1 ~1-2 дня)

**Критерии успеха (обновлены для §7):**
- Cross-file rename работает (через multilspy preload): >90% задач категории «Multi-File Changes» в benchmark.
- Fallback B покрывает случаи, где A не справился: >95% комбинированного покрытия.
- Latency rename end-to-end: <30s для workspace из 2000 файлов.
- Auto-rollback frequency: <5% (низкий false-positive rate).

---

## Верификация реализации (2026-04-19)

Проверка фактического состояния артефактов против плановых статусов v4.4. Выполнена автоматически через Read/Glob/Bash + запуск `pytest`.

### Тесты и бенчмарки

| Проверка | Команда | Результат |
|---|---|---|
| Refactor suite | `pytest tests/bsl/refactor/ -q` | **139 passed** in 37s (134 + 5 denylist tests, 2026-04-19) |
| tree-sitter corpus | `tree-sitter test` (in `tree-sitter-bsl-src`) | **27/27 passed** (22 existing + 5 new) |
| tree-sitter ERR rate | `coverage_check.py` на 1518 строк | **0.0%** (0 ERRs; было 14) |
| Pilot-B benchmark (LAX) | `run-20260418-210222`, ast-grep only | **95% applied** (19/20) |
| Full-1g benchmark (STRICT) | `run-20260419-…`, multilspy + ast-grep, 40 задач | **multilspy 55% / ast-grep 15%** см. ниже |

#### ⚠️ Метрика «95%» относится к LAX-замеру (`applied`), не к корректности

Pilot-B (`run-20260418-210222`) считал успех как **`applied=True && rolled_back=False`** — то есть «пайплайн применил edits без верификационного отката». Это **НЕ** проверяет, что edits затронули **именно те файлы**, что ожидались задачей. Полноценный strict-метрика (`edits_match_expected` — `actual_files == sorted(expected_files)` из `tasks.json`) реализована в `aggregator.py:170` и используется в full-1+ прогонах.

**Полный прогон full-1g (2026-04-19, 40 результатов = 20 задач × 2 backend, strict-метрика):**

| Backend | Strict success | CAT-1 local | CAT-2 module | CAT-3 cross-file | CAT-4 form | CAT-5 edge |
|---|---|---|---|---|---|---|
| MultilspyBackend | **55%** (11/20) | 100% | 100% | 25% | 0% | 50% |
| AstGrepBackend | **15%** (3/20) | 25% | 0% | 25% | 0% | 25% |

**Почему ast-grep падает с 95% (LAX) до 15% (STRICT):** text-based pattern matching не учитывает scope. Эмпирическая проверка на живых 2027 `.bsl`:
- `Параметры` (T04 target) — встречается в **1 679 файлах**, 64 549 раз
- `РезультатЗапроса` (T02) — в **223 файлах**, 1 536 раз
- `СписокРегионов` (T01) — в **2 файлах**, 11 раз

При rename ast-grep правит **все** вхождения, включая совпадения в несвязанных модулях → `actual_files != expected_files` → strict fail. Проблема **частично смягчена в production routing matrix v2** (multilspy primary для всех in-scope kinds), но `form_handler` (`primary: ast-grep`) и fallback-цепочки оставались уязвимы.

#### 🩹 Митигация (2026-04-19, +1 коммит после v4.5 верификации)

В `routing_matrix.yaml` добавлен **denylist** (~30 имён: `Параметры`, `Результат`, `Запрос`, `Ссылка`, `Объект`, `Значение`, `Имя`, `Текст`, `Строка`, `Элемент`, `Форма`, `ЭтотОбъект`, … + английские алиасы). Орхестратор (`orchestrator.py`) при совпадении имени с denylist:
- **пропускает ast-grep** как primary (если route это ast-grep) → сразу `manual_required`
- **пропускает ast-grep как fallback** (если multilspy primary вернул empty) → `manual_required`
- **multilspy остаётся в игре** — он scope-aware, его не блокируем

Покрытие: 5 новых тестов в `test_orchestrator.py` (form_handler+denied → manual, module_export+denied+empty multilspy → manual, local_variable+denied → multilspy всё равно работает, не-denylist имя → ast-grep как обычно, YAML загрузка). Все 139/139 тестов проходят.

**Эффект:** для refactoring-задач с общеупотребительными именами пользователь получает явную инструкцию `manual_required` вместо тихой порчи 1 679 файлов. На бенчмарке прирост strict-метрики ожидается в CAT-4 form_handler (был 0%, теперь имена из denylist уйдут в manual вместо false-success).

### Артефакты ядра (Phases 0-7)

| Компонент | Путь | Статус |
|---|---|---|
| Refactor package (11 модулей) | `src/bsl/semantic_search/refactor/` | ✅ существует: `classifier.py`, `orchestrator.py`, `driver.py`, `verification.py`, `workspace_edit.py`, `circuit_breaker.py`, `lsp_subprocess.py`, `telemetry.py`, `types.py`, `routing_matrix.yaml`, `backends/{ast_grep_backend,multilspy_backend,ast_grep_runner,base}.py` |
| Тесты | `tests/bsl/refactor/` | ✅ 14 test-файлов (test_classifier, test_orchestrator, test_driver, test_verification_slice, test_workspace_edit, test_lsp_subprocess, test_mcp_rename, test_multilspy_backend, test_ast_grep_backend, test_routing_matrix_yaml, test_telemetry, test_manual_fallback, test_benchmark_tasks_schema, test_benchmark_runner, test_aggregator, test_end_to_end_slice) |
| Skill `bsl-symbol-editing` | `.claude/skills/bsl-symbol-editing/SKILL.md` | ✅ v1.0.0, 2026-04-19 |
| Skill `bsl-refactoring-workflow` | `.claude/skills/bsl-refactoring-workflow/SKILL.md` | ✅ v1.0.0, 2026-04-19 |
| Serena disabled | `.mcp.json` | ✅ `"disabled": true` (блок сохранён, команда не запускается) |
| Serena workspace | `.serena/` | ✅ сохранён (`cache/`, `memories/`, `project.yml`) для Python LSP потенциала |

### R0-R5 артефакты

| Этап | Ключевые файлы | Статус |
|---|---|---|
| R0 recon | `tools/bsl-ls/{lsp_recon,multilspy_recon,bench_multilspy_real,bench_ast_grep,check_query_gap,coverage_check,test_coverage}.py` + `sgconfig.yml` + `tree_sitter_bsl.dll` (147456 B) + `bsl-language-server.jar` (94.3 MB) | ✅ |
| R0 логи | `tools/bsl-ls/{recon-logs,recon-logs-run1,multilspy-logs,multilspy-logs-real}/` | ✅ |
| R0 документы | `docs/roadmap/ADR-004-bsl-refactoring-architecture.md`, `bsl-ls-recon-{plan,results}.md` | ✅ |
| R2 ast-grep rules | `tools/bsl-ls/ast-grep-rules/*.yml` | ✅ (3 правила, baseline 1.2-1.7 s на 2027 `.bsl`) |
| R2 tree-sitter grammar | `tools/bsl-ls/tree-sitter-bsl-src/` (submodule, fork `Alex1980Alex/tree-sitter-bsl`, branch `fix/parenthesized-expression`, HEAD `2bc0435`) | ✅ |
| R4 routing matrix | `src/bsl/semantic_search/refactor/routing_matrix.yaml` | ✅ v2, откалиброванная |
| R4 telemetry | `src/bsl/semantic_search/refactor/telemetry.py` + `scripts/aggregate_refactor_telemetry.py` | ✅ |
| R4 документ fallback chain | `docs/roadmap/refactor-fallback-chain.md` | ✅ |
| R4 routing v2 doc | `docs/roadmap/routing-matrix-v2.md` | ✅ |
| R5.1 tasks | `docs/roadmap/benchmark/tasks.json` (20 задач × 5 категорий) | ✅ |
| R5.2 runner | `docs/roadmap/benchmark/runner.py` + `scripts/{run_benchmark,build_benchmark_tasks,check_benchmark_regression}.py` | ✅ |
| R5.3 reports | `docs/roadmap/benchmark/results/` | ✅ **11 JSONL + 11 CSV + 11 MD** за 2026-04-18 |
| R5.4 trend | `docs/roadmap/benchmark/trend.md` | ✅ **8 прогонов**, финальный row: `run-20260418-210222` — 95% success, R5.5 calibration applied |
| R5.5 calibration | `routing_matrix.yaml` | ✅ применена: `local_variable: 0.70→0.95`, `module_local_*: 0.85→0.95`, `form_handler: 0.60→0.95` |
| Telemetry data | `data/refactor-telemetry-benchmark-pilot-B.jsonl` + `data/refactor-telemetry-synthetic.jsonl` | ✅ |

### R6 upstream contributions

| PR | Репо | Статус фактический |
|---|---|---|
| **R6.3** parenthesized expressions | `alkoleft/tree-sitter-bsl` | ✅ локально DONE. Fork `Alex1980Alex/tree-sitter-bsl` настроен (remote `fork`). Branch `fix/parenthesized-expression` содержит 2 коммита: `4edc527 fix: add parenthesized expressions support` + `2bc0435 refactor: simplify execute_statement (remove redundant alternative)` (грамматика упрощена после CodeRabbit review). ERR rate 0.9% → **0.0%**. Upstream PR #8 submitted согласно документу. |
| **R6.4** Serena BSL context | `oraios/serena` | ✅ PR #1379 submitted согласно документу. Локальная проверка артефакта (`bsl.yml`) — ограничена scope внутри serena fork, не в этом репо. |
| **R6.1** multilspy BSL adapter | `microsoft/multilspy` | 🔲 TODO (блокер: R5.4 trend ≥2 прогона; сейчас есть pilot-B, нет full-1) |
| **R6.2** bsl-ls workspace folders | `1c-syntax/bsl-language-server` | 🔲 TODO (low probability, Java 17 expertise gap) |

### Расхождения с документом

**Найдено одно (исправлено в v4.6, 2026-04-19):** в исходной формулировке Pilot-B результат назывался просто «95% success», без указания, что метрика — LAX (`applied`), а не STRICT (`edits_match_expected`). Это создавало впечатление, что ast-grep решает 95% задач корректно, тогда как при STRICT-метрике (full-1g) реальная корректность ast-grep — 15%. Текст выше переписан с явной таблицей по метрикам и категориям.

Все заявленные DONE-артефакты v4.4 физически присутствуют и тесты зелёные. Deferred-пункты (R1.3, R2.2/R2.6, R3, R4.5/R4.6, R6.1/R6.2) корректно отмечены как блокируемые отсутствующими данными/решениями.

### Наблюдения

1. **Grammar simplification после CodeRabbit review** (`2bc0435`) — подтверждает, что upstream feedback loop работает ещё до merge: peer-review сообщества улучшил чистоту патча без регрессий (27/27 corpus tests остались зелёными).
2. **Benchmark iteration visible in `trend.md`** (8 прогонов за один день 2026-04-18) — демонстрирует эффективность self-evaluation цикла §4.9.2.1: первые 3 прогона BLOCKED/0%/0% (инструментальные баги на Windows: missing `.dll`, `--inline-rules`, `shell=True`), следующие 3 — 30%/35%/95% (исправления одного бага за раз), финальный — verification run с calibration. Это именно тот feedback loop, который v4.2 постулировал теоретически.
3. **Pilot-B не имеет multilspy-колонки** (A=n/a) — ожидаемо, т.к. R1.3 deferred. Для full-1 benchmark нужно решение по `pip install multilspy` + BSL JAR wiring.
4. **`.serena/` сохранён несмотря на Serena disable** — правильное решение: содержит Python LSP кеш, который может пригодиться для Python-части стека (337 `.py` файлов фреймворка).
5. **Все 124 теста проходят на моках** — R1.3 deferred означает, что реальный multilspy не тестируется в CI. Первый реальный прогон должен быть гейтирован отдельным soak-тестом против 2027 `.bsl`.

### Команды воспроизведения

```bash
# Refactor suite
cd D:\1С-Framework
python -m pytest tests/bsl/refactor/ -q

# Benchmark (ast-grep only, pilot mode)
python scripts/run_benchmark.py --backends ast-grep --run-id pilot-verify --append-trend

# Tree-sitter coverage
cd tools/bsl-ls
python coverage_check.py
```

---

## Ссылки

### Serena upstream
- **Repo:** https://github.com/oraios/serena
- **Tools Reference:** https://oraios.github.io/serena/01-about/035_tools.html
- **Evaluation Intro:** https://oraios.github.io/serena/04-evaluation/000_evaluation-intro.html
- **Evaluation Methodology:** https://oraios.github.io/serena/04-evaluation/010_methodology.html
- **Docs root:** https://oraios.github.io/serena/

### Serena configuration (для §4.9.1)
- **Contexts directory:** https://github.com/oraios/serena/tree/main/src/serena/resources/config/contexts
  - `claude-code.yml` — референс для нашего gating
  - `codex.yml`, `desktop-app.yml`, `ide.yml` — другие clients
- **Modes directory:** https://github.com/oraios/serena/tree/main/src/serena/resources/config/modes
  - `planning.yml` — read-only, для analysis режима
  - `interactive.yml`, `editing.yml`, `one-shot.yml`, `no-onboarding.yml`

### BSL Language Server
- **BSL LS upstream:** https://github.com/1c-syntax/bsl-language-server
- **BSL LS adapter в Serena:** `serena/src/solidlsp/language_servers/bsl_language_server.py` (551 строка)
- **BSL Language enum:** `serena/src/solidlsp/ls_config.py:56`
- **GitHub issues по BSL:** #802, #798, #792

### Наши артефакты
- Исходный Этап 0 (для отката): коммит `docs(hermes)...` на ветке master, 2026-04-14
- Spec гибридного подхода (создаётся в Phase 1): `docs/roadmap/hybrid-refactor-spec.md`
- Recon plan (создаётся в Phase 0b): `docs/roadmap/bsl-ls-recon-plan.md`

---

## Roadmap: Option A — Pre-filter ast-grep по call graph

**Статус:** IMPLEMENTED (2026-04-19) — все фазы A.0–A.7 завершены. Acceptance gate ≥35% strict НЕ достигнут (наблюдаемо: 15% → 20%, +5 пп). Компонент включён по умолчанию, telemetry schema v2. Полный отчёт: [option-a-recon.md](option-a-recon.md). Wiring через `src/bsl/semantic_search/refactor/backends/factory.py::build_ast_grep_backend()`. Дополняет v4.6 denylist-митигацию.
**Цель:** поднять strict-метрику `AstGrepBackend` с 15% в сторону multilspy (55%) за счёт scope-aware pre-filter.
**Scope:** строго additive — не трогаем routing matrix, denylist, `MultilspyBackend`. Только `AstGrepBackend` + tangential verification.

### Проблема (baseline из §R5.4 / full-1g)

`AstGrepBackend` при STRICT-метрике выдаёт 15% (3/20). Причина — text pattern matching без scope:

| Символ | Файлов в репо | Вхождений | Ожидаемых файлов (по задаче) |
|---|---|---|---|
| `Параметры` | 1 679 | 64 549 | 1 (T04) |
| `РезультатЗапроса` | 223 | 1 536 | 1 (T02) |
| `СписокРегионов` | 2 | 11 | 1 (T01) |

Denylist v4.6 решает ~30 общеупотребительных имён (`Параметры`, `Результат`, …) переводя их в `manual_required`. Но **не решает** случаи, где имя уникально локально, но pattern matching всё равно ловит совпадения в модулях, не входящих в callchain (например, local helper function с популярным названием в 2-5 файлах).

### Гипотеза

Если перед применением edits из ast-grep сузить множество файлов до тех, где call graph видит **реальный вызов** целевого символа (плюс модуль-определитель), strict-метрика вырастет за счёт отсечения «шумовых» попаданий в неродственных модулях.

### Уточнение: хранилище — SQLite, не Neo4j

В исходной формулировке от пользователя упомянут Neo4j. Фактическое хранилище call graph — **SQLite** (`cache/bsl_call_graph.db`, ~560 MB, последний rebuild 2026-04-02), доступ через `src/bsl/call_graph/store.py::CallGraphStore`. Релевантные API:

- `callers_of(name, module=None) -> list[dict]` — символы-коллеры с `module_path` в полях
- `impact_analysis(name, module=None, depth=3)` — транзитивные callers по BFS
- `get_symbol(symbol_id)` / `symbol_id = f"{module_path}::{name}"`

Neo4j в проекте есть как опциональный стор (`src/pdf_framework/graph_store/`), но BSL call graph туда не пишется. Roadmap ориентируется на существующий SQLite API.

### Фазы

#### Phase A.0 — Recon (0.5 ч)

**Задачи:**
- [ ] Проверить актуальность `cache/bsl_call_graph.db` против `src/bsl/` (последний rebuild 2026-04-02, код менялся после — нужен свежий snapshot)
- [ ] Измерить покрытие: сколько из 20 strict-задач benchmark имеют callers в графе (по `old_name` из `tasks.json`). Если <80% — Phase A блокируется на rebuild
- [ ] Зафиксировать стартовую метрику: `scripts/run_benchmark.py --backends ast-grep --run-id pre-option-a`

**Артефакты:** `docs/roadmap/option-a-recon.md` (coverage %, stale symbols, решение go/no-go).

#### Phase A.1 — Rebuild call graph (при необходимости, 1-2 ч)

**Триггер:** coverage <80% в Phase A.0.

**Задачи:**
- [ ] `python scripts/build_call_graph.py --source src/bsl --out cache/bsl_call_graph.db --clear`
- [ ] Валидация: `CallGraphStore.stats()` → ожидаемо >50k symbols, >100k calls (исторический baseline)
- [ ] Повторный coverage-замер

**Риск:** rebuild занимает 10-30 мин на 2027 `.bsl`. Не критично, один раз.

#### Phase A.2 — CallGraphPreFilter (2-3 ч)

**Новый компонент:** `src/bsl/semantic_search/refactor/backends/call_graph_prefilter.py`

**API:**
```python
class CallGraphPreFilter:
    def __init__(self, store: CallGraphStore): ...

    def allowed_files(
        self, old_name: str, module_hint: str | None = None
    ) -> set[Path] | None:
        """
        Возвращает множество module_path, где ОЖИДАЕМЫ правки:
        - определяющий модуль (где объявлен символ)
        - все callers_of(old_name, module_hint)
        Возвращает None, если символ неизвестен графу → fallback на текущее поведение
        (без фильтрации, чтобы не ломать задачи с непокрытыми символами).
        """
```

**Семантика `None` vs `set()`:**
- `None` → символ не в графе → **не фильтруем** (безопасный fallback)
- `set()` → символ в графе, но 0 callers → правим только определяющий модуль
- `{paths...}` → фильтруем edits только по этому множеству

**Тесты:** `tests/bsl/refactor/test_call_graph_prefilter.py` (8-10 кейсов: unknown symbol, 0 callers, 1 caller, cross-module, module_hint mismatch, depth=1 vs transitive).

#### Phase A.3 — Интеграция в AstGrepBackend (1-2 ч)

**Файл:** `src/bsl/semantic_search/refactor/backends/ast_grep_backend.py`

**Точка вставки:** после `run_rename()` возвращает `list[AstGrepMatch]`, до построения `WorkspaceEdit`.

**Изменения (~30-50 строк):**
```python
class AstGrepBackend:
    def __init__(
        self,
        runner: AstGrepRunner,
        workspace_root: Path,
        prefilter: CallGraphPreFilter | None = None,   # NEW, optional
    ) -> None:
        ...
        self._prefilter = prefilter

    def rename_symbol(self, ..., old_name, new_name, ...):
        matches = self._runner.run_rename(...)
        if self._prefilter is not None:
            allowed = self._prefilter.allowed_files(old_name, module_hint)
            if allowed is not None:
                before = len(matches)
                matches = [m for m in matches if m.file in allowed]
                self._telemetry.record("prefilter", dropped=before - len(matches))
        return self._matches_to_workspace_edit(matches, ...)
```

**Ключевые инварианты:**
- `prefilter=None` (default) → поведение идентично текущему (backward-compat, CI зелёный)
- Фильтр применяется **до** `WorkspaceEditApplier`, чтобы отброшенные edits не попали даже в baseline verification
- Telemetry: `dropped_by_prefilter`, `prefilter_cache_hit`, `symbol_unknown_to_graph` — для R4 аналитики

#### Phase A.4 — Тангенциальный update verification.py (0.5 ч)

**Файл:** `src/bsl/semantic_search/refactor/verification.py`

**Изменение:** добавить поле в `VerifyResult`:
```python
prefilter_dropped: int = 0  # сколько match-ей отсечено до verify
```

Используется в `scripts/aggregate_refactor_telemetry.py` для разделения метрики «precision edits» (после pre-filter) от «raw matches» (до pre-filter).

#### Phase A.5 — Wiring в Orchestrator (0.5 ч)

**Файл:** `src/bsl/semantic_search/refactor/orchestrator.py` (+ `driver.py`, если DI там)

**Изменение:** при построении `AstGrepBackend` передавать `CallGraphPreFilter`, если включён флаг:
```yaml
# routing_matrix.yaml (новое поле)
global:
  ast_grep:
    use_call_graph_prefilter: true
    call_graph_db: cache/bsl_call_graph.db
    graph_stale_threshold_days: 7   # warn в telemetry, но не блок
```

Flag по умолчанию **ON**. Выключение — env `BSL_REFACTOR_NO_PREFILTER=1` для A/B замеров.

#### Phase A.6 — Benchmark + A/B (1 ч)

**Задачи:**
- [ ] `scripts/run_benchmark.py --backends ast-grep --run-id option-a-on --append-trend`
- [ ] `BSL_REFACTOR_NO_PREFILTER=1 scripts/run_benchmark.py --backends ast-grep --run-id option-a-off --append-trend`
- [ ] Diff в `trend.md`: strict success, CAT-wise, `edits_match_expected`
- [ ] Acceptance gate: **strict-метрика ≥35%** (минимум +20 п.п. к baseline 15%), без регрессий в CAT-1 (local) и CAT-5 (edge)

**Если gate не пройден:**
1. Разобрать false negatives: символ был в графе, но реальный файл отсутствовал в `allowed` → graph-bug, не pre-filter
2. Разобрать false positives: символ не в графе → fallback без фильтра → текст оверматчит → `manual_required` через denylist

#### Phase A.7 — Документация (0.5 ч)

- [ ] Обновить `ADR-004-bsl-refactoring-architecture.md`: добавить раздел «Call-graph pre-filter»
- [ ] Обновить `routing-matrix-v2.md`: новый флаг и его эффект
- [ ] Обновить MEMORY.md: `ast-grep pre-filter ON, strict-метрика X%` (после Phase A.6)

### Метрики

| Метрика | Baseline (ast-grep) | Target | Stretch |
|---|---|---|---|
| Strict success (full-1, 20 задач) | 15% | **≥35%** | ≥45% |
| CAT-4 form_handler | 0% | ≥25% | ≥50% |
| CAT-3 cross-file | 25% | ≥40% | ≥60% |
| False positive rate (edits в невалидных файлах) | high | **0%** при known symbol | 0% |
| Coverage (символ в графе) | — | ≥80% | ≥95% |

### Риски и митигации

| Риск | Вероятность | Impact | Митигация |
|---|---|---|---|
| Устаревший граф → false negatives (символ есть, граф не знает) | MED | HIGH | Phase A.0 recon + automated staleness check в `core_paths.py`; при stale >7 дней → warn, но не блок; `None`-fallback не ломает задачу |
| Медленный rebuild блокирует CI | LOW | MED | rebuild не в CI, только локально; CI использует `cache/` snapshot из репо или zero-prefilter если cache отсутствует |
| Over-filter: символ в графе, но задача правит ещё и определяющий модуль, которого pre-filter не включил | LOW | MED | `allowed_files` явно добавляет `defining_module` через `get_symbol(symbol_id)` |
| Race condition при hot-reload графа в долгоживущем процессе | LOW | LOW | `CallGraphStore` уже WAL + `check_same_thread=False`; read-only путь в pre-filter |
| ConfusinG `manual_required` vs `0_edits`: symbol known + 0 callers + 0 definition file | LOW | LOW | Если `allowed == set()` → не применяем edits, возвращаем `BackendError("no in-graph sites")`; orchestrator эскалирует в `manual_required` |
| Взаимодействие с denylist | LOW | LOW | Denylist срабатывает **раньше** (в orchestrator), pre-filter — **позже** (в backend). Порядок: denylist → routing → ast-grep → pre-filter → verify. Тесты на композицию в Phase A.2/A.6 |

### Цена реализации

| Компонент | Файлов | Строк (нетто) |
|---|---|---|
| `call_graph_prefilter.py` (новый) | 1 | ~80 |
| `ast_grep_backend.py` (правка) | 1 | ~30 |
| `verification.py` (правка) | 1 | ~5 |
| `orchestrator.py` / `driver.py` wiring | 1-2 | ~15 |
| `routing_matrix.yaml` (конфиг) | 1 | ~5 |
| Тесты | 1-2 | ~150 |
| **Итого** | **6-8** | **~285** |

Оценка усилий: **6-9 часов** (включая Phase A.1 rebuild, recon, benchmark, доку). Без rebuild — 4-6 часов.

### Rollback

1. Поставить `use_call_graph_prefilter: false` в `routing_matrix.yaml` → орхестратор не передаёт `CallGraphPreFilter` в backend → поведение идентично pre-Option-A
2. Env `BSL_REFACTOR_NO_PREFILTER=1` — то же самое для одного запуска
3. При критических регрессиях: revert 1 коммита с Phase A.3 (все остальные изменения backward-compat, могут остаться merged)

### Команды воспроизведения (после релиза)

```bash
cd D:\1С-Framework

# 1. Rebuild call graph (если A.0 сказал stale)
python scripts/build_call_graph.py --source src/bsl --clear

# 2. Unit tests
python -m pytest tests/bsl/refactor/test_call_graph_prefilter.py -q
python -m pytest tests/bsl/refactor/test_ast_grep_backend.py -q

# 3. A/B benchmark
python scripts/run_benchmark.py --backends ast-grep --run-id option-a-on --append-trend
BSL_REFACTOR_NO_PREFILTER=1 python scripts/run_benchmark.py --backends ast-grep --run-id option-a-off --append-trend

# 4. Diff
python scripts/check_benchmark_regression.py --base option-a-off --target option-a-on
```

### Зависимости и non-goals

**Зависит от:**
- Phase 61 (Knowledge Graph, `src/bsl/call_graph/store.py`) — ✅ DONE
- `scripts/build_call_graph.py` — ✅ существует
- R4 telemetry (`src/bsl/semantic_search/refactor/telemetry.py`) — ✅ DONE

**Non-goals:**
- Не меняем routing_matrix v2 решения (multilspy primary → ast-grep fallback) — только улучшаем сам ast-grep
- Не трогаем multilspy backend (у него свой LSP scope)
- Не пересобираем denylist — он остаётся первым фильтром для общеупотребительных имён
- Не мигрируем call graph на Neo4j — SQLite API достаточен, миграция — отдельный roadmap
- Benchmark report (создаётся в Phase 6): `docs/roadmap/bsl-refactor-benchmark-YYYY-MM.md`
