# Serena Audit — углублённый анализ эффективности в 1С-Framework

**Дата аудита:** 2026-04-14
**Резолюция:** 2026-04-15
**Статус:** ✅ РЕШЕНО — принят **Сценарий W (Hybrid Extract-only)**
**Авторы:** Claude Opus 4.6 (первичный), GLM-5.1 (коррекция), Claude Opus 4.6 1M (резолюция)

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
| **5** | Symbol-first workflow skill | Skill `bsl-refactoring-workflow` с 5-категорийной матрицей, интеграция с `implement-1c-task` | 0.5 дня | — | Phase 1-4 |
| **6** | Benchmark (Serena methodology) | 20 задач из git history × 5 категорий × (a)(b)(c) таксономия. Git diff verification + auto-revert. Артефакт: `docs/roadmap/bsl-refactor-benchmark-YYYY-MM.md` | 1.5 дня (было 0.5 — расширено до Serena-стандарта) | — | Phase 4 |
| **7** | Cleanup | Удалить `.serena/`, обновить `MEMORY.md` с правилами выбора инструмента | 0.5 дня | — | Phase 6 |

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
  - **Статус:** ⏸ **DEFERRED**. Требует `pip install multilspy` + BSL JAR wiring + async↔sync мост + real soak test против 2027 `.bsl`. Откладывается до R5 benchmark — бенчмарк покажет, нужен ли bulk_open или достаточно lazy per-file open. См. обсуждение: альтернативы (lazy open, SCIP pre-index).
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

- **R5.1 Benchmark tasks.json:** 20 реальных git commits с rename-операциями. **Артефакт:** `docs/roadmap/benchmark/tasks.json`. **DoD:** 20 задач × 5 категорий.
- **R5.2 Dual execution runner:** Claude API + isolated worktree. **Артефакт:** `docs/roadmap/benchmark/runner.py`. **DoD:** запуск одной задачи с обоими инструментами + git reset между.
- **R5.3 Comparison report:** A (multilspy) vs B (ast-grep) vs A+B merge. **Артефакт:** `docs/roadmap/benchmark/results-2026-05.md`. **DoD:** таксономия заполнена для всех 20 задач.
- **R5.4 Trend tracker:** агрегат по всем прогонам. **Артефакт:** `trend.md`. **DoD:** 3+ прогона зафиксированы.

#### Этап R6 — Upstream contributions (опционально, 2-3 дня, после R5)

- **R6.1 PR в multilspy:** BSL language adapter (language_id="bsl", JAR launcher). **Артефакт:** PR. **DoD:** PR принят или получен отзыв.
- **R6.2 PR в bsl-language-server:** `workspace/didChangeWorkspaceFolders` handler. **Артефакт:** PR + changelog. **DoD:** PR submitted.
- **R6.3 PR в tree-sitter-bsl:** улучшения грамматики (если из R2.2 найдено). **Артефакт:** PR. **DoD:** submitted.
- **R6.4 PR в Serena:** опциональный BSL context (contexts/bsl.yml). **Артефакт:** PR. **DoD:** submitted.

#### Промежуточный итог (2026-04-17)

