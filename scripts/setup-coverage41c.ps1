$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = "D:\1С-Framework"
$Coverage41CVersion = "2.7.3"  # ZIP distribution (bin/lib), requires EDT runtime

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
$ZipPath = Join-Path $ToolsDir "coverage41c.zip"
$BinDir = Join-Path $ToolsDir "Coverage41C-$Coverage41CVersion"
$DownloadUrl = "https://github.com/1c-syntax/Coverage41C/releases/download/v$Coverage41CVersion/Coverage41C-$Coverage41CVersion.zip"

if (Test-Path "$BinDir\bin\Coverage41C.bat") {
    Write-Host "  Coverage41C already exists, skipping download" -ForegroundColor Yellow
} else {
    Write-Host "  Downloading from: $DownloadUrl"
    try {
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $ZipPath -UseBasicParsing
        Expand-Archive -Path $ZipPath -DestinationPath $ToolsDir -Force
        Remove-Item $ZipPath -Force
        Write-Host "  Extracted to: $BinDir" -ForegroundColor Green
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
$BatPath = Join-Path $BinDir "bin\Coverage41C.bat"
if (Test-Path $BatPath) {
    Write-Host "  Coverage41C binary found: $BatPath" -ForegroundColor Green
    Write-Host "  Note: v2.7.3 requires 1C:EDT runtime for debug core" -ForegroundColor Yellow
} else {
    Write-Host "  ERROR: Coverage41C.bat not found" -ForegroundColor Red
    throw "Coverage41C installation failed"
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
Write-Host "   tools\coverage41c\Coverage41C-$Coverage41CVersion\bin\Coverage41C.bat start --debugger `"localhost:1550`" --output `"build\reports\coverage.xml`" --format `"genericCoverage`" --projectDir `"src\projects\configuration`"" -ForegroundColor White
Write-Host ""
Write-Host "3. Run your tests (YAxUnit/BDD)" -ForegroundColor Yellow
Write-Host ""
Write-Host "4. Stop coverage and generate report:" -ForegroundColor Yellow
Write-Host "   tools\coverage41c\Coverage41C-$Coverage41CVersion\bin\Coverage41C.bat stop" -ForegroundColor White
Write-Host ""
Write-Host "Coverage report will be saved to: build\reports\coverage.xml" -ForegroundColor Cyan
