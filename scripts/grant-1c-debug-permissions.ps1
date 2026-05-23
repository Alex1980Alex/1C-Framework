#requires -Version 5.1
#requires -RunAsAdministrator
<#
.SYNOPSIS
Grant Authenticated Users Stop/Start rights on "1C:Enterprise 8.3 Server Agent" service.

.DESCRIPTION
One-time setup для closing roadmap §11/Gap #1 — позволяет non-admin Claude Code
вызывать `Restart-Service "1C:Enterprise 8.3 Server Agent"` без UAC dialog'а.
После этого `mcp_debug_server.py` `force_recycle_rphost=True` (когда rac.exe
недоступен) сможет recycle ВСЕ rphost'ы через service-restart fallback path.

Workflow:
    1. Получить current SDDL через `sc sdshow`
    2. Inject ACE `(A;;LCSWRPWPCR;;;AU)` для группы Authenticated Users
       (LC=Service Start, SW=Service Stop, RP=Query Config, WP=Change Config,
        CR=User-defined Control)
    3. Применить через `sc sdset`
    4. Idempotent: если ACE для AU уже есть с нужными правами — skip

Requires elevation. Использовать ОДИН раз; effects persistent через перезагрузки
сервера и переустановку платформы 1С (SDDL хранится в SCM database).

.PARAMETER ServiceName
Имя сервиса 1С. По умолчанию "1C:Enterprise 8.3 Server Agent" (русское название
"Агент сервера 1С:Предприятия 8.3" тоже работает на ru-RU локалях).

.PARAMETER Revoke
Удалить ранее inject'нутый ACE (восстановить default permissions).

.EXAMPLE
.\grant-1c-debug-permissions.ps1
# Grant + verify

.EXAMPLE
.\grant-1c-debug-permissions.ps1 -Revoke
# Откатить изменение
#>
[CmdletBinding()]
param(
    [string]$ServiceName = "1C:Enterprise 8.3 Server Agent",
    [switch]$Revoke
)

$ErrorActionPreference = 'Stop'

# Marker ACE (Authenticated Users: Start + Stop + Read/Write Config + Custom Control)
$AceForAU = '(A;;LCSWRPWPCR;;;AU)'

Write-Host "=== 1C Service SDDL Permission Grant ===" -ForegroundColor Cyan
Write-Host "Service: $ServiceName"

# Verify service exists
try {
    $svc = Get-Service -Name $ServiceName -ErrorAction Stop
    Write-Host "[OK] Service found, status=$($svc.Status)" -ForegroundColor Green
} catch {
    Write-Error "Service '$ServiceName' not found. Try alternate localized name."
    exit 1
}

# Read current SDDL via sc.exe
$sdshowOutput = & sc.exe sdshow "$ServiceName" 2>&1 | Out-String
$current = ($sdshowOutput -split "`n" | Where-Object { $_.Trim().StartsWith('D:') } | Select-Object -First 1).Trim()
if (-not $current) {
    Write-Error "sc sdshow returned no SDDL string. Output: $sdshowOutput"
    exit 2
}
Write-Host "[OK] Current SDDL:"
Write-Host "     $current" -ForegroundColor Gray

if ($Revoke) {
    if ($current -notmatch [regex]::Escape($AceForAU)) {
        Write-Host "[--] AU ACE not present — nothing to revoke." -ForegroundColor Yellow
        exit 0
    }
    $newSddl = $current -replace [regex]::Escape($AceForAU), ''
    Write-Host "[..] Revoking AU ACE..."
} else {
    if ($current -match [regex]::Escape($AceForAU)) {
        Write-Host "[OK] AU ACE already present — no change needed." -ForegroundColor Green
        Write-Host ""
        Write-Host "Verify (run as non-admin user):"
        Write-Host "  Stop-Service '$ServiceName' -ErrorAction Stop" -ForegroundColor Cyan
        exit 0
    }
    # Insert AU ACE right after "D:" prefix (most permissive position не важна для DACL)
    $newSddl = $current -replace '^D:', "D:$AceForAU"
    Write-Host "[..] Granting Authenticated Users Service Start/Stop rights..."
}

Write-Host "     New SDDL:"
Write-Host "     $newSddl" -ForegroundColor Gray

# Apply via sc sdset
$sdsetOutput = & sc.exe sdset "$ServiceName" "$newSddl" 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Error "sc sdset failed (exit=$LASTEXITCODE): $sdsetOutput"
    exit 3
}

if ($Revoke) {
    Write-Host "[OK] AU ACE revoked. Default service permissions restored." -ForegroundColor Green
} else {
    Write-Host "[OK] AU ACE applied. Authenticated Users могут Start/Stop service без UAC." -ForegroundColor Green
    Write-Host ""
    Write-Host "Now non-admin can run:" -ForegroundColor Cyan
    Write-Host "  Stop-Service '$ServiceName'"
    Write-Host "  Start-Service '$ServiceName'"
    Write-Host ""
    Write-Host "Wrapper integration:" -ForegroundColor Cyan
    Write-Host "  Set env BSL_DEBUG_ALLOW_SERVICE_RESTART=true to enable in mcp_debug_server.py"
    Write-Host "  force_recycle_rphost_processes() chain: rac → service.restart → taskkill"
}

Write-Host ""
Write-Host "Roadmap ref: docs/roadmap/260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md §11.6 Fix #4" -ForegroundColor DarkGray
