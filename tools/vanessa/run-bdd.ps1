# VA BDD Test Runner for 1С-Framework
# Features sync from project -> D:\va-test, VA runs there, results copy back
# Usage: powershell -ExecutionPolicy Bypass -File tools\vanessa\run-bdd.ps1 [-Feature "smoke_testclient.feature"]
#
# Parameters:
#   -Feature           single feature file to run (relative to features/ directory)
#   -TimeoutSec        timeout in seconds (default 120)
#   -KeepRunning       do not kill 1C processes after the run
#   -OutputJson        absolute path to write a structured result JSON (for /run-1c-tests integration)
#   -RunId             unique run identifier; when set, va-log and JUnit are copied to
#                      build/reports/runs/<RunId>/ for isolation between sequential runs
#   -MaxRetries        max attempts per feature (1 = no retry, default 1)
#   -BackoffBaseSec    base delay in seconds before first retry (default 5)
#   -BackoffMultiplier delay multiplier per subsequent retry (default 3.0: 5s, 15s, 45s)
#   -BackoffMaxSec     max delay cap in seconds (default 60)
#   -JitterPct         random jitter +/-% added to delay to avoid thundering herd (default 30)
#
# When -OutputJson is set, the script writes a JSON summary with fields:
#   feature, started_at, finished_at, duration_s, exit_code, build_status,
#   junit_xml, va_log, process_pid, last_step, run_id
# /run-1c-tests uses this file to update .run-state.json without parsing console output.
param(
    [string]$Feature = "",
    [int]$TimeoutSec = 120,
    [switch]$KeepRunning,
    [string]$OutputJson = "",
    [string]$RunId = "",
    [switch]$SkipPreflight,
    [int]$MaxRetries = 1,
    [int]$BackoffBaseSec = 5,
    [double]$BackoffMultiplier = 3.0,
    [int]$BackoffMaxSec = 60,
    [int]$JitterPct = 30
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# Capture start time ISO-8601 for structured output
$startedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
$startedTicks = (Get-Date).Ticks

# --- Error classification for retry logic ---
function Test-TransientError {
    param(
        [string]$vaLogPath,
        [string]$buildStatusPath
    )

    # Crash: no build status AND no/empty VA log → transient
    $buildStatusExists = Test-Path -LiteralPath $buildStatusPath
    $vaLogExists = Test-Path -LiteralPath $vaLogPath
    $vaLogHasContent = $false
    if ($vaLogExists) {
        $vaLogHasContent = ((Get-Item -LiteralPath $vaLogPath).Length -gt 0)
    }

    if (-not $buildStatusExists -and (-not $vaLogExists -or -not $vaLogHasContent)) {
        return $true
    }

    if (-not $vaLogExists -or -not $vaLogHasContent) {
        return $false
    }

    $logContent = Get-Content -LiteralPath $vaLogPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue

    # Logical errors — never retry (wrong test, not infrastructure)
    $logicalPatterns = @(
        'Не найдена процедура для шага'
        'Неверный тип навигационной ссылки'
        'Кнопка не найдена'
        'Строка не найдена в таблице'
        'Поле формы не существует'
        'Неизвестный элемент формы'
    )
    foreach ($pattern in $logicalPatterns) {
        if ($logContent -match [regex]::Escape($pattern)) {
            return $false
        }
    }

    # Transient errors — worth retrying (infrastructure, timing)
    $transientPatterns = @(
        'Не найдено окно'
        'не удалось подключить клиент тестирования'
        'TestClient.*не отвечает'
        'Таймаут ожидания'
        'Поле не доступно'
        'Ошибка при подключении'
        'Could not connect'
        'Connection refused'
        'Время ожидания операции истекло'
    )
    foreach ($pattern in $transientPatterns) {
        if ($logContent -match $pattern) {
            return $true
        }
    }

    # Conservative default: don't retry unknown errors
    return $false
}

$projectDir = "D:\va-test"
$frameworkRoot = (Get-Item "D:\1*-Framework" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '1' }).FullName
$featuresSource = "$frameworkRoot\features"
$featuresDest = "$projectDir\features"
$exe = "C:\Program Files\1Cv8\8.3.27.1859\bin\1cv8c.exe"
$vaEpf = "$projectDir\va.epf"
$vaParams = "$projectDir\VAParams.json"
$buildStatus = "$projectDir\BuildStatus.log"
$vaLog = "$projectDir\va-out.txt"
$reportDir = "$projectDir\build\reports"

