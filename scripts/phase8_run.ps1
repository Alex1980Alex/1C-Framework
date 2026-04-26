<#
Phase 8 Orchestrator — Phase 8.1 to 8.4 of the embedder migration to CUDA 12.8 + Qwen3-Embedding-8B.
Runs as 4 stages: uninstall CPU torch, install cu128 wheels, download the 16 GB Qwen3 model, run the benchmark.
Each stage is gated by a confirmation prompt (bypass with -AutoConfirm) and tees output to tmp/phase8/.

Usage:
  pwsh -File scripts/phase8_run.ps1
  pwsh -File scripts/phase8_run.ps1 -AutoConfirm
  pwsh -File scripts/phase8_run.ps1 -SkipDownload -AutoConfirm
  pwsh -File scripts/phase8_run.ps1 -SkipUninstall -SkipInstall
#>

param(
    [switch]$AutoConfirm,
    [switch]$SkipUninstall,
    [switch]$SkipInstall,
    [switch]$SkipDownload,
    [switch]$SkipBenchmark
)

$ErrorActionPreference = 'Stop'

# --- Paths ---
$Root        = Split-Path -Parent $PSScriptRoot
$Python      = Join-Path $Root '.venv\Scripts\python.exe'
$Pip         = Join-Path $Root '.venv\Scripts\pip.exe'
$HfCli       = Join-Path $Root '.venv\Scripts\huggingface-cli.exe'
$BenchScript = Join-Path $Root 'scripts\bench_qwen3_embedding.py'
$LogDir      = Join-Path $Root 'tmp\phase8'

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# --- Helpers ---
function Banner($n, $t) {
    Write-Host "`n===== Phase $n - $t =====" -ForegroundColor Cyan
}

function Confirm-Step($msg) {
    if ($AutoConfirm) {
        Write-Host "AutoConfirm: $msg" -ForegroundColor DarkGray
        return
    }
    $answer = Read-Host "$msg (y/N)"
    if ($answer -ne 'y' -and $answer -ne 'Y') {
        throw 'Aborted by user'
    }
}

function Assert-ExitOk($what) {
    if ($LASTEXITCODE -ne 0) {
        throw "$what failed (exit $LASTEXITCODE)"
    }
}

# --- Pre-flight ---
Banner '8.0' 'Pre-flight'

if (-not (Test-Path $Python)) {
    throw "Python executable not found at $Python"
}

& $Python --version
Write-Host "Executable: $Python" -ForegroundColor DarkGray

$heavyProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.WorkingSet64 -gt 100MB }
if ($heavyProcs) {
    Write-Warning "Found Python processes consuming > 100 MB. Recommend closing Claude Code and MCP servers first."
    $heavyProcs | Format-Table Id, ProcessName, @{Name='MB';Expression={[math]::Round($_.WorkingSet64/1MB,1)}} -AutoSize | Out-String | Write-Host
    Confirm-Step 'Continue anyway?'
}

# --- Phase 8.1: Uninstall CPU torch ---
if (-not $SkipUninstall) {
    Banner '8.1' 'Uninstall CPU torch'

    $freezeLog = Join-Path $LogDir 'pip_freeze_before.txt'
    & $Pip freeze | Out-File -FilePath $freezeLog -Encoding utf8
    Assert-ExitOk 'pip freeze'
    Write-Host "Saved rollback snapshot: $freezeLog" -ForegroundColor DarkGray

    Confirm-Step 'Uninstall torch and torchvision?'

    $uninstallLog = Join-Path $LogDir '8.1_uninstall.log'
    & $Pip uninstall -y torch torchvision | Tee-Object -FilePath $uninstallLog -Encoding utf8
    Assert-ExitOk 'pip uninstall'

    $remaining = & $Pip list | Select-String -Pattern '^torch\s'
    if ($remaining) {
        Write-Warning "Torch packages still present after uninstall:`n$remaining"
        Confirm-Step 'Torch still installed. Proceed anyway?'
    } else {
        Write-Host 'Torch removed.' -ForegroundColor Green
    }
}

