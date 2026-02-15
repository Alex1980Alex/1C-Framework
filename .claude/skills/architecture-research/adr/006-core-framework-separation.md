# ADR-006: Разделение Core и Framework через User-Level / Project-Level

## Status: accepted (Phase 1 + Phase 2 + Phase 3 — COMPLETE)

## Date: 2026-02-12 (updated: 2026-02-14)

## Context

В проекте PDF Vector & Graph Framework перемешаны два слоя с разными жизненными циклами:

- **Core** (~27% кодовой базы): инфраструктура Claude Code CLI — hook protocol (BaseHook), FuzzyMatcher, TaskMaster, Ralph Wiggum, Triad Factory, generic guards. Стабильный слой, только улучшается.
- **Framework** (~73%): PDF-специфичная логика — domain hooks (research-task-detector), domain skills (1c-doc-research, tech-research), конфигурации, MCP server. Изменчивый слой — фичи добавляются и удаляются.

Проблема: нельзя переиспользовать Core в другом проекте без ручного копирования. Улучшения Core не портятся автоматически.

### Обнаруженные Constraints (Phase 1 Analysis)

При наивном переносе файлов обнаружены 4 критические точки связи:

1. **Import Coupling**: все 10 hooks импортируют `base/` и/или `shared/` через `sys.path.insert(0, os.path.dirname(__file__))` — ищут модули в СВОЕЙ директории
2. **Ralph State Hardcoded**: `shared/ralph_state.py` использовал `Path(__file__).parent.parent` — привязка к физической структуре каталогов
3. **Cache Path Hardcoded**: `task_master.py` и `hook_lock.py` строили путь к `.claude/cache/` через 3 уровня `parent.parent.parent`
4. **Cross-Level State**: ralph_wiggum_stop (Core) читает hook-todos.json, а factory-enforcer (Framework) пишет в него — нужна общая точка

## Decision

### Двухфазный подход:

**Phase 1: Infrastructure Refactoring (COMPLETE)**
Убрать все hardcoded пути, сделать hooks location-agnostic.

**Phase 2: Physical Separation (COMPLETE)**
Перенести Core в `~/.claude/`, оставить Framework в `.claude/`.

### Phase 1: Что сделано

#### 1. `shared/core_paths.py` — единый path resolver

```python
get_project_dir()  → .claude/ (project-level, найден по CWD)
get_cache_dir()    → .claude/cache/ (для hook-todos, lock files)
get_state_dir()    → .claude/hooks/ (для Ralph state files)
get_core_dir()     → ~/.claude/hooks/ или .claude/hooks/ (auto-detect)
```

Discovery order: `ENV var → user-level (~/.claude/) → project-level (.claude/)`.
State files ВСЕГДА в project-level (per-project, per-session).

#### 2. Refactored shared/ modules

- `ralph_state.py`: `HOOK_DIR = parent.parent` → `_get_state_dir()` via core_paths
- `task_master.py`: `CACHE_DIR = parent³/cache` → `get_cache_dir()` via core_paths
- `hook_lock.py`: `CACHE_DIR = parent³/cache` → `get_cache_dir()` via core_paths

#### 3. All 10 hooks updated — auto-discovery sys.path