# Sources for the reglament-trigger helper (invoked from VA via "я запускаю команду ОС")
$triggerSourceDir = "$frameworkRoot\tools\vanessa"
$triggerPs1Src    = "$triggerSourceDir\trigger-reglament.ps1"
$triggerPySrc     = "$triggerSourceDir\trigger-reglament.py"
$preflightPySrc   = "$triggerSourceDir\preflight-probe.py"

# 1. Kill old 1C processes
Get-Process -Name '1cv8c','1cv8' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 2. Sync features from project to va-test
Write-Host "[SYNC] $featuresSource -> $featuresDest"
if (Test-Path $featuresSource) {
    Get-ChildItem "$featuresSource" -Recurse -Filter "*.feature" | ForEach-Object {
        $relPath = $_.FullName.Substring($featuresSource.Length + 1)
        $destDir = Split-Path "$featuresDest\$relPath" -Parent
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        Copy-Item $_.FullName "$featuresDest\$relPath" -Force
        Write-Host "  copied: $relPath"
    }
}

# 2b. Sync trigger-reglament helpers to $projectDir
#     (VA calls "powershell -File D:\va-test\trigger-reglament.ps1" which delegates
#     to trigger-reglament.py through the project venv; the .py file also lives
#     in $projectDir so both are visible from the latin-path working directory.)
foreach ($src in @($triggerPs1Src, $triggerPySrc)) {
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $projectDir (Split-Path $src -Leaf)) -Force
        Write-Host "  synced: $(Split-Path $src -Leaf)"
    } else {
        Write-Host "  [WARN] missing: $src"
    }
}

# 2c. Pre-flight data probe against live TestDB (unless -SkipPreflight)
if (-not $SkipPreflight) {
    $python = Join-Path $frameworkRoot ".venv\Scripts\python.exe"
    if ((Test-Path $python) -and (Test-Path $preflightPySrc)) {
        $preflightArgs = @($preflightPySrc)
        if ($Feature) {
            $preflightArgs += @("--feature", (Join-Path $featuresDest $Feature))
        } else {
            $preflightArgs += @("--feature", $featuresDest)
        }
        $env:PYTHONIOENCODING = "utf-8"
        Write-Host "[PREFLIGHT] $python preflight-probe.py"
        & $python @preflightArgs
        $preflightExit = $LASTEXITCODE
        if ($preflightExit -ne 0) {
            Write-Host "[PREFLIGHT] BLOCKER detected (exit $preflightExit) -- aborting VA launch."
            Write-Host "[PREFLIGHT] Fix the flagged data items, or re-run with -SkipPreflight to bypass."
            exit $preflightExit
        }
        Write-Host "[PREFLIGHT] OK"
    } else {
        Write-Host "[PREFLIGHT] skipped (python or preflight script missing)"
    }
} else {
    Write-Host "[PREFLIGHT] skipped (-SkipPreflight)"
}

# 3. If specific feature requested, disable others
if ($Feature) {
    # Support subdirectory paths like "gkstcplk2256/00_smoke.feature"
    $targetFile = Join-Path $featuresDest $Feature
    Get-ChildItem "$featuresDest" -Recurse -Filter "*.feature" | Where-Object { $_.FullName -ne $targetFile } | ForEach-Object {
        Rename-Item $_.FullName "$($_.FullName).off"
    }
    Write-Host "[RUN] Only: $Feature"
} else {
    # Re-enable any .off files
    Get-ChildItem "$featuresDest" -Recurse -Filter "*.off" | ForEach-Object {
        Rename-Item $_.FullName ($_.FullName -replace '\.off$','')
    }
    Write-Host "[RUN] All features in $featuresDest"
}

# === RETRY LOOP ===
$allAttempts = @()
$currentAttempt = 0
$errorCategory = "none"

