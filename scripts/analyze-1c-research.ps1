#!/usr/bin/env pwsh
# analyze-1c-research.ps1 v4 - Micro-Agent Architecture
# 1 phase = 1 claude -p call. 10 micro-agents per iteration.

param(
    [string]$TaskFile,
    [string]$SessionDir,
    [int]$TargetScore = 85,
    [int]$MaxIterations = 7,
    [int]$CompareEvery = 3,
    [int]$PhaseTimeoutMin = 8,
    [int]$PhaseMaxTurns = 30
)

chcp 65001 > $null 2>&1
$env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = (Get-Item "$scriptDir/..").FullName
Set-Location $projectRoot
$dataDir = "$projectRoot/data/analyze-1c-research"
$script:ProgressFile = $null

function Log($msg) {
    $ts = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host "    $line" -ForegroundColor DarkGray
    if ($script:ProgressFile) { $line | Add-Content $script:ProgressFile -Encoding UTF8 }
}

# Write file without BOM (PowerShell 5.1 Set-Content adds BOM)
function Write-Utf8($path, $text) {
    [System.IO.File]::WriteAllText($path, $text, [System.Text.UTF8Encoding]::new($false))
}

function Extract-TaskId($path) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($path)
    if ($name -match '^(GKSTCPLK-\d+|[A-Za-z0-9_-]+)') { return $Matches[1] }
    return "task-$(Get-Date -f 'yyyyMMdd-HHmmss')"
}

function Run-Phase($phaseName, $prompt, $outputFile, $maxTurns) {
    if (-not $maxTurns) { $maxTurns = $PhaseMaxTurns }
    $start = Get-Date
    Log "$phaseName START"
    Write-Utf8 "$outputFile.status" "# $phaseName - RUNNING"

    # Save prompt to file to avoid command-line length limits + pass UTF-8
    $promptFile = "$outputFile.prompt"
    Write-Utf8 $promptFile $prompt

    $job = Start-Job -ScriptBlock {
        param($pFile, $mt)
        chcp 65001 > $null 2>&1
        $env:PYTHONIOENCODING = "utf-8"
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $p = [System.IO.File]::ReadAllText($pFile, [System.Text.Encoding]::UTF8)
        $r = claude -p $p --dangerously-skip-permissions --output-format json --max-turns $mt 2>&1 | Out-String
        # Write raw result to file to bypass Receive-Job encoding issues
        $outPath = $pFile -replace '\.prompt$', '.raw'
        [System.IO.File]::WriteAllText($outPath, $r, [System.Text.UTF8Encoding]::new($false))
        return "DONE"
    } -ArgumentList $promptFile, $maxTurns

    $deadlineSec = $PhaseTimeoutMin * 60
    $waited = 0
    while ($job.State -eq "Running" -and $waited -lt $deadlineSec) {
        Start-Sleep -Seconds 5
        $waited += 5
        if ($waited % 30 -lt 6) {
            $cpu = try { [math]::Round((Get-Process -Name "node" -ErrorAction SilentlyContinue | Measure-Object CPU -Sum).Sum, 1) } catch { 0 }
            Log "$phaseName | ${waited}s cpu=$cpu"
            Write-Utf8 "$outputFile.status" "# $phaseName - RUNNING ${waited}s cpu=$cpu"
        }
    }

    if ($job.State -eq "Running") {
        Log "$phaseName TIMEOUT ${PhaseTimeoutMin}m - killing"
        Stop-Job $job -ErrorAction SilentlyContinue
        Remove-Job $job -Force -ErrorAction SilentlyContinue
        Write-Utf8 "$outputFile.status" "# $phaseName - TIMEOUT"
        Write-Utf8 $outputFile ""
        return ""
    }

    Receive-Job $job > $null 2>&1
    Remove-Job $job -Force -ErrorAction SilentlyContinue

    # Read result from .raw file (bypasses Receive-Job cp1251 encoding)
    $rawFile = "$outputFile.raw"
    $raw = ""
    if (Test-Path $rawFile) {
        $raw = [System.IO.File]::ReadAllText($rawFile, [System.Text.Encoding]::UTF8)
    }

    $resultText = ""; $turns = 0; $cost = ""
    try {
        $json = $raw | ConvertFrom-Json -ErrorAction Stop
        $resultText = $json.result
        $turns = if ($json.num_turns) { $json.num_turns } else { 0 }
        $cost = "$([math]::Round($json.total_cost_usd, 3))"
    } catch { $resultText = $raw }

    $elapsed = [math]::Round(((Get-Date) - $start).TotalSeconds)
    Log "$phaseName DONE: ${elapsed}s turns=$turns cost=$cost chars=$($resultText.Length)"

    Write-Utf8 $outputFile $resultText
    Write-Utf8 "$outputFile.json" $raw
    Write-Utf8 "$outputFile.status" "# $phaseName - DONE ${elapsed}s turns=$turns cost=$cost"

    # Cleanup temp files
    Remove-Item $promptFile -ErrorAction SilentlyContinue
    Remove-Item $rawFile -ErrorAction SilentlyContinue

    return $resultText
}

