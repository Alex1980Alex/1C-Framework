# Phase 3: IIS + 1C HTTP Service Setup
# Run as Administrator!
# Usage: powershell -ExecutionPolicy Bypass -File setup-phase3-iis.ps1

param(
    [string]$PlatformPath = "C:\Program Files\1cv8\8.3.27.1859",
    [string]$PublishPath = "C:\inetpub\wwwroot\TestDB",
    [string]$DbServer = "KOMPUTER",
    [string]$DbRef = "TestDB",
    [string]$SiteName = "Default Web Site",
    [string]$AppPoolName = "1CAppPool",
    [switch]$SkipIISInstall,
    [switch]$EnableOData
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Step, [string]$Message)
    Write-Host "`n[$Step] $Message" -ForegroundColor Cyan
}

function Write-Ok {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "  [WARN] $Message" -ForegroundColor Yellow
}

function Write-Fail {
    param([string]$Message)
    Write-Host "  [FAIL] $Message" -ForegroundColor Red
}

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Fail "This script requires Administrator privileges!"
    Write-Host "Right-click PowerShell > Run as administrator" -ForegroundColor Yellow
    exit 1
}

Write-Host "=" * 70
Write-Host "  Phase 3: IIS + 1C MCP HTTP Service Setup" -ForegroundColor White
Write-Host "=" * 70

# Step 1: Install IIS
if (-not $SkipIISInstall) {
    Write-Step "1/6" "Installing IIS with required features..."

    $features = @(
        "IIS-WebServerRole",
        "IIS-WebServer",
        "IIS-CommonHttpFeatures",
        "IIS-DefaultDocument",
        "IIS-StaticContent",
        "IIS-ISAPIExtensions",
        "IIS-ISAPIFilter",
        "IIS-BasicAuthentication",
        "IIS-WindowsAuthentication",
        "IIS-ManagementConsole",
        "IIS-RequestFiltering"
    )

    foreach ($feature in $features) {
        $state = Get-WindowsOptionalFeature -Online -FeatureName $feature -ErrorAction SilentlyContinue
        if ($state -and $state.State -eq "Enabled") {
            Write-Ok "$feature already enabled"
        }
        else {
            Write-Host "  Installing $feature..."
            Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart -ErrorAction SilentlyContinue | Out-Null
            Write-Ok "$feature installed"
        }
    }

    # Start IIS
    Start-Service W3SVC -ErrorAction SilentlyContinue
    Write-Ok "IIS service started"
}
else {
    Write-Step "1/6" "Skipping IIS install (--SkipIISInstall)"
}

# Step 2: Configure Application Pool for 1C
Write-Step "2/6" "Configuring IIS Application Pool..."

Import-Module WebAdministration -ErrorAction SilentlyContinue

if (-not (Test-Path "IIS:\AppPools\$AppPoolName")) {
    New-WebAppPool -Name $AppPoolName | Out-Null
    Write-Ok "Created AppPool: $AppPoolName"
}
else {
    Write-Ok "AppPool $AppPoolName already exists"
}

# Configure pool: 32-bit disabled (1C is 64-bit), pipeline=Integrated
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "enable32BitAppOnWin64" -Value $false
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "managedRuntimeVersion" -Value ""
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "managedPipelineMode" -Value 1  # Classic
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "processModel.identityType" -Value 0  # LocalSystem
Write-Ok "AppPool configured (Classic pipeline, LocalSystem identity)"

# Step 3: Create publication directory and copy ISAPI
Write-Step "3/6" "Setting up publication directory..."

if (-not (Test-Path $PublishPath)) {
    New-Item -ItemType Directory -Path $PublishPath -Force | Out-Null
    Write-Ok "Created $PublishPath"
}

# Copy wsisapi.dll
$isapi = "$PlatformPath\bin\wsisapi.dll"
if (Test-Path $isapi) {
    Copy-Item $isapi "$PublishPath\wsisapi.dll" -Force
    Write-Ok "Copied wsisapi.dll"
}
else {
    Write-Fail "wsisapi.dll not found at $isapi"
    exit 1
}

# Step 4: Configure default.vrd
Write-Step "4/6" "Configuring default.vrd..."

$vrdContent = @"
<?xml version="1.0" encoding="UTF-8"?>
<point xmlns="http://v8.1c.ru/8.2/virtual-resource-system"
		xmlns:xs="http://www.w3.org/2001/XMLSchema"
		xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
		base="/TestDB"
		ib="Srvr=$DbServer;Ref=$DbRef;">
	<ws pointEnableCommon="true"/>
	<standardOdata enable="$(if ($EnableOData) { 'true' } else { 'false' })"
			reuseSessions="autouse"
			sessionMaxAge="20"
			poolSize="10"
			poolTimeout="5"/>
	<analytics enable="true"/>
	<httpServices publishByDefault="false">
		<service name="mcp_APIBackend"
				rootUrl="mcp"
				enable="true"
				reuseSessions="autouse"
				sessionMaxAge="20"
				poolSize="10"
				poolTimeout="5"/>
	</httpServices>
</point>
"@

Set-Content -Path "$PublishPath\default.vrd" -Value $vrdContent -Encoding UTF8
Write-Ok "default.vrd written"

# Step 5: Register in IIS
Write-Step "5/6" "Registering TestDB in IIS..."

