#requires -Version 5.1
<#
.SYNOPSIS
Запускает Scenario B autonomous debug environment: dbgs.exe + 1cv8c.exe (/Debug /DebuggerURL).

.DESCRIPTION
Поднимает dbgs.exe (HTTP RDBG debug server) на :1550 (если ещё не запущен) и стартует
1С:Предприятие тонкий клиент с auto-attach к этому debug server. После этого MCP-server
"1c-debug" может выполнить debug_connect и стать единственным Debug UI с full access.

Конфигуратор остаётся открытым отдельно как редактор кода (без F5/Shift+F5).

.PARAMETER InfobaseAlias
Имя информационной базы в кластере 1С (например "ИБTransportManagementDevelop"). Используется
в строке подключения /S "localhost\<alias>".

.PARAMETER PlatformVersion
Версия платформы 1С. По умолчанию 8.3.27.1936.

.PARAMETER DebugPort
Порт debug server. По умолчанию 1550.

.PARAMETER UserName
Имя пользователя 1С (опционально, для авто-логина).

.PARAMETER Password
Пароль (опционально). Если -UserName указан, а -Password нет — будет запрос интерактивно.

.PARAMETER NoLaunchClient
Только запустить dbgs.exe, без 1С:Предприятие. Полезно когда клиент уже открыт или будет
запущен пользователем вручную.

.PARAMETER FileBase
Альтернатива /S — путь к файловой базе (для тестов на файловой инфобазе).

.EXAMPLE
.\start-onec-autonomous-debug.ps1 -InfobaseAlias "ИБTransportManagementDevelop"

.EXAMPLE
.\start-onec-autonomous-debug.ps1 -InfobaseAlias "TestDB" -UserName "Admin"

.EXAMPLE
.\start-onec-autonomous-debug.ps1 -NoLaunchClient
# поднять только dbgs.exe, клиент пользователь запустит вручную (например через ярлык)

.NOTES
После выполнения скрипта в Claude Code вызвать:
    mcp__1c-debug__debug_connect(infobase_alias="<alias>")
Должен вернуть result=registered, fully_registered=true → full Debug UI access.

См. cache/dbgs-rdbg-debug-server.md §10 (Scenario B).
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false, Position = 0)]
    [string]$InfobaseAlias = "ИБTransportManagementDevelop",

    [string]$PlatformVersion = "8.3.27.1936",

    [int]$DebugPort = 1550,

    [string]$UserName = "",

    [string]$Password = "",

    [switch]$NoLaunchClient,

    [string]$FileBase = ""
)

$ErrorActionPreference = 'Stop'

# Resolve 1C bin path
$BinPaths = @(
    "C:\Program Files (x86)\1cv8\$PlatformVersion\bin",
    "C:\Program Files\1cv8\$PlatformVersion\bin"
)
$BinPath = $BinPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $BinPath) {
    Write-Error "1C platform $PlatformVersion not found in standard locations: $($BinPaths -join '; ')"
    exit 1
}
Write-Host "[OK] 1C bin: $BinPath" -ForegroundColor Green

$DbgsExe   = Join-Path $BinPath 'dbgs.exe'
$ClientExe = Join-Path $BinPath '1cv8c.exe'
foreach ($exe in @($DbgsExe, $ClientExe)) {
    if (-not (Test-Path $exe)) {
        Write-Error "Missing executable: $exe"
        exit 1
    }
}

# Check if dbgs.exe is already listening
$portCheck = Test-NetConnection -ComputerName localhost -Port $DebugPort -InformationLevel Quiet -WarningAction SilentlyContinue
if ($portCheck) {
    Write-Host "[OK] dbgs.exe already listening on localhost:$DebugPort (skip start)" -ForegroundColor Green
} else {
    Write-Host "[..] Starting dbgs.exe on localhost:$DebugPort ..." -ForegroundColor Yellow
    $dbgsProcess = Start-Process -FilePath $DbgsExe `
        -ArgumentList @('-a', 'localhost', '-p', $DebugPort) `
        -WindowStyle Hidden `
        -PassThru
    Write-Host "[OK] dbgs.exe started (PID=$($dbgsProcess.Id))" -ForegroundColor Green

    # Wait until port is actually listening (max 5 seconds)
    $maxWait = 50
    $check = $false
    while ($maxWait-- -gt 0) {
        Start-Sleep -Milliseconds 100
        $check = Test-NetConnection -ComputerName localhost -Port $DebugPort -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($check) { break }
    }
    if (-not $check) {
        Write-Error "dbgs.exe started but port $DebugPort not listening within 5s. Check process state."
        exit 2
    }
    Write-Host "[OK] Port $DebugPort confirmed listening" -ForegroundColor Green
}

# Launch 1C:Enterprise client (optional)
if ($NoLaunchClient) {
    Write-Host "[--] Skipping 1С:Предприятие launch (-NoLaunchClient)" -ForegroundColor Gray
} else {
    $clientArgs = @('ENTERPRISE')
    if ($FileBase) {
        $clientArgs += @('/F', $FileBase)
    } else {
        $clientArgs += @('/S', "localhost\$InfobaseAlias")
    }
    $clientArgs += @('/Debug')
    $clientArgs += @('/DebuggerURL', "http://localhost:$DebugPort")
    if ($UserName) {
        $clientArgs += @('/N', $UserName)
        if ($Password) {
            $clientArgs += @('/P', $Password)
        }
    }
    Write-Host "[..] Starting 1cv8c.exe with /Debug /DebuggerURL=http://localhost:$DebugPort ..." -ForegroundColor Yellow
    $clientProcess = Start-Process -FilePath $ClientExe -ArgumentList $clientArgs -PassThru
    Write-Host "[OK] 1cv8c.exe started (PID=$($clientProcess.Id))" -ForegroundColor Green
}

# Final summary
Write-Host ""
Write-Host "=== Scenario B autonomous debug ready ===" -ForegroundColor Cyan
Write-Host "Debug server: http://localhost:$DebugPort"
Write-Host "Infobase    : $InfobaseAlias"
Write-Host ""
Write-Host "Next step (in Claude Code):" -ForegroundColor Cyan
Write-Host "  mcp__1c-debug__debug_connect(infobase_alias=`"$InfobaseAlias`")"
Write-Host ""
Write-Host "Expected response:"
Write-Host "  result: registered"
Write-Host "  fully_registered: true"
Write-Host ""
Write-Host "If response = 'ibInDebug' - Конфигуратор удерживает Debug UI."
Write-Host "Решение: в Конфигураторе нажать Shift+F5 (Stop Debugging), затем повторить debug_connect."