function Extract-Verdict($text) {
    if ($text -match 'VERDICT:\s*(KEEP|IMPROVE|REVERT)') { return $Matches[1] }
    # Fallback: look for keywords
    if ($text -match '\bKEEP\b') { return "KEEP" }
    if ($text -match '\bIMPROVE\b') { return "IMPROVE" }
    if ($text -match '\bREVERT\b') { return "REVERT" }
    return "IMPROVE"  # default to IMPROVE if score exists
}
function Extract-Metric($text) {
    if ($text -match 'METRIC:\s*(\d+)') { return [int]$Matches[1] }
    # Fallback: look for "score" patterns
    if ($text -match 'score[:\s]+(\d+)') { return [int]$Matches[1] }
    return $null
}

# --- Init ---
if (-not $SessionDir -and -not $TaskFile) { Write-Host "[ERROR] Specify -TaskFile or -SessionDir" -ForegroundColor Red; exit 1 }

if ($SessionDir) {
    if (-not (Test-Path "$SessionDir/autoresearch.md")) { Write-Host "[ERROR] Not found" -ForegroundColor Red; exit 1 }
} else {
    if (-not (Test-Path $TaskFile)) { Write-Host "[ERROR] Task file not found: $TaskFile" -ForegroundColor Red; exit 1 }
    $taskId = Extract-TaskId $TaskFile
    $SessionDir = "$dataDir/$taskId"
    if (-not (Test-Path $SessionDir)) {
        New-Item -ItemType Directory -Path "$SessionDir/phases" -Force > $null
        New-Item -ItemType Directory -Path "$SessionDir/results" -Force > $null
        Copy-Item $TaskFile "$SessionDir/task.md"
        $bl = (git rev-parse --short HEAD 2>$null)
        Write-Utf8 "$SessionDir/autoresearch.md" "# Analyze-1C-Research: $taskId`nIteration: 0 | BestMetric: 0 | Plateau: 0`nBaselineCommit: $bl`n## History`n| Iter | Score | Verdict |`n|------|-------|---------|"
    }
}

$script:ProgressFile = "$SessionDir/progress.log"
Write-Utf8 $script:ProgressFile ""
$phasesDir = "$SessionDir/phases"
if (-not (Test-Path $phasesDir)) { New-Item -ItemType Directory -Path $phasesDir -Force > $null }
# Clean phases from previous run
Get-ChildItem $phasesDir -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse

$md = Get-Content "$SessionDir/autoresearch.md" -Raw -Encoding UTF8
$startIter = 0; $bestMetric = 0; $plateauCount = 0; $baselineCommit = ""
if ($md -match 'Iteration:\s*(\d+)') { $startIter = [int]$Matches[1] }
if ($md -match 'BestMetric:\s*(\d+)') { $bestMetric = [int]$Matches[1] }
if ($md -match 'Plateau:\s*(\d+)') { $plateauCount = [int]$Matches[1] }
if ($md -match 'BaselineCommit:\s*(\S+)') { $baselineCommit = $Matches[1] }