# Remove existing app if any
if (Get-WebApplication -Site $SiteName -Name "TestDB" -ErrorAction SilentlyContinue) {
    Remove-WebApplication -Site $SiteName -Name "TestDB"
    Write-Warn "Removed existing TestDB application"
}

# Create IIS application
New-WebApplication -Site $SiteName -Name "TestDB" -PhysicalPath $PublishPath -ApplicationPool $AppPoolName | Out-Null
Write-Ok "Created IIS application /TestDB"

# Add ISAPI handler mapping
$handlerName = "1C-ISAPI"
$existingHandler = Get-WebHandler -Name $handlerName -PSPath "IIS:\Sites\$SiteName\TestDB" -ErrorAction SilentlyContinue
if (-not $existingHandler) {
    Add-WebConfigurationProperty -PSPath "IIS:\Sites\$SiteName\TestDB" `
        -Filter "system.webServer/handlers" `
        -Name "." `
        -Value @{
            name = $handlerName
            path = "*"
            verb = "*"
            modules = "IsapiModule"
            scriptProcessor = "$PublishPath\wsisapi.dll"
            resourceType = "Unspecified"
            requireAccess = "Execute"
        }
    Write-Ok "Added ISAPI handler mapping"
}
else {
    Write-Ok "ISAPI handler already exists"
}

# Allow ISAPI extension
$isapiFull = "$PublishPath\wsisapi.dll"
$restrictions = Get-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Filter "system.webServer/security/isapiCgiRestriction" -Name "collection" `
    -ErrorAction SilentlyContinue

$found = $restrictions | Where-Object { $_.path -eq $isapiFull }
if (-not $found) {
    Add-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" `
        -Filter "system.webServer/security/isapiCgiRestriction" `
        -Name "." `
        -Value @{
            path = $isapiFull
            allowed = $true
            description = "1C Enterprise ISAPI"
        }
    Write-Ok "ISAPI restriction added (allowed)"
}
else {
    Write-Ok "ISAPI restriction already configured"
}

# Enable Windows Auth on TestDB app
Set-WebConfigurationProperty -PSPath "IIS:\Sites\$SiteName\TestDB" `
    -Filter "system.webServer/security/authentication/anonymousAuthentication" `
    -Name "enabled" -Value $false -ErrorAction SilentlyContinue
Set-WebConfigurationProperty -PSPath "IIS:\Sites\$SiteName\TestDB" `
    -Filter "system.webServer/security/authentication/basicAuthentication" `
    -Name "enabled" -Value $true -ErrorAction SilentlyContinue
Write-Ok "Authentication configured (Basic=on, Anonymous=off)"

# Restart AppPool
Restart-WebAppPool -Name $AppPoolName -ErrorAction SilentlyContinue
Write-Ok "AppPool restarted"

# Step 6: Test
Write-Step "6/6" "Testing HTTP service..."

Start-Sleep -Seconds 3

$testUrl = "http://localhost/TestDB/hs/mcp/health"
Write-Host "  Testing: $testUrl"

try {
    $cred = [System.Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes("a.terletskiy@sodru.com:Alex80Alex"))
    $headers = @{ "Authorization" = "Basic $cred" }
    $response = Invoke-WebRequest -Uri $testUrl -Headers $headers -UseBasicParsing -TimeoutSec 30
    $body = $response.Content
    Write-Ok "HTTP $($response.StatusCode): $body"

    if ($body -match '"status"\s*:\s*"ok"') {
        Write-Host "`n" + "=" * 70 -ForegroundColor Green
        Write-Host "  Phase 3 HTTP Service: WORKING!" -ForegroundColor Green
        Write-Host "=" * 70 -ForegroundColor Green
    }
}
catch {
    $err = $_.Exception.Message
    if ($err -match "401") {
        Write-Warn "HTTP 401 - extension may not be installed yet"
        Write-Host "  Install MCP_Server.cfe extension first (see Step 3.5)" -ForegroundColor Yellow
    }
    elseif ($err -match "404") {
        Write-Warn "HTTP 404 - HTTP service not found"
        Write-Host "  Extension mcp_APIBackend may not be published" -ForegroundColor Yellow
    }
    elseif ($err -match "503") {
        Write-Warn "HTTP 503 - 1C server may be starting up"
    }
    else {
        Write-Fail "Error: $err"
    }
}

# OData test
if ($EnableOData) {
    Write-Step "ODATA" "Testing OData endpoint..."
    $odataUrl = "http://localhost/TestDB/odata/standard.odata/"
    try {
        $response = Invoke-WebRequest -Uri $odataUrl -Headers $headers -UseBasicParsing -TimeoutSec 10
        Write-Ok "OData available: HTTP $($response.StatusCode)"
    }
    catch {
        Write-Warn "OData not available yet: $($_.Exception.Message)"
    }
}

Write-Host "`n--- Summary ---" -ForegroundColor White
Write-Host "Publication: $PublishPath"
Write-Host "VRD:         $PublishPath\default.vrd"
Write-Host "Health URL:  http://localhost/TestDB/hs/mcp/health"
Write-Host "MCP URL:     http://localhost/TestDB/hs/mcp/"
if ($EnableOData) {
    Write-Host "OData URL:   http://localhost/TestDB/odata/standard.odata/"
}
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Install MCP_Server.cfe extension in Configurator (if not done)"
Write-Host "  2. Test: curl -u user:pass http://localhost/TestDB/hs/mcp/health"
Write-Host "  3. Start Python proxy or use directly via .mcp.json"
