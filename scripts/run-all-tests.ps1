<#
.SYNOPSIS
    Comprehensive test orchestrator for 1C:Enterprise CI pipeline
.DESCRIPTION
    Runs BSL analysis, YAxUnit tests, BDD tests, and generates Allure reports
.PARAMETER SkipBSL
    Skip BSL Language Server analysis
.PARAMETER SkipYAxUnit
    Skip YAxUnit tests
.PARAMETER SkipBDD
    Skip BDD tests
.PARAMETER SkipCoverage
    Skip coverage collection
.PARAMETER SkipAllure
    Skip Allure report generation
#>

param(
    [switch]$SkipBSL,
    [switch]$SkipYAxUnit,
    [switch]$SkipBDD,
    [switch]$SkipCoverage,
    [switch]$SkipAllure
)

$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = "D:\1С-Framework"
$OnecPath = "C:\Program Files\1cv8\8.3.27.1859\bin"
$OscriptPath = "C:\Tools\OneScript\bin\oscript.exe"
$BSLSourcePath = "$ProjectRoot\src\projects\configuration\260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС\src"

$Results = @{}
$GlobalStopwatch = [System.Diagnostics.Stopwatch]::StartNew()

function Write-StepHeader {
    param([string]$StepName)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $StepName" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Result {
    param([string]$StepName, [string]$Status, [string]$Duration = "")
    $d = if ($Duration) { " ($Duration)" } else { "" }
    switch ($Status) {
        "PASS" { Write-Host "[$Status] $StepName$d" -ForegroundColor Green }
        "FAIL" { Write-Host "[$Status] $StepName$d" -ForegroundColor Red }
        "SKIP" { Write-Host "[$Status] $StepName$d" -ForegroundColor Yellow }
    }
}

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action, [bool]$Skip = $false)

    $sw = [System.Diagnostics.Stopwatch]::StartNew()

    if ($Skip) {
        $Results[$Name] = "SKIP"
        Write-Result -StepName $Name -Status "SKIP"
        return
    }

    try {
        & $Action
        if ($LASTEXITCODE -eq 0 -or $null -eq $LASTEXITCODE) {
            $Results[$Name] = "PASS"
            $sw.Stop()
            Write-Result -StepName $Name -Status "PASS" -Duration $sw.Elapsed.ToString("mm\:ss")
        } else {
            $Results[$Name] = "FAIL"
            $sw.Stop()
            Write-Result -StepName $Name -Status "FAIL" -Duration $sw.Elapsed.ToString("mm\:ss")
        }
    } catch {
        Write-Host "  Exception: $($_.Exception.Message)" -ForegroundColor Red
        $Results[$Name] = "FAIL"
        $sw.Stop()
        Write-Result -StepName $Name -Status "FAIL" -Duration $sw.Elapsed.ToString("mm\:ss")
    }
}

Set-Location $ProjectRoot

Write-Host @"

==============================================
  1C:Enterprise CI Test Orchestrator
==============================================
Project Root: $ProjectRoot
1C Path:      $OnecPath
OneScript:    $OscriptPath
Skip BSL:     $SkipBSL
Skip YAxUnit: $SkipYAxUnit
Skip BDD:     $SkipBDD
Skip Coverage:$SkipCoverage
Skip Allure:  $SkipAllure
"@ -ForegroundColor White

# Step 1: BSL Language Server Analysis
Write-StepHeader "Step 1: BSL Language Server Analysis"
Invoke-Step -Name "BSL Analysis" -Skip:$SkipBSL -Action {
    $bslJar = Join-Path $ProjectRoot "tools\bsl-ls\bsl-language-server.jar"
    $outputDir = Join-Path $ProjectRoot "build\bsl-report"

    if (-not (Test-Path $bslJar)) {
        throw "BSL LS jar not found: $bslJar"
    }

    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

    java -jar $bslJar --analyze --srcDir "$BSLSourcePath" --reporter json --outputDir "$outputDir"

    # BSL LS returns non-zero when issues found, but analysis itself succeeded
    $global:LASTEXITCODE = 0
}

