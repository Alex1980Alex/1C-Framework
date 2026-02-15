# Claude Code Integration Structure

> Status: Single-level (all in `.claude/`) | Date: 2026-02-14

## Обзор

Все hooks, skills и конфигурация живут в **одной папке** `.claude/` внутри проекта.

```
.claude/
│
├── hooks/
│   ├── base/                        ← BaseHook protocol
│   ├── shared/                      ← infrastructure (FuzzyMatcher, TaskMaster, core_paths)
│   │
│   ├── ralph_activator.py           ← автономный цикл (активация)
│   ├── ralph_wiggum_stop.py         ← автономный цикл (стоп-контроль)
│   ├── root-clutter-guard.py        ← блокирует мусор в корне проекта
│   ├── bulk-action-guard.py         ← детектит массовые удаления
│   ├── git-commit-enforcer.py       ← блокирует стоп без коммита
│   │
│   ├── research-task-detector.py    ← маршрутизация research-задач
│   ├── decision-to-triad.py         ← перенаправляет решения на фабрику
│   ├── knowledge-cache-reminder.py  ← напоминает сохранить в кеш
│   ├── factory-enforcer.py          ← блокирует выход до завершения фабрики
│   ├── task-enforcer.py             ← блокирует выход до завершения задач
│   ├── search-optimizer.py          ← оптимизирует поисковые запросы
│   └── docs-change-tracker.py       ← напоминает обновить документацию
│
├── skills/
│   ├── triad-factory/               ← процедурный: Q1-Q5 классификация
│   ├── create-hook/                 ← процедурный: шаблон создания хука
│   ├── doc-to-skill/                ← процедурный: конвертер доки → SKILL.md
│   ├── task-evaluation/             ← процедурный: Research / Brainstorm / Hybrid
│   │
│   ├── 1c-doc-research/            ← knowledge + cache
│   ├── tech-research/              ← knowledge + cache
│   ├── architecture-research/      ← knowledge + cache + adr/
│   ├── hooks-skills-mcp-triad/     ← knowledge
│   └── pdf-knowledge/              ← project-specific
│
├── cache/                           ← hook-todos.json, lock files
└── settings.json                    ← all hooks registration
```

**12 hooks** + **9 skills** — всё в одном месте.

---

## Категории

### Hooks (12 штук)

| Категория | Hooks | Назначение |
|-----------|-------|-----------|
| **Ralph Wiggum** (2) | ralph_activator, ralph_wiggum_stop | Автономный цикл для сложных задач |
| **Guards** (3) | root-clutter-guard, bulk-action-guard, git-commit-enforcer | Защита от ошибок |
| **Domain routing** (3) | research-task-detector, decision-to-triad, search-optimizer | Маршрутизация задач |
| **Enforcement** (4) | knowledge-cache-reminder, factory-enforcer, task-enforcer, docs-change-tracker | Обязательные действия |

### Skills (9 штук)

| Категория | Skills | Назначение |
|-----------|--------|-----------|
| **Procedural** (4) | triad-factory, create-hook, doc-to-skill, task-evaluation | Алгоритмы и шаблоны |
| **Knowledge** (4) | 1c-doc-research, tech-research, architecture-research, hooks-skills-mcp-triad | Домены знаний + кеш |
| **Project** (1) | pdf-knowledge | Специфичные для PDF Framework |

---

## Path Resolution

Модуль `shared/core_paths.py` определяет пути:

```python
get_project_dir()  → .claude/           # Все файлы проекта
get_cache_dir()    → .claude/cache/     # hook-todos.json, lock files
get_state_dir()    → .claude/hooks/     # Ralph state files
```

---

## Автодокументирование

Hook `docs-change-tracker.py` отслеживает изменения и напоминает обновить документацию:

| Изменение в | Обновить документ |
|-------------|-------------------|
| `.claude/hooks/` | hooks-reference.md |
| `.claude/skills/` | skills-reference.md |
| `.claude/settings.json` | core-framework-separation.md |
| `src/pdf_framework/search/` | overview.md |
| `src/pdf_framework/agents/` | overview.md |
| `src/pdf_framework/config/` | overview.md |
| `src/pdf_framework/loaders/` | overview.md |
| `src/api/routes/` | overview.md |

Skip: `docs/architecture/`, `cache/`, `__pycache__`, `_index.json`.

---

## См. также

- **ADR-006** — `.claude/skills/architecture-research/adr/006-core-framework-separation.md`
- [Triad Architecture](triad-architecture.md) — Hooks + Skills + MCP
- [Hooks Reference](hooks-reference.md) — все 12 hooks
- [Skills Reference](skills-reference.md) — все 9 skills