Old (1 line):
```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

New (5 lines, location-agnostic):
```python
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)
```

Каждый hook:
1. Проверяет `~/.claude/hooks/shared/` (user-level Core)
2. Если есть — добавляет user-level в sys.path (приоритет)
3. Всегда добавляет свою директорию (fallback)

#### 4. Standalone hooks (ralph_stop, task-enforcer)

- `ralph_wiggum_stop.py`: `_find_hook_todos()` — пробует core_paths, fallback на relative path
- `task-enforcer.py`: `_find_cache_dir()` — аналогично
- `root-clutter-guard.py`: исправлен import (был `from protocol import`, стал `from base import`)

### Phase 2: Physical Separation — Что сделано

#### 1. Core перенесён в `~/.claude/` (User-Level)

```
~/.claude/
  hooks/
    base/                  # BaseHook, protocol.py
    shared/                # core_paths, FuzzyMatcher, TaskMaster, HookLock, RalphState
    ralph_activator.py     # UserPromptSubmit — Ralph activation
    ralph_wiggum_stop.py   # Stop — Ralph completion check
    root-clutter-guard.py  # PreToolUse/Write — блокирует мусор
    bulk-action-guard.py   # PostToolUse/Bash — детектит bulk ops
  skills/
    triad-factory/         # Фабрика триады
    create-hook/           # Шаблон создания хука
    doc-to-skill/          # Конвертер документации в SKILL.md
    task-evaluation/       # Research/Brainstorm/Hybrid классификатор
    1c-doc-research/       # Phase 3: Knowledge skill (с cache)
    tech-research/         # Phase 3: Knowledge skill (с cache)
    architecture-research/ # Phase 3: Knowledge skill (с cache + ADR)
    hooks-skills-mcp-triad/# Phase 3: Knowledge skill
  settings.json            # Core hooks → python (global Python 3.13)
```

#### 2. Framework остаётся в `.claude/` (Project-Level)

```
.claude/
  hooks/
    base/                  # FALLBACK (копия, если нет ~/.claude/)
    shared/                # FALLBACK
    research-task-detector.py
    decision-to-triad.py
    knowledge-cache-reminder.py
    factory-enforcer.py
    task-enforcer.py
    search-optimizer.py
    git-commit-enforcer.py
  skills/
    1c-doc-research/       # SKILL.md only (fallback, без cache)
    tech-research/         # SKILL.md only (fallback, без cache)
    architecture-research/ # SKILL.md only (fallback, без cache)
    hooks-skills-mcp-triad/# SKILL.md only (fallback)
    pdf-knowledge/         # Project-specific (полный, с SKILL.md)
  cache/                   # hook-todos.json, lock files
  settings.json            # Framework hooks → venv Python
