---
confidence: 0.9
created_at: 2026-04-20 10:00:00+00:00
related:
- '[[_index]]'
- '[[overview]]'
- '[[hooks-reference]]'
- '[[skills-reference]]'
- '[[ralph-wiggum]]'
- '[[patterns]]'
- '[[bsl-integration]]'
sources:
- '[.claude/skills/hooks-skills-mcp-triad/SKILL.md](../../.claude/skills/hooks-skills-mcp-triad/SKILL.md)'
- '[13 ТРИАДА HOOK SKILL MCP](../framework documentation/13_ТРИАДА_HOOK_SKILL_MCP/13.1_Обзор.md)'
status: active
tags:
- architecture
- automation
- triad
- hooks
- skills
- mcp
title: Hooks + Skills + MCP Triad
unified_id: 019e1e30-10a7-7de2-ab96-bb7c1755b1aa
updated_at: 2026-05-14 23:30:00+00:00
---

# Hooks + Skills + MCP Triad

Триада автоматизации Claude Code: **Hooks** (КОГДА — event-driven enforcement), **Skills** (КАК / ЧТО — knowledge + workflows), **MCP servers** (ЧЕМ — capabilities извне). Три ортогональных оси. Каждая может работать без других, но real production-power — в комбинации.

Каноническая deep reference — [`hooks-skills-mcp-triad`](../../.claude/skills/hooks-skills-mcp-triad/SKILL.md). Эта страница — wiki-уровень summary с навигацией.

## Три оси

```
┌──────────────────────────┐       ┌──────────────────────────┐       ┌──────────────────────────┐
│        HOOKS (51)         │       │       SKILLS (86)        │       │       MCP (~50)          │
│        КОГДА              │       │       КАК / ЧТО          │       │       ЧЕМ                │
├──────────────────────────┤       ├──────────────────────────┤       ├──────────────────────────┤
│ UPS (9)                  │       │ 1С (9)                   │       │ 1c-mcp-crud              │
│ PreToolUse (4)           │       │ Framework (12)           │       │ 1c-debug / 1c-debug-hmr  │
│ PostToolUse (18)         │  ←→   │ LangChain (8)            │  ←→   │ bsl-semantic-search      │
│ Stop (9 — chained)       │       │ Claude Code (10)         │       │ edt-mcp                  │
│ SessionStart (2)         │       │ Hooks (6)                │       │ auto-documenter          │
│                          │       │ Memory (5)               │       │ pdf-vector-graph         │
│                          │       │ Research (6)             │       │ memory-orchestrator      │
│                          │       │ Token Economy (3)        │       │ openspec-mcp             │
│                          │       │ Wiki (4)                 │       │ skill-learning           │
│                          │       │ Misc / specialized (~23) │       │ ... (lazy-mcp registry)  │
└──────────────────────────┘       └──────────────────────────┘       └──────────────────────────┘
         ▲                                    ▲                                    ▲
         │ enforce                            │ provide knowledge                  │ provide capability
         │                                    │                                    │
         └────────────────────────────────────┴────────────────────────────────────┘
                                              │
                                              ▼
                                       USER + CLAUDE
```

## Hooks — КОГДА (51, см. [[hooks-reference]])

Event-driven Python скрипты в [`.claude/hooks/`](../../.claude/hooks/), регистрация в [`.claude/settings.json`](../../.claude/settings.json). По событию:

| Event | # | Назначение |
|---|---|---|
| **UserPromptSubmit** | 9 | Routing промптов: skill-router, research detector, decision detector, preflight для 1С slash-команд, slash tracker |
| **PreToolUse** | 4 | Enforcement до выполнения tool: code-skill-enforcer, root-clutter-guard, search-optimizer, approval-gate |
| **PostToolUse** | 18 | Реакция на результат: post-verification, docs-tracker, auto-git-save, code-verify-reminder, MCP/slash logger, quality feedback, delegation tracker, web-cache, ... |
| **Stop** | 9 | Enforcer chain перед завершением: task-enforcer, git-commit-enforcer, docs-change-enforcer, ralph_wiggum_stop, session-memory-save, ... |
| **SessionStart** | 2 | Запуск инфраструктуры: ensure-docker-qdrant, logging-status-banner |

3-уровневая защита: L1 создание (PostToolUse трекеры) → L2 напоминание (UPS bridge `todo-sync.py` → TodoWrite) → L3 блокировка (Stop enforcers с exit code 2). Паттерны: [[multi-level-enforcement]], [[stop-gate]], [[guard-gate]], [[silent-observer]], [[invocation-logger]].

## Skills — КАК / ЧТО (86, см. [[skills-reference]])

Markdown-документы в [`.claude/skills/<name>/SKILL.md`](../../.claude/skills/) с frontmatter triggers. Discovery — Skill Router (3 layers: keyword + fuzzy + TF-IDF), config [`skill-router-config.json`](../../.claude/skills/skill-router-config.json) — 16 bundles v9.

