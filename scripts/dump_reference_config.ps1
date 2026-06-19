<#
.SYNOPSIS
  Dump a 1C configuration to source files for read-only study (UT/ERP reference layer).
  Modules land as <Object>/Ext/ObjectModule.bsl|ManagerModule.bsl|RecordSetModule.bsl etc.
  Output dir external/1c-reference-src/ is gitignored (bodies not tracked; a UT dump is ~2 GB / 13k+ modules).

.EXAMPLE
  .\dump_reference_config.ps1 -Base trade -ServerRef "DESKTOP-TNU600C\Trade_11_5_27_52"
  .\dump_reference_config.ps1 -Base erp   -ServerRef "DESKTOP-TNU600C\Enterprise20_2_5_27_52"

.NOTES
  ASCII-only on purpose: PowerShell 5.1 reads a UTF-8-no-BOM .ps1 as the system codepage,
  which mangles any non-ASCII literal. Paths are derived from $PSScriptRoot (no hardcoded
  Cyrillic). The platform client MUST match the running server-agent version of the base
  (local cluster is x86 8.3.27.1936 -> default below). Read-only operation (DB not modified).
  Semantic index is a separate heavy step (see skill bsl-development) into its OWN collection.
#>
param(
    [Parameter(Mandatory = $true)][string]$Base,
    [Parameter(Mandatory = $true)][string]$ServerRef,
    [string]$User = "Admin",
    [string]$Password = "",
    [string]$Platform = "C:\Program Files (x86)\1cv8\8.3.27.1936\bin\1cv8.exe"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent
$root = Join-Path $repoRoot "external\1c-reference-src\$Base"
$log = Join-Path $repoRoot "tmp\dump_$Base.log"

if (-not (Test-Path $Platform)) { throw "Platform client not found: $Platform" }
New-Item -ItemType Directory -Force $root | Out-Null
New-Item -ItemType Directory -Force (Split-Path $log -Parent) | Out-Null

$argline = "DESIGNER /S `"$ServerRef`" /N $User /P `"$Password`" /DumpConfigToFiles `"$root`" /Out `"$log`" /DisableStartupDialogs /DisableStartupMessages"
Write-Host "Dumping $Base ($ServerRef) -> $root ..."
$p = Start-Process -FilePath $Platform -ArgumentList $argline -Wait -PassThru
Write-Host "exit code: $($p.ExitCode)"
if ($p.ExitCode -ne 0 -and (Test-Path $log)) { Get-Content $log -Encoding UTF8 | Select-Object -Last 8 }

$cnt = (Get-ChildItem $root -Recurse -Filter '*.bsl' -ErrorAction SilentlyContinue | Measure-Object).Count
$mb = "{0:N0}" -f ((Get-ChildItem $root -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "$Base done: $cnt .bsl modules, ~$mb MB. Read/Grep under $root"

# Auto-version: each base is its own git repo (gitignored from the main repo). Snapshot this dump.
# NOTE: DumpConfigToFiles re-exports in place and does NOT prune files of objects removed from the
# config; `git add -A` captures additions/modifications. For strict version diffs, clear $root
# (keeping .git) before a re-dump.
if (-not (Test-Path (Join-Path $root ".git"))) { git -C $root init -q; Write-Host "git init: $Base repo" }
git -C $root add -A
git -C $root -c core.quotepath=false commit -q -m "$Base config dump $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
if ($LASTEXITCODE -eq 0) { Write-Host "git: committed dump snapshot to $Base repo" } else { Write-Host "git: no changes since last dump" }
