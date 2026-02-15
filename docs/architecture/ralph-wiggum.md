# Ralph Wiggum — Autonomous Loop System

## Overview

Ralph Wiggum is a dual-purpose system that provides:

1. **Autonomous Loop** (Hooks) — prevents Claude from stopping prematurely on complex tasks
2. **Self-Correcting Retry** (LLM Calls) — feedback-driven retries in all LLM integrations

Philosophy: **"Failures are data"** — instead of treating errors as terminal, both systems feed failure information back into the next iteration for self-improvement.

---

## Part 1: Autonomous Loop

Three hooks work together to create an autonomous execution loop:

```
ralph_activator.py (UserPromptSubmit)
    |
    v
Creates .ralph_active + .ralph_criteria.json
    |
    v
Claude works on task (multiple iterations)
    |
    v
Other hooks create mandatory tasks (hook-todos.json)
    |
    v
Claude tries to stop
    |
    v
ralph_wiggum_stop.py (Stop)
    |
    v
Criteria met? ──yes──> deactivate, allow stop
    |
    no
    |
    v
Block stop (exit 2), Claude continues
```

### Activation: ralph_activator.py

**Event**: `UserPromptSubmit` (fires on every user prompt)
**Level**: Core (`~/.claude/hooks/`)
**Python**: Global (stdlib-only)

#### Negative-First Detection

The hook uses a **negative-first** approach — filters out simple tasks before checking for complex ones:

1. Check `SIMPLE_SIGNALS` — if 2+ match, skip Ralph entirely
2. Check complex task tiers — activate if any matches

Simple signals that NEVER trigger Ralph:
- Fix/typo commands: "fix", "typo", "исправь", "поправь"
- Read commands: "покажи", "прочитай", "открой"
- Git operations: "git status", "commit", "push"
- Single-line edits: "удали строку", "переименуй"
- Questions: "что это", "объясни", "расскажи"

#### Tier System

| Tier | Type | Max Iterations | Criteria | Signals |
|------|------|---------------|----------|---------|
| 0 | Simple | — (skip) | — | "fix", "typo", "покажи", "git status" |
| 1 | Factory | 12 | settings.json updated, MEMORY.md updated, test passed | "новый хук", "фабрика", "триада" |
| 2 | Phase | 15 | all files created, tests pass, MEMORY.md updated | "новая фаза", "implement phase", "новый pipeline" |
| 2.5 | Brainstorm | 10 | comparison table created, recommendation given | "придумай", "предложи", "какой подход выбрать" |
| 3 | Research | 8 | cache saved, _index.json updated | "исследуй", "сравни подходы", "обзор по" |
| 4 | Multi-step | 10 | all listed items completed | Numbered lists (3+), sequential markers |
| 5 | Fuzzy | 10 | (varies) | pymorphy3 lemmatization fallback |

**Detection order**: Simple(skip) → Factory → Phase → Brainstorm → Research → Multi-step → Fuzzy

#### Fuzzy Fallback

When no phrase matches, `FuzzyMatcher` (pymorphy3 + rapidfuzz) tries single-word matching:

```python
keywords = [
    "исследовать", "проанализировать", "реализовать",
    "автоматизировать", "интегрировать", "рефакторить",
    "мигрировать", "оптимизировать"
]
threshold = 78  # rapidfuzz score
required_matches = 2  # need 2+ fuzzy matches
```

#### Activation Output

When activated, the hook injects a system message:

```
[RALPH-ACTIVATED] Autonomous mode ON (type=factory, max 12 iterations).

Ralph Wiggum автономный цикл активирован.
Claude НЕ остановится пока все критерии не выполнены:
  - settings.json updated
  - MEMORY.md updated
  - test passed

Когда ВСЕ критерии выполнены, включи маркер: RALPH_DONE
```

### State Management: shared/ralph_state.py

**Location**: `~/.claude/hooks/shared/ralph_state.py`

#### State Files (always in project-level `.claude/hooks/`)

| File | Purpose |
|------|---------|
| `.ralph_active` | Flag file (existence = active) |
| `.ralph_criteria.json` | Structured criteria + metadata |
| `.ralph_wiggum_count` | Iteration counter |

#### .ralph_criteria.json Format

```json
{
  "task_type": "factory",
  "activated_at": "2026-02-14T17:49:00.123456+00:00",
  "prompt_excerpt": "first 200 chars of user prompt...",
  "completion_criteria": ["settings.json updated", "test passed"],
  "max_iterations": 12
}
```

#### API

