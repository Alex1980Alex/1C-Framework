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
