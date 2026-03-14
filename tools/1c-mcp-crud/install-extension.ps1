# Install MCP_Server.cfe extension into TestDB
# Uses ibcmd (no Configurator needed!) or DESIGNER batch mode as fallback
# Run as Administrator recommended
# Usage: powershell -ExecutionPolicy Bypass -File install-extension.ps1

param(
    [string]$PlatformBin = "C:\Program Files\1cv8\8.3.27.1859\bin",
    [string]$DbServer = "KOMPUTER",
    [string]$DbRef = "TestDB",
    [string]$User = "a.terletskiy@sodru.com",
    [string]$Pass = "Alex80Alex",
    [string]$ExtensionFile = "D:\1C-Enterprise_Framework\src\external\1c_mcp\build\MCP_Сервер.cfe",
    [string]$ExtensionName = "MCP_Сервер",
    [switch]$UseDesigner
)

$ErrorActionPreference = "Stop"

Write-Host "=" * 60
Write-Host "  Install Extension: $ExtensionName" -ForegroundColor Cyan
Write-Host "=" * 60

# Verify extension file
if (-not (Test-Path $ExtensionFile)) {
    Write-Host "[FAIL] Extension file not found: $ExtensionFile" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Extension file: $ExtensionFile" -ForegroundColor Green

$ibcmd = "$PlatformBin\ibcmd.exe"
$designer = "$PlatformBin\1cv8.exe"
$connStr = "/S `"$DbServer\$DbRef`""

if (-not $UseDesigner -and (Test-Path $ibcmd)) {
    # Method 1: ibcmd (preferred, no GUI needed)
    Write-Host ""
    Write-Host "[1] Using ibcmd to install extension..." -ForegroundColor Cyan

    # ibcmd connection string for server base
    $ibConnStr = "--dbms=MSSQLServer --db-server=$DbServer --db-name=testdb1c --db-user=sa --db-pwd=1980"

    Write-Host "  Applying extension..."
    $proc = Start-Process -FilePath $ibcmd -ArgumentList @(
        "infobase", "config", "extension", "apply",
        "--file=`"$ExtensionFile`"",
        "--name=`"$ExtensionName`"",
        "--safe-mode=no",
        "--unsafe-action-protection=no",
        $ibConnStr
    ) -NoNewWindow -Wait -PassThru -RedirectStandardOutput "$env:TEMP\ibcmd_out.txt" -RedirectStandardError "$env:TEMP\ibcmd_err.txt"

    $stdout = Get-Content "$env:TEMP\ibcmd_out.txt" -Raw -ErrorAction SilentlyContinue
    $stderr = Get-Content "$env:TEMP\ibcmd_err.txt" -Raw -ErrorAction SilentlyContinue

    if ($stdout) { Write-Host "  stdout: $stdout" -ForegroundColor Gray }
    if ($stderr) { Write-Host "  stderr: $stderr" -ForegroundColor Gray }

    if ($proc.ExitCode -eq 0) {
        Write-Host "[OK] Extension installed via ibcmd" -ForegroundColor Green
    }
    else {
        Write-Host "[WARN] ibcmd exit code: $($proc.ExitCode)" -ForegroundColor Yellow
        Write-Host "  Trying DESIGNER batch mode as fallback..." -ForegroundColor Yellow
        $UseDesigner = $true
    }
}

if ($UseDesigner -or -not (Test-Path $ibcmd)) {
    # Method 2: DESIGNER batch mode
    Write-Host ""
    Write-Host "[2] Using DESIGNER batch mode..." -ForegroundColor Cyan

    $logFile = "$env:TEMP\1c_install_ext.log"

    # Step 1: Load extension config
    Write-Host "  Loading extension from file..."
    $args1 = @(
        "DESIGNER",
        "/S", "`"$DbServer\$DbRef`"",
        "/N", "`"$User`"",
        "/P", "`"$Pass`"",
        "/LoadCfg", "`"$ExtensionFile`"",
        "/Extension", "`"$ExtensionName`"",
        "/Out", "`"$logFile`"",
        "/DisableStartupMessages",
        "/DisableStartupDialogs"
    )

    $proc1 = Start-Process -FilePath $designer -ArgumentList ($args1 -join " ") -NoNewWindow -Wait -PassThru
    $log1 = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
    if ($log1) { Write-Host "  Log: $log1" -ForegroundColor Gray }

    if ($proc1.ExitCode -ne 0) {
        Write-Host "[FAIL] LoadCfg failed (exit: $($proc1.ExitCode))" -ForegroundColor Red
        Write-Host "  Check log: $logFile" -ForegroundColor Yellow
        exit 1
    }

    # Step 2: Update database
    Write-Host "  Updating database configuration..."
    $args2 = @(
        "DESIGNER",
        "/S", "`"$DbServer\$DbRef`"",
        "/N", "`"$User`"",
        "/P", "`"$Pass`"",
        "/UpdateDBCfg",
        "/Extension", "`"$ExtensionName`"",
        "/Out", "`"$logFile`"",
        "/DisableStartupMessages",
        "/DisableStartupDialogs"
    )

    $proc2 = Start-Process -FilePath $designer -ArgumentList ($args2 -join " ") -NoNewWindow -Wait -PassThru
    $log2 = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
    if ($log2) { Write-Host "  Log: $log2" -ForegroundColor Gray }

    if ($proc2.ExitCode -eq 0) {
        Write-Host "[OK] Extension installed via DESIGNER" -ForegroundColor Green
    }
    else {
        Write-Host "[FAIL] UpdateDBCfg failed (exit: $($proc2.ExitCode))" -ForegroundColor Red
        Write-Host "  Check log: $logFile" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""
Write-Host "=" * 60
Write-Host "  Extension $ExtensionName installed!" -ForegroundColor Green
Write-Host "=" * 60
Write-Host ""
Write-Host "Next: run setup-phase3-iis.ps1 to configure IIS" -ForegroundColor Yellow
