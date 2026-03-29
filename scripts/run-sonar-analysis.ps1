$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$ProjectRoot = "D:\1С-Framework"
$BslSrc = "$ProjectRoot\src\projects\configuration\260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС\src"
$ScannerVersion = "6.2.1.4610"
$ScannerBin = "$ProjectRoot\tools\sonar-scanner-$ScannerVersion-windows-x64\bin\sonar-scanner.bat"

# 1. BSL Language Server -> JSON report
Write-Host "`n[1/2] BSL Language Server analysis..." -ForegroundColor Cyan

New-Item -ItemType Directory -Force -Path "$ProjectRoot\build\bsl-report" | Out-Null

java -jar "$ProjectRoot\tools\bsl-ls\bsl-language-server.jar" `
    --analyze `
    --srcDir "$BslSrc" `
    --reporter json `
    --outputDir "$ProjectRoot\build\bsl-report"

if ($LASTEXITCODE -ne 0) {
    Write-Host "BSL LS analysis failed!" -ForegroundColor Red
    exit 1
}

$reportFile = "$ProjectRoot\build\bsl-report\bsl-json.json"
if (Test-Path $reportFile) {
    $sizeMB = [math]::Round((Get-Item $reportFile).Length / 1MB, 1)
    Write-Host "Report generated: $reportFile ($sizeMB MB)" -ForegroundColor Green
} else {
    Write-Host "Warning: report file not found at $reportFile" -ForegroundColor Yellow
}

# 2. Sonar Scanner -> send to SonarQube
Write-Host "`n[2/2] Sonar Scanner..." -ForegroundColor Cyan

if (-not $env:SONAR_TOKEN) {
    Write-Host "SONAR_TOKEN not set. Skipping SonarQube upload." -ForegroundColor Yellow
    Write-Host "Set it: `$env:SONAR_TOKEN = 'your-token'" -ForegroundColor Yellow
    exit 0
}

if (-not (Test-Path $ScannerBin)) {
    Write-Host "sonar-scanner not found at $ScannerBin" -ForegroundColor Red
    Write-Host "Run scripts/setup-sonar.ps1 first" -ForegroundColor Yellow
    exit 1
}

& $ScannerBin `
    "-Dsonar.host.url=http://localhost:9000" `
    "-Dsonar.token=$env:SONAR_TOKEN" `
    "-Dsonar.projectBaseDir=$ProjectRoot"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Sonar Scanner failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`nDone! Dashboard: http://localhost:9000/dashboard?id=upravlenie-transportom-plk" -ForegroundColor Green