do {
$currentAttempt++

# Backoff delay + kill stale processes (skip on first attempt)
if ($currentAttempt -gt 1) {
    $delay = [Math]::Min($BackoffBaseSec * [Math]::Pow($BackoffMultiplier, $currentAttempt - 2), $BackoffMaxSec)
    $jitterRange = $delay * $JitterPct / 100
    $jitter = (Get-Random -Minimum (-1000) -Maximum 1000) / 1000 * $jitterRange
    $delay = [Math]::Max(1, [Math]::Round($delay + $jitter, 1))
    Write-Host "`n[RETRY] Attempt $currentAttempt/$MaxRetries after ${delay}s backoff..."
    Start-Sleep -Seconds ([Math]::Ceiling($delay))
    Get-Process -Name '1cv8c','1cv8' -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2
}

# 4. Clean old results
Remove-Item $buildStatus -ErrorAction SilentlyContinue
Remove-Item $vaLog -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$attemptStartedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
$attemptStartTicks = (Get-Date).Ticks

# 5. Launch VA
$cParam = "StartFeaturePlayer;DisableFirstRunHelper;VAParams=$vaParams"
$proc = Start-Process -FilePath $exe -ArgumentList @(
    'ENTERPRISE',
    '/S"KOMPUTER\TestDB"',
    '/N"a.terletskiy@sodru.com"',
    "/P`"$env:ONEC_PASSWORD`"",
    '/DisableStartupMessages',
    '/DisableStartupDialogs',
    '/TESTMANAGER',
    "/Execute""$vaEpf""",
    "/C""$cParam""",
    "/out""$vaLog"""
) -PassThru

Write-Host "[VA] PID=$($proc.Id) timeout=${TimeoutSec}s"

# 6. Wait for completion
$elapsed = 0
while ($elapsed -lt $TimeoutSec) {
    Start-Sleep -Seconds 5
    $elapsed += 5
    $p = Get-Process -Id $proc.Id -ErrorAction SilentlyContinue
    if (-not $p) { Write-Host "[$elapsed`s] Process exited"; break }
    if (Test-Path $buildStatus) {
        $status = (Get-Content $buildStatus -Encoding UTF8).Trim()
        Write-Host "[$elapsed`s] BuildStatus=$status"
        break
    }
    $procs = (Get-Process -Name "1cv8c" -ErrorAction SilentlyContinue).Count
    $port = if (netstat -ano | Select-String ":1538\s" | Select-String "LISTENING") {" PORT1538"} else {""}
    Write-Host "[$elapsed`s] ${procs}proc$port"
}

# 7. Results
$exitCode = 1
if (Test-Path $buildStatus) {
    $status = (Get-Content $buildStatus -Encoding UTF8).Trim()
    Write-Host "`n=== BUILD STATUS: $status ==="
    if ($status -eq "0") { $exitCode = 0 }
} else {
    Write-Host "`n=== NO BUILD STATUS (VA may have crashed) ==="
}

if (Test-Path $vaLog) {
    Write-Host "=== VA LOG ==="
    Get-Content $vaLog -Encoding UTF8
}

# Extract last executed VA step from log (needed for retry classification + output)
$lastStep = ""
if (Test-Path $vaLog) {
    try {
        $logLines = Get-Content $vaLog -Encoding UTF8 -ErrorAction SilentlyContinue
        if ($logLines) {
            $stepLine = $logLines |
                Where-Object { $_ -match '^\s*\p{IsCyrillic}+\s+' } |
                Select-Object -Last 1
            if ($stepLine) { $lastStep = $stepLine.Trim() }
        }
    } catch { $lastStep = "" }
}

# Classify error and record attempt
$attemptDurationS = [Math]::Round(((Get-Date).Ticks - $attemptStartTicks) / 10000000.0, 1)
$isTransient = $false
$errorCategory = "none"
if ($exitCode -ne 0) {
    $isTransient = Test-TransientError -vaLogPath $vaLog -buildStatusPath $buildStatus
    $errorCategory = if ($isTransient) { "transient" } else { "logical" }
}

$attemptRecord = [PSCustomObject]@{
    attempt        = $currentAttempt
    started_at     = $attemptStartedAt
    duration_s     = $attemptDurationS
    exit_code      = $exitCode
    error_category = $errorCategory
    last_step      = $lastStep
}
$allAttempts += $attemptRecord

if ($exitCode -eq 0) {
    Write-Host "[ATTEMPT $currentAttempt] PASSED in ${attemptDurationS}s"
} else {
    Write-Host "[ATTEMPT $currentAttempt] FAILED ($errorCategory) in ${attemptDurationS}s"
    if ($isTransient -and $currentAttempt -lt $MaxRetries) {
        Write-Host "[ATTEMPT $currentAttempt] Transient error — will retry"
    }
}