```python
activate(task_type, prompt_excerpt, criteria, max_iterations)
deactivate()                    # Removes all state files
is_active() -> bool             # .ralph_active exists?
is_stale() -> bool              # activated_at > 2 hours ago?
increment_iteration() -> int    # Atomic increment + return
get_max_iterations() -> int     # From criteria or DEFAULT (15)
```

#### Constants

```python
DEFAULT_MAX_ITERATIONS = 15
STALE_HOURS = 2  # Auto-deactivate after 2 hours
```

#### Atomic Writes

All file operations use temp + rename pattern for crash safety:

```python
fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp", prefix=".ralph_")
with os.fdopen(fd, "w") as f:
    json.dump(data, f)
os.replace(tmp, path)  # Atomic on both Windows and Unix
```

### Exit Control: ralph_wiggum_stop.py

**Event**: `Stop` (when Claude tries to finish)
**Level**: Core (`~/.claude/hooks/`)

#### 9-Step Decision Cascade

```
1. Ralph not active?              → allow stop (exit 0)
2. Stale activation (>2 hours)?   → auto-deactivate, allow stop
3. Max iterations reached?        → force deactivate, allow stop
4. RALPH_DONE marker in output?   → deactivate, allow stop
5. All structured criteria met?   → deactivate, allow stop
6. Pending mandatory tasks?       → BLOCK (exit 2)
7. Incomplete signals found?      → BLOCK (exit 2)
8. Early iterations (<=3)?        → BLOCK (exit 2)
9. Later iterations, no signals?  → allow stop (exit 0)
```

#### Completion Markers

```python
COMPLETION_MARKERS = ["RALPH_DONE", "TASK_COMPLETE_OK", "ALL_DONE"]
```

Claude can include any of these in its output to signal completion.

#### Criteria Signal Mapping

The hook checks the transcript for evidence that criteria are met:

| Criterion | Signals Searched |
|-----------|-----------------|
| `cache saved` | cache, saved, кеш, сохранен, cached |
| `_index.json updated` | _index.json, index updated, индекс обновлен |
| `settings.json updated` | settings.json |
| `MEMORY.md updated` | memory.md, memory updated |
| `test passed` | test pass, tests pass, тест пройден, verified |
| `all files created` | created, написан, создан |
| `comparison table created` | comparison, таблица, matrix, pros, cons |
| `recommendation given` | recommendation, рекомендация, выбран, chosen |

#### Incomplete Signals (block exit)

```python
INCOMPLETE_SIGNALS = [
    "todo", "fixme", "need to", "will implement", "next step",
    "pending", "will continue", "need to register", "need to test",
    "need to save", "need to update",
]
```

#### Mandatory Task Blocking

The stop hook checks `hook-todos.json` for pending tasks from mandatory hooks:

```python
MANDATORY_HOOKS = {
    "knowledge-cache-reminder-hook",
    "factory-enforcer-hook",
}
```

If any mandatory tasks are pending → block stop, inject reminder.

### Task Coordination: shared/task_master.py

Cross-process-safe task management for inter-hook communication.

#### Features

- Atomic writes (temp file + rename)
- Cross-platform file locking (Windows msvcrt / Unix fcntl)
- Stats self-validation
- Cooldown checks (prevent rapid task re-creation)
- STRICT MODE: complete instead of delete (audit trail)

#### hook-todos.json Format

```json
{
  "todos": [
    {
      "content": "Save research results to knowledge cache",
      "description": "Phase 5 of skill: create topic file...",
      "status": "pending",
      "priority": "high",
      "createdBy": "knowledge-cache-reminder-hook",
      "createdAt": "2026-02-14T17:30:00.123456",
      "completedAt": null
    }
  ],
  "timestamp": "...",
  "stats": { "total": 1, "pending": 1, "in_progress": 0, "completed": 0 }
}
```

---

## Part 2: Self-Correcting Retry Pattern

The "Ralph Wiggum" pattern in the codebase is a **feedback-driven retry loop** used in all LLM calls. Instead of blind retries, the system passes the **reason for failure** to the next attempt.

### Pattern Template

```python
# Ralph Wiggum: self-correcting retry
max_rw_retries = 2
rw_feedback = ""

for rw_attempt in range(1, max_rw_retries + 1):
    try:
        messages = list(base_messages)
        if rw_feedback:
            messages.append(HumanMessage(content=f"CORRECTION: {rw_feedback}"))

        response = await llm.ainvoke(messages)
        result = parse_response(response)

        # Validate result
        if not is_valid(result):
            rw_feedback = f"Validation failed: {reason}. Please fix."
            continue  # Retry WITH feedback

        return result  # Success

    except Exception as e:
        rw_feedback = f"Previous call failed: {e}."

# All retries exhausted — graceful degradation
return fallback_value
```

