#!/usr/bin/env pwsh
# analyze-1c-research.ps1 - Three-Agent 1C Analysis Engine v3
# Real-time monitoring via phase files + CPU check + smart timeout

param(
    [string]$TaskFile,
    [string]$SessionDir,
    [int]$TargetScore = 85,
    [int]$MaxIterations = 7,
    [int]$CompareEvery = 3,
    [int]$AgentTimeoutMin = 15,
    [int]$AgentMaxTurns = 50,
    [int]$IdleTimeoutMin = 5
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

# --- Per-phase timeout limits in seconds ---
$script:PhaseLimits = @{
    "phase1" = 180;  "phase2" = 240;  "phase3" = 300
    "phase4" = 180;  "phase5" = 180
    "review1" = 180; "review2" = 180; "review3" = 180
    "compare1" = 180; "compare2" = 180
    "default" = 180
}
$script:CpuGraceSec = 120

$script:ProgressFile = $null
$script:SessionDirPath = $null
$script:LastKnownCommit = $null
$script:CurrentIter = 0

function Log-Progress($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host "    $line" -ForegroundColor DarkGray
    if ($script:ProgressFile) {
        $line | Add-Content $script:ProgressFile -Encoding UTF8
    }
}

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

function Get-ClaudeCpu {
    try {
        $procs = Get-Process -Name "node" -ErrorAction SilentlyContinue
        if ($procs) {
            return [math]::Round(($procs | Measure-Object -Property CPU -Sum).Sum, 1)
        }
    } catch {}
    return 0
}

function Get-PhaseFiles($dir) {
    if (-not (Test-Path $dir)) { return @() }
    return Get-ChildItem $dir -Filter "*.md" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime
}

function Get-PhaseLimit($fileName) {
    if ($fileName -match '^(phase\d|review\d|compare\d)') {
        $key = $Matches[1]
        if ($script:PhaseLimits.ContainsKey($key)) { return $script:PhaseLimits[$key] }
    }
    return $script:PhaseLimits["default"]
}

# =============================================================
# Run-Claude: Start-Job + phase file monitoring + CPU check
# =============================================================
function Run-Claude($prompt, $logFile, $agentName) {
    Log-Progress "$agentName START timeout=${AgentTimeoutMin}m idle=${IdleTimeoutMin}m turns=$AgentMaxTurns"
    $agentStart = Get-Date

    $statusFile = $logFile -replace '\.txt$', '_status.md'
    @"
# $agentName - RUNNING
Started: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
"@ | Set-Content $statusFile -Encoding UTF8

    # Phases dir for heartbeat files
    $phasesDir = "$script:SessionDirPath/phases"
    if (-not (Test-Path $phasesDir)) { New-Item -ItemType Directory -Path $phasesDir -Force > $null }
    $phaseCountBefore = (Get-PhaseFiles $phasesDir).Count

    # Launch agent as background job
    $jsonOutFile = "$logFile.json"
    $job = Start-Job -ScriptBlock {
        param($p, $mt, $outFile)
        $r = claude -p $p --dangerously-skip-permissions --output-format json --max-turns $mt 2>&1 | Out-String
        $r | Set-Content $outFile -Encoding UTF8
        return $r
    } -ArgumentList $prompt, $AgentMaxTurns, $jsonOutFile

    # Monitor loop
    $lastPhaseTime = Get-Date
    $lastPhaseFile = ""
    $currentPhase = "starting"
    $deadline = (Get-Date).AddMinutes($AgentTimeoutMin)
    $cpuBaseline = Get-ClaudeCpu

    while ($job.State -eq "Running") {
        Start-Sleep -Seconds 5

        $elapsed = [math]::Round(((Get-Date) - $agentStart).TotalSeconds)
        $sincePhase = [math]::Round(((Get-Date) - $lastPhaseTime).TotalSeconds)

        # Check new phase files
        $phaseFiles = Get-PhaseFiles $phasesDir
        if ($phaseFiles.Count -gt $phaseCountBefore) {
            $newest = $phaseFiles[-1]
            if ($newest.Name -ne $lastPhaseFile) {
                $lastPhaseFile = $newest.Name
                $lastPhaseTime = Get-Date
                $currentPhase = $newest.BaseName
                $firstLine = (Get-Content $newest.FullName -TotalCount 2 -Encoding UTF8 -ErrorAction SilentlyContinue) -join " "
                if ($firstLine.Length -gt 100) { $firstLine = $firstLine.Substring(0, 100) + "..." }
                Log-Progress "$agentName >> $currentPhase [file $($phaseFiles.Count - $phaseCountBefore + 1)]"
                Log-Progress "$agentName    $firstLine"
                $phaseCountBefore = $phaseFiles.Count
            }
        }

        # Check git commits
        $curCommit = git rev-parse --short HEAD 2>$null
        if ($script:LastKnownCommit -and $curCommit -ne $script:LastKnownCommit) {
            $lastPhaseTime = Get-Date
            Log-Progress "$agentName | git commit: $curCommit"
            $script:LastKnownCommit = $curCommit
        }

        # CPU check
        $cpuNow = Get-ClaudeCpu
        $cpuActive = ($cpuNow - $cpuBaseline) -gt 1

        # Heartbeat every ~30s
        if ($elapsed % 30 -lt 6) {
            Log-Progress "$agentName | ${elapsed}s phase=$currentPhase idle=${sincePhase}s cpu=$cpuNow"
            @"
# $agentName - RUNNING
Elapsed: ${elapsed}s | Phase: $currentPhase | Idle: ${sincePhase}s | CPU: $cpuNow
"@ | Set-Content $statusFile -Encoding UTF8
        }

        # --- TIMEOUT LOGIC ---
        $phaseLimit = Get-PhaseLimit $currentPhase
        $effectiveLimit = if ($cpuActive) { $phaseLimit + $script:CpuGraceSec } else { $phaseLimit }

        # Phase timeout
        if ($sincePhase -gt $effectiveLimit) {
            if ($cpuActive) {
                Log-Progress "$agentName | WARNING: $currentPhase over limit but CPU active"
                $lastPhaseTime = Get-Date
            } else {
                Log-Progress "$agentName HUNG: $currentPhase idle=${sincePhase}s cpu=$cpuNow - killing"
                Stop-Job $job -ErrorAction SilentlyContinue
                Remove-Job $job -Force -ErrorAction SilentlyContinue
                @"
# $agentName - HUNG
Killed: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Reason: $currentPhase no progress ${sincePhase}s, CPU=$cpuNow
"@ | Set-Content $statusFile -Encoding UTF8
                "" | Set-Content $logFile -Encoding UTF8
                return ""
            }
        }

        # Hard deadline
        if ((Get-Date) -gt $deadline) {
            if ($cpuActive -or $sincePhase -lt 60) {
                $deadline = (Get-Date).AddMinutes(5)
                Log-Progress "$agentName | deadline extended +5m"
            } else {
                Log-Progress "$agentName HARD TIMEOUT: ${AgentTimeoutMin}m cpu=$cpuNow - killing"
                Stop-Job $job -ErrorAction SilentlyContinue
                Remove-Job $job -Force -ErrorAction SilentlyContinue
                @"
# $agentName - HARD TIMEOUT
Killed: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Reason: ${AgentTimeoutMin}m exceeded, idle=${sincePhase}s, CPU=$cpuNow
"@ | Set-Content $statusFile -Encoding UTF8
                "" | Set-Content $logFile -Encoding UTF8
                return ""
            }
        }
    }

    # --- Job completed ---
    $output = Receive-Job $job 2>&1 | Out-String
    Remove-Job $job -Force -ErrorAction SilentlyContinue

    if (-not $output -and (Test-Path $jsonOutFile)) {
        $output = Get-Content $jsonOutFile -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    }

    $resultText = ""
    $numTurns = 0
    $cost = ""
    try {
        $json = $output | ConvertFrom-Json -ErrorAction Stop
        $resultText = $json.result
        $cost = "$([math]::Round($json.total_cost_usd, 3))"
        $numTurns = if ($json.num_turns) { $json.num_turns } else { 0 }
    } catch {
        $resultText = $output
    }

    $elapsed = [math]::Round(((Get-Date) - $agentStart).TotalSeconds)
    $finalPhases = Get-PhaseFiles $phasesDir
    $phaseNames = ($finalPhases | ForEach-Object { $_.BaseName }) -join ", "
    Log-Progress "$agentName DONE: ${elapsed}s turns=$numTurns cost=$cost phases=[$phaseNames]"

    @"
# $agentName - DONE
Duration: ${elapsed}s | Turns: $numTurns | Cost: $cost
Phases: $phaseNames
Output: $($resultText.Length) chars
"@ | Set-Content $statusFile -Encoding UTF8

    $resultText | Set-Content $logFile -Encoding UTF8
    $output | Set-Content "$logFile.json" -Encoding UTF8

    # Copy phases to results, then clean
    $resultsDir = "$script:SessionDirPath/results"
    if (-not (Test-Path $resultsDir)) { New-Item -ItemType Directory -Path $resultsDir -Force > $null }
    if ($finalPhases.Count -gt 0) {
        $iterPhasesDir = "$resultsDir/iter$($script:CurrentIter)_${agentName}_phases"
        if (-not (Test-Path $iterPhasesDir)) { New-Item -ItemType Directory -Path $iterPhasesDir -Force > $null }
        Copy-Item "$phasesDir/*.md" $iterPhasesDir -ErrorAction SilentlyContinue
    }
    Get-ChildItem $phasesDir -Filter "*.md" -ErrorAction SilentlyContinue | Remove-Item -Force

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
        New-Item -ItemType Directory -Path "$SessionDir/phases" -Force > $null
        New-Item -ItemType Directory -Path "$SessionDir/results" -Force > $null
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

$script:ProgressFile = "$SessionDir/progress.log"
$script:SessionDirPath = $SessionDir
$script:LastKnownCommit = (git rev-parse --short HEAD 2>$null)
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
Write-Host "=== Analyze-1C-Research v3 ===" -ForegroundColor Cyan
Write-Host "Session:  $SessionDir"
Write-Host "Target:   $TargetScore | Max: $MaxIterations | Timeout: ${AgentTimeoutMin}m | Idle: ${IdleTimeoutMin}m | Turns: $AgentMaxTurns"
Write-Host "Start:    iter=$startIter best=$bestMetric plateau=$plateauCount baseline=$baselineCommit"
Write-Host "Progress: $script:ProgressFile"
Write-Host ""

Log-Progress "=== SESSION START target=$TargetScore max=$MaxIterations ==="

# --- Main Loop ---
for ($i = $startIter + 1; $i -le $MaxIterations; $i++) {
    $script:CurrentIter = $i
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    Write-Host "`n=== Iteration $i / $MaxIterations [$ts] ===" -ForegroundColor Cyan
    Log-Progress "=== ITERATION $i / $MaxIterations ==="

    $commitBefore = (git rev-parse --short HEAD 2>$null)

    # --- EXECUTOR ---
    $execStart = Get-Date
    Write-Host "  [EXECUTOR] 5-phase analysis..." -ForegroundColor Yellow
    $vars = @{
        iter = $i; max_iterations = $MaxIterations
        task_description = $taskContent; session_dir = $SessionDir
        best_metric = $bestMetric; target_score = $TargetScore
        baseline_commit = $baselineCommit
    }
    $executorPrompt = Load-Template "$templatesDir/1c-analysis-executor.md" $vars
    $executorOutput = Run-Claude $executorPrompt "$logDir/executor_$i.txt" "EXEC"
    $execSec = [math]::Round(((Get-Date) - $execStart).TotalSeconds)
    Write-Host "  [EXECUTOR] Done ${execSec}s" -ForegroundColor Green
    Log-Progress "EXECUTOR: ${execSec}s $($executorOutput.Length) chars"

    if ($executorOutput -match "AUTORESEARCH_DONE") {
        Write-Host "`n  AUTORESEARCH_DONE" -ForegroundColor Green
        break
    }

    $commitAfter = (git rev-parse --short HEAD 2>$null)
    if ($commitAfter -eq $commitBefore) {
        Write-Host "  [SKIP] No commit." -ForegroundColor Yellow
        Log-Progress "SKIP: no commit"
        $plateauCount++
        (@{iter=$i;ts=$ts;score=$bestMetric;delta=0;verdict="SKIP";reason="no commit"} | ConvertTo-Json -Compress) | Add-Content $jsonlPath -Encoding UTF8
        continue
    }

    # --- REVIEWER ---
    $revStart = Get-Date
    Write-Host "  [REVIEWER] Scoring..." -ForegroundColor Yellow
    $vars.best_metric = $bestMetric
    $reviewerPrompt = Load-Template "$templatesDir/1c-analysis-reviewer.md" $vars
    $reviewerOutput = Run-Claude $reviewerPrompt "$logDir/reviewer_$i.txt" "REV"
    $revSec = [math]::Round(((Get-Date) - $revStart).TotalSeconds)

    $verdict = Extract-Verdict $reviewerOutput
    $metric = Extract-Metric $reviewerOutput
    $reason = ""
    if ($reviewerOutput -match 'REASON:\s*(.+)') { $reason = $Matches[1].Trim() }

    if ($null -eq $metric) {
        $rp = "$SessionDir/analysis-report.md"
        if (Test-Path $rp) {
            $so = python "$projectRoot/scripts/score-analysis-report.py" $rp 2>&1 | Out-String
            $metric = Extract-Metric $so
        }
    }
    if ($null -eq $metric) { $metric = 0 }
    $delta = $metric - $bestMetric

    switch ($verdict) {
        "KEEP"    { if ($metric -gt $bestMetric) { $bestMetric=$metric; $plateauCount=0 } else { $plateauCount++ }; Write-Host "  [REVIEWER] KEEP score=$metric +$delta ${revSec}s" -ForegroundColor Green }
        "IMPROVE" { if ($metric -gt $bestMetric) { $bestMetric=$metric; $plateauCount=0 } else { $plateauCount++ }; Write-Host "  [REVIEWER] IMPROVE score=$metric ${revSec}s" -ForegroundColor Yellow }
        "REVERT"  { $plateauCount++; Write-Host "  [REVIEWER] REVERT score=$metric ${revSec}s" -ForegroundColor Red }
        default   { $plateauCount++; Write-Host "  [REVIEWER] $verdict score=$metric ${revSec}s" -ForegroundColor Yellow }
    }
    Log-Progress "REVIEWER: score=$metric verdict=$verdict delta=$delta ${revSec}s"

    # --- COMPARATOR ---
    $cmpSec = 0
    if ($i % $CompareEvery -eq 0 -and $baselineCommit) {
        $cmpStart = Get-Date
        Write-Host "  [COMPARATOR] A/B..." -ForegroundColor Magenta
        $cmpPrompt = Load-Template "$templatesDir/1c-analysis-comparator.md" $vars
        $cmpOut = Run-Claude $cmpPrompt "$logDir/comparator_$i.txt" "CMP"
        $cmpSec = [math]::Round(((Get-Date) - $cmpStart).TotalSeconds)
        Write-Host "  [COMPARATOR] Done ${cmpSec}s" -ForegroundColor Magenta
        Log-Progress "COMPARATOR: ${cmpSec}s"
    }

    # JSONL + state
    $cd = ""; if ($executorOutput -match '\[AR-\d+\]\s*(.+)') { $cd = $Matches[1].Trim() }
    (@{iter=$i;ts=$ts;commit=(git rev-parse --short HEAD 2>$null);score=$metric;delta=$delta;verdict=$verdict;reason=$reason;change=$cd} | ConvertTo-Json -Compress) | Add-Content $jsonlPath -Encoding UTF8

    $mc = Get-Content "$SessionDir/autoresearch.md" -Raw -Encoding UTF8
    $mc = $mc -replace 'Iteration:\s*\d+', "Iteration: $i"
    $mc = $mc -replace 'BestMetric:\s*\d+', "BestMetric: $bestMetric"
    $mc = $mc -replace 'Plateau:\s*\d+', "Plateau: $plateauCount"
    Set-Content "$SessionDir/autoresearch.md" -Value $mc -Encoding UTF8

    # Summary
    $total = [math]::Round(((Get-Date) - $execStart).TotalSeconds)
    $bar = "#" * [math]::Min([math]::Max([math]::Round($bestMetric / 5), 0), 20)
    $gap = "." * (20 - $bar.Length)
    Write-Host ""
    Write-Host "  ---- Iteration $i ----" -ForegroundColor Cyan
    Write-Host "  Score:   $metric/$TargetScore [$bar$gap] best=$bestMetric" -ForegroundColor White
    Write-Host "  Verdict: $verdict | Delta:$delta | Plateau:$plateauCount/3" -ForegroundColor White
    Write-Host "  Time:    E=${execSec}s R=${revSec}s C=${cmpSec}s T=${total}s" -ForegroundColor DarkGray
    Log-Progress "SUMMARY: $metric/$TargetScore best=$bestMetric $verdict plateau=$plateauCount/3 ${total}s"

    $rd = "$SessionDir/results"
    @"
# Iteration $i
Score: $metric/$TargetScore | Best: $bestMetric | Verdict: $verdict
Executor: ${execSec}s | Reviewer: ${revSec}s | Comparator: ${cmpSec}s | Total: ${total}s
"@ | Set-Content "$rd/iter${i}_summary.md" -Encoding UTF8

    if ($bestMetric -ge $TargetScore) { Write-Host "`n  TARGET: $bestMetric >= $TargetScore" -ForegroundColor Green; Log-Progress "TARGET REACHED"; break }
    if ($plateauCount -ge 3) { Write-Host "`n  PLATEAU: 3x no improvement" -ForegroundColor Yellow; Log-Progress "PLATEAU"; break }
    Start-Sleep -Seconds 2
}

Write-Host "`n=== COMPLETE ===" -ForegroundColor Cyan
$st = if ($bestMetric -ge $TargetScore) { "TARGET" } else { "STOPPED plateau=$plateauCount" }
Write-Host "  Iterations: $i/$MaxIterations | Best: $bestMetric/$TargetScore | Status: $st"
Write-Host "  Report:  $SessionDir/analysis-report.md"
Write-Host "  Results: $SessionDir/results/"
Write-Host "  Log:     $script:ProgressFile"
Log-Progress "=== END best=$bestMetric $st ==="
