<#
.SYNOPSIS
    Quality-preserving fast reindex BSL → bsl_code_v4_late.

.DESCRIPTION
    Wrapper around scripts/reindex_bsl_qwen3.py with optimized flags that
    DON'T degrade retrieval quality (std-pool + context enrichment).
    Late Chunking SUPERSEDED 2026-05-20 (Phase 5 alias swap) — production
    path = standard pooling + sparse BM25 hybrid; see chapter 31.3/31.6.

    Tier 1 (always-on, no extra deps):
      --buffer-size 1024  — fewer Qdrant flushes (5-10% throughput gain)

    Tier 2 (if flash-attn installed):
      --enable-fa2        — Flash Attention 2 (1.5-2x on long sequences)
      --batch-size 100    — uses VRAM saved by FA2 input flattening

    Tier 3 (fallback if no FA2):
      --batch-size 50     — preserves working VRAM headroom on RTX 3090

    Quality-preserving — does NOT use:
      --no-context        (would skip context enrichment, drops recall)
      --pooling-mode late-chunking  (SUPERSEDED 2026-05-20; historical
                          experiment, NOT production — chapter 31.3/31.6)

.PARAMETER Project
    Project name (e.g. "ИБTransportManagementDevelop") OR full path.

.PARAMETER Limit
    Optional: limit to N first files (for smoke testing).

.EXAMPLE
    .\scripts\reindex_bsl_fast.ps1 -Project "ИБTransportManagementDevelop"

.EXAMPLE
    # Smoke test on 5 files to verify config
    .\scripts\reindex_bsl_fast.ps1 -Project "ИБTransportManagementDevelop" -Limit 5

.NOTES
    Speedup expectations vs default reindex:
      - With FA2:    2-3x faster, no quality loss
      - Without FA2: 1.05-1.10x (only buffer-size effect)

    See: .claude/skills/tech-research/cache/qwen3-embedding-speedup.md
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Project,

    [int]$Limit = 0
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$reindexScript = Join-Path $repoRoot "scripts\reindex_bsl_qwen3.py"

if (-not (Test-Path $python)) {
    throw "Python venv not found at $python. Run 'python -m venv .venv' first."
}
if (-not (Test-Path $reindexScript)) {
    throw "Reindex script not found at $reindexScript"
}

# --- Detect Flash Attention 2 availability ---
Write-Host "=== Detecting Flash Attention 2 ===" -ForegroundColor Cyan
$fa2Available = $false
try {
    & $python -c "import flash_attn; import sys; sys.exit(0)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $fa2Available = $true
        $fa2Version = & $python -c "import flash_attn; print(flash_attn.__version__)"
        Write-Host "  [OK] flash-attn $fa2Version available - FA2 + batch=100 mode" -ForegroundColor Green
    }
}
catch {
    # Fall through to disabled
}

if (-not $fa2Available) {
    Write-Host "  [WARN] flash-attn NOT installed - falling back to safe defaults (no batch increase)" -ForegroundColor Yellow
    Write-Host "         To enable 2-3x speedup, install:" -ForegroundColor Yellow
    Write-Host "           .venv\Scripts\pip install flash-attn --no-build-isolation" -ForegroundColor Yellow
    Write-Host "         Note: Python 3.13 + Win + sm_86 may require pre-built wheel from:" -ForegroundColor Yellow
    Write-Host "           https://github.com/bdashore3/flash-attention/releases" -ForegroundColor Yellow
}

# --- Build args based on FA2 availability ---
$pyArgs = @(
    "--project", $Project,
    "--embedder", "qwen3-st",
    "--pooling-mode", "standard",
    "--collection", "bsl_code_v4_late",
    "--buffer-size", "1024"
)

if ($fa2Available) {
    $pyArgs += "--enable-fa2"
    $pyArgs += "--batch-size"; $pyArgs += "100"
}
else {
    # Conservative fallback - preserves current memory profile
    $pyArgs += "--batch-size"; $pyArgs += "50"
}

if ($Limit -gt 0) {
    $pyArgs += "--limit"; $pyArgs += $Limit.ToString()
    Write-Host ""
    Write-Host "=== SMOKE TEST mode (limit=$Limit) ===" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Launching reindex with quality-preserving optimizations ===" -ForegroundColor Cyan
Write-Host "Python:  $python"
Write-Host "Script:  $reindexScript"
Write-Host "Args:    $($pyArgs -join ' ')"
Write-Host ""

$startTime = Get-Date
& $python $reindexScript @pyArgs
$exitCode = $LASTEXITCODE
$duration = (Get-Date) - $startTime

Write-Host ""
Write-Host "=== Reindex finished ===" -ForegroundColor Cyan
Write-Host "Exit code: $exitCode"
Write-Host "Duration:  $([int]$duration.TotalMinutes) min $([int]$duration.Seconds) sec"

exit $exitCode
