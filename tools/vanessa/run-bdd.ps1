# VA BDD Test Runner for 1С-Framework
# Features sync from project -> D:\va-test, VA runs there, results copy back
# Usage: powershell -ExecutionPolicy Bypass -File tools\vanessa\run-bdd.ps1 [-Feature "smoke_testclient.feature"]
param(
    [string]$Feature = "",
    [int]$TimeoutSec = 120,
    [switch]$KeepRunning
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

$projectDir = "D:\va-test"
$featuresSource = (Get-Item "D:\1*-Framework" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '1' }).FullName + "\features"
$featuresDest = "$projectDir\features"
$exe = "C:\Program Files\1Cv8\8.3.27.1859\bin\1cv8c.exe"
$vaEpf = "$projectDir\va.epf"
$vaParams = "$projectDir\VAParams.json"
$buildStatus = "$projectDir\BuildStatus.log"
$vaLog = "$projectDir\va-out.txt"
$reportDir = "$projectDir\build\reports"

# 1. Kill old 1C processes
Get-Process -Name '1cv8c','1cv8' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 2. Sync features from project to va-test
Write-Host "[SYNC] $featuresSource -> $featuresDest"
if (Test-Path $featuresSource) {
    Get-ChildItem "$featuresSource\*.feature" | ForEach-Object {
        Copy-Item $_.FullName "$featuresDest\$($_.Name)" -Force
        Write-Host "  copied: $($_.Name)"
    }
}

# 3. If specific feature requested, disable others
if ($Feature) {
    Get-ChildItem "$featuresDest\*.feature" | Where-Object { $_.Name -ne $Feature } | ForEach-Object {
        Rename-Item $_.FullName "$($_.FullName).off"
    }
    Write-Host "[RUN] Only: $Feature"
} else {
    # Re-enable any .off files
    Get-ChildItem "$featuresDest\*.off" | ForEach-Object {
        Rename-Item $_.FullName ($_.FullName -replace '\.off$','')
    }
    Write-Host "[RUN] All features in $featuresDest"
}

# 4. Clean old results
Remove-Item $buildStatus -ErrorAction SilentlyContinue
Remove-Item $vaLog -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

# 5. Launch VA
$cParam = "StartFeaturePlayer;DisableFirstRunHelper;VAParams=$vaParams"
$proc = Start-Process -FilePath $exe -ArgumentList @(
    'ENTERPRISE',
    '/S"KOMPUTER\TestDB"',
    '/N"a.terletskiy@sodru.com"',
    '/P"Alex80Alex"',
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

# 8. Copy results back to project
$projectBuild = (Get-Item "D:\1*-Framework" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '1' }).FullName + "\build"
if (Test-Path "$reportDir\*.xml") {
    New-Item -ItemType Directory -Path "$projectBuild\reports" -Force | Out-Null
    Copy-Item "$reportDir\*" "$projectBuild\reports\" -Force
    Write-Host "[SYNC] JUnit reports -> $projectBuild\reports\"
}

# 9. Re-enable disabled features
Get-ChildItem "$featuresDest\*.off" | ForEach-Object {
    Rename-Item $_.FullName ($_.FullName -replace '\.off$','')
}

# 10. Cleanup
if (-not $KeepRunning) {
    Get-Process -Name '1cv8c','1cv8' -ErrorAction SilentlyContinue | Stop-Process -Force
}

exit $exitCode
