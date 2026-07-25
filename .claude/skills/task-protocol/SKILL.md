---
name: task-protocol
description: "Task Protocol: обязательный алгоритм выполнения задач. Classify → Skill Check → (Decompose) → Execute → Verify. Skill() ОБЯЗАТЕЛЕН для всех задач включая trivial. Триггеры: 'задача', 'implement', 'реализовать', 'new feature', 'добавь', 'сделай', 'создай функцию'."
---

# task-protocol — Mandatory Execution Algorithm

## Overview

**ALL tasks** (включая trivial) требуют проверки скиллов через `Skill()` перед Write/Edit. Enforcement через хуки блокирует Write/Edit пока `Skill()` не вызван.

---

## Algorithm

```
USER PROMPT
  │
  ▼
CLASSIFY complexity (auto)
  │
  ├── trivial  (< 30 words, no multi-file markers)
  │     │
  │     ▼
  │   SKILL CHECK ← обязательно!
  │   Skill('relevant') or Skill('learning-loop')
  │     │
  │     ▼
  │   EXECUTE (Write/Edit) ← разблокировано
  │
  ├── medium (1-3 files)
  │     │
  │     ▼
  │   DECOMPOSE → TaskCreate (subtasks)
  │     │
  │     ▼
  │   FOR EACH subtask:
  │     SKILL CHECK → Skill() or Skill('learning-loop')
  │     EXECUTE → TaskUpdate(completed)
  │     │
  │     ▼
  │   VERIFY → Skill('code-verify')
  │
  └── complex (4+ files)
        │
        ▼
      DECOMPOSE → TaskCreate (full decomposition)
        │
        ▼
      FOR EACH subtask:
        SKILL CHECK → Skill() or Skill('learning-loop')
        EXECUTE → TaskUpdate(completed)
        │
        ▼
      VERIFY → Skill('code-verify')
```

---

## Phase Machine

```
idle → classified → skill_checked → ALLOW Write/Edit
idle → classified → decomposed → skill_checked → ALLOW Write/Edit
```

| Phase | Что произошло | Write/Edit |
|-------|--------------|------------|
| `idle` | Ничего | BLOCKED |
| `classified` | Промпт классифицирован | BLOCKED |
| `decomposed` | TaskCreate вызван | BLOCKED |
| `skill_checked` | Skill() вызван | ALLOWED |

**Фаза монотонна — назад не откатывается** (фикс 2026-07-25, ретро 260725). До фикса
`record_decomposition` писала `decomposed` безусловно, поэтому порядок
**Skill() → TaskCreate → Write** сбрасывал уже достигнутый `skill_checked` и ронял
легитимную запись в ложный блок «Decomposed but skills not checked» (за одну сессию
сработало 5 раз). Теперь `decomposed` ставится только если фаза ещё не `skill_checked`;
`subtask_count` растёт независимо от фазы. Симметрично `set_task_classified`, где guard
«не понижать из decomposed» был с самого начала.
Регресс: [`tests/unit/test_task_protocol_phase_monotonic.py`](../../../tests/unit/test_task_protocol_phase_monotonic.py).

Сброс в `idle` на новом промпте (UserPromptSubmit) — **штатное** поведение: новый промпт =
новая задача, скилл нужно подтвердить заново.

---

## Classification Heuristic

| Complexity | Criteria | Action |
|------------|----------|--------|
| **trivial** | < 30 words, no multi-file indicators | Skill check → Write |
| **medium** | 30-100 words, 1-3 files | TaskCreate → Skill check → Write |
| **complex** | 100+ words or 4+ files | Full TaskCreate → Skill check → Write |

**Multi-file indicators** (force non-trivial): 'и также', 'а также', 'плюс', 'additionally', 'across', 'multiple files', 'refactor', 'все файлы', 'each file'.

---

## Step-by-Step

### 1. CLASSIFY

Автоматически через `skill-eval-enforcer-shell`. Можно уточнить:
```
This is a MEDIUM task (2 files affected).
```

### 2. DECOMPOSE (if not trivial)

