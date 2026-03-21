#!/usr/bin/env pwsh
# analyze-1c-research.ps1 — Three-Agent 1C Analysis Engine
#
# Usage:
#   .\scripts\analyze-1c-research.ps1 -TaskFile docs/tasks/GKSTCPLK-1234.md
#   .\scripts\analyze-1c-research.ps1 -TaskFile task.md -TargetScore 90 -MaxIterations 10
#   .\scripts\analyze-1c-research.ps1 -SessionDir data/analyze-1c-research/GKSTCPLK-1234

param(
    [string]$TaskFile,
    [string]$SessionDir,
    [int]$TargetScore = 85,
    [int]$MaxIterations = 7,
    [int]$CompareEvery = 3
)

# --- UTF-8 Setup ---
chcp 65001 > $null 2>&1
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# --- Project Root ---
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item "$scriptDir/..").FullName
Set-Location $projectRoot

$templatesDir = "$projectRoot/.claude/skills/autoresearch/templates"
$dataDir = "$projectRoot/data/analyze-1c-research"

# --- Phase Detection ---
$script:PhaseMap = @{
    "Read"                = "Phase 1: Requirements"
    "Skill"               = "Phase 1: Requirements"
    "bsl_search"          = "Phase 2: Objects"
    "bsl_hybrid_search"   = "Phase 2: Objects"
    "bsl_object_info"     = "Phase 2: Objects"
    "get_metadata"        = "Phase 2: Objects"
    "search_in_code"      = "Phase 3: Patterns"
    "read_method_source"  = "Phase 3: Patterns"
    "get_module_structure" = "Phase 3: Patterns"
    "read_module_source"  = "Phase 3: Patterns"
    "bsl_coding_context"  = "Phase 3: Patterns"
    "Write"               = "Phase 4: Plan"
    "write_module_source" = "Phase 4: Plan"
    "validate_query"      = "Phase 5: Verification"
    "execute_query"       = "Phase 5: Verification"
    "bsl_analyze"         = "Phase 5: Verification"
}
$script:PhaseOrder = @(
    "Phase 1: Requirements",
    "Phase 2: Objects",
    "Phase 3: Patterns",
    "Phase 4: Plan",
    "Phase 5: Verification"
)
$script:ProgressFile = $null

function Detect-Phase($toolName) {
    foreach ($key in $script:PhaseMap.Keys) {
        if ($toolName -match $key) { return $script:PhaseMap[$key] }
    }
    return $null
}

function Log-Progress($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host "    $line" -ForegroundColor DarkGray
    if ($script:ProgressFile) {
        $line | Add-Content $script:ProgressFile -Encoding UTF8
    }
}

# --- Helper Functions ---
function Extract-TaskId($path) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($path)
    if ($name -match '^(GKSTCPLK-\d+|[A-Za-z0-9_-]+)') { return $Matches[1] }
    $content = Get-Content $path -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if ($content -match '(?m)^#\s+(GKSTCPLK-\d+)') { return $Matches[1] }
    return "task-$(Get-Date -f 'yyyyMMdd-HHmmss')"
}

function Load-Template($path, [hashtable]$vars) {
    $text = Get-Content $path -Raw -Encoding UTF8
    foreach ($key in $vars.Keys) {
        $text = $text.Replace("{$key}", [string]$vars[$key])
    }
    return $text
}

