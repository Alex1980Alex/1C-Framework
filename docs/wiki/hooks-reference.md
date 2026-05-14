---
confidence: 0.9
created_at: 2026-04-20 10:00:00+00:00
related:
- '[[_index]]'
- '[[overview]]'
- '[[triad-architecture]]'
- '[[skills-reference]]'
- '[[ralph-wiggum]]'
- '[[patterns]]'
sources:
- '[.claude/skills/hooks-skills-mcp-triad/SKILL.md](../../.claude/skills/hooks-skills-mcp-triad/SKILL.md)'
- '[09.7 Система хуков](../framework documentation/09_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md)'
status: active
tags:
- reference
- hooks
- automation
- enforcement
title: Hooks Reference
unified_id: 019e1e30-10a7-7c47-9b31-7f95bc84cda4
updated_at: 2026-05-14 23:30:00+00:00
---

# Hooks Reference

51 Python хук в [`.claude/hooks/`](../../.claude/hooks/), активируемые событиями Claude Code. Полная enumeration с per-hook поведением — skill [`hooks-skills-mcp-triad`](../../.claude/skills/hooks-skills-mcp-triad/SKILL.md). Эта страница — wiki-уровень organization by event + cross-refs на ключевые паттерны.

## Event lifecycle

```
UserPromptSubmit  → классификация запроса, routing, slash detection
       ↓
[Pre-text processing — context injection]
       ↓
PreToolUse        → enforcement перед выполнением tool
       ↓
[Tool executes]
       ↓
PostToolUse       → реакция на результат, метрики, tracking
       ↓
[Response]
       ↓
Stop              → enforcer chain перед завершением сессии
```

Дополнительно: `SessionStart` (старт сессии — Docker, баннеры), `UserPromptExpansion` (forward-compat fallback на Windows).

## Хуки по событию

### UserPromptSubmit (UPS, 9)

| Hook | Назначение |
|---|---|
| [`skill-router.py`](../../.claude/hooks/skill-router.py) | Config-driven routing: Layer A+B+C (keyword + fuzzy + TF-IDF) → рекомендация скиллов (16 bundles v9, weighted_keywords) |
| [`research-task-detector.py`](../../.claude/hooks/research-task-detector.py) | Детекция ВОПРОСОВ → routing: Architecture / 1С / Tech |
| [`decision-to-triad.py`](../../.claude/hooks/decision-to-triad.py) | Детекция РЕШЕНИЙ/ИДЕЙ → Фабрика (triad-factory Q1-Q5) |
| [`ralph_activator.py`](../../.claude/hooks/ralph_activator.py) | Активация Ralph Wiggum для сложных многошаговых задач |
| [`document-persistence.py`](../../.claude/hooks/document-persistence.py) | Детекция roadmap / analysis / plan → сохранение в `docs/` |
| [`implement-1c-task-preflight.py`](../../.claude/hooks/implement-1c-task-preflight.py) | Content-фильтр `/implement-1c-task` → smoke-test → pipeline mode + debug-hmr readiness |
| [`analyze-1c-task-preflight.py`](../../.claude/hooks/analyze-1c-task-preflight.py) | Content-фильтр `/analyze-1c-task` → debug-hmr probe → Phase 2.5 Runtime Trace status |
| [`slash-command-tracker.py`](../../.claude/hooks/slash-command-tracker.py) | UPS + Stop, генерация `run_id` для каждой `/cmd`, складывает в `.current-runs.json` |
| [`bsl-tool-router.py`](../../.claude/hooks/bsl-tool-router.py) | Routes BSL/1C запросы на `bsl-development` skill |

### PreToolUse (4)