```
TaskCreate: "Add validation to UserInput schema"
TaskCreate: "Update API endpoint to use new schema"
```

### 3. SKILL CHECK (MANDATORY for ALL tasks)

**Перед любым Write/Edit** — проверить скиллы:
- Проверить `<available_skills>` в контексте
- Проверить рекомендации `[SKILL-ROUTER]`
- Если найден релевантный скилл → `Skill('skill-name')`
- Если скилла нет → `Skill('learning-loop')` (поиск + создание)

**Write/Edit будет ЗАБЛОКИРОВАН пока Skill() не вызван.**

### 4. EXECUTE

Код пишется с учётом знаний из скилла:
```
TaskUpdate(taskId, status="in_progress")
... write code ...
TaskUpdate(taskId, status="completed")
```

### 5. VERIFY

После всех изменений:
- `Skill('code-verify')` для ревью кода

### 6. CAPTURE (после verify PASS — roadmap 260611 P1.1)

Для **нетривиальных** задач (medium/complex) после verify PASS — зафиксировать
переиспользуемый паттерн в карантин skill-learning:

```
mcp__skill-learning__capture_pattern(
  pattern_type="workflow-pattern" | "bsl-pattern" | "error-fix",
  name=..., content="проблема → решение (1-3 предложения)",
  evidence_sources=[{"session": <sid>, "files": [...]}],
  require_confirmation=true,
)
```

`action=dup`/`dup_rejected` в ответе — паттерн уже известен/отклонён, не дублировать.

**Негативный вход (P1.3):** если пользователь явно скорректировал ранее применённый
тобой паттерн («не так, надо иначе») — зафиксируй анти-паттерн:
`capture_pattern(confidence=0.3, ...)` → немедленный `reject_pattern(pattern_id)`.
Rejected-silo блокирует повторный авто-захват этого контента (P0.2 dedup).

---

## Antipatterns

| Antipattern | Correct Approach |
|------------|-----------------|
| Jump to Write/Edit without Skill() | Always call Skill() first — enforcer blocks otherwise |
| Skip skill search for "trivial" | ALL tasks require Skill() — even trivial |
| Mention skill without Skill() call | Only Skill() tool call counts, not text mention |
| One giant TaskCreate | Break into logical subtasks (1 per concern) |
| Skip verify | Always Skill('code-verify') after code changes |
| No skill exists → skip | Use Skill('learning-loop') to search and create |

---

## Enforcement

- **task-protocol-enforcer** (PreToolUse:Write|Edit) — blocks unless phase == `skill_checked`
- **task-protocol-observer** (**PreToolUse**:`Skill` / `TaskCreate` / `llm_complete`) — records
  decomposition and skill check. ⚠ Именно **Pre**, а не Post (сверено с `settings.json`
  2026-07-25): регистрация на PostToolUse была бы ненадёжна на Windows (#6305), но её и нет —
  прежняя строка «PostToolUse:TaskCreate|Skill» была дрейфом документации
- **skill-eval-enforcer-shell** (UserPromptSubmit) — auto-classifies, resets protocol
- Exempt files: `.claude/`, `docs/`, `data/`, config files (`.json`, `.toml`, `.yml`, `.env`)

---

## Examples

### Trivial Task
```
User: "Fix typo in README"
→ Auto-classified as trivial
→ Check skills → Skill('pdf-knowledge') or no relevant skill
→ If no skill: Skill('learning-loop') — or any Skill() call
→ Write/Edit UNBLOCKED
→ Fix typo
```

### Medium Task
```
User: "Add input validation to the search endpoint"
→ Classify: MEDIUM (2 files)
→ TaskCreate: "Add SearchQuery validation schema"
→ TaskCreate: "Update search endpoint"
→ Skill('pdf-knowledge') for search context
→ Execute each subtask → Write/Edit allowed
→ Skill('code-verify')
```

### Complex Task
```
User: "Implement multi-tenant support for vector store"
→ Classify: COMPLEX (5+ files)
→ TaskCreate: full decomposition (6 subtasks)
→ Skill('architecture-research') for design
→ Execute each subtask with relevant skills
→ Skill('code-verify')
```
