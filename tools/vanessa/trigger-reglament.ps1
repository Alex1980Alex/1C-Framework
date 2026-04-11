# trigger-reglament.ps1
# Thin wrapper that invokes trigger-reglament.py through the project venv.
# Cyrillic payloads (BSL + JSON) are handled inside Python — PowerShell on
# Windows corrupts Cyrillic when marshalled via ConvertTo-Json / -c arguments.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File trigger-reglament.ps1
#
# Called from VA BDD feature files via:
#   И я запускаю команду операционной системы "powershell -ExecutionPolicy Bypass -File D:\va-test\trigger-reglament.ps1"

param(
    [string]$RpcUrl = "",
    [string]$Username = "",
    [string]$Password = "",
    [int]$TimeoutSec = 30
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$ErrorActionPreference = "Stop"

# Locate project root and Python executable
$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent (Split-Path -Parent $scriptDir)
$python      = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pyScript    = Join-Path $scriptDir "trigger-reglament.py"

if (-not (Test-Path $python)) {
    Write-Host "[ERROR] Python venv not found: $python"
    exit 2
}
if (-not (Test-Path $pyScript)) {
    Write-Host "[ERROR] Python helper not found: $pyScript"
    exit 2
}

# Pass overrides through environment (avoids Cyrillic-in-argv issues)
if ($RpcUrl)   { $env:ONEC_RPC_URL  = $RpcUrl }
if ($Username) { $env:ONEC_USERNAME = $Username }
if ($Password) { $env:ONEC_PASSWORD = $Password }

& $python $pyScript --timeout $TimeoutSec
$pyExit = $LASTEXITCODE

# Clean overrides
Remove-Item env:ONEC_RPC_URL, env:ONEC_USERNAME, env:ONEC_PASSWORD -ErrorAction SilentlyContinue

exit $pyExit
