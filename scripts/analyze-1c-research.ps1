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
    # Stream claude -p with --output-format stream-json for real-time progress
    $streamFile = "$logFile.stream"
    $promptFile = "$logFile.prompt"
    $errFile = "$logFile.err"

    $prompt | Set-Content $promptFile -Encoding UTF8
    "" | Set-Content $streamFile -Encoding UTF8

    # Start claude -p in background with stream-json output
    $proc = Start-Process -FilePath "claude" `
        -ArgumentList "-p","-","--dangerously-skip-permissions","--output-format","stream-json" `
        -RedirectStandardInput $promptFile -RedirectStandardOutput $streamFile -RedirectStandardError $errFile `
        -NoNewWindow -PassThru

    # Poll stream file for real-time events
    $lastPos = 0
    $toolCount = 0
    $resultText = ""
    $lastReport = Get-Date

    while (-not $proc.HasExited) {
        Start-Sleep -Milliseconds 1500
        if (-not (Test-Path $streamFile)) { continue }
        $bytes = [System.IO.File]::ReadAllBytes($streamFile)
        if ($bytes.Length -le $lastPos) {
            # Heartbeat every 30s if no new data
            if (((Get-Date) - $lastReport).TotalSeconds -ge 30) {
                Write-Host "    [$agentName] ... tools=$toolCount, waiting..." -ForegroundColor DarkGray
                $lastReport = Get-Date
            }
            continue
        }
        $newText = [System.Text.Encoding]::UTF8.GetString($bytes, $lastPos, $bytes.Length - $lastPos)
        $lastPos = $bytes.Length
        $lastReport = Get-Date

        foreach ($jsonLine in ($newText -split "`n")) {
            $jsonLine = $jsonLine.Trim()
            if (-not $jsonLine) { continue }
            try { $evt = $jsonLine | ConvertFrom-Json -ErrorAction Stop } catch { continue }

            # Tool use events
            if ($evt.type -eq "content_block_start" -and $evt.content_block -and $evt.content_block.type -eq "tool_use") {
                $toolCount++
                Write-Host "    [$agentName] #${toolCount} $($evt.content_block.name)" -ForegroundColor DarkGray
            }
            # Result text (assistant message blocks)
            if ($evt.type -eq "result" -and $evt.result) {
                $resultText = $evt.result
            }
            # Message start — show subtype
            if ($evt.type -eq "assistant" -and $evt.message -and $evt.message.content) {
                foreach ($block in $evt.message.content) {
                    if ($block.type -eq "tool_use") {
                        $toolCount++
                        Write-Host "    [$agentName] #${toolCount} $($block.name)" -ForegroundColor DarkGray
                    }
                }
            }
        }
    }

    # Process remaining data after exit
    if (Test-Path $streamFile) {
        $bytes = [System.IO.File]::ReadAllBytes($streamFile)
        if ($bytes.Length -gt $lastPos) {
            $newText = [System.Text.Encoding]::UTF8.GetString($bytes, $lastPos, $bytes.Length - $lastPos)
            foreach ($jsonLine in ($newText -split "`n")) {
                $jsonLine = $jsonLine.Trim()
                if (-not $jsonLine) { continue }
                try { $evt = $jsonLine | ConvertFrom-Json -ErrorAction Stop } catch { continue }
                if ($evt.type -eq "content_block_start" -and $evt.content_block -and $evt.content_block.type -eq "tool_use") {
                    $toolCount++
                    Write-Host "    [$agentName] #${toolCount} $($evt.content_block.name)" -ForegroundColor DarkGray
                }
                if ($evt.type -eq "result" -and $evt.result) { $resultText = $evt.result }
            }
        }
    }

    Write-Host "    [$agentName] Done: $toolCount tool calls" -ForegroundColor DarkGray

    # Save final text to log
    $resultText | Set-Content $logFile -Encoding UTF8

    # Cleanup
    Remove-Item $streamFile -ErrorAction SilentlyContinue
    Remove-Item $promptFile -ErrorAction SilentlyContinue
    Remove-Item $errFile -ErrorAction SilentlyContinue

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
Write-Host "Session: $SessionDir | Target: $TargetScore | Max: $MaxIterations"
Write-Host "Start: iter=$startIter best=$bestMetric plateau=$plateauCount baseline=$baselineCommit"
Write-Host ""

# --- Main Loop ---
for ($i = $startIter + 1; $i -le $MaxIterations; $i++) {
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    Write-Host "`n=== Iteration $i / $MaxIterations [$ts] ===" -ForegroundColor Cyan

    $commitBefore = (git rev-parse --short HEAD 2>$null)

    # --- EXECUTOR ---
    $execStart = Get-Date
    Write-Host "  [EXECUTOR] Running analysis..." -ForegroundColor Yellow
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

    if ($executorOutput -match "AUTORESEARCH_DONE") {
        Write-Host "`n  AUTORESEARCH_DONE" -ForegroundColor Green
        break
    }

    $commitAfter = (git rev-parse --short HEAD 2>$null)
    if ($commitAfter -eq $commitBefore) {
        Write-Host "  [SKIP] Executor made no commit." -ForegroundColor Yellow
        $plateauCount++
        $entry = @{ iter=$i; ts=$ts; score=$bestMetric; delta=0; verdict="SKIP"; reason="no commit" }
        ($entry | ConvertTo-Json -Compress) | Add-Content $jsonlPath -Encoding UTF8
        continue
    }

    # --- REVIEWER ---
    $revStart = Get-Date
    Write-Host "  [REVIEWER] Verifying..." -ForegroundColor Yellow
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

    # --- COMPARATOR (every N iterations) ---
    $cmpSec = 0
    if ($i % $CompareEvery -eq 0 -and $baselineCommit) {
        $cmpStart = Get-Date
        Write-Host "  [COMPARATOR] Blind A/B..." -ForegroundColor Magenta
        $comparatorPrompt = Load-Template "$templatesDir/1c-analysis-comparator.md" $vars
        $comparatorOutput = Run-Claude $comparatorPrompt "$logDir/comparator_$i.txt" "CMP"
        $cmpSec = [math]::Round(((Get-Date) - $cmpStart).TotalSeconds)
        Write-Host "  [COMPARATOR] Done (${cmpSec}s)" -ForegroundColor Magenta
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

    # --- Stop Conditions ---
    if ($bestMetric -ge $TargetScore) {
        Write-Host "`n  TARGET REACHED: $bestMetric >= $TargetScore" -ForegroundColor Green
        break
    }
    if ($plateauCount -ge 3) {
        Write-Host "`n  PLATEAU: 3 iterations without improvement." -ForegroundColor Yellow
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
Write-Host "  Logs:        $logDir/"
Write-Host "======================================"  -ForegroundColor Cyan
