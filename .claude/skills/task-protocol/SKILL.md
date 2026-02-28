---
name: task-protocol
description: "Task Protocol: обязательный алгоритм выполнения задач. Classify → Decompose → Skill Search → Execute → Verify. Триггеры: 'задача', 'implement', 'реализовать', 'new feature', 'добавь', 'сделай', 'создай функцию'. НЕ для trivial (typo fix, 1 строка) — они авто-классифицируются."
---

# task-protocol — Mandatory Execution Algorithm

## Overview

Every non-trivial task MUST follow this protocol. Enforcement via hooks blocks Write/Edit until protocol is satisfied.

---

## Algorithm

```
USER PROMPT
  │
  ▼
CLASSIFY complexity
  ├── trivial  (< 1 file, < 30 words) → auto-allow → EXECUTE directly
  ├── medium   (1-3 files)            → DECOMPOSE → per-subtask flow
  └── complex  (4+ files)             → DECOMPOSE → per-subtask flow
                                         │
                                         ▼
                                    TaskCreate (subtasks)
                                         │
                                         ▼
                                    FOR EACH subtask:
                                      1. SKILL SEARCH (check available skills)
                                      2. Skill() activate OR Skill('learning-loop')
                                      3. EXECUTE (Write/Edit code)
                                      4. TaskUpdate(completed)
                                         │
                                         ▼
                                    VERIFY (code-verify)
```

---

## Classification Heuristic

| Complexity | Criteria | Action |
|------------|----------|--------|
| **trivial** | < 30 words in prompt, single file, no multi-file indicators | Auto-classified, Write/Edit allowed immediately |
| **medium** | 1-3 files affected, 30-100 words | Must TaskCreate at least 1 subtask |
| **complex** | 4+ files, 100+ words, architectural changes | Must TaskCreate with full decomposition |

**Multi-file indicators** (force non-trivial): 'и также', 'а также', 'плюс', 'additionally', 'across', 'multiple files', 'refactor', 'все файлы', 'each file'.

---

## Step-by-Step

### 1. CLASSIFY

State the complexity explicitly:
```
This is a MEDIUM task (2 files affected).
```

### 2. DECOMPOSE (if not trivial)

Use TaskCreate for each logical subtask:
```
TaskCreate: "Add validation to UserInput schema"
TaskCreate: "Update API endpoint to use new schema"
TaskCreate: "Add tests for validation"
```

### 3. SKILL SEARCH (per subtask)

Before implementing, check if a skill exists:
- Review `<available_skills>` in context
- Check `[SKILL-ROUTER]` recommendations
- If relevant skill found → `Skill('skill-name')`
- If no skill but need to learn → `Skill('learning-loop')`

### 4. EXECUTE

Write code following skill guidance. Mark subtask:
```
TaskUpdate(taskId, status="in_progress")
... write code ...
TaskUpdate(taskId, status="completed")
```

### 5. VERIFY

After all code changes, run verification:
- Skill('code-verify') for code review
- Run tests if applicable

---

## Antipatterns

| Antipattern | Correct Approach |
|------------|-----------------|
| Jump straight to Write/Edit | Classify first, then decompose |
| Skip skill search | Always check available skills before coding |
| One giant TaskCreate | Break into logical subtasks (1 per concern) |
| Forget TaskUpdate | Mark each subtask completed as you go |
| Skip verify on "simple" changes | Always verify code changes |
| Classify everything as trivial | Only truly trivial: typo fix, 1-line change, config tweak |

---

## Enforcement

- **task-protocol-enforcer** (PreToolUse:Write|Edit) blocks code changes if phase == "idle"
- **task-protocol-observer** (PostToolUse:TaskCreate) records decomposition in session state
- **skill-eval-enforcer-shell** (UserPromptSubmit) auto-classifies prompt complexity
- Exempt files: `.claude/`, `docs/`, `data/`, config files (`.json`, `.toml`, `.yml`, `.env`)

---

## Examples

### Trivial Task
```
User: "Fix typo in README"
→ Auto-classified as trivial (< 30 words, single file)
→ Write/Edit allowed immediately
→ No TaskCreate needed
```

### Medium Task
```
User: "Add input validation to the search endpoint"
→ Classify: MEDIUM (2 files: schema + endpoint)
→ TaskCreate: "Add SearchQuery validation schema"
→ TaskCreate: "Update search endpoint to validate input"
→ Skill('pdf-knowledge') for search context
→ Execute each subtask
→ Skill('code-verify')
```

### Complex Task
```
User: "Implement multi-tenant support for vector store"
→ Classify: COMPLEX (5+ files, architectural change)
→ TaskCreate: "Design tenant isolation schema"
→ TaskCreate: "Add tenant_id to VectorStore base class"
→ TaskCreate: "Update Qdrant provider with tenant filtering"
→ TaskCreate: "Update ChromaDB provider with tenant filtering"
→ TaskCreate: "Add tenant middleware to API"
→ TaskCreate: "Add tests for multi-tenant isolation"
→ Skill('architecture-research') for design
→ Execute each subtask with relevant skills
→ Skill('code-verify')
```
