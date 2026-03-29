# Roadmap v2: PostToolUse Hooks — Resilience & Performance

**Версия:** 1.0.0
**Дата:** 2026-03-29
**Статус:** PLANNED
**Предшественник:** 260329_ROADMAP_POSTTOOLUSE_HOOKS.md (v3.0.0 — COMPLETE)
**Триггер:** Анализ GitHub issues (#18427, #24788, #36121, #6371) и community patterns (Lefthook, Aider, Resilience4j)

---

## Обзор

Эволюция от работающей трёхуровневой системы (Guard → React → Enforce) к **устойчивой, производительной и самодиагностируемой** инфраструктуре хуков.

### Ключевые метрики

| Метрика | Текущее (v1 roadmap) | Цель (v2) |
|---------|---------------------|-----------|
| PostToolUse хуков | 8 (roadmap) + 11 (pre-existing) = 19 | 19 + 3 новых |
| Hook latency (Write\|Edit) | ~350ms (7 хуков serial) | <100ms (parallel + async) |
| False "Hook Error" в UI | неизвестно | 0 |
| Circuit breaker | нет | per-hook auto-disable |
| Async хуков | 0 | 4 (logging-only) |
| PostToolUseFailure | 0 | 2 |
| Conditional `if` field | 0 | 3 |
| Auto-fix loop | нет | ruff → Claude → ruff (max 3) |
| SQLite live write | 0 хуков | 8 хуков |
| PostCompact recovery | нет | context restore |

### Архитектура: текущая vs целевая

```
ТЕКУЩАЯ:
  Write/Edit → [7 sync hooks serial] → ~350ms → feedback

ЦЕЛЕВАЯ:
  Write/Edit → if field filter → [2 sync hooks] + [3 async hooks parallel] → <100ms
              ↓ fail?
              PostToolUseFailure → diagnostics
              ↓ compact?
              PostCompact → context restore
              ↓ hook crash?
              Circuit Breaker → auto-disable → probe → restore
```

---

## Фаза 5: Quick Wins (Effort: LOW)

**Приоритет:** Критический
**Цель:** Устранить известные баги, использовать новые фичи Claude Code v2.1.86+

---

### Шаг 5.1: stdin consumption — fix false "Hook Error"

**Цель:** Устранить false "Hook Error" в UI при раннем exit
**Источник:** [anthropics/claude-code#36121](https://github.com/anthropics/claude-code/issues/36121)

**Проблема:** Хуки делают `sys.exit(0)` до чтения stdin при non-matching tool_name → broken pipe → false error label.

**Файлы:**
- `.claude/hooks/posttooluse-skill-metrics.py` (модификация)
- `.claude/hooks/posttooluse-web-cache.py` (модификация)
- `.claude/hooks/posttooluse-docs-tracker.py` (модификация)
- `.claude/hooks/posttooluse-delegation-tracker.py` (модификация)
- `.claude/hooks/posttooluse-quality-feedback.py` (модификация)
- `.claude/hooks/posttooluse-bash-errors.py` (модификация)
- `.claude/hooks/posttooluse-auto-git-save.py` (модификация)
- `.claude/hooks/posttooluse-knowledge-cache.py` (модификация)

**Реализация:**

В каждом хуке заменить паттерн:
```python
# ❌ ТЕКУЩИЙ (stdin не потреблён при раннем exit):
def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except:
        sys.exit(0)

    if tool_name != "Skill":
        sys.exit(0)  # stdin прочитан, но другие хуки exit ДО чтения

# ✅ НОВЫЙ (stdin ВСЕГДА потреблён):
def main():
    stdin_data = sys.stdin.read()  # ВСЕГДА потребляем stdin
    try:
        input_data = json.loads(stdin_data)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)
    ...
```

**План тестирования:**
- [ ] Все 8 хуков читают stdin ДО любого exit
- [ ] Eval suite: 19/19 pass после изменений
- [ ] Manual: запустить 30-мин сессию, проверить отсутствие "Hook Error"
- [ ] Критерий успеха: 0 false "Hook Error" в UI

**Риски:** Минимальные — это refactor чтения stdin, не логики
**Rollback:** Git revert

---

### Шаг 5.2: `if` field — conditional hooks без spawn

**Цель:** Убрать ~50ms spawn overhead для non-matching файлов
**Источник:** Claude Code v2.1.86 changelog

**Файлы:**
- `.claude/settings.json` (модификация — добавить `if` field)

**Реализация:**

```json
{
  "matcher": "Write|Edit",
  "if": "Write(*.py)|Edit(*.py)",
  "hooks": [{
    "command": "python .../posttooluse-quality-feedback.py"
  }]
},
{
  "matcher": "Write|Edit",
  "if": "Write(*.bsl)|Edit(*.bsl)",
  "hooks": [{
    "command": "python .../bsl-impact-analysis.py"
  }]
},
{
  "matcher": "Write|Edit",
  "if": "Write(src/*)|Edit(src/*)|Write(scripts/*)|Edit(scripts/*)|Write(.claude/hooks/*)|Edit(.claude/hooks/*)",
  "hooks": [{
    "command": "python .../posttooluse-docs-tracker.py"
  }]
}
```

**План тестирования:**
- [ ] Write .py → quality-feedback fires
- [ ] Write .bsl → quality-feedback NOT fires, bsl-impact fires
- [ ] Write .json в cache/ → docs-tracker NOT fires
- [ ] Write .py в src/ → docs-tracker fires + quality-feedback fires
- [ ] Измерить latency: до и после (ожидание: -150ms на non-.py edits)
- [ ] Критерий успеха: hooks spawn only for matching files

**Риски:** `if` field syntax может отличаться от ожидаемого. Нужна верификация на реальной версии Claude Code.
**Rollback:** Убрать `if` field, вернуть фильтрацию в Python

---

### Шаг 5.3: `async: true` для logging хуков

**Цель:** 4 logging-only хука не блокируют tool execution
**Источник:** Roadmap v1 шаг 2.3 (DEFERRED), Claude Code docs

**Файлы:**
- `.claude/settings.json` (модификация — добавить `async: true`)

**Реализация:**

Хуки без feedback (не используют `hookSpecificOutput` для влияния на Claude):
```json
{
  "matcher": "Skill",
  "hooks": [{
    "command": "python .../posttooluse-skill-metrics.py",
    "async": true
  }]
},
{
  "matcher": "mcp__llm-rotation__llm_complete",
  "hooks": [{
    "command": "python .../posttooluse-delegation-tracker.py",
    "async": true
  }]
},
{
  "matcher": "WebSearch|WebFetch",
  "hooks": [{
    "command": "python .../posttooluse-knowledge-cache.py",
    "async": true
  }]
},
{
  "matcher": "Write|Edit",
  "hooks": [{
    "command": "python .../posttooluse-auto-git-save.py",
    "async": true
  }]
}
```

**Примечание:** `posttooluse-web-cache.py` остаётся sync — его feedback ("Cache: N entries") полезен для Claude. `posttooluse-quality-feedback.py` и `posttooluse-bash-errors.py` остаются sync — их feedback критичен.

**План тестирования:**
- [ ] Async хуки не блокируют tool execution
- [ ] Данные всё равно записываются в JSONL/log файлы
- [ ] Feedback от async хуков не доставляется (expected — logging only)
- [ ] Измерить latency: Write|Edit до и после (ожидание: -100ms)
- [ ] Критерий успеха: sync hooks latency <100ms для Write|Edit

**Риски:** `async: true` + `hookSpecificOutput` — feedback может не доставляться. Именно поэтому только logging хуки.
**Rollback:** Убрать `async: true`

---

### Шаг 5.4: PostToolUseFailure — реакция на ошибки

**Цель:** Ловить ошибки инструментов, которые PostToolUse пропускает
**Источник:** [anthropics/claude-code#6371](https://github.com/anthropics/claude-code/issues/6371), v2.1.9

**Файлы:**
- `.claude/hooks/posttooluse-failure-handler.py` (создание)
- `.claude/settings.json` (добавить PostToolUseFailure entry)

**Реализация:**
```python
#!/usr/bin/env python3
"""PostToolUseFailure handler — diagnostics for failed tools."""

import json, sys

def main():
    stdin_data = sys.stdin.read()
    try:
        input_data = json.loads(stdin_data)
    except (json.JSONDecodeError, Exception):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    error = input_data.get("error", input_data.get("tool_response", ""))

    diagnostics = []

    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")
        if "Permission" in str(error) or "Access" in str(error):
            diagnostics.append("Permission denied — check file/directory permissions")
        elif "No such file" in str(error) or "not found" in str(error):
            diagnostics.append(f"Path not found — verify parent directory exists: {file_path}")
        else:
            diagnostics.append(f"Write/Edit failed: {str(error)[:200]}")

    elif tool_name == "Bash":
        diagnostics.append(f"Command failed: {tool_input.get('command', '')[:100]}")

    elif "mcp__" in tool_name:
        diagnostics.append(f"MCP tool failed: {tool_name} — check server status")

    if diagnostics:
        feedback = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUseFailure",
                "additionalContext": "[TOOL-FAILURE] " + "; ".join(diagnostics)
            }
        }
        print(json.dumps(feedback, ensure_ascii=True))

    sys.exit(0)
```

settings.json:
```json
"PostToolUseFailure": [{
  "matcher": "Write|Edit|Bash|mcp__.*",
  "hooks": [{
    "command": "python D:/.../posttooluse-failure-handler.py"
  }]
}]
```

**План тестирования:**
- [ ] Simulated Write failure → diagnostics feedback
- [ ] Simulated Bash failure → command info
- [ ] Simulated MCP failure → server status hint
- [ ] Normal successful Write → PostToolUseFailure NOT triggered (confirmed by #6371)
- [ ] Критерий успеха: structured diagnostics on tool failures

**Риски:** `PostToolUseFailure` event format может отличаться от `PostToolUse`
**Rollback:** Удалить хук и entry из settings.json

---

## Фаза 6: Resilience (Effort: MEDIUM)

**Приоритет:** Высокий
**Цель:** Хуки не ломают workflow даже при собственных ошибках

---

### Шаг 6.1: Circuit Breaker per hook

**Цель:** Auto-disable сломавшихся хуков вместо cascading failures
**Источник:** Resilience4j CircuitBreaker, Netflix Hystrix

**Файлы:**
- `.claude/hooks/shared/circuit_breaker.py` (создание)
- `.claude/hooks/posttooluse-*.py` (модификация — wrap main() в circuit breaker)

**Реализация:**

```python
# shared/circuit_breaker.py

"""
Circuit Breaker for PostToolUse hooks.

States: CLOSED → OPEN → HALF_OPEN → CLOSED
- CLOSED: normal execution, counting failures
- OPEN: skip hook entirely (too many failures)
- HALF_OPEN: try one probe after cooldown

State stored in cache/circuit-breaker-state.json
"""

import json, time
from pathlib import Path

CACHE_FILE = Path(__file__).parent.parent.parent.parent / "cache" / "circuit-breaker-state.json"
FAILURE_THRESHOLD = 5        # failures before OPEN
RESET_TIMEOUT = 300          # seconds before HALF_OPEN
SUCCESS_THRESHOLD = 2        # successes in HALF_OPEN to CLOSE

def get_state(hook_name: str) -> dict:
    """Get circuit breaker state for a hook."""
    ...

def record_success(hook_name: str):
    """Record successful execution."""
    ...

def record_failure(hook_name: str, error: str = ""):
    """Record failed execution. May transition to OPEN."""
    ...

def is_open(hook_name: str) -> bool:
    """Check if circuit is OPEN (should skip hook)."""
    ...

def with_circuit_breaker(hook_name: str):
    """Decorator: skip execution if circuit is OPEN."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            if is_open(hook_name):
                return None  # skip silently
            try:
                result = func(*args, **kwargs)
                record_success(hook_name)
                return result
            except Exception as e:
                record_failure(hook_name, str(e))
                raise
        return wrapper
    return decorator
```

Использование в хуках:
```python
from shared.circuit_breaker import with_circuit_breaker

@with_circuit_breaker("posttooluse-quality-feedback")
def main():
    ...
```

**План тестирования:**
- [ ] Simulate 5 failures → circuit OPEN → hook skipped
- [ ] Wait 5 min → circuit HALF_OPEN → probe execution
- [ ] Probe success → circuit CLOSED → normal execution
- [ ] Probe failure → circuit OPEN again
- [ ] Verify state persistence in cache/circuit-breaker-state.json
- [ ] Dashboard shows circuit states
- [ ] Критерий успеха: flaky hook auto-disables, recovers after fix

**Риски:** Race condition при concurrent hook executions
**Rollback:** Убрать decorator, хуки работают как раньше (без circuit breaker)

---

### Шаг 6.2: Reflected Message Loop — auto-fix цикл

**Цель:** quality-feedback → Claude auto-fix → quality re-check (max 3 iterations)
**Источник:** Aider `linter.py` `reflected_message` + `max_reflections`

**Файлы:**
- `.claude/hooks/posttooluse-quality-feedback.py` (модификация)
- `.claude/hooks/shared/reflection_tracker.py` (создание)

**Реализация:**

```python
# shared/reflection_tracker.py

"""
Tracks reflection loops to prevent infinite fix cycles.

Pattern: PostToolUse detects issue → feedback → Claude fixes →
         PostToolUse re-checks → clean? done : reflect again

Max reflections per file per session: 3
"""

CACHE_FILE = "cache/reflection-tracker.json"
MAX_REFLECTIONS = 3

def can_reflect(file_path: str) -> bool:
    """Check if file hasn't exceeded max reflections."""
    ...

def record_reflection(file_path: str):
    """Increment reflection count for file."""
    ...

def reset_reflections(file_path: str):
    """Reset on clean check (no issues found)."""
    ...
```

Модификация quality-feedback:
```python
# В posttooluse-quality-feedback.py:
from shared.reflection_tracker import can_reflect, record_reflection, reset_reflections

if analysis and analysis.get("issues"):
    if can_reflect(file_path):
        record_reflection(file_path)
        feedback = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": (
                    f"[QUALITY] ruff found {n} issue(s) in {name}:\n"
                    f"{formatted_issues}\n"
                    f"[ACTION REQUIRED] Fix these issues now. "
                    f"Reflection {count}/{MAX_REFLECTIONS}."
                )
            }
        }
    else:
        # Max reflections reached — advisory only
        feedback = { ... "[QUALITY] (max reflections reached, advisory only)" }
else:
    reset_reflections(file_path)  # clean check resets counter
```

**План тестирования:**
- [ ] Write .py с ошибкой → feedback с "ACTION REQUIRED"
- [ ] Claude исправляет → Write → ruff clean → reset reflections
- [ ] Claude не исправляет → 3 reflections → advisory only (no infinite loop)
- [ ] Критерий успеха: auto-fix loop работает, max 3 итерации

**Риски:** Claude может не реагировать на "ACTION REQUIRED". hookSpecificOutput advisory, не blocking.
**Rollback:** Убрать reflection tracking, вернуть simple feedback

---

## Фаза 7: Performance (Effort: MEDIUM)

**Приоритет:** Средний
**Цель:** Минимизировать overhead хуков на critical path

---

### Шаг 7.1: Priority groups + parallel execution

**Цель:** Организовать 7 Write|Edit хуков в parallel groups
**Источник:** Lefthook `priority` + `parallel`, lint-staged concurrent

**Проблема:** Сейчас на Write|Edit последовательно запускается 7 хуков (~350ms):
1. skill-linker.py
2. bsl-impact-analysis.py
3. posttooluse-docs-tracker.py
4. posttooluse-quality-feedback.py
5. posttooluse-auto-git-save.py
6. git-commit-reminder.py
7. documentation-blocker.py

**Реализация (settings.json):**

```json
"PostToolUse": [
  {
    "matcher": "Write|Edit",
    "hooks": [
      {"command": "python .../posttooluse-docs-tracker.py", "async": true},
      {"command": "python .../posttooluse-auto-git-save.py", "async": true},
      {"command": "python .../skill-linker.py", "async": true}
    ]
  },
  {
    "matcher": "Write|Edit",
    "if": "Write(*.py)|Edit(*.py)",
    "hooks": [
      {"command": "python .../posttooluse-quality-feedback.py"}
    ]
  },
  {
    "matcher": "Write|Edit",
    "if": "Write(*.bsl)|Edit(*.bsl)",
    "hooks": [
      {"command": "python .../bsl-impact-analysis.py"}
    ]
  },
  {
    "matcher": "Write|Edit|mcp__filesystem__*",
    "hooks": [
      {"command": "python .../git-commit-reminder.py"},
      {"command": "python .../documentation-blocker.py"}
    ]
  }
]
```

**Ожидаемый результат:**
- Write .py: quality-feedback (sync, ~50ms) + 3 async → **~50ms** (было ~350ms)
- Write .bsl: bsl-impact (sync, ~50ms) + 3 async → **~50ms**
- Write .json: 3 async + git/docs (sync, ~100ms) → **~100ms**

**План тестирования:**
- [ ] Измерить latency до реорганизации (baseline)
- [ ] Применить новую структуру
- [ ] Измерить latency после (ожидание: <100ms для Write|Edit)
- [ ] Verify: async хуки пишут в логи (data/ файлы обновляются)
- [ ] Verify: sync хуки возвращают feedback
- [ ] 30-мин stress test: нет пропущенных событий
- [ ] Критерий успеха: Write|Edit latency <100ms (p95)

**Риски:** Claude Code может не поддерживать `async` + `if` одновременно. Порядок execution в пределах entry может быть undefined.
**Rollback:** Вернуть текущую sequential структуру

---

### Шаг 7.2: SQLite live write

**Цель:** Хуки пишут напрямую в SQLite вместо JSONL
**Источник:** Roadmap v1 шаг 3.4 (migration script готов)

**Файлы:**
- `.claude/hooks/shared/db_writer.py` (создание — thread-safe SQLite writer)
- `.claude/hooks/posttooluse-skill-metrics.py` (модификация)
- `.claude/hooks/posttooluse-delegation-tracker.py` (модификация)
- `.claude/hooks/posttooluse-quality-feedback.py` (модификация)
- `.claude/hooks/shared/latency_tracker.py` (модификация)

**Реализация:**

```python
# shared/db_writer.py

"""
Thread-safe SQLite writer for hook metrics.
Uses WAL mode for concurrent read/write.
Auto-creates tables on first write.
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent.parent.parent / "data" / "hooks.db"

@contextmanager
def get_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def log_hook_event(hook_name, tool_name, latency_ms, status="ok", metadata=None):
    ...

def log_skill_usage(skill_name, args, session_id, response_len, success):
    ...

def log_delegation(provider, model, response_time, quality, content_type, ...):
    ...

def log_quality_issue(file_path, tool, issue_count, issues):
    ...
```

**План тестирования:**
- [ ] Write events записываются в SQLite (не JSONL)
- [ ] Concurrent writes не вызывают lock errors (WAL mode)
- [ ] Dashboard читает из SQLite
- [ ] Migration script: JSONL → SQLite (existing data preserved)
- [ ] Performance: <5ms per write (vs ~2ms JSONL)
- [ ] Критерий успеха: все метрики в SQLite, query <10ms

**Риски:** SQLite lock contention при parallel async хуках
**Rollback:** Вернуть JSONL write, SQLite как read-only analytics

---

## Фаза 8: Context Recovery (Effort: LOW)

**Приоритет:** Средний
**Цель:** Не терять контекст при compaction и между сессиями

---

### Шаг 8.1: PostCompact — восстановление контекста

**Цель:** Re-inject критический контекст после auto-compact
**Источник:** Claude Code v2.1.76, [#36121](https://github.com/anthropics/claude-code/issues/36121) bug #3

**Файлы:**
- `.claude/hooks/postcompact-context-restore.py` (создание)
- `.claude/settings.json` (добавить PostCompact entry)

**Реализация:**

```python
#!/usr/bin/env python3
"""
PostCompact — Re-inject critical context after auto-compaction.

Restores:
- Active project info (from cache/active-project.json)
- Session state summary (from cache/session-state.json)
- Pending tasks count (from cache/hook-todos.json)
- Circuit breaker states (from cache/circuit-breaker-state.json)
"""

import json, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
CACHE = PROJECT_ROOT / "cache"

def main():
    stdin_data = sys.stdin.read()

    context_parts = []

    # Active project
    ap = CACHE / "active-project.json"
    if ap.exists():
        data = json.loads(ap.read_text(encoding='utf-8'))
        if data.get("project_name"):
            context_parts.append(f"Active project: {data['project_name']}")

    # Session state
    ss = CACHE / "session-state.json"
    if ss.exists():
        data = json.loads(ss.read_text(encoding='utf-8'))
        skills = data.get("skills", [])
        if skills:
            names = [s["name"] for s in skills[-5:]]
            context_parts.append(f"Recent skills: {', '.join(names)}")

    # Pending tasks
    ht = CACHE / "hook-todos.json"
    if ht.exists():
        data = json.loads(ht.read_text(encoding='utf-8'))
        pending = [t for t in data.get("todos", []) if t.get("status") == "pending"]
        if pending:
            context_parts.append(f"Pending tasks: {len(pending)}")

    if context_parts:
        feedback = {
            "hookSpecificOutput": {
                "hookEventName": "PostCompact",
                "additionalContext": "[CONTEXT RESTORED] " + " | ".join(context_parts)
            }
        }
        print(json.dumps(feedback, ensure_ascii=True))

    sys.exit(0)
```

settings.json:
```json
"PostCompact": [{
  "matcher": "auto|manual",
  "hooks": [{
    "command": "python D:/.../postcompact-context-restore.py"
  }]
}]
```

**План тестирования:**
- [ ] Trigger auto-compact → PostCompact fires → context restored
- [ ] Manual compact → same behavior
- [ ] Empty cache → no crash, no feedback (graceful)
- [ ] Verify Claude sees restored context in system-reminder
- [ ] Критерий успеха: active project + pending tasks visible after compact

**Риски:** `PostCompact` event может не поддерживать `hookSpecificOutput`. Нужна верификация.
**Rollback:** Удалить хук

---

## Сводная таблица

| Фаза | Шаг | Название | Effort | Impact | Зависит от |
|------|-----|----------|--------|--------|------------|
| **5** | 5.1 | stdin consumption fix | LOW | HIGH | — |
| **5** | 5.2 | `if` field conditional | LOW | HIGH | — |
| **5** | 5.3 | `async: true` logging | LOW | MEDIUM | — |
| **5** | 5.4 | PostToolUseFailure handler | LOW | MEDIUM | — |
| **6** | 6.1 | Circuit Breaker per hook | MEDIUM | HIGH | — |
| **6** | 6.2 | Reflected Message Loop | MEDIUM | HIGH | 5.1 |
| **7** | 7.1 | Priority groups + parallel | MEDIUM | HIGH | 5.2, 5.3 |
| **7** | 7.2 | SQLite live write | MEDIUM | MEDIUM | 6.1 |
| **8** | 8.1 | PostCompact context restore | LOW | MEDIUM | — |

## Порядок реализации

```
Неделя 1 (Quick Wins):
  5.1 stdin fix ──────┐
  5.2 if field ───────┤ параллельно
  5.3 async:true ─────┤
  5.4 PostToolUseFail ┘

Неделя 2 (Resilience):
  6.1 Circuit Breaker ─→ 6.2 Reflected Loop

Неделя 3 (Performance):
  7.1 Priority groups (зависит от 5.2 + 5.3)
  7.2 SQLite live write (зависит от 6.1)

Неделя 4 (Context):
  8.1 PostCompact restore
```

## Метрики успеха всего Roadmap v2

| Метрика | Текущее | Цель | Как измерить |
|---------|---------|------|-------------|
| Write\|Edit hook latency (p95) | ~350ms | <100ms | `data/hook-latency.jsonl` |
| False "Hook Error" | неизвестно | 0 | Visual inspection в UI |
| Hook failure cascade | whole session | isolated per-hook | Circuit breaker state |
| Auto-fix success rate | 0% (no loop) | >50% ruff issues | `data/quality-metrics.jsonl` |
| Tool failure diagnostics | none | structured feedback | PostToolUseFailure log |
| Context after compact | lost | restored | PostCompact feedback |
| Metrics query speed | ~30s (JSONL grep) | <10ms (SQLite) | `data/hooks.db` |

### Формула завершения

```
Roadmap v2 DONE когда:
  ✓ Фаза 5: 4/4 quick wins deployed + tested
  ✓ Фаза 6: circuit breaker active + reflected loop working
  ✓ Фаза 7: Write|Edit latency <100ms (p95)
  ✓ Фаза 8: PostCompact restores context
```

---

## Источники

### GitHub Issues
- [#18427](https://github.com/anthropics/claude-code/issues/18427) — PostToolUse additionalContext не работает
- [#24788](https://github.com/anthropics/claude-code/issues/24788) — PostToolUse + MCP additionalContext не доставляется
- [#36121](https://github.com/anthropics/claude-code/issues/36121) — Community workarounds for 5 open bugs
- [#6371](https://github.com/anthropics/claude-code/issues/6371) — PostToolUse не вызывается для failed tools
- [#33656](https://github.com/anthropics/claude-code/issues/33656) — PostToolUse "hook error" при non-zero Bash
- [#5513](https://github.com/anthropics/claude-code/issues/5513) — Нет hook hot-reload (81 upvotes)
- [#19627](https://github.com/anthropics/claude-code/issues/19627) — High latency in hook invocation
- [#34600](https://github.com/anthropics/claude-code/issues/34600) — Exit code 2 displays as error

### Community Patterns
- [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) — 13 lifecycle events
- [disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability) — Real-time monitoring
- [Aider linter.py](https://github.com/Aider-AI/aider) — Reflected message loop
- [Lefthook](https://github.com/evilmartians/lefthook) — Priority + parallel execution
- [Resilience4j](https://github.com/resilience4j/resilience4j) — Circuit Breaker pattern