$taskContent = Get-Content "$SessionDir/task.md" -Raw -Encoding UTF8

Write-Host "=== Analyze-1C-Research v4: Micro-Agent ===" -ForegroundColor Cyan
Write-Host "Session:  $SessionDir"
Write-Host "Target:   $TargetScore | Max: $MaxIterations | Phase: ${PhaseTimeoutMin}m/${PhaseMaxTurns}t"
Write-Host ""
Log "=== START target=$TargetScore max=$MaxIterations ==="

for ($i = $startIter + 1; $i -le $MaxIterations; $i++) {
    $iterStart = Get-Date
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    Write-Host "`n=== Iteration $i / $MaxIterations [$ts] ===" -ForegroundColor Cyan
    Log "=== ITERATION $i ==="

    Get-ChildItem $phasesDir -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
    $commitBefore = (git rev-parse --short HEAD 2>$null)

    # ===== EXECUTOR 5 PHASES =====
    Write-Host "  [EXEC] Phase 1/5: Requirements..." -ForegroundColor Yellow
    $p1 = Run-Phase "EXEC-P1" "You are analyzing a 1C:Enterprise task. Parse requirements ONLY.`nTask: $taskContent`n`nInstructions:`n1. Read the task description carefully`n2. Extract numbered requirements [REQ-1], [REQ-2], etc.`n3. For each requirement: one sentence describing what needs to be done`n4. Output a numbered markdown list of requirements" "$phasesDir/phase1_requirements.md" 10

    Write-Host "  [EXEC] Phase 2/5: Objects..." -ForegroundColor Yellow
    $p2 = Run-Phase "EXEC-P2" "You are analyzing a 1C:Enterprise task. Find configuration objects.`nTask: $taskContent`nRequirements found:`n$p1`n`nInstructions:`n1. Use bsl_search to find relevant configuration objects`n2. Use get_metadata to verify object structure and fields`n3. List each found object with type, name, and relevant fields`n4. Mark verified fields with checkmark" "$phasesDir/phase2_objects.md" $PhaseMaxTurns

    Write-Host "  [EXEC] Phase 3/5: Patterns..." -ForegroundColor Yellow
    $p3 = Run-Phase "EXEC-P3" "You are analyzing a 1C:Enterprise task. Find code patterns.`nTask: $taskContent`nRequirements:`n$p1`nObjects found:`n$p2`n`nInstructions:`n1. Use bsl_hybrid_search or search_in_code to find similar implementations`n2. For each requirement, find existing code patterns in the configuration`n3. List code patterns with module names and brief description`n4. Note reusable patterns vs new code needed" "$phasesDir/phase3_patterns.md" $PhaseMaxTurns

    Write-Host "  [EXEC] Phase 4/5: Plan..." -ForegroundColor Yellow
    $p4 = Run-Phase "EXEC-P4" "You are analyzing a 1C:Enterprise task. Create modification plan.`nTask: $taskContent`n`nPrevious phases wrote results to files. Read them:`n- Requirements: Read file $phasesDir/phase1_requirements.md`n- Objects: Read file $phasesDir/phase2_objects.md`n- Patterns: Read file $phasesDir/phase3_patterns.md`n`nInstructions:`n1. Read all 3 phase files above`n2. Create numbered modification plan`n3. Each point: [REQ-N] Module > Method > What to change`n4. Include SQL queries needed`n5. Write complete analysis report to $SessionDir/analysis-report.md using Write tool`n6. Then run via Bash: git add -A && git commit -m '[AR-$i] Analysis report'" "$phasesDir/phase4_plan.md" $PhaseMaxTurns

    Write-Host "  [EXEC] Phase 5/5: Verification..." -ForegroundColor Yellow
    $p5 = Run-Phase "EXEC-P5" "You are verifying a 1C:Enterprise analysis.`nTask: $taskContent`n`nRead the analysis report: Read file $SessionDir/analysis-report.md`nIf it does not exist, read $phasesDir/phase4_plan.md instead.`n`nInstructions:`n1. For each SQL query in the plan: call validate_query or execute_query to verify`n2. For each field name: call get_metadata to confirm it exists`n3. List verification results: PASS or FAIL for each check`n4. Update $SessionDir/analysis-report.md with verification markers using Write tool`n5. Commit via Bash: git add -A && git commit -m '[AR-$i] Verification'" "$phasesDir/phase5_verification.md" $PhaseMaxTurns

    $execSec = [math]::Round(((Get-Date) - $iterStart).TotalSeconds)
    Write-Host "  [EXEC] All 5 phases: ${execSec}s" -ForegroundColor Green
    Log "EXECUTOR: ${execSec}s"

    # Orchestrator commits if agent didn't (agent may lack Bash access)
    $commitAfter = (git rev-parse --short HEAD 2>$null)
    if ($commitAfter -eq $commitBefore) {
        $reportPath = "$SessionDir/analysis-report.md"
        if (Test-Path $reportPath) {
            Log "Orchestrator: committing analysis-report.md"
            git add -A 2>$null
            git commit -m "[AR-$i] Analysis report" 2>$null
            $commitAfter = (git rev-parse --short HEAD 2>$null)
        }
    }
    if ($commitAfter -eq $commitBefore) {
        Write-Host "  [SKIP] No report created." -ForegroundColor Yellow
        Log "SKIP: no report"
        $plateauCount++
        continue
    }
    Write-Host "  [EXEC] Committed: $commitAfter" -ForegroundColor Green
    Log "Committed: $commitAfter"

    # ===== REVIEWER 3 PHASES =====
    $revStart = Get-Date

    Write-Host "  [REV] Step 1/3: Scoring..." -ForegroundColor Yellow
    $r1 = Run-Phase "REV-S1" "You are scoring a 1C analysis report.`nRun: python $projectRoot/scripts/score-analysis-report.py $SessionDir/analysis-report.md`nParse and output: METRIC, BREAKDOWN, GAPS" "$phasesDir/review1_scoring.md" 10

    Write-Host "  [REV] Step 2/3: MCP Verify..." -ForegroundColor Yellow
    $r2 = Run-Phase "REV-S2" "You are verifying a 1C analysis report via MCP.`nScorer results:`n$r1`n`n1. Pick up to 3 unverified fields, call get_metadata`n2. Pick up to 2 SQL queries, call execute_query`n3. Report which passed, which failed" "$phasesDir/review2_verification.md" 15

    Write-Host "  [REV] Step 3/3: Verdict..." -ForegroundColor Yellow
    $r3 = Run-Phase "REV-S3" "You MUST output EXACTLY these 3 lines as your FIRST output, nothing before them:`nMETRIC: 55`nVERDICT: IMPROVE`nREASON: Requirements section missing`n`nNow decide the real values for iteration $i:`n- Previous best score: $bestMetric`n- Target: $TargetScore`n- Scorer output: $r1`n- Verification: $r2`n`nRules:`n- If score > previous best AND no critical failures: VERDICT: KEEP`n- If score > previous best BUT gaps remain: VERDICT: IMPROVE`n- If score <= previous best: VERDICT: REVERT`n`nOutput your 3 lines: METRIC, VERDICT, REASON. Nothing else before them." "$phasesDir/review3_verdict.md" 10

    $revSec = [math]::Round(((Get-Date) - $revStart).TotalSeconds)

    $verdict = Extract-Verdict $r3
    $metric = Extract-Metric $r3
    if ($null -eq $metric) { $metric = Extract-Metric $r1 }
    if ($null -eq $metric) {
        $rp = "$SessionDir/analysis-report.md"
        if (Test-Path $rp) { $metric = Extract-Metric (python "$projectRoot/scripts/score-analysis-report.py" $rp 2>&1 | Out-String) }
    }
    if ($null -eq $metric) { $metric = 0 }
    $delta = $metric - $bestMetric

    switch ($verdict) {
        "KEEP"    { if ($metric -gt $bestMetric) { $bestMetric=$metric; $plateauCount=0 } else { $plateauCount++ }; Write-Host "  [REV] KEEP $metric +$delta ${revSec}s" -ForegroundColor Green }
        "IMPROVE" { if ($metric -gt $bestMetric) { $bestMetric=$metric; $plateauCount=0 } else { $plateauCount++ }; Write-Host "  [REV] IMPROVE $metric ${revSec}s" -ForegroundColor Yellow }
        "REVERT"  { $plateauCount++; Write-Host "  [REV] REVERT $metric ${revSec}s" -ForegroundColor Red }
        default   { $plateauCount++; Write-Host "  [REV] $verdict $metric ${revSec}s" -ForegroundColor Yellow }
    }
    Log "REVIEWER: score=$metric verdict=$verdict delta=$delta ${revSec}s"

    # ===== COMPARATOR =====
    $cmpSec = 0
    if ($i % $CompareEvery -eq 0 -and $baselineCommit) {
        $cmpStart = Get-Date
        Write-Host "  [CMP] Comparing..." -ForegroundColor Magenta
        $c1 = Run-Phase "CMP" "Compare two versions of 1C analysis.`nTask: $taskContent`n`n1. Read current: $SessionDir/analysis-report.md`n2. Read baseline: git show ${baselineCommit}:$SessionDir/analysis-report.md`n3. Rate both 1-10: completeness, correctness, patterns, actionability`n4. Output winner and notes" "$phasesDir/compare1_analysis.md" 15
        $cmpSec = [math]::Round(((Get-Date) - $cmpStart).TotalSeconds)
        Write-Host "  [CMP] Done ${cmpSec}s" -ForegroundColor Magenta
        Log "COMPARATOR: ${cmpSec}s"
    }

    # State
    $mc = Get-Content "$SessionDir/autoresearch.md" -Raw -Encoding UTF8
    $mc = $mc -replace 'Iteration:\s*\d+', "Iteration: $i"
    $mc = $mc -replace 'BestMetric:\s*\d+', "BestMetric: $bestMetric"
    $mc = $mc -replace 'Plateau:\s*\d+', "Plateau: $plateauCount"
    Write-Utf8 "$SessionDir/autoresearch.md" $mc

    # Copy phases to results
    $iterDir = "$SessionDir/results/iter$i"
    New-Item -ItemType Directory -Path $iterDir -Force > $null
    Copy-Item "$phasesDir/*.md" $iterDir -ErrorAction SilentlyContinue

    # Summary
    $total = [math]::Round(((Get-Date) - $iterStart).TotalSeconds)
    $bar = "#" * [math]::Min([math]::Max([math]::Round($bestMetric / 5), 0), 20)
    $gap = "." * (20 - $bar.Length)
    Write-Host "`n  ---- Iter ${i} | ${metric}/${TargetScore} [$bar$gap] $verdict E=${execSec}s R=${revSec}s C=${cmpSec}s T=${total}s ----" -ForegroundColor Cyan
    Log "SUMMARY: $metric/$TargetScore $verdict ${total}s"
    Write-Utf8 "$iterDir/summary.md" "# Iter $i`nScore: $metric/$TargetScore | Best: $bestMetric | Verdict: $verdict`nExec: ${execSec}s | Rev: ${revSec}s | Cmp: ${cmpSec}s | Total: ${total}s"

    if ($bestMetric -ge $TargetScore) { Write-Host "`n  TARGET: $bestMetric >= $TargetScore" -ForegroundColor Green; break }
    if ($plateauCount -ge 3) { Write-Host "`n  PLATEAU" -ForegroundColor Yellow; break }
    Start-Sleep -Seconds 2
}

Write-Host "`n=== COMPLETE ===" -ForegroundColor Cyan
$st = if ($bestMetric -ge $TargetScore) { "TARGET" } else { "STOPPED" }
Write-Host "  Best: $bestMetric/$TargetScore | $st"
Write-Host "  Report:  $SessionDir/analysis-report.md"
Write-Host "  Phases:  $phasesDir/"
Write-Host "  Results: $SessionDir/results/"
Log "=== END $bestMetric $st ==="
