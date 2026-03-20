# Phase 4: In-Session Subagents

**Priority:** HIGH | **Effort:** 1 day | **Depends on:** Phase 1, 2 | **Effect:** Interactive mode

**Goal:** Команда `/analyze-1c-task:research` — интерактивный режим с Agent subagents внутри Claude Code сессии.

---

## Problem Statement

Phase 3 (headless скрипт) подходит для автономной работы. Но в интерактивном режиме пользователь хочет:
- Видеть прогресс в реальном времени
- Корректировать направление между итерациями
- Использовать полный доступ к MCP tools (не через `claude -p`)

---

## Architecture

```
User: /analyze-1c-task:research
      GKSTCPLK-1234: Добавить расчёт НДС

Claude (main context):
  │
  ├── Iteration 1:
  │   ├── [EXECUTOR] Main context: full 5-phase analysis
  │   │   (uses bsl-semantic-search, 1c-mcp-toolkit, etc.)
  │   │   → writes analysis-report.md
  │   │
  │   ├── Agent(subagent_type="general"):
  │   │   [REVIEWER] Score + verify + feedback
  │   │   → returns: METRIC, VERDICT, GAPS
  │   │
  │   └── User sees: "Score: 68/100. 4 gaps. Improving..."
  │
  ├── Iteration 2:
  │   ├── [EXECUTOR] Fix top gap from feedback
  │   ├── Agent: [REVIEWER] Re-score
  │   └── User sees: "Score: 78/100. 2 gaps. Improving..."
  │
  ├── Iteration 3:
  │   ├── [EXECUTOR] Fix remaining gaps
  │   ├── Agent: [REVIEWER] Re-score
  │   ├── Agent: [COMPARATOR] Blind A/B (every 3)
  │   └── User sees: "Score: 87/100. Target reached!"
  │
  └── Output: final ANALYSIS-REPORT.md
```

### Key Design Decision: Executor = Main Context

В headless режиме (Phase 3) все 3 агента запускаются через `claude -p` — изолированно. В интерактивном режиме **Executor — это основной контекст Claude**, потому что:
1. Executor нуждается в полном доступе к MCP tools
2. Executor делает основную работу (фазы 1-4)
3. Main context уже имеет все permissions

Reviewer и Comparator делегируются в Agent subagents — они только проверяют, не пишут.

---

## Skill Command

Добавить в `analyze-1c-task-v2/SKILL.md`:

```yaml
commands:
  - /analyze-1c-task-v2             # Однопроходный анализ (текущий)
  - /analyze-1c-task:research       # Итеративный с 3 агентами
```

### Flow `/analyze-1c-task:research`

```
1. Parse task description from user input
2. Create session dir: data/analyze-1c-research/{task-id}/
3. Save task.md
4. EXECUTOR (main): Run 5-phase analysis → analysis-report.md
5. Loop (max 7 iterations):
   a. REVIEWER (Agent subagent):
      - Read analysis-report.md
      - Run scorer (or parse manually)
      - Verify fields via get_metadata (up to 3)
      - Output: score, gaps, verdict
   b. If score >= target → DONE
   c. If plateau >= 3 → DONE
   d. Show user: "Score: {N}/100. {gaps} gaps. {verdict}."
   e. EXECUTOR (main): Fix ONE gap from reviewer feedback
   f. Every 3 iterations: COMPARATOR (Agent subagent)
6. Save final analysis-report.md
7. Git commit: "[ANALYSIS] {task-id}: score {final_score}"
```

---

## Tasks

### 4.1 Reviewer Subagent

```python
# Pseudo-code for reviewer invocation
reviewer_result = Agent(
    description="Review 1C analysis report",
    prompt=f"""
You are REVIEWER. Read {session_dir}/analysis-report.md.
Run: python scripts/score-analysis-report.py {session_dir}/analysis-report.md
Previous best: {best_score}. Target: {target}.

Output:
METRIC: <number>
GAPS: <count> (<types>)
VERDICT: KEEP or IMPROVE
REASON: <1 sentence>

Save reviewer_feedback.json with gap details.
""",
    subagent_type="general"
)
```

### 4.2 Comparator Subagent

```python
comparator_result = Agent(
    description="Compare analysis versions A/B",
    prompt=f"""
You are COMPARATOR. Blind comparison.
Version A: git show {baseline}:{session_dir}/analysis-report.md
Version B: current {session_dir}/analysis-report.md

Rate both (1-10): completeness, correctness, patterns, actionability, test_coverage.
Output JSON with winner.
""",
    subagent_type="general"
)
```

### 4.3 Progress Display

After each iteration, display to user:

```
--- Iteration 2/7 ---
Score: 78/100 (prev: 68, +10)
Gaps: 2 (1 field_unverified, 1 pattern_missing)
Verdict: IMPROVE
Next: verifying field Справочник.Контрагенты.гкс_КодОрганизации
```

### 4.4 User Intervention Points

Between iterations, allow user to:
- Adjust direction: "сфокусируйся на SQL запросах"
- Skip gap: "этот вопрос неактуален, пропусти"
- Stop early: "достаточно, score 78 хватит"
- Add context: "учти что регистр гкс_СтатусыМаршрутныхЛистов — новый"

---

## Deliverables

- [ ] Updated `analyze-1c-task-v2/SKILL.md` with `:research` command section
- [ ] Reviewer subagent prompt integration
- [ ] Comparator subagent prompt integration
- [ ] Progress display format
- [ ] Session state management (iteration counter, best score, plateau)

## Acceptance Criteria

1. `/analyze-1c-task:research` запускает итеративный цикл
2. Reviewer subagent возвращает parseable score + gaps
3. Executor (main context) использует MCP tools для фиксов
4. Пользователь видит прогресс после каждой итерации
5. Цикл останавливается при достижении target или plateau
6. Session files создаются и обновляются корректно
