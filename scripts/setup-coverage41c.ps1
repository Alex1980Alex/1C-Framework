$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = "D:\1С-Framework"
$Coverage41CVersion = "2.4.3"

Write-Host "=== Coverage41C Setup Script ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Create directory
Write-Host "[Step 1] Creating tools directory..." -ForegroundColor Cyan
$ToolsDir = Join-Path $ProjectRoot "tools\coverage41c"
if (-not (Test-Path $ToolsDir)) {
    New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null
    Write-Host "  Created: $ToolsDir" -ForegroundColor Green
} else {
    Write-Host "  Directory exists: $ToolsDir" -ForegroundColor Green
}

# Step 2: Download Coverage41C JAR
Write-Host ""
Write-Host "[Step 2] Downloading Coverage41C v$Coverage41CVersion..." -ForegroundColor Cyan
$JarPath = Join-Path $ToolsDir "coverage41c.jar"
$DownloadUrl = "https://github.com/1c-syntax/Coverage41C/releases/download/v$Coverage41CVersion/Coverage41C-$Coverage41CVersion.jar"

if (Test-Path $JarPath) {
    Write-Host "  JAR already exists, skipping download: $JarPath" -ForegroundColor Yellow
} else {
    Write-Host "  Downloading from: $DownloadUrl"
    try {
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $JarPath -UseBasicParsing
        Write-Host "  Downloaded successfully: $JarPath" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to download Coverage41C: $_" -ForegroundColor Red
        throw "Download failed"
    }
}

# Step 3: Verify Java is available
Write-Host ""
Write-Host "[Step 3] Verifying Java installation..." -ForegroundColor Cyan
try {
    $JavaVersion = & java -version 2>&1 | Select-Object -First 1
    Write-Host "  Java found: $JavaVersion" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "  ERROR: Java is not installed or not in PATH!" -ForegroundColor Red
    Write-Host "  Please install Java JDK/JRE 8 or higher." -ForegroundColor Red
    throw "Java not found"
}

# Step 4: Test Coverage41C works
Write-Host ""
Write-Host "[Step 4] Testing Coverage41C..." -ForegroundColor Cyan
try {
    $HelpOutput = & java -jar $JarPath --help 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Coverage41C is working correctly!" -ForegroundColor Green
    } else {
        Write-Host "  Warning: Coverage41C returned non-zero exit code" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ERROR: Failed to run Coverage41C: $_" -ForegroundColor Red
    throw "Coverage41C test failed"
}

# Print usage instructions
Write-Host ""
Write-Host "=== Coverage41C Setup Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Usage Instructions:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Start 1C debug server:" -ForegroundColor Yellow
Write-Host '   & "C:\Program Files\1cv8\8.3.27.1859\bin\dbgs.exe" --addr=localhost --port=1550' -ForegroundColor White
Write-Host ""
Write-Host "2. Start coverage collection:" -ForegroundColor Yellow
Write-Host '   java -jar tools\coverage41c\coverage41c.jar start --debugger "localhost:1550" --output "build\reports\coverage.xml" --format "genericCoverage" --projectDir "src\projects\configuration"' -ForegroundColor White
Write-Host ""
Write-Host "3. Run your tests (YAxUnit/BDD)" -ForegroundColor Yellow
Write-Host ""
Write-Host "4. Stop coverage and generate report:" -ForegroundColor Yellow
Write-Host '   java -jar tools\coverage41c\coverage41c.jar stop' -ForegroundColor White
Write-Host ""
Write-Host "Coverage report will be saved to: build\reports\coverage.xml" -ForegroundColor Cyan
