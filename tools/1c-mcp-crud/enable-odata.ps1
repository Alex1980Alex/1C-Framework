# Phase 3: Enable OData for TestDB
# Modifies default.vrd to enable standard OData interface
# Usage: powershell -ExecutionPolicy Bypass -File enable-odata.ps1

param(
    [string]$VrdPath = "C:\inetpub\wwwroot\TestDB\default.vrd",
    [switch]$Disable
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $VrdPath)) {
    Write-Host "[FAIL] VRD not found: $VrdPath" -ForegroundColor Red
    exit 1
}

$content = Get-Content $VrdPath -Raw -Encoding UTF8

if ($Disable) {
    $content = $content -replace 'standardOdata enable="true"', 'standardOdata enable="false"'
    Write-Host "[OK] OData DISABLED in $VrdPath" -ForegroundColor Yellow
}
else {
    $content = $content -replace 'standardOdata enable="false"', 'standardOdata enable="true"'
    Write-Host "[OK] OData ENABLED in $VrdPath" -ForegroundColor Green
    Write-Host "  URL: http://localhost/TestDB/odata/standard.odata/" -ForegroundColor Cyan
}

Set-Content -Path $VrdPath -Value $content -Encoding UTF8

# Restart IIS app pool if possible
$pool = Get-WebAppPool -Name "1CAppPool" -ErrorAction SilentlyContinue
if ($pool) {
    Restart-WebAppPool -Name "1CAppPool"
    Write-Host "[OK] AppPool restarted" -ForegroundColor Green
}
else {
    Write-Host "[INFO] Restart IIS manually: iisreset" -ForegroundColor Yellow
}
