# Roadmap: OpenSpec integration v2 (deferred gaps)

**Дата:** 2026-05-20
**Статус:** roadmap (не план реализации)

## Контекст

OpenSpec интегрирован во фреймворк (MCP server, skills, slash-commands, approval-gate hook). В сессии 2026-05-20 закрыты следующие gap'ы:

- **N+O** — проверка путей AGENTS.md/project.md
- **P** — правило openspec в `code-skill-patterns.json`
- **F** — Stop-hook `opsx-apply-postvalidate.py` (напоминает запустить brownfield-validate)
- **D** — PostToolUse hook `openspec-change-coverage.py` (warn на edit с JIRA без active change)
- **B** — GitHub Actions workflow `.github/workflows/openspec.yml`
- **C** — pre-commit script `scripts/openspec_lint_ci.py`
- **Q** — smoke-test `scripts/smoke_test_openspec.py`
- **Регистрация** F+D в `.claude/settings.json`

Остальные gap'ы документированы ниже как deferred.

## Deferred gaps

### A — CLI `openspec` (npm package)

- **Зачем**: команды `openspec init / diff / list / archive` вне MCP.
- **Что делать**: `npm install -g @fission-codes/openspec` (имя пакета — reverse engineer из openspec-mcp deps). Добавить в `tools/install_dev.ps1`.

### E — Stop-hook auto-update `tasks.md`

- **Зачем**: diff git → `openspec_batch_update_tasks` с completed-метками.
- **Что делать**: hook `openspec-task-progress.py` (Stop). Маппинг file → task через heuristic (jira-token + keywords из задачи).

### G — Memory `route_and_save` в `/opsx:archive`

- **Зачем**: archived change → vector-memory для семантического поиска аналогов.
- **Что делать**: extend skill `openspec-archive-change` шагом `route_and_save` с metadata `{category: openspec-archived, change_id, jira}`.

### H — PDF-vector-graph индексация `openspec/changes/**`

- **Зачем**: Qdrant коллекция `openspec_changes_v1` (1024d MRL) для semantic-search «есть ли change про X».
- **Что делать**: `scripts/index_openspec.py` + auto-reindex в `git_hooks/post-commit`.

### I — Obsidian/Wiki export openspec → markdown wiki

- **Зачем**: archived change'ы как canonical knowledge в `docs/wiki/openspec/`.
- **Что делать**: extend `scripts/export_graph_to_wiki.py` команду `promote-openspec`. Зависит от H.

### J — Debug `openspec_validate_change` (всегда Invalid)

- **Зачем**: `validate_change` возвращает `Invalid` для всех change'ов с `0 errors`. Hidden constraint.
- **Что делать**: clone openspec-mcp source, debug validator logic, либо upstream issue.
- **Workaround текущий**: `critique_proposal` (`score ≥ 8.0`) как proxy для CI gate.

### K — `/analyze-1c-task --auto-propose`

- **Зачем**: автосоздание change'а после анализа.
- **Что делать**: extend skill `analyze-1c-task-v2` — flag `--auto-propose` → `openspec_create_change` + populate.

### L — MCP dashboard + WebSocket probe

- **Зачем**: openspec-mcp v0.4.2 упоминает дашборд, порт нигде не задокументирован.
- **Что делать**: `netstat -ano | findstr LISTENING` поиск порта, документировать в `16.6 EDT-MCP setup`.

### M — JIRA bridge

- **Зачем**: двусторонняя связь change ↔ JIRA тикет.
- **Что делать (опц.)**: `scripts/openspec_jira_sync.py` с JIRA API token.
- **Альтернатива**: ручная ссылка через `.openspec.yaml: jira_task_id`.

### Extra — slash-detect для `/opsx:*`

В `data/hook-invocations.jsonl` 0 записей `slash:opsx-*`. Возможные причины: `/opsx:*` команды из `.claude/commands/opsx/*.md` обрабатываются Claude Code иначе чем raw CLI, не эмитят UPS hook. Нужна диагностика при следующем `/opsx:apply`.

## Резюме

| ID | Описание | Статус | Затраты |
|---|---|---|---|
| A | CLI install | deferred | 15м |
| E | task-progress auto-sync | deferred | 2-3ч |
| G | memory integration | deferred | 30м |
| H | pdf-vector-graph indexing | deferred | 4-6ч |
| I | wiki export | deferred | 2ч |
| J | validate debug | deferred | 1-3ч |
| K | --auto-propose | deferred | 1ч |
| L | dashboard probe | deferred | 30м |
| M | JIRA bridge | deferred | 4-8ч |
| extra | slash-detect opsx | deferred | 30м |

Все deferred — nice-to-have, не блокеры. Workflow `/opsx:explore → propose → approve → apply → archive` работает.