Skill = knowledge + workflow + antipatterns. Содержит copy-pasteable templates, диагностику, cross-refs. **Заменяет частые WebSearch / Context7 запросы** при повторных задачах. Создание через [`doc-to-skill`](../../.claude/skills/doc-to-skill/SKILL.md), audit через [`audit-docs`](../../.claude/skills/audit-docs/SKILL.md).

Skill-First Enforcement: `code-skill-enforcer.py` блокирует Write/Edit пока релевантный `Skill()` не вызван. Конфиг — [`shared/code-skill-patterns.json`](../../.claude/hooks/shared/code-skill-patterns.json) (массив `{pattern, skill, label, domain}`).

## MCP — ЧЕМ (~50 серверов через lazy-mcp)

Model Context Protocol servers — внешние capabilities. Стандарт Anthropic, прозрачный для Claude Code. Профили:

- [`.mcp/pdf.json`](../../.mcp/pdf.json) — PDF Framework серверы
- [`.mcp/bsl.json`](../../.mcp/bsl.json) — 1С (bsl-semantic-search, 1c-mcp-crud, 1c-debug, 1c-debug-hmr, edt-mcp, mcp-onec-test-runner, auto-documenter, ast-grep-mcp, bsl-semantic-diff)
- [`.mcp/full.json`](../../.mcp/full.json) — все серверы (heavy)
- [`.mcp/lazy-mcp.json`](../../.mcp/lazy-mcp.json) — lazy proxy, on-demand activation 27 серверов

[`infra/lazy-mcp/`](../../infra/lazy-mcp/): прокси-маршрутизация по 11 категориям, on-demand spin-up. См. [chapter 26 LAZY_MCP](../framework%20documentation/26_LAZY_MCP/26.1_Обзор.md).

Универсальный аудит — [`mcp-invocation-logger.py`](../../.claude/hooks/mcp-invocation-logger.py) (regex matcher `mcp__.*`) логирует **любой** MCP-вызов в `data/hook-invocations.jsonl` с `category="mcp_call"` и `run_id` (cross-trace со slash-командой). Новые MCP-серверы покрываются автоматически без правок settings.json.

## Взаимодействие

### Flow примера: `/implement-1c-task`

```
User: /implement-1c-task GKSTCPLK-1234
         │
         ▼
UPS:  slash-command-tracker.py → run_id UUID → .current-runs.json
      implement-1c-task-preflight.py → smoke-test MCP availability
              → outputs pipeline mode (Full / Code-only / Read-only) via systemMessage
         │
         ▼
[Claude reads systemMessage, активирует skill]

Skill('implement-1c-task') ← knowledge + 8-stage workflow
                              │
                              ├─ Stage 1: get_module_structure (edt-mcp MCP)
                              ├─ Stage 2: read_method_source  (edt-mcp MCP)
                              ├─ Stage 3: write_module_source (edt-mcp MCP)
                              ├─ Stage 4: validate_query      (1c-mcp-crud MCP)
                              ├─ Stage 5: debug_set_breakpoint (1c-debug-hmr MCP)
                              ...
         │
         ▼
PreToolUse: code-skill-enforcer (Skill('implement-1c-task') активен → ALLOW)

PostToolUse: docs-change-tracker, posttooluse-skill-metrics, auto-git-save

Stop: task-enforcer, git-commit-enforcer
      session-memory-save → SQLite + wiki log + try_promote_patterns()
      implement-1c-task-smoke-stop-alert (если preflight выявил проблемы)
```

Hooks направляют (КОГДА), Skill знает что делать (КАК), MCP выполняет операции с внешними системами (ЧЕМ).

## Фабрика для нового компонента

Skill [`triad-factory`](../../.claude/skills/triad-factory/SKILL.md) проводит через Q1-Q6 для решения о добавлении hook / skill / MCP:

- Q1: Нужен ли event-trigger? → возможно hook
- Q2: Это многоразовое знание / workflow? → skill
- Q3: Нужна внешняя capability (DB / API / debugger)? → MCP
- Q4-Q6: scope, enforcement, registration, verification

Регистрация: skill в `.claude/skills/` + (опционально) `skill-router-config.json`. Hook в `.claude/hooks/` + регистрация в `.claude/settings.json`. MCP в `.mcp/<profile>.json` или lazy-mcp registry.

## Связано

- [[overview]] §Automation — общая картина scale
- [[hooks-reference]] · [[skills-reference]] — детальные перечни
- [[ralph-wiggum]] — self-correction цикл, используется внутри `code-verify` skill
- [[bsl-integration]] — конкретный пример триады на 1С-домене
- [[patterns]] — формальный pattern catalogue (Provider, Strategy, Stop-Gate, ...)
