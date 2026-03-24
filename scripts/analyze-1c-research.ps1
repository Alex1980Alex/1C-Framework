#!/usr/bin/env pwsh
# analyze-1c-research.ps1 v4 - Micro-Agent Architecture
# 1 phase = 1 claude -p call. 10 micro-agents per iteration.

param(
    [string]$TaskFile,
    [string]$SessionDir,
    [int]$TargetScore = 85,
    [int]$MaxIterations = 7,
    [int]$CompareEvery = 3,
    [int]$PhaseMaxTurns = 30,
    [switch]$SkipMcpCheck,
    [string]$ResumeFrom = ""  # auto, EXEC-P1..P5, REV-S1..S3, CMP
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

# Phase order for resume detection
$script:AllPhases = @("EXEC-P1","EXEC-P2","EXEC-P3","EXEC-P4","EXEC-P5","REV-S1","REV-S2","REV-S3","CMP")
$script:PhaseFileMap = @{
    "EXEC-P1" = "phase1_requirements.md"; "EXEC-P2" = "phase2_objects.md"
    "EXEC-P3" = "phase3_patterns.md"; "EXEC-P4" = "phase4_plan.md"
    "EXEC-P5" = "phase5_verification.md"
    "REV-S1" = "review1_scoring.md"; "REV-S2" = "review2_verification.md"
    "REV-S3" = "review3_verdict.md"; "CMP" = "compare1_analysis.md"
}
# For iter>1 incremental mode
$script:IncrPhases = @("EXEC-FIX","EXEC-VERIFY","REV-S1","REV-S2","REV-S3","CMP")
$script:IncrPhaseFileMap = @{
    "EXEC-FIX" = "phase4_fix.md"; "EXEC-VERIFY" = "phase5_verify.md"
    "REV-S1" = "review1_scoring.md"; "REV-S2" = "review2_verification.md"
    "REV-S3" = "review3_verdict.md"; "CMP" = "compare1_analysis.md"
}

function Detect-ResumePhase($dir, $isIncremental) {
    # Find the first phase that has NO completed output file
    $phases = if ($isIncremental) { $script:IncrPhases } else { $script:AllPhases }
    $fileMap = if ($isIncremental) { $script:IncrPhaseFileMap } else { $script:PhaseFileMap }
    foreach ($ph in $phases) {
        $f = Join-Path $dir $fileMap[$ph]
        $sf = "$f.status"
        # Phase is done if file exists AND status contains DONE
        $isDone = (Test-Path $f) -and (Test-Path $sf) -and ((Get-Content $sf -Raw -ErrorAction SilentlyContinue) -match "DONE")
        if (-not $isDone) { return $ph }
    }
    return $null  # all phases done
}

function Should-Skip($currentPhase, $resumeFrom, $isIncremental) {
    if (-not $resumeFrom) { return $false }
    $phases = if ($isIncremental) { $script:IncrPhases } else { $script:AllPhases }
    $currentIdx = [array]::IndexOf($phases, $currentPhase)
    $resumeIdx = [array]::IndexOf($phases, $resumeFrom)
    if ($resumeIdx -lt 0) { return $false }
    return $currentIdx -lt $resumeIdx
}

function Extract-TaskId($path) {
    $name = [System.IO.Path]::GetFileNameWithoutExtension($path)
    if ($name -match '^(GKSTCPLK-\d+|[A-Za-z0-9_-]+)') { return $Matches[1] }
    return "task-$(Get-Date -f 'yyyyMMdd-HHmmss')"
}

# =============================================================
# MCP Health Check: quick test before MCP-dependent phases
# =============================================================
function Test-MCP() {
    Log "MCP HEALTH CHECK..."
    $checks = @{}
    $allOk = $true

    # 1. bsl-semantic-search: bsl_stats is cheapest ping
    $r1 = Run-Phase "MCP-BSL" "Call bsl_stats tool. Output only the result." "$phasesDir/mcp_check_bsl.md" 3
    if ($r1 -and $r1.Length -gt 20) { $checks["bsl-semantic-search"] = "OK"; Log "  bsl-semantic-search: OK" }
    else { $checks["bsl-semantic-search"] = "FAIL"; $allOk = $false; Log "  bsl-semantic-search: FAIL" }

    # 2. 1c-mcp-toolkit: get_metadata is cheapest
    $r2 = Run-Phase "MCP-1C" "Call get_metadata with object_type='Configuration' and object_name=''. Output only the result." "$phasesDir/mcp_check_1c.md" 3
    if ($r2 -and $r2.Length -gt 20) { $checks["1c-mcp-toolkit"] = "OK"; Log "  1c-mcp-toolkit: OK" }
    else { $checks["1c-mcp-toolkit"] = "FAIL"; $allOk = $false; Log "  1c-mcp-toolkit: FAIL" }

    # 3. bsl-platform-context: search is cheapest
    $r3 = Run-Phase "MCP-API" "Call the bsl-platform-context search tool with query 'Справочник'. Output only the result." "$phasesDir/mcp_check_api.md" 3
    if ($r3 -and $r3.Length -gt 10) { $checks["bsl-platform-context"] = "OK"; Log "  bsl-platform-context: OK" }
    else { $checks["bsl-platform-context"] = "FAIL"; $allOk = $false; Log "  bsl-platform-context: FAIL" }

    # Write health report
    $report = "# MCP Health Check`n"
    foreach ($k in $checks.Keys) { $report += "- $k : $($checks[$k])`n" }
    Write-Utf8 "$phasesDir/mcp_health.md" $report

    if ($allOk) {
        Write-Host "  [MCP] All 3 servers OK" -ForegroundColor Green
    } else {
        $failed = ($checks.GetEnumerator() | Where-Object { $_.Value -eq "FAIL" } | ForEach-Object { $_.Key }) -join ", "
        Write-Host "  [MCP] FAILED: $failed" -ForegroundColor Red
        Write-Host "  [MCP] Analysis will continue but MCP-dependent phases may fail" -ForegroundColor Yellow
    }
    return $allOk
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

    # Wait for completion — no timeout, only --max-turns protects from infinite loops
    # Heartbeat every 30s shows agent is alive
    $waited = 0
    while ($job.State -eq "Running") {
        Start-Sleep -Seconds 5
        $waited += 5
        if ($waited % 30 -lt 6) {
            $cpu = try { [math]::Round((Get-Process -Name "node" -ErrorAction SilentlyContinue | Measure-Object CPU -Sum).Sum, 1) } catch { 0 }
            Log "$phaseName | ${waited}s cpu=$cpu"
            Write-Utf8 "$outputFile.status" "# $phaseName - RUNNING ${waited}s cpu=$cpu"
        }
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

    # Record timing for summary
    if ($script:PhaseTimes) { $script:PhaseTimes[$phaseName] = $elapsed }
    if ($script:PhaseCosts) { $script:PhaseCosts[$phaseName] = $cost }

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
Write-Host "Target:   $TargetScore | Max: $MaxIterations | MaxTurns/phase: $PhaseMaxTurns | No timeout"
Write-Host ""
Log "=== START target=$TargetScore max=$MaxIterations ==="

# --- Pre-flight MCP health check ---
if ($SkipMcpCheck) {
    Write-Host "  [PRE-FLIGHT] MCP check SKIPPED (-SkipMcpCheck)" -ForegroundColor Yellow
    $mcpOk = $true
} else {
    Write-Host "  [PRE-FLIGHT] Checking MCP servers..." -ForegroundColor Cyan
    $mcpOk = Test-MCP
}
Get-ChildItem $phasesDir -Filter "mcp_check*" -ErrorAction SilentlyContinue | Remove-Item -Force

if (-not $mcpOk) {
    $healthFile = "$SessionDir/MCP_FAILED.md"
    $failed = Get-Content "$phasesDir/mcp_health.md" -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    @"
# MCP SERVERS UNAVAILABLE

Analysis STOPPED. Some MCP servers are not responding.

$failed

## Options:
1. Fix MCP servers and re-run the script
2. Run with -SkipMcpCheck to analyze without MCP (reduced quality)

Re-run command:
``powershell
.\scripts\analyze-1c-research.ps1 -SessionDir "$SessionDir"
``
"@ | Set-Content $healthFile -Encoding UTF8

    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Red
    Write-Host "  MCP SERVERS UNAVAILABLE - ANALYSIS STOPPED" -ForegroundColor Red
    Write-Host "  ============================================" -ForegroundColor Red
    Write-Host "  Fix MCP servers and re-run, or use -SkipMcpCheck" -ForegroundColor Yellow
    Write-Host "  Details: $healthFile" -ForegroundColor Yellow
    Write-Host ""
    Log "STOPPED: MCP health check failed"
    exit 1
}
Write-Host ""

for ($i = $startIter + 1; $i -le $MaxIterations; $i++) {
    $iterStart = Get-Date
    $ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ"
    Write-Host "`n=== Iteration $i / $MaxIterations [$ts] ===" -ForegroundColor Cyan
    Log "=== ITERATION $i ==="

    $commitBefore = (git rev-parse --short HEAD 2>$null)
    $script:PhaseTimes = @{}
    $script:PhaseCosts = @{}
    $isIncr = ($i -gt 1)

    # Determine resume point
    $resumePhase = $null
    if ($ResumeFrom -eq "auto" -or ($ResumeFrom -eq "" -and $i -eq $startIter + 1)) {
        # Auto-detect: check existing phase files
        $detected = Detect-ResumePhase $phasesDir $isIncr
        if ($detected -and $ResumeFrom -eq "auto") {
            $resumePhase = $detected
            Write-Host "  [RESUME] Auto-detected: starting from $resumePhase" -ForegroundColor Cyan
            Log "RESUME: auto-detected $resumePhase"
        }
    } elseif ($ResumeFrom -ne "") {
        $resumePhase = $ResumeFrom
        Write-Host "  [RESUME] Manual: starting from $resumePhase" -ForegroundColor Cyan
        Log "RESUME: manual $resumePhase"
    }

    # Only clean phases if starting fresh (no resume)
    if (-not $resumePhase) {
        Get-ChildItem $phasesDir -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
    }
    # Clear ResumeFrom after first iteration (only applies once)
    $ResumeFrom = ""

    # Read reviewer feedback from previous iteration
    $feedbackContext = ""
    $feedbackFile = "$SessionDir/reviewer_feedback.json"
    if ($isIncr -and (Test-Path $feedbackFile)) {
        $feedbackContext = Get-Content $feedbackFile -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    }

    if (-not $isIncr) {
        # --- ITERATION 1: Full 5-phase analysis ---
        if (-not (Should-Skip "EXEC-P1" $resumePhase $false)) {
            Write-Host "  [EXEC] Phase 1/5: Requirements..." -ForegroundColor Yellow
            $p1 = Run-Phase "EXEC-P1" "You are analyzing a 1C:Enterprise task. Parse requirements ONLY.`nTask: $taskContent`n`nInstructions:`n1. Read the task description carefully`n2. Extract numbered requirements [REQ-1], [REQ-2], etc.`n3. For each requirement: one sentence describing what needs to be done`n4. Output a numbered markdown list of requirements" "$phasesDir/phase1_requirements.md" 10
        } else { Write-Host "  [EXEC] Phase 1/5: SKIPPED (resume)" -ForegroundColor DarkGray }

        if (-not (Should-Skip "EXEC-P2" $resumePhase $false)) {
            Write-Host "  [EXEC] Phase 2/5: Objects..." -ForegroundColor Yellow
            $p2 = Run-Phase "EXEC-P2" "You are analyzing a 1C:Enterprise task. Find configuration objects.`nTask: $taskContent`n`nRequirements are in file: Read file $phasesDir/phase1_requirements.md`n`nInstructions:`n1. Use bsl_search to find relevant configuration objects`n2. Use get_metadata to verify object structure and fields`n3. List each found object with type, name, and relevant fields`n4. Mark verified fields with checkmark" "$phasesDir/phase2_objects.md" $PhaseMaxTurns
        } else { Write-Host "  [EXEC] Phase 2/5: SKIPPED (resume)" -ForegroundColor DarkGray }

        if (-not (Should-Skip "EXEC-P3" $resumePhase $false)) {
            Write-Host "  [EXEC] Phase 3/5: Patterns..." -ForegroundColor Yellow
            $p3 = Run-Phase "EXEC-P3" "You are analyzing a 1C:Enterprise task. Find code patterns.`nTask: $taskContent`n`nRequirements: Read file $phasesDir/phase1_requirements.md`nObjects: Read file $phasesDir/phase2_objects.md`n`nInstructions:`n1. Use bsl_hybrid_search or search_in_code to find similar implementations`n2. For each requirement, find existing code patterns in the configuration`n3. List code patterns with module names and brief description`n4. Note reusable patterns vs new code needed" "$phasesDir/phase3_patterns.md" $PhaseMaxTurns
        } else { Write-Host "  [EXEC] Phase 3/5: SKIPPED (resume)" -ForegroundColor DarkGray }

        if (-not (Should-Skip "EXEC-P4" $resumePhase $false)) {
            Write-Host "  [EXEC] Phase 4/5: Plan..." -ForegroundColor Yellow
            $p4 = Run-Phase "EXEC-P4" "You are analyzing a 1C:Enterprise task. Create modification plan.`nTask: $taskContent`n`nPrevious phases wrote results to files. Read them:`n- Requirements: Read file $phasesDir/phase1_requirements.md`n- Objects: Read file $phasesDir/phase2_objects.md`n- Patterns: Read file $phasesDir/phase3_patterns.md`n`nInstructions:`n1. Read all 3 phase files above`n2. Create numbered modification plan`n3. Each point: [REQ-N] Module > Method > What to change`n4. Include SQL queries needed`n5. Write complete analysis report to $SessionDir/analysis-report.md using Write tool" "$phasesDir/phase4_plan.md" $PhaseMaxTurns
        } else { Write-Host "  [EXEC] Phase 4/5: SKIPPED (resume)" -ForegroundColor DarkGray }

        if (-not (Should-Skip "EXEC-P5" $resumePhase $false)) {
            Write-Host "  [EXEC] Phase 5/5: Verification..." -ForegroundColor Yellow
            $p5 = Run-Phase "EXEC-P5" "You are verifying a 1C:Enterprise analysis.`nTask: $taskContent`n`nRead the analysis report: Read file $SessionDir/analysis-report.md`nIf it does not exist, read $phasesDir/phase4_plan.md instead.`n`nInstructions:`n1. For each SQL query in the plan: call validate_query or execute_query to verify`n2. For each field name: call get_metadata to confirm it exists`n3. List verification results: PASS or FAIL for each check`n4. Update $SessionDir/analysis-report.md with verification markers using Write tool" "$phasesDir/phase5_verification.md" $PhaseMaxTurns
        } else { Write-Host "  [EXEC] Phase 5/5: SKIPPED (resume)" -ForegroundColor DarkGray }
    } else {
        # --- ITERATION N > 1: Incremental improvement based on feedback ---
        if (-not (Should-Skip "EXEC-FIX" $resumePhase $true)) {
            Write-Host "  [EXEC] Incremental: Fix gaps..." -ForegroundColor Yellow
            $p4 = Run-Phase "EXEC-FIX" "You are IMPROVING an existing 1C analysis report. Iteration ${i}.`nTask: $taskContent`n`nCurrent report: Read file $SessionDir/analysis-report.md`nReviewer feedback: $feedbackContext`n`nInstructions:`n1. Read the current analysis-report.md`n2. Read the reviewer feedback carefully - it lists specific GAPS to fix`n3. Fix ONE or TWO gaps from the feedback:`n   - requirement_gap: add missing [REQ-N] markers or requirements section`n   - field_unverified: call get_metadata to verify the field, add checkmark`n   - pattern_missing: call bsl_search to find pattern, add to report`n   - query_invalid: call execute_query to validate SQL, add marker`n4. Update $SessionDir/analysis-report.md with improvements using Write tool`n5. Keep all existing content, only ADD or FIX the gaps" "$phasesDir/phase4_fix.md" $PhaseMaxTurns
        } else { Write-Host "  [EXEC] Fix: SKIPPED (resume)" -ForegroundColor DarkGray }

        if (-not (Should-Skip "EXEC-VERIFY" $resumePhase $true)) {
            Write-Host "  [EXEC] Verify fixes..." -ForegroundColor Yellow
            $p5 = Run-Phase "EXEC-VERIFY" "Verify the fixes made to the analysis report.`nTask: $taskContent`n`nRead: $SessionDir/analysis-report.md`n`n1. Check if the gaps mentioned in feedback were fixed`n2. For any new SQL queries: call validate_query`n3. For any new fields: call get_metadata`n4. Update report with verification markers using Write tool" "$phasesDir/phase5_verify.md" $PhaseMaxTurns
        } else { Write-Host "  [EXEC] Verify: SKIPPED (resume)" -ForegroundColor DarkGray }
    }

    $execSec = [math]::Round(((Get-Date) - $iterStart).TotalSeconds)
    Write-Host "  [EXEC] All 5 phases: ${execSec}s" -ForegroundColor Green
    Log "EXECUTOR: ${execSec}s"

    # Check report exists (file-based — data/ may be gitignored)
    $reportPath = "$SessionDir/analysis-report.md"
    if (-not (Test-Path $reportPath)) {
        # Fallback: assemble report from phase files
        Write-Host "  [ASSEMBLE] Agent didn't write report — assembling from phases..." -ForegroundColor Yellow
        Log "ASSEMBLE: building from phases"
        $assembledContent = "# Analysis Report`n`n"
        $phaseFiles = if ($isIncr) { @("phase4_fix.md","phase5_verify.md") } else { @("phase1_requirements.md","phase2_objects.md","phase3_patterns.md","phase4_plan.md","phase5_verification.md") }
        foreach ($ph in $phaseFiles) {
            $phFile = "$phasesDir/$ph"
            if (Test-Path $phFile) {
                $phContent = Get-Content $phFile -Raw -Encoding UTF8
                if ($phContent -and $phContent.Length -gt 10) {
                    $assembledContent += $phContent + "`n`n---`n`n"
                }
            }
        }
        if ($assembledContent.Length -gt 200) {
            Write-Utf8 $reportPath $assembledContent
            Write-Host "  [ASSEMBLE] Report assembled ($($assembledContent.Length) chars)" -ForegroundColor Green
            Log "ASSEMBLE: done $($assembledContent.Length) chars"
        }
    }

    if (-not (Test-Path $reportPath)) {
        Write-Host "  [SKIP] No report created." -ForegroundColor Yellow
        Log "SKIP: no report"
        $plateauCount++
        continue
    }

    # Try to commit (git add -f to bypass gitignore for data/)
    $commitAfter = (git rev-parse --short HEAD 2>$null)
    if ($commitAfter -eq $commitBefore) {
        Log "Orchestrator: committing report"
        git add -f "$reportPath" 2>$null
        git add -f "$SessionDir/phases/" 2>$null
        git add -f "$SessionDir/reviewer_feedback.json" 2>$null
        git commit -m "[AR-${i}] Analysis report" 2>$null
        $commitAfter = (git rev-parse --short HEAD 2>$null)
    }
    if ($commitAfter -ne $commitBefore) {
        Write-Host "  [EXEC] Committed: $commitAfter" -ForegroundColor Green
        Log "Committed: $commitAfter"
    } else {
        Write-Host "  [EXEC] Report exists ($([math]::Round((Get-Item $reportPath).Length / 1024))KB)" -ForegroundColor Green
        Log "Report exists, git skipped (gitignored)"
    }

    # ===== REVIEWER 3 PHASES =====
    $revStart = Get-Date

    if (-not (Should-Skip "REV-S1" $resumePhase $isIncr)) {
        Write-Host "  [REV] Step 1/3: Scoring..." -ForegroundColor Yellow
        $r1 = Run-Phase "REV-S1" "You are scoring a 1C analysis report.`nRun: python $projectRoot/scripts/score-analysis-report.py $SessionDir/analysis-report.md`nParse and output: METRIC, BREAKDOWN, GAPS" "$phasesDir/review1_scoring.md" 10
    } else { Write-Host "  [REV] Step 1/3: SKIPPED (resume)" -ForegroundColor DarkGray; $r1 = Get-Content "$phasesDir/review1_scoring.md" -Raw -Encoding UTF8 -ErrorAction SilentlyContinue }

    if (-not (Should-Skip "REV-S2" $resumePhase $isIncr)) {
        Write-Host "  [REV] Step 2/3: MCP Verify..." -ForegroundColor Yellow
        $r2 = Run-Phase "REV-S2" "You are verifying a 1C analysis report via MCP.`nScorer results:`n$r1`n`n1. Pick up to 3 unverified fields, call get_metadata`n2. Pick up to 2 SQL queries, call execute_query`n3. Report which passed, which failed" "$phasesDir/review2_verification.md" 15
    } else { Write-Host "  [REV] Step 2/3: SKIPPED (resume)" -ForegroundColor DarkGray; $r2 = Get-Content "$phasesDir/review2_verification.md" -Raw -Encoding UTF8 -ErrorAction SilentlyContinue }

    if (-not (Should-Skip "REV-S3" $resumePhase $isIncr)) {
        Write-Host "  [REV] Step 3/3: Verdict + Feedback..." -ForegroundColor Yellow
        $r3 = Run-Phase "REV-S3" "You MUST output EXACTLY these 3 lines FIRST:`nMETRIC: 55`nVERDICT: IMPROVE`nREASON: Requirements section missing`n`nNow decide real values for iteration ${i}:`n- Previous best: $bestMetric. Target: $TargetScore.`n- Scorer: $r1`n- Verification: $r2`n`nRules: score > best = KEEP. score > best but gaps = IMPROVE. score <= best = REVERT.`n`nAfter the 3 lines, save reviewer feedback for next iteration:`nWrite file $SessionDir/reviewer_feedback.json with JSON:`n{`"iteration`": ${i}, `"score`": NUMBER, `"gaps`": [{`"type`": `"requirement_gap|field_unverified|pattern_missing|query_invalid`", `"detail`": `"what to fix`"}]}`n`nThis feedback will be used by the next iteration to fix specific gaps." "$phasesDir/review3_verdict.md" 15
    } else { Write-Host "  [REV] Step 3/3: SKIPPED (resume)" -ForegroundColor DarkGray; $r3 = Get-Content "$phasesDir/review3_verdict.md" -Raw -Encoding UTF8 -ErrorAction SilentlyContinue }

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
    # Phase timing table
    Write-Host "`n  ---- Iter ${i} | Score: ${metric}/${TargetScore} [$bar$gap] $verdict ----" -ForegroundColor Cyan
    Write-Host "  Phase Timings:" -ForegroundColor White
    $totalCost = 0.0
    foreach ($pk in @("EXEC-P1","EXEC-P2","EXEC-P3","EXEC-P4","EXEC-P5","REV-S1","REV-S2","REV-S3","CMP")) {
        $pt = if ($script:PhaseTimes.ContainsKey($pk)) { $script:PhaseTimes[$pk] } else { "-" }
        $pc = if ($script:PhaseCosts.ContainsKey($pk)) { $script:PhaseCosts[$pk] } else { "-" }
        if ($pc -ne "-") { try { $totalCost += [double]$pc } catch {} }
        if ($pt -ne "-") {
            $label = switch ($pk) {
                "EXEC-P1" { "Requirements" } "EXEC-P2" { "Objects    " } "EXEC-P3" { "Patterns   " }
                "EXEC-P4" { "Plan       " } "EXEC-P5" { "Verify     " }
                "REV-S1"  { "Scoring    " } "REV-S2"  { "MCP Verify " } "REV-S3"  { "Verdict    " }
                "CMP"     { "Comparator " } default { $pk }
            }
            Write-Host "    $label  ${pt}s  `$$pc" -ForegroundColor DarkGray
        }
    }
    Write-Host "    TOTAL        ${total}s  `$$([math]::Round($totalCost, 2))" -ForegroundColor White
    Write-Host "  -------------------------------------------" -ForegroundColor Cyan

    Log "SUMMARY: $metric/$TargetScore $verdict ${total}s cost=`$$([math]::Round($totalCost, 2))"

    # Save detailed summary
    $timingLines = "# Iter $i`nScore: $metric/$TargetScore | Best: $bestMetric | Verdict: $verdict`n`n| Phase | Time | Cost |`n|-------|------|------|`n"
    foreach ($pk in @("EXEC-P1","EXEC-P2","EXEC-P3","EXEC-P4","EXEC-P5","REV-S1","REV-S2","REV-S3","CMP")) {
        $pt = if ($script:PhaseTimes.ContainsKey($pk)) { "$($script:PhaseTimes[$pk])s" } else { "-" }
        $pc = if ($script:PhaseCosts.ContainsKey($pk)) { "`$$($script:PhaseCosts[$pk])" } else { "-" }
        $timingLines += "| $pk | $pt | $pc |`n"
    }
    $timingLines += "| **TOTAL** | **${total}s** | **`$$([math]::Round($totalCost, 2))** |`n"
    Write-Utf8 "$iterDir/summary.md" $timingLines

    if ($bestMetric -ge $TargetScore) { Write-Host "`n  TARGET: $bestMetric >= $TargetScore" -ForegroundColor Green; break }
    if ($plateauCount -ge 3) { Write-Host "`n  PLATEAU" -ForegroundColor Yellow; break }
    Start-Sleep -Seconds 2
}

# --- Post-iteration: Format analysis report via Z.AI ---
$reportPath = "$SessionDir/analysis-report.md"
if (Test-Path $reportPath) {
    Write-Host "`n  [FORMAT] Formatting analysis report via Z.AI..." -ForegroundColor Cyan
    $formatPrompt = @"
You are formatting a 1C analysis report for readability. Use llm_complete to delegate formatting.

1. Read file: $reportPath
2. Prepare a prompt for mcp__llm-rotation__llm_complete with the full report content and these instructions:
   - Add executive summary (3-5 bullet points) at the top
   - Ensure consistent [REQ-N] markers throughout
   - Align tables, fix broken markdown formatting
   - Do NOT change any technical content, field names, or SQL queries
3. Call mcp__llm-rotation__llm_complete(prompt=<your prompt with report content>, max_tokens=8192)
4. Review the Z.AI result: verify field names and references match the original
5. Write the formatted version to $reportPath using Write tool
"@
    $formatResult = Run-Phase "FORMAT" $formatPrompt "$phasesDir/format_report.md" 15
    if ($formatResult -and $formatResult.Length -gt 100) {
        Write-Host "  [FORMAT] Done" -ForegroundColor Green
        Log "FORMAT: report formatted via Z.AI"
        git add "$reportPath" 2>$null
        git commit -m "[AR-FMT] Format analysis report via Z.AI" 2>$null
    } else {
        Write-Host "  [FORMAT] Skipped (no result)" -ForegroundColor Yellow
        Log "FORMAT: skipped"
    }
}

$sessionTotal = [math]::Round(((Get-Date) - $iterStart).TotalSeconds)
Write-Host "`n=== COMPLETE ===" -ForegroundColor Cyan
$st = if ($bestMetric -ge $TargetScore) { "TARGET" } else { "STOPPED" }
Write-Host "  Iterations: $i/$MaxIterations | Best: $bestMetric/$TargetScore | Status: $st"
Write-Host "  Report:  $SessionDir/analysis-report.md"
Write-Host "  Phases:  $phasesDir/"
Write-Host "  Results: $SessionDir/results/"

# Final timing report
$finalReport = "# Analyze-1C-Research: Final Report`n`nTask: $taskId`nScore: $bestMetric/$TargetScore | Status: $st`nIterations: $i`n`n"
$finalReport += "## Iteration Summaries`n`n"
for ($j = 1; $j -le $i; $j++) {
    $sf = "$SessionDir/results/iter$j/summary.md"
    if (Test-Path $sf) {
        $finalReport += (Get-Content $sf -Raw -Encoding UTF8) + "`n---`n"
    }
}
Write-Utf8 "$SessionDir/final-report.md" $finalReport
Write-Host "  Final:   $SessionDir/final-report.md"

Log "=== END $bestMetric $st ==="
