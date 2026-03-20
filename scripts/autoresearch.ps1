#!/usr/bin/env pwsh
# autoresearch.ps1 — AutoResearch v2: Three-Agent Engine (Executor + Reviewer + Comparator)
#
# Usage:
#   .\scripts\autoresearch.ps1 -Domain skills -MaxIterations 15
#   .\scripts\autoresearch.ps1 -Domain python-quality -Target 0
#   .\scripts\autoresearch.ps1 -Domain skills -MaxIterations 20 -Target 0.85
#   .\scripts\autoresearch.ps1 -IdeaDir data/autoresearch/api-speed-20260320

param(
    [ValidateSet("skills", "skill-health", "python-quality", "bsl", "docs", "hooks", "security", "tests")]
    [string]$Domain,

    [string]$IdeaDir,

    [int]$MaxIterations = 10,
    [string]$Target,
    [int]$CompareEvery = 5
)

# --- UTF-8 Setup ---
chcp 65001 > $null 2>&1
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Project Root ---
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item "$scriptDir\..").FullName
Set-Location $projectRoot

if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" > $null }

# --- Domain Recipes ---
$recipes = @{
    "skills" = @{
        Verify = "python scripts/eval-skill-router.py"
        Test = "echo PASS"
        Scope = ".claude/skills/"
        Metric = "F1 score"
        Direction = "higher"
        ExecutorHint = "Улучши description ОДНОГО скилла для повышения F1. Pushy стиль с триггерами и негативными маркерами."
    }
    "skill-health" = @{
        Verify = "python scripts/eval-skill-router.py"
        Test = "echo PASS"
        Scope = ".claude/skills/, .claude/skills/skill-router-config.json"
        Metric = "F1(All) + health report"
        Direction = "higher"
        ExecutorHint = "Запусти skill-health-analyzer.py --no-eval. Найди проблемный скилл: HIGH WASTE -> сузь description, ROUTER MISS -> добавь keywords в config, NEVER USED -> перемести в _archived/."
    }
    "python-quality" = @{
        Verify = "ruff check src/ --output-format json 2>`$null | python -c `"import sys,json; print(len(json.load(sys.stdin)))`""
        Test = "pytest tests/ -q --tb=short"
        Scope = "src/**/*.py"
        Metric = "ruff errors count"
        Direction = "lower"
        ExecutorHint = "Запусти ruff check src/ --statistics. Найди самую частую категорию ошибок. Исправь ВСЕ файлы с этой ошибкой."
    }
    "bsl" = @{
        Verify = "echo 0"
        Test = "echo PASS"
        Scope = "src/bsl/**/*.bsl"
        Metric = "bsl_analyze errors"
        Direction = "lower"
        ExecutorHint = "Проанализируй BSL код через bsl_analyze. Исправь ОДНУ категорию ошибок."
    }
    "docs" = @{
        Verify = "echo 0"
        Test = "echo PASS"
        Scope = "src/**/*.py"
        Metric = "documented functions %"
        Direction = "higher"
        ExecutorHint = "Найди модуль с наименьшим % документированных функций. Добавь docstrings к ОДНОМУ модулю."
    }
    "hooks" = @{
        Verify = "python scripts/eval-hooks.py"
        Test = "echo PASS"
        Scope = ".claude/hooks/"
        Metric = "eval-hooks accuracy"
        Direction = "higher"
        ExecutorHint = "Улучши ОДИН хук для повышения accuracy eval-hooks.py."
    }
    "security" = @{
        Verify = "bandit -r src/ -f json 2>`$null | python -c `"import sys,json; print(len(json.load(sys.stdin).get('results',[])))`""
        Test = "echo PASS"
        Scope = "src/**/*.py (READ-ONLY)"
        Metric = "findings count"
        Direction = "higher"
        ExecutorHint = "Анализируй ОДИН attack vector (STRIDE). НЕ модифицируй код — только анализ."
    }
    "tests" = @{
        Verify = "pytest --cov=src --cov-report=json -q 2>`$null; python -c `"import json; d=json.load(open('coverage.json')); print(d['totals']['percent_covered'])`""
        Test = "pytest tests/ -q --tb=short"
        Scope = "tests/**/*.py"
        Metric = "coverage %"
        Direction = "higher"
        ExecutorHint = "Найди модуль с наименьшим покрытием. Напиши тесты для ОДНОГО модуля."
    }
}

# --- Resolve idea directory or domain ---
$sessionDir = $null
if ($IdeaDir) {
    $sessionDir = $IdeaDir
    if (-not (Test-Path "$sessionDir/autoresearch.md")) {
        Write-Host "[ERROR] $sessionDir/autoresearch.md not found. Run /autoresearch:plan first." -ForegroundColor Red
        exit 1
    }
} elseif ($Domain) {
    $sessionDir = "data/autoresearch"
    if (-not (Test-Path $sessionDir)) { New-Item -ItemType Directory -Path $sessionDir > $null }
} else {
    Write-Host "[ERROR] Specify -Domain or -IdeaDir" -ForegroundColor Red
    exit 1
}

$recipe = if ($Domain) { $recipes[$Domain] } else { $null }

$jsonlPath = "$sessionDir/autoresearch.jsonl"
$tsvPath = "$sessionDir/autoresearch-results.tsv"
$mdPath = "$sessionDir/autoresearch.md"
$logDir = "$sessionDir/logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir > $null }

# --- Session State ---
$bestMetric = $null
$plateauCount = 0
$startIter = 0
$baselineCommit = $null

if (Test-Path $mdPath) {
    $md = Get-Content $mdPath -Raw -Encoding UTF8
    if ($md -match 'Iteration:\s*(\d+)') { $startIter = [int]$Matches[1] }
    if ($md -match 'BestMetric:\s*([\d.]+)') { $bestMetric = [double]$Matches[1] }
    if ($md -match 'Plateau:\s*(\d+)') { $plateauCount = [int]$Matches[1] }
    if ($md -match 'BaselineCommit:\s*(\w+)') { $baselineCommit = $Matches[1] }
}

if (-not $baselineCommit) {
    $baselineCommit = (git rev-parse --short HEAD 2>$null)
}

# --- TSV Header ---
if (-not (Test-Path $tsvPath)) {
    "iteration`ttimestamp`tcommit`tchange`tmetric_before`tmetric_after`tdelta`ttests`tverdict`treason" | Set-Content $tsvPath -Encoding UTF8
}

Write-Host "=== AutoResearch v2: Three-Agent Engine ===" -ForegroundColor Cyan
Write-Host "Domain: $(if($Domain){$Domain}else{'custom'}) | Max: $MaxIterations | Target: $(if($Target){$Target}else{'none'})"
Write-Host "Session: $sessionDir | Baseline commit: $baselineCommit"
Write-Host "Compare every: $CompareEvery iterations"
Write-Host ""

# --- Helper: Extract verdict from reviewer output ---
function Extract-Verdict($text) {
    if ($text -match '"verdict"\s*:\s*"(KEEP|REVERT|FIX|SKIP)"') { return $Matches[1] }
    if ($text -match 'VERDICT:\s*(KEEP|REVERT|FIX|SKIP)') { return $Matches[1] }
    return "unknown"
}

function Extract-Metric($text) {
    if ($text -match 'METRIC:\s*([\d.]+)') { return [double]$Matches[1] }
    if ($text -match '"metric_after"\s*:\s*([\d.]+)') { return [double]$Matches[1] }
    if ($text -match 'F1[\s:=]+([\d.]+)') { return [double]$Matches[1] }
    return $null
}

# --- Main Loop ---
$lastIter = $startIter
$env:RALPH_ENABLED = "1"

for ($i = $startIter + 1; $i -le $MaxIterations; $i++) {
    $lastIter = $i
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    Write-Host "`n=== Iteration $i / $MaxIterations [$ts] ===" -ForegroundColor Cyan

    $commitBefore = (git rev-parse --short HEAD 2>$null)

    # ==========================================
    # AGENT 1: EXECUTOR — Make ONE atomic change
    # ==========================================
    Write-Host "  [EXECUTOR] Making change..." -ForegroundColor Yellow

    $executorPrompt = @"
You are EXECUTOR in AutoResearch v2. Iteration $i of $MaxIterations.
Domain: $(if($Domain){$Domain}else{'custom'}). Scope: $(if($recipe){$recipe.Scope}else{'see autoresearch.md'}).

INSTRUCTIONS:
1. Read $mdPath for context (dead ends, history, next ideas).
2. Check git log --oneline -5 for recent changes.
3. Make ONE atomic change to improve the metric.
$(if($recipe){"   Hint: $($recipe.ExecutorHint)"}else{"   Follow the plan in autoresearch.md."})
4. Git commit: git add -A && git commit -m "[AR-$i] description of change"
5. Do NOT run tests or verify. Do NOT evaluate your own change.
6. Output what you changed in 1 sentence.

RULES:
- ONE change only (explainable in 1 sentence)
- Only modify files in scope
- Check Dead Ends in $mdPath - do NOT retry them
- Commit BEFORE verification
"@

    $executorOutput = claude -p $executorPrompt --dangerously-skip-permissions 2>&1 | Out-String
    $executorOutput | Set-Content "$logDir/executor_$i.txt" -Encoding UTF8
    Write-Host "  [EXECUTOR] Done." -ForegroundColor Green

    $commitAfter = (git rev-parse --short HEAD 2>$null)

    # If executor didn't commit, skip review
    if ($commitAfter -eq $commitBefore) {
        Write-Host "  [SKIP] Executor made no commit. Skipping review." -ForegroundColor Yellow
        $plateauCount++
        $entry = @{ iter=$i; ts=$ts; domain=$(if($Domain){$Domain}else{"custom"}); commit="none"; change="no commit"; metric_before=$bestMetric; metric_after=$bestMetric; delta=0; tests_pass=$true; verdict="SKIP"; reason="executor made no commit" }
        ($entry | ConvertTo-Json -Compress) | Add-Content $jsonlPath -Encoding UTF8
        continue
    }

    # ==========================================
    # AGENT 2: REVIEWER — Verify and decide
    # ==========================================
    Write-Host "  [REVIEWER] Verifying..." -ForegroundColor Yellow

    $reviewerPrompt = @"
You are REVIEWER in AutoResearch v2. Iteration $i.
Domain: $(if($Domain){$Domain}else{'custom'}). Scope: $(if($recipe){$recipe.Scope}else{'see autoresearch.md'}).
Direction: $(if($recipe){$recipe.Direction}else{'see autoresearch.md'}) is better.

INSTRUCTIONS:
1. Run: git diff HEAD~1 --stat
2. Run verify command to get metric:
$(if($recipe){"   $($recipe.Verify)"}else{"   See autoresearch.md for verify command."})
3. Run test command:
$(if($recipe){"   $($recipe.Test)"}else{"   See autoresearch.md for test command."})
4. Check: files outside scope modified? (git diff HEAD~1 --name-only)
5. Compare metric with previous best: $bestMetric

OUTPUT (mandatory format):
METRIC: <number>
TESTS: PASS or FAIL
VERDICT: KEEP or REVERT or FIX or SKIP
REASON: <1 sentence>

6. If VERDICT is REVERT or SKIP: execute git revert HEAD --no-edit
7. Update $mdPath: add row to History table, update Current Best if KEEP, add to Dead Ends if REVERT.

RULES:
- Do NOT write code. Do NOT make changes beyond revert.
- Be objective: only numbers decide the verdict.
- KEEP only if metric improved AND tests pass AND no out-of-scope changes.
"@

    $reviewerOutput = claude -p $reviewerPrompt --dangerously-skip-permissions 2>&1 | Out-String
    $reviewerOutput | Set-Content "$logDir/reviewer_$i.txt" -Encoding UTF8

    # Parse verdict
    $verdict = Extract-Verdict $reviewerOutput
    $metric = Extract-Metric $reviewerOutput
    $testsPass = if ($reviewerOutput -match 'TESTS:\s*PASS') { $true } else { $false }
    $reason = ""
    if ($reviewerOutput -match 'REASON:\s*(.+)') { $reason = $Matches[1].Trim() }

    $delta = if ($bestMetric -ne $null -and $metric -ne $null) { [math]::Round($metric - $bestMetric, 4) } else { 0 }

    # Apply verdict logic
    switch ($verdict) {
        "KEEP" {
            if ($metric -ne $null -and ($bestMetric -eq $null -or (
                ($recipe -and $recipe.Direction -eq "higher" -and $metric -gt $bestMetric) -or
                ($recipe -and $recipe.Direction -eq "lower" -and $metric -lt $bestMetric) -or
                (-not $recipe -and $metric -gt $bestMetric)
            ))) {
                $bestMetric = $metric
                $plateauCount = 0
            } else {
                $plateauCount++
            }
            Write-Host "  [REVIEWER] KEEP: metric=$metric delta=$delta" -ForegroundColor Green
        }
        "REVERT" {
            $plateauCount++
            Write-Host "  [REVIEWER] REVERT: metric=$metric reason=$reason" -ForegroundColor Red
        }
        "FIX" {
            $plateauCount++
            Write-Host "  [REVIEWER] FIX: tests failed, idea has merit" -ForegroundColor Yellow
        }
        "SKIP" {
            $plateauCount++
            Write-Host "  [REVIEWER] SKIP: no change in metric" -ForegroundColor Yellow
        }
        default {
            $plateauCount++
            Write-Host "  [REVIEWER] Unknown verdict: $verdict" -ForegroundColor Yellow
        }
    }

    # ==========================================
    # AGENT 3: COMPARATOR — Blind A/B every N iterations
    # ==========================================
    if ($i % $CompareEvery -eq 0 -and $baselineCommit) {
        Write-Host "  [COMPARATOR] Blind A/B comparison..." -ForegroundColor Magenta

        $comparatorPrompt = @"
You are COMPARATOR in AutoResearch v2. Blind A/B comparison at iteration $i.
Scope: $(if($recipe){$recipe.Scope}else{'see autoresearch.md'}).

INSTRUCTIONS:
1. Read current code in scope (this is one version).
2. Run: git diff $baselineCommit HEAD -- $(if($recipe){$recipe.Scope}else{'./'})
   to see all changes since baseline.
3. Evaluate BOTH versions (baseline vs current) on:
   - Code quality (1-10)
   - Readability (1-10)
   - Complexity (1-10, lower is better)
4. Output JSON:
   {"winner":"A or B","quality_A":N,"quality_B":N,"readability_A":N,"readability_B":N,"notes":"brief"}
   where A=baseline, B=current.
5. Append to $mdPath under ## Comparator Reviews.

RULES:
- Be UNBIASED. Judge code quality holistically, not just the metric.
- If current code is worse despite better metric, note this.
"@

        $comparatorOutput = claude -p $comparatorPrompt --dangerously-skip-permissions 2>&1 | Out-String
        $comparatorOutput | Set-Content "$logDir/comparator_$i.txt" -Encoding UTF8
        Write-Host "  [COMPARATOR] Done." -ForegroundColor Magenta
    }

    # --- LOG: TSV + JSONL ---
    $commitHash = (git rev-parse --short HEAD 2>$null)
    $changeDesc = ""
    if ($executorOutput -match '\[AR-\d+\]\s*(.+)') { $changeDesc = $Matches[1].Trim() }
    if (-not $changeDesc -and $reason) { $changeDesc = $reason }

    "$i`t$ts`t$commitHash`t$changeDesc`t$bestMetric`t$metric`t$delta`t$(if($testsPass){'pass'}else{'fail'})`t$verdict`t$reason" | Add-Content $tsvPath -Encoding UTF8

    $entry = @{
        iter = $i; ts = $ts; domain = $(if($Domain){$Domain}else{"custom"})
        commit = $commitHash; change = $changeDesc
        metric_before = $bestMetric; metric_after = $metric; delta = $delta
        tests_pass = $testsPass; verdict = $verdict; reviewer_reason = $reason
    }
    ($entry | ConvertTo-Json -Compress) | Add-Content $jsonlPath -Encoding UTF8

    # --- Update session state ---
    @"
# AutoResearch Session
Domain: $(if($Domain){$Domain}else{'custom'})
Iteration: $i
BestMetric: $bestMetric
Plateau: $plateauCount
Target: $Target
BaselineCommit: $baselineCommit
Updated: $ts
"@ | Set-Content $mdPath -Encoding UTF8

    # --- Completion markers ---
    if ($executorOutput -match "AUTORESEARCH_DONE" -or $reviewerOutput -match "AUTORESEARCH_DONE") {
        Write-Host "`n  AUTORESEARCH_DONE" -ForegroundColor Green
        break
    }

    # --- Target check ---
    if ($Target -and $bestMetric -ne $null) {
        $targetMet = $false
        if ($recipe -and $recipe.Direction -eq "lower") {
            $targetMet = $bestMetric -le [double]$Target
        } else {
            $targetMet = $bestMetric -ge [double]$Target
        }
        if ($targetMet) {
            Write-Host "`n  Target reached: $bestMetric (target: $Target)" -ForegroundColor Green
            break
        }
    }

    # --- Plateau check ---
    if ($plateauCount -ge 5) {
        Write-Host "`n  Plateau: 5 iterations without improvement. Stopping." -ForegroundColor Yellow
        break
    }

    Start-Sleep -Seconds 2
}

Write-Host "`n=== AutoResearch v2 Complete ===" -ForegroundColor Cyan
Write-Host "Domain: $(if($Domain){$Domain}else{'custom'}) | Iterations: $lastIter | Best: $bestMetric | Target: $(if($Target){$Target}else{'N/A'})"
Write-Host "Logs: $logDir/ | TSV: $tsvPath | JSONL: $jsonlPath"
