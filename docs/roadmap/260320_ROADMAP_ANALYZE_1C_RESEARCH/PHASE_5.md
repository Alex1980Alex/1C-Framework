# Phase 5: Ralph Integration

**Priority:** MEDIUM | **Effort:** 0.5 day | **Depends on:** Phase 3 | **Effect:** Autonomous loop

**Goal:** Интеграция analyze-1c-research с Ralph Wiggum: сигналы активации, критерии завершения, шаблон для `ralph.bat`.

---

## Changes

### 5.1 Ralph Activator — новые сигналы

Файл: `.claude/hooks/ralph_activator.py`

Добавить секцию сигналов для анализа 1С:

```python
ANALYSIS_SIGNALS = {
    "keywords": [
        "анализ задачи 1С", "analyze 1c task", "1c analysis research",
        "итеративный анализ", "улучши анализ", "доработай отчёт",
        "проверь покрытие требований", "score analysis",
    ],
    "task_type": "analysis",
    "max_iterations": 7,
    "criteria": [
        "analysis_score >= target",
        "all fields verified via get_metadata",
        "all requirements have modification points",
        "reviewer_feedback.json has 0 gaps",
    ],
}
```

### 5.2 Ralph Stop Hook — критерии завершения

Файл: `.claude/hooks/ralph_wiggum_stop.py`

Добавить в `CRITERIA_SIGNAL_MAP`:

```python
"analysis": {
    "analysis_score_above_target": {
        "check": lambda state: _read_score(state) >= _read_target(state),
        "signal_file": "autoresearch.md",
        "description": "Analysis score reached target"
    },
    "reviewer_gaps_zero": {
        "check": lambda state: _read_gaps_count(state) == 0,
        "signal_file": "reviewer_feedback.json",
        "description": "No remaining gaps in analysis"
    },
    "report_committed": {
        "check": lambda state: _last_commit_has_analysis(state),
        "signal_file": None,
        "description": "Final report committed to git"
    },
}
```

### 5.3 Ralph Template — 1c-analysis

Файл: обновить `scripts/ralph.bat` + `scripts/ralph.sh`

```batch
@rem Template: 1c-analysis
if "%TEMPLATE%"=="1c-analysis" (
    set RALPH_PROMPT=Ты в режиме Analyze-1C-Research. Задача: прочитай файл %TASK_FILE%. ^
Запусти итеративный анализ: Executor (фазы 1-4) → scorer → Reviewer (фаза 5) → fix gaps → repeat. ^
Target score: 85. Max iterations: 7. Plateau: 3. ^
Используй bsl-semantic-search, 1c-mcp-toolkit, bsl-platform-context. ^
Для каждого поля SQL — get_metadata. Для каждой точки — bsl_search на паттерн. ^
Сохраняй результат в data/analyze-1c-research/{task-id}/analysis-report.md. ^
Маркеры: ✓ get_metadata, ✓ pattern, ✓ execute_query. ^
Когда score >= 85 или 0 gaps: выведи RALPH_DONE.
)
```

Использование:

```bash
scripts\ralph.bat --template 1c-analysis --task docs/tasks/GKSTCPLK-1234.md --max-iterations 7
```

### 5.4 Ralph Activator — auto-detection

В `ralph_activator.py` добавить auto-detect для промптов вида:
- "проанализируй задачу GKSTCPLK-..." → analysis type
- "сделай ANALYSIS-REPORT для..." → analysis type

```python
def _detect_analysis_task(prompt: str) -> bool:
    """Detect if prompt is a 1C task analysis request."""
    patterns = [
        r"GKSTCPLK-\d+",
        r"анализ.*задач[иу].*1[СC]",
        r"ANALYSIS.?REPORT",
        r"analyze.*1[cс].*task",
    ]
    return any(re.search(p, prompt, re.IGNORECASE) for p in patterns)
```

---

## Deliverables

- [ ] Updated `ralph_activator.py` with ANALYSIS_SIGNALS
- [ ] Updated `ralph_wiggum_stop.py` with analysis criteria
- [ ] Updated `ralph.bat` / `ralph.sh` with `1c-analysis` template
- [ ] Auto-detection for 1C analysis prompts

## Acceptance Criteria

1. `ralph.bat --template 1c-analysis` запускает цикл с правильным промптом
2. Ralph stop hook проверяет analysis_score и gaps count
3. Auto-detection срабатывает на "проанализируй задачу GKSTCPLK-1234"
4. RALPH_DONE выводится когда score >= target