| Этап | Статус | Артефакты | Тесты |
|------|--------|-----------|------:|
| **R0** | ✅ DONE | recon-отчёты, ADR-004, 3 ast-grep правила, sgconfig.yml, tree_sitter_bsl.dll | — |
| **R1.1** | ✅ DONE (на моках) | [multilspy_backend.py](../../src/bsl/semantic_search/refactor/backends/multilspy_backend.py) | 10 |
| **R1.2** | ✅ DONE (на моках) | [circuit_breaker.py](../../src/bsl/semantic_search/refactor/circuit_breaker.py), [lsp_subprocess.py](../../src/bsl/semantic_search/refactor/lsp_subprocess.py) | 17 |
| **R1.3** | ⏸ DEFERRED | — | — |
| **R1.4** | ✅ DONE | [driver.py](../../src/bsl/semantic_search/refactor/driver.py) | 9 |
| **R1.5** | ✅ DONE | [workspace_edit.py](../../src/bsl/semantic_search/refactor/workspace_edit.py) | 4 |
| **R1.6** | ✅ DONE | [classifier.py](../../src/bsl/semantic_search/refactor/classifier.py), [routing-matrix-v2.md](./routing-matrix-v2.md) | 17 |
| **R1.7** | ✅ DONE | [mcp.py](../../src/bsl/semantic_search/mcp.py) (`bsl_rename_symbol` + `register_rename_driver_factory`) | 6 |
| **R1.8** | ✅ DONE | [verification.py](../../src/bsl/semantic_search/refactor/verification.py) | — (покрыто R1.5 тестами) |
| **R2.1** | ✅ DONE (в R0.3) | tree_sitter_bsl.dll | — |
| **R2.2** | ⏸ DEFERRED | — | — |
| **R2.3** | ✅ DONE (в R0.3) | 3 YAML правила | — |
| **R2.4** | ✅ DONE | [ast_grep_backend.py](../../src/bsl/semantic_search/refactor/backends/ast_grep_backend.py), [ast_grep_runner.py](../../src/bsl/semantic_search/refactor/backends/ast_grep_runner.py) | 13 |
| **R2.5** | ✅ DONE | [orchestrator.py](../../src/bsl/semantic_search/refactor/orchestrator.py), [test_orchestrator.py](../../tests/bsl/refactor/test_orchestrator.py) | 13 |
| **R2.6** | ⏸ DEFERRED | — | — |
| **R4.0** | ✅ DONE | [routing_matrix.yaml](../../src/bsl/semantic_search/refactor/routing_matrix.yaml) + `RoutingMatrix.load/reset()` | 5 |
| **R4.1** | ✅ DONE | [telemetry.py](../../src/bsl/semantic_search/refactor/telemetry.py) + try/finally интеграция в orchestrator | 7 |
| **R4.2** | ✅ DONE | `ManualFallbackInstruction` + 3-tier fallback + MCP `bsl_rename_symbol` surface | 4 |
| **R4.3** | ✅ DONE | [refactor-fallback-chain.md](./refactor-fallback-chain.md) | — |
| **R4.4** | ✅ DONE | [aggregate_refactor_telemetry.py](../../scripts/aggregate_refactor_telemetry.py) + synthetic dataset | 3 |
| **R4.5** | ⏸ DEFERRED | — (ждёт R5 benchmark или ≥50 реальных событий) | — |
| **R4.6** | ⏸ DEFERRED | — (ждёт Phase 10 dashboard) | — |

**Агрегатно:**
- **111/111 refactor-тестов зелёные** (`pytest tests/bsl/refactor/`, +19 R4 тестов + 2 dopоl. после ревью).
- **11 Python-модулей** в [`src/bsl/semantic_search/refactor/`](../../src/bsl/semantic_search/refactor/) (добавлен [`telemetry.py`](../../src/bsl/semantic_search/refactor/telemetry.py); [`orchestrator.py`](../../src/bsl/semantic_search/refactor/orchestrator.py) расширен manual-tier и telemetry-интеграцией).
- **13 багов** найдено и исправлено ревью-циклом (subagent quality-review): security (path traversal, workspace-root containment), robustness (process leak, stale state, counter reset, best-effort rollback, **blocking I/O inside write lock — fix в R4**), correctness (ast-grep json format, exit codes, relative path resolution, trailing comment parsing, tab separator), singleton cache.
- **Делегирование Z.AI:** большинство кода сгенерировано через `mcp__llm-rotation__llm_complete` (glm-5.1), Opus — планнер + ревьюер + ассемблер. Периодические перебои провайдеров → Opus fallback для тестов.

**Что блокирует прогресс по R1.3 / реальному multilspy:** решение об установке `pip install multilspy` + wiring BSL JAR + async↔sync мост. Целесообразно откладывать до R5 benchmark, чтобы данные показали реальную цену lazy-open vs bulk-preload.

#### Сводная таблица этапов и оценки трудозатрат

| Этап | Задача | Оценка | Зависимости |
|------|--------|--------|-------------|
| **R0** | Research validation | 1-2 дня | Блокер для R1-R2 |
| **R1** | Variant A rewrite (multilspy) | 3-5 дней | R0.5 = Scenario 1 |
| **R2** | Variant B (ast-grep) | 3-5 дней | Параллельно R1 |
| **R3** | SCIP cache layer | 5-7 дней | После R1 |
| **R4** | Orchestrator v2 + routing | 1-2 дня | После R1+R2 |
| **R5** | Benchmark + validation | 2-3 дня | После R4 |
| **R6** | Upstream PRs | 2-3 дня | После R5 |

**Итого v4.5:**
- **Критический путь:** R0 → R1 → R4 → R5 = **7-12 дней**
- **Полный объём:** R0-R6 = **17-27 дней**

**Критерии успеха (обновлены для §7):**
- Cross-file rename работает (через multilspy preload): >90% задач категории «Multi-File Changes» в benchmark.
- Fallback B покрывает случаи, где A не справился: >95% комбинированного покрытия.
- Latency rename end-to-end: <30s для workspace из 2000 файлов.
- Auto-rollback frequency: <5% (низкий false-positive rate).

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
- Benchmark report (создаётся в Phase 6): `docs/roadmap/bsl-refactor-benchmark-YYYY-MM.md`
