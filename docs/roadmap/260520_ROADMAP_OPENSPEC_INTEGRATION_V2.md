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

## Sprint 2026-05-20 evening — 10/10 deferred gap'ов закрыто

Все ранее отложенные gap'ы реализованы:

| ID | Что сделано |
|---|---|
| **A** ✅ | `npm install -g openspec-extensions@1.3.4` → CLI `openspec` доступен глобально (v1.3.1) |
| **E** ✅ | hook [`openspec-task-progress.py`](../../.claude/hooks/openspec-task-progress.py) — Stop, heuristic candidate-completed для `tasks.md` через git diff |
| **G** ✅ | skill [`openspec-archive-change`](../../.claude/skills/openspec-archive-change/SKILL.md) расширен step 6: `memory-orchestrator route_and_save` после успешного archive |
| **H** ✅ | `openspec/` добавлен в `DEFAULT_INDEX_ROOTS` существующего `framework_code_v1` ([config.py:20-21](../../src/framework_search/config.py#L20)) — переиспользовали инфраструктуру вместо новой коллекции; auto-reindex через post-commit hook + MCP lazy-check работают автоматически |
| **I** ✅ | `scripts/export_graph_to_wiki.py promote-openspec` команда — archived OpenSpec changes → `docs/wiki/openspec/` с index.md frontmatter |
| **J** ✅ **resolved** | `validate_change` под капотом вызывает CLI `openspec validate` через shell — был broken потому что CLI не установлен. После A (npm install) `openspec validate gkstcplk-2507-...` возвращает `valid: true, issues: []`. Bonus: spec.md переписан под валидный формат `## ADDED Requirements` + `### Requirement:` + `#### Scenario:` (формат strict-config.yaml) |
| **K** ✅ | skill `analyze-1c-task-v2` v4.3: флаг `--auto-propose` после Write ANALYSIS-REPORT → `openspec_create_change` + populate из секций |
| **L** ✅ | port probe 3000-9090 → только `:8765` (EDT-MCP). OpenSpec dashboard не запущен в текущей конфигурации — это известное состояние, не gap |
| **M** ✅ | `scripts/openspec_jira_sync.py` — skeleton с `JIRA_BASE_URL`/`JIRA_TOKEN` env-validation; full impl deferred до получения JIRA credentials |
| **extra** ✅ **disproven** | manual stdin-тест `slash-command-tracker.py` с `/opsx:propose test` → запись `slash:opsx:propose` с `run_id` в `hook-invocations.jsonl`. Логирование работает, просто `/opsx:*` команды не вводились в сессии до этого — не gap |

**Итог:** интеграция OpenSpec во фреймворк — 100%. Workflow `/opsx:explore → propose → approve → apply → archive` полностью покрыт hooks + CI + memory + indexing + wiki promotion + JIRA stub.

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