$shouldRetry = ($exitCode -ne 0) -and ($currentAttempt -lt $MaxRetries) -and $isTransient

} while ($shouldRetry)
# === END RETRY LOOP ===

# 8. Copy results back to project
$projectBuild = (Get-Item "D:\1*-Framework" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '1' }).FullName + "\build"
if (Test-Path "$reportDir\*.xml") {
    New-Item -ItemType Directory -Path "$projectBuild\reports" -Force | Out-Null
    Copy-Item "$reportDir\*" "$projectBuild\reports\" -Force
    Write-Host "[SYNC] JUnit reports -> $projectBuild\reports\"
}

# 9. Re-enable disabled features
Get-ChildItem "$featuresDest" -Recurse -Filter "*.off" | ForEach-Object {
    Rename-Item $_.FullName ($_.FullName -replace '\.off$','')
}

# 10. If -OutputJson or -RunId is set, write structured result JSON
#     for /run-1c-tests integration (state machine needs machine-readable outcome)
if ($OutputJson -or $RunId) {
    $finishedAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ss")
    $durationS = [math]::Round(((Get-Date).Ticks - $startedTicks) / 10000000.0, 1)

    # Resolve isolated copy destinations when RunId is provided
    $junitCopiedPath = ""
    $vaLogCopiedPath = ""
    if ($RunId) {
        $runDir = Join-Path $projectBuild "reports\runs\$RunId"
        New-Item -ItemType Directory -Path $runDir -Force | Out-Null
        # Copy JUnit XMLs
        if (Test-Path "$reportDir\*.xml") {
            Copy-Item "$reportDir\*.xml" "$runDir\" -Force
            $firstXml = Get-ChildItem "$runDir" -Filter "*.xml" | Select-Object -First 1
            if ($firstXml) { $junitCopiedPath = $firstXml.FullName }
        }
        # Copy VA log
        if (Test-Path $vaLog) {
            $vaLogCopiedPath = Join-Path $runDir "va-out.txt"
            Copy-Item $vaLog $vaLogCopiedPath -Force
        }
    } else {
        # Without RunId: point to the canonical paths
        $firstXml = Get-ChildItem "$projectBuild\reports" -Filter "*.xml" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($firstXml) { $junitCopiedPath = $firstXml.FullName }
        if (Test-Path $vaLog) { $vaLogCopiedPath = $vaLog }
    }

    # $lastStep already extracted inside retry loop (before error classification)

    # Build structured result object
    $result = [PSCustomObject]@{
        feature        = $Feature
        run_id         = $RunId
        started_at     = $startedAt
        finished_at    = $finishedAt
        duration_s     = $durationS
        exit_code      = $exitCode
        build_status   = if (Test-Path $buildStatus) { (Get-Content $buildStatus -Encoding UTF8).Trim() } else { "missing" }
        junit_xml      = $junitCopiedPath
        va_log         = $vaLogCopiedPath
        process_pid    = $proc.Id
        last_step      = $lastStep
        timeout_sec    = $TimeoutSec
        total_attempts = $currentAttempt
        retried        = ($currentAttempt -gt 1)
        error_category = $errorCategory
        attempts       = $allAttempts
    }

    # Resolve OutputJson target: explicit path OR conventional runs/<RunId>/result.json
    $outputJsonPath = $OutputJson
    if (-not $outputJsonPath -and $RunId) {
        $outputJsonPath = Join-Path $projectBuild "reports\runs\$RunId\result.json"
    }

    if ($outputJsonPath) {
        $outputJsonDir = Split-Path $outputJsonPath -Parent
        if ($outputJsonDir -and -not (Test-Path $outputJsonDir)) {
            New-Item -ItemType Directory -Path $outputJsonDir -Force | Out-Null
        }
        $result | ConvertTo-Json -Depth 4 | Out-File -FilePath $outputJsonPath -Encoding UTF8
        Write-Host "[OUTPUT] JSON result -> $outputJsonPath"
    }
}

# 11. Cleanup
if (-not $KeepRunning) {
    Get-Process -Name '1cv8c','1cv8' -ErrorAction SilentlyContinue | Stop-Process -Force
}

exit $exitCode