function Run-Claude($prompt, $logFile, $agentName) {
    Log-Progress "$agentName START"
    $agentStart = Get-Date

    # Run claude -p with JSON output, capture result
    $output = claude -p $prompt --dangerously-skip-permissions --output-format json 2>&1 | Out-String

    # Parse JSON result
    $resultText = ""
    $toolCount = 0
    $cost = ""
    $duration = ""
    try {
        $json = $output | ConvertFrom-Json -ErrorAction Stop
        $resultText = $json.result
        $duration = "$([math]::Round($json.duration_ms / 1000))s"
        $cost = "$([math]::Round($json.total_cost_usd, 3))$"
        # Extract tool count from usage iterations
        if ($json.usage -and $json.usage.iterations) {
            foreach ($iter in $json.usage.iterations) {
                if ($iter.tool_uses) { $toolCount += $iter.tool_uses }
            }
        }
        # Fallback: count from num_turns
        if ($toolCount -eq 0 -and $json.num_turns) { $toolCount = $json.num_turns }
    } catch {
        # Not JSON — raw text output
        $resultText = $output
    }

    $elapsed = [math]::Round(((Get-Date) - $agentStart).TotalSeconds)
    Log-Progress "$agentName DONE: ${elapsed}s, turns=$toolCount, cost=$cost"

    # Detect phases from result text
    $phases = @()
    foreach ($phaseName in $script:PhaseOrder) {
        $phaseNum = $phaseName.Substring(0, 7)  # "Phase N"
        if ($resultText -match $phaseNum) { $phases += $phaseName }
    }
    if ($phases.Count -gt 0) {
        Log-Progress "$agentName phases: $($phases -join ' -> ')"
    }

    # Save full output to log
    $resultText | Set-Content $logFile -Encoding UTF8
    # Save raw JSON next to it
    $output | Set-Content "$logFile.json" -Encoding UTF8

    return $resultText
}

function Extract-Verdict($text) {
    if ($text -match 'VERDICT:\s*(KEEP|IMPROVE|REVERT)') { return $Matches[1] }
    if ($text -match '"verdict"\s*:\s*"(KEEP|IMPROVE|REVERT)"') { return $Matches[1] }
    return "UNKNOWN"
}

function Extract-Metric($text) {
    if ($text -match 'METRIC:\s*(\d+)') { return [int]$Matches[1] }
    if ($text -match '"score"\s*:\s*(\d+)') { return [int]$Matches[1] }
    return $null
}

# --- Validation ---
if (-not $SessionDir -and -not $TaskFile) {
    Write-Host "[ERROR] Specify -TaskFile or -SessionDir" -ForegroundColor Red
    exit 1
}

# --- Initialize or Resume ---
if ($SessionDir) {
    if (-not (Test-Path "$SessionDir/autoresearch.md")) {
        Write-Host "[ERROR] $SessionDir/autoresearch.md not found" -ForegroundColor Red
        exit 1
    }
} else {
    if (-not (Test-Path $TaskFile)) {
        Write-Host "[ERROR] Task file not found: $TaskFile" -ForegroundColor Red
        exit 1
    }
    $taskId = Extract-TaskId $TaskFile
    $SessionDir = "$dataDir/$taskId"
    if (-not (Test-Path $SessionDir)) {
        New-Item -ItemType Directory -Path "$SessionDir/logs" -Force > $null
        Copy-Item $TaskFile "$SessionDir/task.md"
        $baseline = (git rev-parse --short HEAD 2>$null)
        @"
# Analyze-1C-Research: $taskId
Domain: 1c-analysis | Metric: quality score | Target: $TargetScore
Iteration: 0 | BestMetric: 0 | Plateau: 0
BaselineCommit: $baseline
## Dead Ends
(none yet)
## History
| Iter | Score | Delta | Verdict | Change |
|------|-------|-------|---------|--------|
"@ | Set-Content "$SessionDir/autoresearch.md" -Encoding UTF8
    }
}

$logDir = "$SessionDir/logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force > $null }
$jsonlPath = "$SessionDir/autoresearch.jsonl"

# --- Init progress log ---
$script:ProgressFile = "$SessionDir/progress.log"
"" | Set-Content $script:ProgressFile -Encoding UTF8

# --- Read State ---
$md = Get-Content "$SessionDir/autoresearch.md" -Raw -Encoding UTF8
$startIter = 0; $bestMetric = 0; $plateauCount = 0; $baselineCommit = ""

