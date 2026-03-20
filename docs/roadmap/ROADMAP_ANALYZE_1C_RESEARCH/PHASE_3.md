# Phase 3: Runner Script

**Priority:** HIGH | **Effort:** 1-2 days | **Depends on:** Phase 1, 2 | **Effect:** Headless execution

**Goal:** PowerShell скрипт `analyze-1c-research.ps1` — адаптация autoresearch.ps1 для домена анализа задач 1С.

---

## Problem Statement

`autoresearch.ps1` работает с доменами кода (skills, python-quality, bsl). Для анализа задач 1С нужен адаптированный runner:
- Вход: файл с ТЗ (не domain name)
- Session directory per task (не общий `data/autoresearch/`)
- Подстановка переменных в prompt templates (не inline prompts)
- Plateau threshold 3 (не 5)
- Scorer вместо ruff/pytest

---

## Architecture

```
scripts/analyze-1c-research.ps1
  │
  ├── reads: task file (ТЗ)
  ├── creates: data/analyze-1c-research/{task-id}/
  │
  ├── iteration loop:
  │   ├── EXECUTOR: claude -p (from template + variables)
  │   ├── REVIEWER: claude -p (from template + variables)
  │   ├── COMPARATOR: claude -p (every 3 iterations)
  │   ├── parse verdict → KEEP/IMPROVE/REVERT
  │   └── log → JSONL + TSV
  │
  ├── stop conditions:
  │   ├── score >= target (default 85)
  │   ├── plateau >= 3
  │   ├── max_iterations reached (default 7)
  │   └── RALPH_DONE marker
  │
  └── output: analysis-report.md (final)
```

---

## CLI Interface

```powershell
# Basic usage
.\scripts\analyze-1c-research.ps1 -TaskFile docs/tasks/GKSTCPLK-1234.md

# With target and limits
.\scripts\analyze-1c-research.ps1 -TaskFile docs/tasks/GKSTCPLK-1234.md -TargetScore 90 -MaxIterations 10

# Resume existing session
.\scripts\analyze-1c-research.ps1 -SessionDir data/analyze-1c-research/GKSTCPLK-1234

# With custom compare frequency
.\scripts\analyze-1c-research.ps1 -TaskFile docs/tasks/GKSTCPLK-1234.md -CompareEvery 2
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `-TaskFile` | string | required* | Путь к файлу с ТЗ |
| `-SessionDir` | string | auto | Директория сессии (для resume) |
| `-TargetScore` | int | 85 | Целевой score (0-100) |
| `-MaxIterations` | int | 7 | Максимум итераций |
| `-CompareEvery` | int | 3 | Частота Comparator |

*Required если не указан `-SessionDir`

---

## Key Differences from autoresearch.ps1

| Aspect | autoresearch.ps1 | analyze-1c-research.ps1 |
|--------|------------------|------------------------|
| Input | `-Domain skills` | `-TaskFile task.md` |
| Session dir | `data/autoresearch/` | `data/analyze-1c-research/{task-id}/` |
| Prompts | Inline in script | From template files + variable substitution |
| Verify | `python scripts/eval-skill-router.py` | `python scripts/score-analysis-report.py` |
| Plateau | 5 | 3 |
| Default iterations | 10 | 7 |
| Executor creates | Code changes | ANALYSIS-REPORT.md |
| Reviewer creates | - | reviewer_feedback.json |

---

## Tasks

### 3.1 Script skeleton

Fork `autoresearch.ps1`, rename, adapt parameters.

### 3.2 Session initialization

```powershell
# Extract task ID from filename or first heading
$taskId = extract_task_id($TaskFile)
$sessionDir = "data/analyze-1c-research/$taskId"

# Create session structure
New-Item -ItemType Directory -Path "$sessionDir/logs" -Force
Copy-Item $TaskFile "$sessionDir/task.md"

# Initialize autoresearch.md
@"
# Analyze-1C-Research: $taskId
Domain: 1c-analysis | Metric: quality score | Target: $TargetScore
Iteration: 0 | BestMetric: 0 | Plateau: 0
BaselineCommit: $(git rev-parse --short HEAD)
## Dead Ends
(none yet)
## History
| Iter | Score | Delta | Verdict | Change |
|------|-------|-------|---------|--------|
"@ | Set-Content "$sessionDir/autoresearch.md"
```

### 3.3 Template loading and variable substitution

```powershell
function Load-Template($templatePath, $variables) {
    $text = Get-Content $templatePath -Raw -Encoding UTF8
    foreach ($key in $variables.Keys) {
        $text = $text.Replace("{$key}", $variables[$key])
    }
    return $text
}

$vars = @{
    iter = $i
    max_iterations = $MaxIterations
    task_description = (Get-Content "$sessionDir/task.md" -Raw -Encoding UTF8)
    session_dir = $sessionDir
    best_metric = $bestMetric
    target_score = $TargetScore
    baseline_commit = $baselineCommit
}
```

### 3.4 Agent invocations

Same pattern as autoresearch.ps1 but with template-loaded prompts:

```powershell
$executorPrompt = Load-Template $executorTemplate $vars
$executorOutput = claude -p $executorPrompt --dangerously-skip-permissions 2>&1 | Out-String
```

### 3.5 Reviewer feedback parsing

Extended parsing for `reviewer_feedback.json`:

```powershell
# After reviewer runs, read feedback for next Executor iteration
if (Test-Path "$sessionDir/reviewer_feedback.json") {
    $feedback = Get-Content "$sessionDir/reviewer_feedback.json" -Raw | ConvertFrom-Json
    $vars["reviewer_gaps"] = ($feedback.gaps | ConvertTo-Json -Compress)
}
```

---

## Deliverables

- [ ] `scripts/analyze-1c-research.ps1` — runner script
- [ ] `scripts/analyze-1c-research.sh` — bash version (Linux/WSL)
- [ ] README section in INDEX.md

## Acceptance Criteria

1. Скрипт создаёт session directory с правильной структурой
2. Executor/Reviewer/Comparator вызываются последовательно через `claude -p`
3. Score извлекается из Reviewer output и логируется в JSONL
4. Plateau detection (3 итерации) корректно останавливает цикл
5. Resume: скрипт продолжает с последней итерации при повторном запуске
6. Логи каждого агента сохраняются в `logs/`
