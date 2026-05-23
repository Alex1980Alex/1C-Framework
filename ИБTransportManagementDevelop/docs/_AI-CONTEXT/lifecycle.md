# Расширенный жизненный цикл задачи

## 8 стадий

```
Discovery → Analysis → Design → Implementation → Testing → Review → Audit → Deployment
```

### Стадия 0: Discovery (опционально, для незнакомой области)

**Цель:** понять контекст до анализа задачи.

**Инструменты:**
- `mcp__bsl-semantic-search__bsl_search` — найти похожие реализации
- `mcp__bsl-semantic-search__bsl_object_info` — получить структуру объекта
- `mcp__bsl-semantic-search__find_callers` — карта вызовов
- Поиск в `docs/` по ключевым словам (исторические анализы)

**Output:** ничего формального — внутреннее понимание + ссылки на код.

---

### Стадия 1: Analysis (`/analyze-1c-task`)

**Вход:** ТЗ от заказчика в `docs/<YYMMDD>_<JIRA>/<тикет>.md`.

**Процесс (5 фаз через skill `analyze-1c-task-v2`):**
1. **Требования** — формализация
2. **Объекты** — какие справочники/документы/регистры затронуты
3. **Алгоритм** — пошаговая логика
4. **План** — пронумерованные точки модификации
5. **Верификация** — sanity-check vs ТЗ

**Output:** `docs/<JIRA>/ANALYSIS-REPORT.md` — пронумерованные точки
модификации (P1, P2, …) с указанием файлов, методов, строк.

**Опциональные дополнения:**
- `DATA-ROADMAP.md` — план по данным (если задача миграции/импорта)
- `TEST-ROADMAP.md` — план тестирования

---

### Стадия 2: Design (опционально, для крупных задач)

**Цель:** spec-driven design до кода.

**Инструменты:**
- OpenSpec (если `openspec/` создан): `/opsx:propose`, `/opsx:explore`
- Brownfield validation: skill `brownfield-validate` (Gap, Design, Impl)

**Output:** `docs/<JIRA>/DESIGN.md` или `openspec/changes/<id>/design.md`.

---

### Стадия 3: Implementation (`/implement-1c-task`)

**Вход:** ANALYSIS-REPORT с готовыми точками модификации.

**Процесс:**
- EDT-MCP правки BSL/XML по точкам (P1, P2, …)
- Skill `bsl-symbol-editing` — symbol-anchored правки
- Skill `bsl-refactoring-workflow` — refactoring с `bsl_rename_symbol`

**Output:**
- Изменения в `Конфигурация/src/`
- `docs/<JIRA>/IMPLEMENTATION-PROGRESS.md` — чек-лист статусов точек

---

### Стадия 4: Testing (`/write-1c-tests` + `/run-1c-tests`)

**Вход:** `IMPLEMENTATION-PROGRESS.md` (что реализовано → что тестировать).

**4a — Подготовка (skill `va-bdd-testing` Stage 4a):**
- **MANDATORY pre-scenario TestDB check** — проверить что нужные данные
  есть в TestDB ДО написания .feature.
- При отсутствии данных — заполнить через `1c-mcp-crud`.

**4b — Написание тестов:**
- `.feature` файлы в `features/` (gherkin)
- Скриптинг шагов калибрруется по существующим примерам

**4c — Прогон:**
- `tools/vanessa/run-bdd.ps1` — chained execution с resume
- `.run-state.json` — состояние прогона между сессиями
- Pre-scenario TestDB check — повторная проверка перед каждым сценарием

**Output:**
- `features/<feature-name>.feature`
- `docs/<JIRA>/test-plan.md` — список сценариев + ожидаемые результаты
- `docs/<JIRA>/ТЕСТ-<N>_<имя>.md` — детальное описание сценария

---

### Стадия 5: Review (опционально)

**Инструменты:**
- Skill `code-verify` (4 режима: knowledge-compliance, behavior-preservation,
  bug-fix-validation, quality-review)
- `mcp__auto-documenter__autoreview`
- Subagent (general-purpose) с custom prompt'ом

**Output:** `docs/<JIRA>/REVIEW.md` — вердикт + рекомендации.

---

### Стадия 6: Audit (`/audit-docs`)

**Цель:** убедиться что код-документация-скиллы выровнены.

**Output:** action items в `docs/<JIRA>/AUDIT-RESULT.md` (если расхождения).

---

### Стадия 7: Deployment (для крупных изменений)

**Артефакты:**
- `docs/<JIRA>/DEPLOYMENT.md` — последовательность накатки на прод-БД
- `docs/<JIRA>/CHANGELOG.md` — что включено в релиз
- Конфигурационный файл (`*.cf`) или расширение (`*.cfe`) — собирается
  из EDT через `Конфигурация → Сохранить конфигурацию в файл`

**Auto-reindex on commit:** при коммите `.bsl` — `bsl_code_v4_late` коллекция
автоматически переиндексирует через `scripts/git_post_commit_reindex.py`.

---

## Шаблоны промптов

См. `scripts/PROMPT-TEMPLATE-1C-TASK-ANALYSIS.md` (мигрировано из reference).

## Чек-лист «начало новой задачи»

```
□ Создать docs/<YYMMDD>_<JIRA-TICKET> <короткое описание>/
□ Положить ТЗ → <тикет>.md (+ скриншоты при необходимости)
□ /analyze-1c-task → ANALYSIS-REPORT.md
□ Согласовать ANALYSIS с заказчиком
□ /implement-1c-task → правки + IMPLEMENTATION-PROGRESS.md
□ /write-1c-tests → features/*.feature + test-plan.md
□ /run-1c-tests → проверка
□ /audit-docs (опц.)
□ git commit (auto-git-save сделает сам)
```