if ($md -match 'Iteration:\s*(\d+)') { $startIter = [int]$Matches[1] }
if ($md -match 'BestMetric:\s*(\d+)') { $bestMetric = [int]$Matches[1] }
if ($md -match 'Plateau:\s*(\d+)') { $plateauCount = [int]$Matches[1] }
if ($md -match 'BaselineCommit:\s*(\S+)') { $baselineCommit = $Matches[1] }
if (-not $baselineCommit) { $baselineCommit = (git rev-parse --short HEAD 2>$null) }

$taskContent = Get-Content "$SessionDir/task.md" -Raw -Encoding UTF8

# --- Banner ---
Write-Host "=== Analyze-1C-Research: Three-Agent Engine ===" -ForegroundColor Cyan
Write-Host "Session:  $SessionDir"
Write-Host "Target:   $TargetScore | Max iterations: $MaxIterations"
Write-Host "Start:    iter=$startIter best=$bestMetric plateau=$plateauCount baseline=$baselineCommit"
Write-Host "Progress: $script:ProgressFile"
Write-Host ""

Log-Progress "=== SESSION START: target=$TargetScore max=$MaxIterations ==="

# --- Main Loop ---
for ($i = $startIter + 1; $i -le $MaxIterations; $i++) {
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    Write-Host "`n=== Iteration $i / $MaxIterations [$ts] ===" -ForegroundColor Cyan
    Log-Progress "=== ITERATION $i / $MaxIterations ==="

    $commitBefore = (git rev-parse --short HEAD 2>$null)

    # --- EXECUTOR ---
    $execStart = Get-Date
    Write-Host "  [EXECUTOR] Running 5-phase analysis..." -ForegroundColor Yellow
    $vars = @{
        iter = $i; max_iterations = $MaxIterations
        task_description = $taskContent; session_dir = $SessionDir
        best_metric = $bestMetric; target_score = $TargetScore
        baseline_commit = $baselineCommit
    }

    $executorPrompt = Load-Template "$templatesDir/1c-analysis-executor.md" $vars
    $executorOutput = Run-Claude $executorPrompt "$logDir/executor_$i.txt" "EXEC"
    $execSec = [math]::Round(((Get-Date) - $execStart).TotalSeconds)
    Write-Host "  [EXECUTOR] Done (${execSec}s)" -ForegroundColor Green
    Log-Progress "EXECUTOR result: ${execSec}s, output=$($executorOutput.Length) chars"

    # Save intermediate result
    $resultsDir = "$SessionDir/results"
    if (-not (Test-Path $resultsDir)) { New-Item -ItemType Directory -Path $resultsDir -Force > $null }
    @"
# Iteration $i — Executor Result
**Time:** $ts | **Duration:** ${execSec}s

## Output (truncated)
$($executorOutput.Substring(0, [math]::Min($executorOutput.Length, 2000)))
"@ | Set-Content "$resultsDir/iter${i}_executor.md" -Encoding UTF8

    if ($executorOutput -match "AUTORESEARCH_DONE") {
        Write-Host "`n  AUTORESEARCH_DONE" -ForegroundColor Green
        Log-Progress "AUTORESEARCH_DONE signal received"
        break
    }

    $commitAfter = (git rev-parse --short HEAD 2>$null)
    if ($commitAfter -eq $commitBefore) {
        Write-Host "  [SKIP] Executor made no commit." -ForegroundColor Yellow
        Log-Progress "SKIP: no commit by executor"
        $plateauCount++
        $entry = @{ iter=$i; ts=$ts; score=$bestMetric; delta=0; verdict="SKIP"; reason="no commit" }
        ($entry | ConvertTo-Json -Compress) | Add-Content $jsonlPath -Encoding UTF8
        continue
    }

    # --- REVIEWER ---
    $revStart = Get-Date
    Write-Host "  [REVIEWER] Scoring & verifying..." -ForegroundColor Yellow
    $vars.best_metric = $bestMetric
    $reviewerPrompt = Load-Template "$templatesDir/1c-analysis-reviewer.md" $vars
    $reviewerOutput = Run-Claude $reviewerPrompt "$logDir/reviewer_$i.txt" "REV"
    $revSec = [math]::Round(((Get-Date) - $revStart).TotalSeconds)

    $verdict = Extract-Verdict $reviewerOutput
    $metric = Extract-Metric $reviewerOutput
    $reason = ""
    if ($reviewerOutput -match 'REASON:\s*(.+)') { $reason = $Matches[1].Trim() }

    # Fallback: run scorer directly
    if ($null -eq $metric) {
        $reportPath = "$SessionDir/analysis-report.md"
        if (Test-Path $reportPath) {
            $scorerOutput = python "$projectRoot/scripts/score-analysis-report.py" $reportPath 2>&1 | Out-String
            $metric = Extract-Metric $scorerOutput
        }
    }
    if ($null -eq $metric) { $metric = 0 }

    $delta = $metric - $bestMetric

    switch ($verdict) {
        "KEEP" {
            if ($metric -gt $bestMetric) {
                $bestMetric = $metric
                $plateauCount = 0
            } else { $plateauCount++ }
            Write-Host "  [REVIEWER] KEEP: score=$metric delta=+$delta (${revSec}s)" -ForegroundColor Green
        }
        "IMPROVE" {
            if ($metric -gt $bestMetric) {
                $bestMetric = $metric
                $plateauCount = 0
            } else { $plateauCount++ }
            Write-Host "  [REVIEWER] IMPROVE: score=$metric gaps remain (${revSec}s)" -ForegroundColor Yellow
        }
        "REVERT" {
            $plateauCount++
            Write-Host "  [REVIEWER] REVERT: score=$metric reason=$reason (${revSec}s)" -ForegroundColor Red
        }
        default {
            $plateauCount++
            Write-Host "  [REVIEWER] $verdict : score=$metric (${revSec}s)" -ForegroundColor Yellow
        }
    }

    Log-Progress "REVIEWER result: score=$metric verdict=$verdict delta=$delta reason=$reason (${revSec}s)"

    # Save reviewer intermediate result
    @"
# Iteration $i — Reviewer Result
**Time:** $ts | **Duration:** ${revSec}s
**Score:** $metric / $TargetScore | **Verdict:** $verdict | **Delta:** $delta

## Reason
$reason

## Reviewer Output (truncated)
$($reviewerOutput.Substring(0, [math]::Min($reviewerOutput.Length, 2000)))
"@ | Set-Content "$resultsDir/iter${i}_reviewer.md" -Encoding UTF8

    # --- COMPARATOR (every N iterations) ---
    $cmpSec = 0
    if ($i % $CompareEvery -eq 0 -and $baselineCommit) {
        $cmpStart = Get-Date
        Write-Host "  [COMPARATOR] Blind A/B comparison..." -ForegroundColor Magenta
        $comparatorPrompt = Load-Template "$templatesDir/1c-analysis-comparator.md" $vars
        $comparatorOutput = Run-Claude $comparatorPrompt "$logDir/comparator_$i.txt" "CMP"
        $cmpSec = [math]::Round(((Get-Date) - $cmpStart).TotalSeconds)
        Write-Host "  [COMPARATOR] Done (${cmpSec}s)" -ForegroundColor Magenta
        Log-Progress "COMPARATOR done (${cmpSec}s)"

        # Save comparator intermediate result
        @"
# Iteration $i — Comparator Result
**Time:** $ts | **Duration:** ${cmpSec}s

## A/B Comparison (truncated)
$($comparatorOutput.Substring(0, [math]::Min($comparatorOutput.Length, 2000)))
"@ | Set-Content "$resultsDir/iter${i}_comparator.md" -Encoding UTF8
    }

    # --- LOG: JSONL ---
    $changeDesc = ""
    if ($executorOutput -match '\[AR-\d+\]\s*(.+)') { $changeDesc = $Matches[1].Trim() }
    $entry = @{
        iter = $i; ts = $ts; commit = (git rev-parse --short HEAD 2>$null)
        score = $metric; delta = $delta; verdict = $verdict
        reason = $reason; change = $changeDesc
    }
    ($entry | ConvertTo-Json -Compress) | Add-Content $jsonlPath -Encoding UTF8

    # --- Update State File ---
    $mdContent = Get-Content "$SessionDir/autoresearch.md" -Raw -Encoding UTF8
    $mdContent = $mdContent -replace 'Iteration:\s*\d+', "Iteration: $i"
    $mdContent = $mdContent -replace 'BestMetric:\s*\d+', "BestMetric: $bestMetric"
    $mdContent = $mdContent -replace 'Plateau:\s*\d+', "Plateau: $plateauCount"
    Set-Content "$SessionDir/autoresearch.md" -Value $mdContent -Encoding UTF8

    # --- Iteration Summary ---
    $iterTotalSec = [math]::Round(((Get-Date) - $execStart).TotalSeconds)
    $bar = "#" * [math]::Min([math]::Max([math]::Round($bestMetric / 5), 0), 20)
    $gap = "." * (20 - $bar.Length)
    Write-Host ""
    Write-Host "  ---- Iteration $i Summary ----" -ForegroundColor Cyan
    Write-Host "  Score:    $metric / $TargetScore  [$bar$gap] best=$bestMetric" -ForegroundColor White
    Write-Host "  Verdict:  $verdict  |  Delta: $delta  |  Plateau: $plateauCount/3" -ForegroundColor White
    Write-Host "  Time:     Exec=${execSec}s  Review=${revSec}s  Compare=${cmpSec}s  Total=${iterTotalSec}s" -ForegroundColor DarkGray
    Write-Host "  ----------------------------" -ForegroundColor Cyan

    Log-Progress "SUMMARY: score=$metric/$TargetScore best=$bestMetric verdict=$verdict plateau=$plateauCount/3 time=${iterTotalSec}s"

    # Save iteration summary
    @"
# Iteration $i — Summary
**Time:** $ts | **Total Duration:** ${iterTotalSec}s

| Metric | Value |
|--------|-------|
| Score | $metric / $TargetScore |
| Best | $bestMetric |
| Verdict | $verdict |
| Delta | $delta |
| Plateau | $plateauCount / 3 |
| Executor | ${execSec}s |
| Reviewer | ${revSec}s |
| Comparator | ${cmpSec}s |
"@ | Set-Content "$resultsDir/iter${i}_summary.md" -Encoding UTF8

    # --- Stop Conditions ---
    if ($bestMetric -ge $TargetScore) {
        Write-Host "`n  TARGET REACHED: $bestMetric >= $TargetScore" -ForegroundColor Green
        Log-Progress "TARGET REACHED: $bestMetric >= $TargetScore"
        break
    }
    if ($plateauCount -ge 3) {
        Write-Host "`n  PLATEAU: 3 iterations without improvement." -ForegroundColor Yellow
        Log-Progress "PLATEAU: 3 iterations without improvement"
        break
    }

    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Analyze-1C-Research COMPLETE" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Iterations:  $i / $MaxIterations"
Write-Host "  Best Score:  $bestMetric / $TargetScore"
$status = if ($bestMetric -ge $TargetScore) { "TARGET REACHED" } else { "STOPPED (plateau=$plateauCount)" }
Write-Host "  Status:      $status"
Write-Host "  Report:      $SessionDir/analysis-report.md"
Write-Host "  Progress:    $script:ProgressFile"
Write-Host "  Logs:        $logDir/"
Write-Host "======================================"  -ForegroundColor Cyan

Log-Progress "=== SESSION END: best=$bestMetric status=$status ==="