| Hook | Matcher | Назначение |
|---|---|---|
| [`code-skill-enforcer.py`](../../.claude/hooks/code-skill-enforcer.py) | Write\|Edit\|Bash | Skill-First: BLOCK если скилл не активирован (Layers A-C). Конфиг: [`shared/code-skill-patterns.json`](../../.claude/hooks/shared/code-skill-patterns.json) |
| [`root-clutter-guard.py`](../../.claude/hooks/root-clutter-guard.py) | Write | Блокировка ad-hoc файлов в корне (test_*, debug_*) |
| [`search-optimizer.py`](../../.claude/hooks/search-optimizer.py) | Bash | Оптимизация Search API параметров |
| [`approval-gate.py`](../../.claude/hooks/approval-gate.py) | Skill | SDD Phase 3: блокировка implementation skills без `approval.status: approved`. Профили `1c-bsl`, `python-framework` |

### PostToolUse (13)

| Hook | Matcher | Назначение |
|---|---|---|
| [`code-skill-enforcer.py`](../../.claude/hooks/code-skill-enforcer.py) | Write\|Edit | Post-verification + LEARN phase (Levels E-F) |
| [`code-skill-enforcer.py`](../../.claude/hooks/code-skill-enforcer.py) | WebSearch\|WebFetch | Research cache reminder (Level D) |
| [`knowledge-cache-reminder.py`](../../.claude/hooks/knowledge-cache-reminder.py) | WebSearch\|WebFetch | Напоминание сохранить в кеш (1С / Tech / Architecture) |
| [`factory-enforcer.py`](../../.claude/hooks/factory-enforcer.py) | Write | Контроль ШАГ 4-5 Фабрики |
| [`docs-change-tracker.py`](../../.claude/hooks/docs-change-tracker.py) | Write\|Edit | Код изменён → mandatory task на обновление docs/skills |
| [`auto-git-save.py`](../../.claude/hooks/auto-git-save.py) | Write\|Edit\|Bash | Mandatory task / threshold-based автокоммит (см. [`auto-git-save`](../../.claude/skills/auto-git-save/SKILL.md)) |
| [`posttooluse-auto-git-save.py`](../../.claude/hooks/posttooluse-auto-git-save.py) | Write\|Edit | Instant debounced commit (workaround #6305 на Windows) |
| [`auto-git-save-prompt.py`](../../.claude/hooks/auto-git-save-prompt.py) | UserPromptSubmit | Третий слой auto-save (UPS fallback при PostToolUse mis-fire) |
| [`skill-usage-metrics.py`](../../.claude/hooks/skill-usage-metrics.py) | Skill | Логирование в `data/skill-usage.log` |
| [`bulk-action-guard.py`](../../.claude/hooks/bulk-action-guard.py) | Bash | Детекция bulk/destructive → Q5 enforcer |
| [`code-verify-reminder.py`](../../.claude/hooks/code-verify-reminder.py) | Write\|Edit, Skill, Task, Stop | Mandatory task на code-verify; tri-registered (workaround #6305) |
| [`posttooluse-quality-feedback.py`](../../.claude/hooks/posttooluse-quality-feedback.py) | Write\|Edit | `ruff check *.py` → hookSpecificOutput feedback |
| [`posttooluse-delegation-tracker.py`](../../.claude/hooks/posttooluse-delegation-tracker.py) | mcp__llm-rotation__llm_complete | Z.AI delegation outcomes → JSONL |
| [`posttooluse-web-cache.py`](../../.claude/hooks/posttooluse-web-cache.py) | WebSearch\|WebFetch | Кэширование результатов 24h TTL |
| [`posttooluse-docs-tracker.py`](../../.claude/hooks/posttooluse-docs-tracker.py) | Write\|Edit | Мгновенный docs-change reminder |
| [`posttooluse-skill-metrics.py`](../../.claude/hooks/posttooluse-skill-metrics.py) | Skill\|Task | Metrics DB (HookMetricsDB source tracking) |
| [`posttooluse-bash-errors.py`](../../.claude/hooks/posttooluse-bash-errors.py) | Bash | Bash error classifier |
| [`mcp-invocation-logger.py`](../../.claude/hooks/mcp-invocation-logger.py) | `mcp__.*` regex | Унифицированный лог любых MCP-вызовов в `data/hook-invocations.jsonl` (см. [[patterns]] → [[invocation-logger]]) |

### Stop (5)

| Hook | Назначение |
|---|---|
| [`task-enforcer.py`](../../.claude/hooks/task-enforcer.py) | BLOCK если есть pending mandatory tasks (cache / factory / docs / git / code-verify) |
| [`git-commit-enforcer.py`](../../.claude/hooks/git-commit-enforcer.py) | BLOCK если незакоммиченные изменения в watched paths (`src/`, `docs/`, `tests/`, `.claude/skills/`, `.claude/hooks/`) |
| [`docs-change-enforcer.py`](../../.claude/hooks/docs-change-enforcer.py) | BLOCK если код изменён без обновления docs. SKIP_PATTERNS для инфра-файлов |
| [`ralph_wiggum_stop.py`](../../.claude/hooks/ralph_wiggum_stop.py) | Контроль итеративного цикла Ralph |
| [`session-memory-save.py`](../../.claude/hooks/session-memory-save.py) | Auto-save session context → SQLite + wiki log. **2026-05-14:** + `try_promote_patterns()` invocation (L5 drafts pipeline) |
| [`implement-1c-task-smoke-stop-alert.py`](../../.claude/hooks/implement-1c-task-smoke-stop-alert.py) | Informational alert если был preflight fail в `/implement-1c-task` run |
| [`todo-sync.py`](../../.claude/hooks/todo-sync.py) | UPS bridge: hook-todos → TodoWrite (видимость) |
| [`code-verify-reminder.py`](../../.claude/hooks/code-verify-reminder.py) | Stop-fallback closer (см. PostToolUse) |
| [`logging-status-banner.py`](../../.claude/hooks/logging-status-banner.py) | SessionStart → status баннер [mcp/slash logging: ACTIVE] |

### SessionStart (2)

| Hook | Назначение |
|---|---|
| [`ensure-docker-qdrant.py`](../../.claude/hooks/ensure-docker-qdrant.py) | Авто-старт Docker Desktop + `pdf-rag-qdrant` контейнера; graceful degradation на Linux/Mac или без Docker |
| [`logging-status-banner.py`](../../.claude/hooks/logging-status-banner.py) | Status баннер по `mcp_call` / `slash_run` за 24ч |

## Защитные цепочки (3-уровневая защита)

| Уровень | Что | Hooks |
|---|---|---|
| L1 Создание | Tracking + создание pending task | `auto-git-save`, `code-verify-reminder`, `docs-change-tracker` |
| L2 Напоминание | UPS bridge → TodoWrite visibility | `todo-sync` |
| L3 Блокировка | Stop event → exit code 2 | `task-enforcer`, `git-commit-enforcer`, `docs-change-enforcer`, `ralph_wiggum_stop` |

См. [[patterns]] → [[multi-level-enforcement]], [[stop-gate]], [[guard-gate]].

## Shared utilities

`.claude/hooks/shared/`: `base.py` (BaseHook ABC), `task_master.py` (pending tasks API), `invocation_logger.py` (universal MCP logging), `run_context.py` (slash-cmd UUID tracking), `slash_detect.py` (UPS-based slash parsing — backtick-aware), `debug_hmr_health.py` (probe для 1С debug pipeline), `trust_scorer.py` (FETCH source ranking), `code-skill-patterns.json` (enforcer config).

## Конфигурация

Регистрация в [`.claude/settings.json`](../../.claude/settings.json) (hooks section, по event). Управление через [`claude-code-settings`](../../.claude/skills/claude-code-settings/SKILL.md), troubleshooting — [`hook-debugging`](../../.claude/skills/hook-debugging/SKILL.md), типовые баги — [`claude-code-hooks-bugs`](../../.claude/skills/claude-code-hooks-bugs/SKILL.md).