### Key Principles

1. **Max 2 attempts** — controls costs, prevents infinite loops
2. **Feedback-driven** — pass specific failure reason, not blind retry
3. **Validators** — check length, language, format, identity, JSON structure
4. **Graceful degradation** — always return a fallback on complete failure

### Integration Points (13 points across 10 files)

| File | Validator | What it Checks |
|------|-----------|---------------|
| `agents/rag/nodes/grader.py` | Format | Response starts with yes/no/relevant/not |
| `agents/rag/nodes/hallucination_checker.py` | Format | Starts with grounded/not_grounded |
| `agents/rag/nodes/rewriter.py` | Prefix cleanup | Removes "Rewritten:", "Here is..." |
| `agents/rag/agent.py` | Answer quality | Non-empty, non-refusal answer |
| `processing/context_generator.py` | Length + refusal | Context >= 15 chars, not a refusal |
| `search/query_expansion.py` | Count | N alternatives generated, non-empty |
| `search/hyde.py` | Length | Hypothetical passage >= 30 chars |
| `processing/extractors/entity_extractor.py` | JSON parse | Valid JSON array of entities |
| `graph_store/summarizer.py` | Length | Summary within bounds |
| `chains/qa/enrichment.py` | Structure | Valid enrichment response |

### Example: Grader

```python
# grader.py — Ralph Wiggum self-correcting loop
rw_feedback = ""
for rw_attempt in range(1, 3):
    messages = [SystemMessage(content=GRADING_PROMPT), HumanMessage(...)]
    if rw_feedback:
        messages.append(HumanMessage(content=f"CORRECTION: {rw_feedback}"))

    response = await llm.ainvoke(messages)
    text = response.content.strip().lower()

    if text.startswith(("yes", "relevant", "да")):
        return True
    elif text.startswith(("no", "not", "нет")):
        return False
    else:
        rw_feedback = f"Expected 'yes' or 'no', got: '{text[:50]}'. Answer with exactly 'yes' or 'no'."
```

---

## Path Resolution

All Ralph state files use `shared/core_paths.py` for location-agnostic path resolution:

| Path | Resolves To | Purpose |
|------|------------|---------|
| `get_state_dir()` | `.claude/hooks/` (project-level) | Ralph state files |
| `get_cache_dir()` | `.claude/cache/` (project-level) | hook-todos.json |
| `get_core_dir()` | `~/.claude/hooks/` (user-level) | Ralph hook source code |

State files are **always project-level** — each project has its own Ralph session.

---

## Typical Lifecycle Example

```
User: "Создай новый hook для валидации коммитов"

1. ralph_activator.py fires on UserPromptSubmit
   - Detects "создай hook" → Factory tier
   - Creates .ralph_active, .ralph_criteria.json (max 12 iterations)
   - Injects system message with criteria

2. Claude creates hook file, registers in settings.json
   - factory-enforcer.py fires on Write → creates mandatory task in hook-todos.json

3. Claude tries to stop after writing the hook
   - ralph_wiggum_stop.py fires
   - Checks criteria: settings.json updated? ✓  test passed? ✗
   - Pending mandatory task from factory-enforcer? ✓
   - BLOCKS exit (exit 2) → "Need to run tests"

4. Claude runs tests, they pass
   - Iteration 4, tests pass ✓

5. Claude updates MEMORY.md, marks RALPH_DONE
   - ralph_wiggum_stop.py fires
   - All criteria met, no pending tasks
   - Deactivates Ralph, allows stop (exit 0)
```

---

## Safety Mechanisms

| Mechanism | Purpose |
|-----------|---------|
| **2-hour staleness** | Auto-deactivate if session hangs |
| **Max iterations** | Hard cap per tier (8-15) |
| **RALPH_DONE marker** | Manual override — Claude can signal completion |
| **Negative-first detection** | Prevents false positives on simple tasks |
| **Atomic state files** | Crash-safe via temp + rename |
| **Mandatory task check** | Ensures critical steps aren't skipped |

---

## See Also

- [Hooks Reference](hooks-reference.md) — complete hook specifications
- [Triad Architecture](triad-architecture.md) — how Ralph fits into Hooks+Skills+MCP
- [Core/Framework Separation](core-framework-separation.md) — where Ralph hooks live