# --- Phase 8.2: Install PyTorch CUDA 12.8 ---
if (-not $SkipInstall) {
    Banner '8.2' 'Install PyTorch CUDA 12.8'

    Confirm-Step 'Install torch + torchvision (cu128)?'

    $installLog = Join-Path $LogDir '8.2_install.log'
    & $Pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128 | Tee-Object -FilePath $installLog -Encoding utf8
    Assert-ExitOk 'pip install cu128'

    Write-Host 'Verifying CUDA + FP16 smoke...' -ForegroundColor Yellow
    $cudaCheck = @(
        'import torch;',
        'assert torch.cuda.is_available(), "CUDA not available";',
        'print("torch:", torch.__version__);',
        'print("cuda:", torch.version.cuda);',
        'print("device:", torch.cuda.get_device_name(0));',
        't = torch.zeros((1,1024), dtype=torch.float16, device="cuda");',
        'print("fp16 smoke shape:", tuple(t.shape))'
    ) -join ' '
    & $Python -c $cudaCheck
    Assert-ExitOk 'CUDA verification'
    Write-Host 'CUDA check passed.' -ForegroundColor Green

    $pipCheckLog = Join-Path $LogDir '8.2_pip_check.log'
    & $Pip check | Tee-Object -FilePath $pipCheckLog -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "pip check reported issues (exit $LASTEXITCODE). Review $pipCheckLog. Continuing."
    }
}

# --- Phase 8.3: Download Qwen3-Embedding-8B ---
if (-not $SkipDownload) {
    Banner '8.3' 'Download Qwen3-Embedding-8B'

    Write-Warning 'About to download ~16 GB. Expect 15-60 min depending on bandwidth.'
    Confirm-Step 'Start model download?'

    if (-not (Test-Path $HfCli)) {
        Write-Host 'huggingface-cli not found, installing huggingface_hub...' -ForegroundColor Yellow
        & $Pip install -U huggingface_hub
        Assert-ExitOk 'pip install huggingface_hub'
    }

    $downloadLog = Join-Path $LogDir '8.3_download.log'
    & $HfCli download Qwen/Qwen3-Embedding-8B | Tee-Object -FilePath $downloadLog -Encoding utf8
    Assert-ExitOk 'huggingface-cli download'

    Write-Host 'Verifying 1_Pooling/config.json...' -ForegroundColor Yellow
    $verifyModel = @(
        'from huggingface_hub import snapshot_download;',
        'import os;',
        'p = snapshot_download("Qwen/Qwen3-Embedding-8B", allow_patterns=["1_Pooling/*"]);',
        'cfg = os.path.join(p, "1_Pooling", "config.json");',
        'assert os.path.exists(cfg), f"Pooling config missing at {cfg}";',
        'print("pooling OK:", cfg)'
    ) -join ' '
    & $Python -c $verifyModel
    Assert-ExitOk 'Pooling config verification'

    Write-Host 'Smoke test: SentenceTransformer encode...' -ForegroundColor Yellow
    $smokeTest = @(
        'from sentence_transformers import SentenceTransformer;',
        'import torch;',
        'm = SentenceTransformer("Qwen/Qwen3-Embedding-8B", device="cuda", model_kwargs={"torch_dtype": torch.float16});',
        'v = m.encode(["test"], convert_to_numpy=True);',
        'print("shape:", v.shape, "dtype:", v.dtype);',
        'assert v.shape == (1, 4096), f"Unexpected shape: {v.shape}"'
    ) -join ' '
    & $Python -c $smokeTest
    Assert-ExitOk 'SentenceTransformer smoke'
    Write-Host 'Smoke test passed (shape 1x4096).' -ForegroundColor Green
}

# --- Phase 8.4: Benchmark ---
if (-not $SkipBenchmark) {
    Banner '8.4' 'Inference benchmark'

    if (-not (Test-Path $BenchScript)) {
        throw "Benchmark script not found: $BenchScript"
    }

    Confirm-Step 'Run bench_qwen3_embedding.py (3 modes, ~5 min)?'

    $benchLog = Join-Path $LogDir '8.4_bench.log'
    & $Python $BenchScript | Tee-Object -FilePath $benchLog -Encoding utf8
    Assert-ExitOk 'benchmark'
}

# --- Final ---
Write-Host "`n------------------------------------------------" -ForegroundColor Cyan
Write-Host ' Phase 8.1 - 8.4 complete' -ForegroundColor Green
Write-Host '------------------------------------------------' -ForegroundColor Cyan
Write-Host "Logs: $LogDir"
Write-Host 'Next steps:' -ForegroundColor Yellow
Write-Host '  1. Review tmp/phase8/8.4_bench.log — confirm rate >= 30 chunks/sec'
Write-Host '  2. Decide answers to Phase 8.7-8.8 questions (named-vector dims, lost-source strategy)'
Write-Host '  3. Re-engage Claude Code session to continue with reindex (8.7 -> 8.8)'
