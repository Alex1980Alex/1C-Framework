$ErrorActionPreference = "Stop"

[Console]::OutputEncoding = [Text.Encoding]::UTF8

$ProjectRoot = "D:\1С-Framework"
$SonarScannerVersion = "6.2.1.4610"
$BslPluginVersion = "0.15.2"

function Wait-SonarQubeReady {
    param (
        [int]$MaxAttempts = 30,
        [int]$DelaySeconds = 10
    )

    $Url = "http://localhost:9000/api/system/status"

    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $Response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 5
            if ($Response.status -eq "UP") {
                return $true
            }
            Write-Host "  Status: $($Response.status). Waiting... ($i/$MaxAttempts)"
        }
        catch {
            Write-Host "  SonarQube not responding. Waiting... ($i/$MaxAttempts)"
        }

        if ($i -lt $MaxAttempts) {
            Start-Sleep -Seconds $DelaySeconds
        }
    }

    return $false
}

# Step 1: Start SonarQube Docker container
Write-Host "`n=== Step 1: Starting SonarQube Docker container ===" -ForegroundColor Cyan

$ComposeFile = "$ProjectRoot\docker\docker-compose.sonarqube.yml"
docker compose -f "$ComposeFile" up -d

if ($LASTEXITCODE -ne 0) {
    throw "Failed to start SonarQube container"
}

Write-Host "SonarQube container started" -ForegroundColor Green

# Step 2: Wait for SonarQube to be ready
Write-Host "`n=== Step 2: Waiting for SonarQube to be ready ===" -ForegroundColor Cyan

if (-not (Wait-SonarQubeReady)) {
    throw "SonarQube failed to start within the expected time"
}

Write-Host "SonarQube is UP and ready!" -ForegroundColor Green

# Step 3: Download and extract sonar-scanner CLI
Write-Host "`n=== Step 3: Setting up sonar-scanner CLI ===" -ForegroundColor Cyan

$ToolsDir = "$ProjectRoot\tools"
$ScannerZipPath = "$ToolsDir\sonar-scanner.zip"
$ScannerDir = "$ToolsDir\sonar-scanner-$SonarScannerVersion-windows-x64"
$ScannerDownloadUrl = "https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-$SonarScannerVersion-windows-x64.zip"

if (-not (Test-Path $ScannerDir)) {
    New-Item -ItemType Directory -Force -Path $ToolsDir | Out-Null

    Write-Host "Downloading sonar-scanner CLI $SonarScannerVersion..."
    Invoke-WebRequest -Uri $ScannerDownloadUrl -OutFile $ScannerZipPath -UseBasicParsing

    Write-Host "Extracting sonar-scanner..."
    Expand-Archive -Path $ScannerZipPath -DestinationPath $ToolsDir -Force

    Remove-Item -Path $ScannerZipPath -Force

    Write-Host "Sonar-scanner CLI installed successfully!" -ForegroundColor Green
}
else {
    Write-Host "Sonar-scanner already exists at $ScannerDir - skipping" -ForegroundColor Green
}

# Step 4: Download and install BSL plugin
Write-Host "`n=== Step 4: Installing BSL plugin ===" -ForegroundColor Cyan

$BslPluginUrl = "https://github.com/1c-syntax/sonar-bsl-plugin-community/releases/download/v$BslPluginVersion/sonar-bsl-plugin-community-$BslPluginVersion.jar"
$BslPluginPath = "$ToolsDir\sonar-bsl-plugin-community-$BslPluginVersion.jar"

Write-Host "Downloading BSL plugin v$BslPluginVersion..."
Invoke-WebRequest -Uri $BslPluginUrl -OutFile $BslPluginPath -UseBasicParsing

Write-Host "Copying BSL plugin to SonarQube container..."
docker cp "$BslPluginPath" sonarqube-1c:/opt/sonarqube/extensions/plugins/

if ($LASTEXITCODE -ne 0) {
    throw "Failed to copy BSL plugin to container"
}

Write-Host "Restarting SonarQube container to load plugin..."
docker restart sonarqube-1c

if ($LASTEXITCODE -ne 0) {
    throw "Failed to restart SonarQube container"
}

Write-Host "BSL plugin installed and container restarted!" -ForegroundColor Green

# Step 5: Wait for SonarQube restart
Write-Host "`n=== Step 5: Waiting for SonarQube to restart ===" -ForegroundColor Cyan

if (-not (Wait-SonarQubeReady)) {
    throw "SonarQube failed to restart within the expected time"
}

Write-Host "SonarQube is UP after restart!" -ForegroundColor Green

# Final message
Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "  SonarQube for BSL is ready!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  URL: http://localhost:9000" -ForegroundColor White
Write-Host "  Login: admin" -ForegroundColor White
Write-Host "  Password: admin (change on first login)" -ForegroundColor White
Write-Host ""
Write-Host "  BSL Plugin: v$BslPluginVersion" -ForegroundColor White
Write-Host "  Sonar-scanner: v$SonarScannerVersion" -ForegroundColor White
Write-Host ""
Write-Host "  Next: run scripts/run-sonar-analysis.ps1" -ForegroundColor Yellow