# Step 2: YAxUnit Tests
Write-StepHeader "Step 2: YAxUnit Tests"
Invoke-Step -Name "YAxUnit" -Skip:$SkipYAxUnit -Action {
    if (-not (Test-Path $OscriptPath)) {
        throw "OneScript not found: $OscriptPath"
    }

    $env:MSYS_NO_PATHCONV = "1"

    & $OscriptPath `
        "C:\Tools\OneScript\lib\vanessa-runner\vanessa-runner.os" `
        run `
        --ibconnection "/SKOMPUTER\testdb1c" `
        --command "RunUnitTests" `
        --execute "$ProjectRoot\tools\vanessa\YAxUnit-25.12.cfe" `
        --settings "$ProjectRoot\tools\yaxunit.json"
}

# Step 3: BDD Tests
Write-StepHeader "Step 3: BDD Tests (Vanessa Automation)"
Invoke-Step -Name "BDD Tests" -Skip:$SkipBDD -Action {
    $bddScript = Join-Path $ProjectRoot "tools\vanessa\run-bdd.ps1"

    if (-not (Test-Path $bddScript)) {
        throw "BDD script not found: $bddScript"
    }

    powershell -NoProfile -ExecutionPolicy Bypass -File $bddScript
}

# Step 4: Coverage (optional)
Write-StepHeader "Step 4: Coverage Collection"
if (-not $SkipCoverage) {
    $coverageJar = Join-Path $ProjectRoot "tools\coverage41c\coverage41c.jar"
    if (Test-Path $coverageJar) {
        Write-Host "  Coverage41C found but requires manual dbgs setup" -ForegroundColor Yellow
        Write-Host "  Run: scripts/setup-coverage41c.ps1 for instructions" -ForegroundColor Yellow
    } else {
        Write-Host "  Coverage41C not installed. Run: scripts/setup-coverage41c.ps1" -ForegroundColor Yellow
    }
    $Results["Coverage"] = "SKIP"
    Write-Result -StepName "Coverage" -Status "SKIP"
} else {
    $Results["Coverage"] = "SKIP"
    Write-Result -StepName "Coverage" -Status "SKIP"
}

# Step 5: Allure Report
Write-StepHeader "Step 5: Allure Report Generation"
Invoke-Step -Name "Allure Report" -Skip:$SkipAllure -Action {
    $allureResults = Join-Path $ProjectRoot "build\allure-results"
    $allureReport = Join-Path $ProjectRoot "build\allure-report"

    if (-not (Get-Command "allure" -ErrorAction SilentlyContinue)) {
        throw "Allure not found in PATH"
    }

    New-Item -ItemType Directory -Path $allureResults -Force | Out-Null
    allure generate $allureResults -o $allureReport --clean
}

# Final Summary
$GlobalStopwatch.Stop()
$TotalTime = $GlobalStopwatch.Elapsed.ToString("hh\:mm\:ss")

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "           TEST RESULTS SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$passCount = 0; $failCount = 0; $skipCount = 0

foreach ($key in @("BSL Analysis", "YAxUnit", "BDD Tests", "Coverage", "Allure Report")) {
    $status = $Results[$key]
    if ($status -eq "PASS") { $passCount++ }
    elseif ($status -eq "FAIL") { $failCount++ }
    else { $skipCount++ }

    $color = switch ($status) { "PASS" { "Green" } "FAIL" { "Red" } default { "Yellow" } }
    Write-Host "  $($key.PadRight(20)) : " -NoNewline
    Write-Host $status -ForegroundColor $color
}

Write-Host "`n----------------------------------------" -ForegroundColor Gray
Write-Host "  Passed : $passCount" -ForegroundColor Green
Write-Host "  Failed : $failCount" -ForegroundColor Red
Write-Host "  Skipped: $skipCount" -ForegroundColor Yellow
Write-Host "  Total  : $TotalTime" -ForegroundColor White
Write-Host "========================================`n" -ForegroundColor Cyan

$exitCode = if ($failCount -gt 0) { 1 } else { 0 }
exit $exitCode