```

#### 3. Path Resolution после разделения

| Path | Resolves to | Level |
|------|------------|-------|
| `core_dir` | `~/.claude/hooks/` | User-level (Core) |
| `project_dir` | `.claude/` | Project-level (Framework) |
| `cache_dir` | `.claude/cache/` | Project-level (per-project) |
| `state_dir` | `.claude/hooks/` | Project-level (Ralph state) |

#### 4. Python interpreters

- **Core hooks**: `python` (global Python 3.13) — Core hooks stdlib-only, FuzzyMatcher optional
- **Framework hooks**: `.venv/Scripts/python.exe` — project-specific with deps (pymorphy3, rapidfuzz)

### Phase 3: Knowledge Skills → Core — Что сделано

**Проблема**: Knowledge skills (1c-doc-research, tech-research, architecture-research, hooks-skills-mcp-triad) были в Framework, хотя нужны во всех проектах. Core содержал только процедурные скиллы (factory, evaluation).

**Решение**: Перенести knowledge skills в Core, оставить SKILL.md в Framework как fallback.

#### 1. Перенесённые skills (с cache)

| Skill | Тип | Cache |
|-------|-----|-------|
| `1c-doc-research` | Knowledge (5-phase, 8 categories) | `~/.claude/skills/1c-doc-research/cache/` |
| `tech-research` | Knowledge (5-phase, 7 categories) | `~/.claude/skills/tech-research/cache/` |
| `architecture-research` | Knowledge (3-tier: facts + ADR) | `~/.claude/skills/architecture-research/cache/` + `adr/` |
| `hooks-skills-mcp-triad` | Knowledge (reference) | — |

#### 2. Framework fallback

Knowledge skills в `.claude/skills/` содержат **только SKILL.md** (без cache/adr). Если кто-то клонирует проект без Core — инструкции работают, cache нет.

#### 3. Hook обновлён

`knowledge-cache-reminder.py`: все пути к cache обновлены на `~/.claude/skills/<skill>/cache/`.

#### Итог Core: 8 skills

- 4 процедурных: triad-factory, create-hook, doc-to-skill, task-evaluation
- 4 knowledge: 1c-doc-research, tech-research, architecture-research, hooks-skills-mcp-triad

## Consequences

### Positive
- Phase 1 + Phase 2 complete: полное разделение Core / Framework
- Core hooks автоматически работают в ЛЮБОМ проекте (user-level)
- Framework hooks работают из project-level, находят Core через auto-discovery
- `base/` и `shared/` в project-level — fallback на случай чистого клона без Core
- Claude Code нативно мерджит: hooks параллельно, skills по приоритету
- Core_paths поддерживает ENV vars для CI/CD и нестандартных конфигураций

### Negative
- 5 дополнительных строк sys.path в каждом hook (+50 строк total)
- core_paths.py добавляет indirect layer для path resolution
- Lazy-caching state dir может вызвать проблемы при смене CWD mid-session

### Mitigations
- ENV vars (`CLAUDE_CACHE_DIR`, `CLAUDE_STATE_DIR`, `CLAUDE_CORE_DIR`) для override
- Держать `~/.claude/` под git (отдельный приватный репо)
- Bootstrap-скрипт: `setup-core.sh` копирует core файлы в `~/.claude/`

## Verification

### Phase 1: 10/10 hooks location-agnostic
- decision-to-triad ✓ (UserPromptSubmit)
- ralph_activator ✓ (UserPromptSubmit)
- research-task-detector ✓ (UserPromptSubmit)
- bulk-action-guard ✓ (PostToolUse/Bash)
- factory-enforcer ✓ (PostToolUse/Write)
- knowledge-cache-reminder ✓ (PostToolUse/WebSearch)
- root-clutter-guard ✓ (PreToolUse/Write)
- search-optimizer ✓ (PreToolUse/Bash)
- ralph_wiggum_stop ✓ (Stop)
- task-enforcer ✓ (Stop)

### Phase 2: Physical separation verified
- Core hooks (4) running from `~/.claude/hooks/` with global Python ✓
- Framework hooks (7) running from `.claude/hooks/` with venv Python ✓
- `core_dir` resolves to `~/.claude/hooks/` (user-level) ✓
- `project_dir` / `cache_dir` / `state_dir` resolve to `.claude/` (project-level) ✓
- Framework hooks import BaseHook from user-level via auto-discovery ✓
- Claude Code skills merge: Core skills (4) from `~/.claude/skills/` + Framework skills (5) from `.claude/skills/` ✓
- Ralph lifecycle: activate(user-level) → state(project-level) → stop(user-level reads project-level) ✓

### Phase 3: Knowledge skills in Core verified
- Core skills: 8 (4 procedural + 4 knowledge) in `~/.claude/skills/` ✓
- Framework skills: 5 (SKILL.md-only fallback for 4, full for pdf-knowledge) ✓
- Cache lives in Core: `~/.claude/skills/<skill>/cache/` ✓
- ADR files in Core: `~/.claude/skills/architecture-research/adr/` ✓
- `knowledge-cache-reminder` hook points to `~/.claude/skills/` paths ✓
- Claude Code merge shows both levels (duplicates with priority) ✓

## Alternatives Considered

| Подход | Причина отказа |
|--------|---------------|
| A: Layered `.claude/` (submodule) | Нестандартные пути, ломает auto-discovery skills |
| B: Separate Git repo + pip | Overengineering для одного разработчика |
| C: Config-Driven YAML | Hooks всё равно дублируются, обновление ручное |
| Naive copy (no refactoring) | Import coupling, hardcoded paths — 7/10 hooks break |

## Research
- [core-vs-framework-separation.md](../cache/core-vs-framework-separation.md)
