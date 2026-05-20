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
