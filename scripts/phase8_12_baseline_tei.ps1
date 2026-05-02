<#
Phase 8.12.3 - Baseline reindex bsl_code_v4 via TEI (text-embeddings-inference).

Runs AFTER Phase 8.12.1/2/5/6/9 (P0 fixes + A2 split + module_summary drop +
TEI service + Late Chunking pooling-hook), all DONE per roadmap section 21.

Stages:
  1. Pre-flight: Docker, Qdrant, GPU headroom, MCP-server warning.
  2. Start TEI service (--profile tei) with Qwen3-Embedding-8B mounted from
     D:/hf-manual/Qwen3-Embedding-8B (no HF Hub re-download).
  3. Cold-load wait + /health + /info smoke.
  4. Reindex bsl_code_v4 via --embedder qwen3-tei --recreate.
  5. Post-reindex points_count + 2-query smoke search.
  6. Tear-down note (TEI keeps running for 8.12.8 A/B).

PRE-FLIGHT WARNING (CRITICAL): close Claude Code + MCP servers BEFORE running.
TEI loads Qwen3-8B at fp16 ~16 GB; MCP embedders compete for VRAM and can
OOM the server-side load. Phase 8.12.1 added Python-side OOM swallow but the
TEI Rust runtime has no equivalent - it will crash the container.

Usage:
  pwsh -File scripts/phase8_12_baseline_tei.ps1
  pwsh -File scripts/phase8_12_baseline_tei.ps1 -AutoConfirm
  pwsh -File scripts/phase8_12_baseline_tei.ps1 -SkipTeiStart    # already running
  pwsh -File scripts/phase8_12_baseline_tei.ps1 -SkipReindex     # smoke-only
  pwsh -File scripts/phase8_12_baseline_tei.ps1 -BslProjectPath "configuration/<name>"
  pwsh -File scripts/phase8_12_baseline_tei.ps1 -Qwen3ModelDir "D:/hf-manual/Qwen3-Embedding-8B"
#>

param(
    [switch]$AutoConfirm,
    [switch]$SkipTeiStart,
    [switch]$SkipReindex,
    [switch]$SkipSmoke,
    [string]$BslProjectPath = "",
    [string]$Qwen3ModelDir = "D:/hf-manual/Qwen3-Embedding-8B",
    [string]$TeiUrl = "http://localhost:8080",
    [int]$TeiStartTimeoutSec = 600,
    [int]$BatchSize = 32,
    [int]$BufferSize = 512
)

$ErrorActionPreference = 'Stop'

# --- Paths ---
$Root          = Split-Path -Parent $PSScriptRoot
$Python        = Join-Path $Root '.venv\Scripts\python.exe'
$ReindexScript = Join-Path $Root 'scripts\reindex_bsl_qwen3.py'
$ComposeBase   = Join-Path $Root 'docker\docker-compose.yml'
$ComposeGpu    = Join-Path $Root 'docker\docker-compose.gpu.yml'
$LogDir        = Join-Path $Root 'tmp\phase8'

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# --- Helpers ---
function Banner($n, $t) {
    Write-Host "`n===== Phase 8.12.3 - $n - $t =====" -ForegroundColor Cyan
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

function Tee-Utf8 {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromPipeline = $true)]$InputObject
    )
    begin {
        '' | Out-File -FilePath $FilePath -Encoding utf8
    }
    process {
        Write-Host $InputObject
        Add-Content -Path $FilePath -Value $InputObject -Encoding utf8
    }
}

# --- Stage 1: Pre-flight ---
Banner '1' 'Pre-flight'

if (-not (Test-Path $Python)) {
    throw "Python executable not found at $Python"
}
if (-not (Test-Path $ReindexScript)) {
    throw "Reindex script not found: $ReindexScript"
}
if (-not (Test-Path $ComposeBase) -or -not (Test-Path $ComposeGpu)) {
    throw "Compose files missing: $ComposeBase / $ComposeGpu"
}
if (-not (Test-Path $Qwen3ModelDir)) {
    throw "Qwen3 model dir not found: $Qwen3ModelDir (pass -Qwen3ModelDir <path> to override)"
}

# Verify the 4 expected shards
$expectedShards = @(
    'model-00001-of-00004.safetensors',
    'model-00002-of-00004.safetensors',
    'model-00003-of-00004.safetensors',
    'model-00004-of-00004.safetensors'
)
foreach ($s in $expectedShards) {
    if (-not (Test-Path (Join-Path $Qwen3ModelDir $s))) {
        throw "Missing shard: $s in $Qwen3ModelDir"
    }
}
Write-Host "Qwen3 model dir OK: $Qwen3ModelDir (4 shards present)" -ForegroundColor Green

# Qdrant health
try {
    $resp = Invoke-WebRequest -Uri 'http://localhost:6333/collections' -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -ne 200) { throw "Qdrant returned status $($resp.StatusCode)" }
    Write-Host 'Qdrant healthy on 6333.' -ForegroundColor Green
} catch {
    throw "Qdrant unreachable on http://localhost:6333: $_"
}

# Docker reachable
try {
    & docker ps -q | Out-Null
    Assert-ExitOk 'docker ps'
    Write-Host 'Docker reachable.' -ForegroundColor Green
} catch {
    throw "Docker unreachable: $_"
}

# GPU headroom - fail fast if Qwen3-8B in fp16 (~16 GB) will not fit
try {
    $gpuLine = & nvidia-smi --query-gpu=memory.total,memory.free --format=csv,noheader,nounits | Select-Object -First 1
    $parts = ($gpuLine -split ',') | ForEach-Object { $_.Trim() }
    $gpuTotalMb = [int]$parts[0]
    $gpuFreeMb  = [int]$parts[1]
    Write-Host ("GPU: total={0} MiB, free={1} MiB" -f $gpuTotalMb, $gpuFreeMb) -ForegroundColor Green
    if ($gpuFreeMb -lt 18000) {
        Write-Warning ("Low VRAM headroom: {0} MiB free, need ~18 GB for Qwen3-8B fp16 + KV-cache + workspace" -f $gpuFreeMb)
        Confirm-Step 'Continue anyway (TEI may OOM)?'
    }
} catch {
    Write-Warning "nvidia-smi unavailable: $_ (skipping GPU pre-check)"
}

# Heavy Python procs warning (likely Claude Code / MCP servers holding VRAM)
$heavyProcs = Get-Process python, pythonw -ErrorAction SilentlyContinue | Where-Object { $_.WorkingSet64 -gt 100MB }
if ($heavyProcs) {
    Write-Warning 'Heavy Python processes detected - likely Claude Code / MCP servers.'
    Write-Warning '  TEI Rust runtime has no OOM-recovery path; close them first if VRAM is tight.'
    $heavyProcs | Format-Table Id, ProcessName, @{Name='MB';Expression={[math]::Round($_.WorkingSet64/1MB,1)}} -AutoSize | Out-String | Write-Host
    Confirm-Step 'Continue anyway?'
}

# --- Stage 2: Start TEI service ---
if (-not $SkipTeiStart) {
    Banner '2' 'Start TEI service (Qwen3-Embedding-8B, fp16)'

    # Export QWEN3_MODEL_DIR so docker-compose.gpu.yml bind-mount picks it up
    $env:QWEN3_MODEL_DIR = $Qwen3ModelDir
    Write-Host "QWEN3_MODEL_DIR=$($env:QWEN3_MODEL_DIR)" -ForegroundColor DarkGray

    # Tear down any stale tei container before re-up (idempotent)
    & docker rm -f pdf-rag-tei 2>$null | Out-Null

    Write-Warning 'Starting TEI container - cold-load takes 1-5 min for 16 GB safetensors.'
    Confirm-Step 'Proceed?'

    & docker compose -f $ComposeBase -f $ComposeGpu --profile tei up -d tei
    Assert-ExitOk 'docker compose up tei'

    # Poll /health until ready or timeout
    Write-Host "Waiting for TEI /health (timeout: $TeiStartTimeoutSec s)..." -ForegroundColor DarkGray
    $deadline = (Get-Date).AddSeconds($TeiStartTimeoutSec)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $h = Invoke-WebRequest -Uri "$TeiUrl/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($h.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            # not ready yet
        }
        Start-Sleep -Seconds 5
        Write-Host "." -NoNewline -ForegroundColor DarkGray
    }
    Write-Host ""
    if (-not $ready) {
        Write-Host "TEI /health timeout. Last container logs:" -ForegroundColor Red
        & docker logs --tail 80 pdf-rag-tei 2>&1 | Write-Host
        throw "TEI did not become healthy within $TeiStartTimeoutSec s"
    }
    Write-Host "TEI healthy on $TeiUrl" -ForegroundColor Green

    # /info smoke - verify model_id matches
    try {
        $info = Invoke-RestMethod -Uri "$TeiUrl/info" -UseBasicParsing -TimeoutSec 10
        Write-Host "TEI /info: model_id=$($info.model_id), max_input_length=$($info.max_input_length)" -ForegroundColor Green
        if ($info.model_id -notmatch 'Qwen3-Embedding-8B') {
            Write-Warning "Unexpected model_id: $($info.model_id) - verify the bind-mount is correct"
        }
    } catch {
        Write-Warning "/info call failed: $_"
    }
}

# --- Stage 3: Resolve BSL project ---
if (-not $BslProjectPath) {
    $candidates = Get-ChildItem -Path (Join-Path $Root 'src\projects\configuration') -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch '^\.' -and $_.Name -notmatch '\.md$' }
    if (-not $candidates) {
        throw 'No BSL project directories found. Pass -BslProjectPath explicitly.'
    }
    if ($candidates.Count -gt 1) {
        # Roadmap section 21.1 pins GKSTCPLK-2368 as the Phase 8.12.3 baseline target
        # (2049 BSL files, 35 548 chunks). Prefer it when present; otherwise refuse.
        $pinned = @($candidates | Where-Object { $_.Name -match 'GKSTCPLK-2368' })
        if ($pinned.Count -eq 1) {
            $BslProjectPath = $pinned[0].FullName
            Write-Host 'Multiple BSL projects found; auto-selected roadmap-pinned GKSTCPLK-2368:' -ForegroundColor Yellow
            Write-Host "  $BslProjectPath" -ForegroundColor DarkGray
        } else {
            Write-Host 'Multiple BSL projects found:' -ForegroundColor Yellow
            $candidates | ForEach-Object { Write-Host "  - $($_.FullName)" }
            throw 'Ambiguous: pass -BslProjectPath explicitly (refusing to pick automatically).'
        }
    } else {
        $BslProjectPath = $candidates[0].FullName
        Write-Host "Using single BSL project: $BslProjectPath" -ForegroundColor DarkGray
    }
}
if (-not (Test-Path $BslProjectPath)) {
    throw "BSL project path not found: $BslProjectPath"
}

# --- Stage 4: Reindex bsl_code_v4 via TEI ---
if (-not $SkipReindex) {
    Banner '4' 'Reindex bsl_code_v4 (TEI, qwen3-tei, fp16)'

    Write-Warning "Reindex bsl_code_v4 from: $BslProjectPath"
    Write-Warning ("  Embedder: qwen3-tei  | TEI URL: {0}  | batch={1}  | buffer={2}  | dims=4096" -f $TeiUrl, $BatchSize, $BufferSize)
    Write-Warning '  --recreate flag will DROP the existing partial bsl_code_v4 (~4057 points).'
    Write-Warning '  Expected: ~30-60 min for ~35.5K chunks (TEI x3-5 vs Python ST baseline per roadmap).'
    Confirm-Step 'Start reindex (DESTRUCTIVE - drops bsl_code_v4)?'

    $reindexLog = Join-Path $LogDir '8.12.3_reindex_bsl_code_v4_tei.log'
    $startTs = Get-Date
    & $Python $ReindexScript `
        --project $BslProjectPath `
        --embedder qwen3-tei `
        --tei-url $TeiUrl `
        --collection bsl_code_v4 `
        --batch-size $BatchSize `
        --buffer-size $BufferSize `
        --recreate `
        | Tee-Utf8 -FilePath $reindexLog
    Assert-ExitOk 'Phase 8.12.3 reindex'
    $elapsed = (Get-Date) - $startTs
    Write-Host ('Reindex complete in {0:hh\:mm\:ss}.' -f $elapsed) -ForegroundColor Green
}

# --- Stage 5: Post-reindex smoke ---
if (-not $SkipSmoke) {
    Banner '5' 'Smoke (points_count + functional search via TEI)'

    $queriesJson = Join-Path $LogDir '8.12.3_queries.json'
    # Smoke queries encoded as JSON \u escapes so the .ps1 source stays ASCII-only.
    # Windows PowerShell 5.1 reads UTF-8-no-BOM source files under the system
    # codepage (cp1251) and would otherwise mangle Cyrillic into mojibake,
    # desyncing the parser. Python's json.load decodes the escapes at runtime.
    #   q1 = "obrabotka provedeniya dokumenta"  (document posting handler)
    #   q2 = "registr svedeniy 1S"              (information register 1C)
    $jsonRaw = '["\u043e\u0431\u0440\u0430\u0431\u043e\u0442\u043a\u0430 \u043f\u0440\u043e\u0432\u0435\u0434\u0435\u043d\u0438\u044f \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430", "\u0440\u0435\u0433\u0438\u0441\u0442\u0440 \u0441\u0432\u0435\u0434\u0435\u043d\u0438\u0439 1\u0421"]'
    $jsonRaw | Out-File -FilePath $queriesJson -Encoding ascii

    $smokePy = Join-Path $LogDir '8.12.3_smoke.py'
    @'
"""Phase 8.12.3 - Smoke: collection sizes + bsl_code_v4 search via TEI HTTP."""

import json
import os
import sys
import time

import httpx
from qdrant_client import QdrantClient

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_PATH = os.path.join(LOG_DIR, "8.12.3_queries.json")
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080")
QWEN3_QUERY_INSTR = (
    "Instruct: Given a web search query, retrieve relevant passages "
    "that answer the query\nQuery: "
)


def embed_via_tei(text: str) -> list:
    """Match Qwen3TEIEmbedder query path: prepend retrieval-instruction."""
    payload = {"inputs": [QWEN3_QUERY_INSTR + text]}
    r = httpx.post(f"{TEI_URL}/embed", json=payload, timeout=60.0)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data and isinstance(data[0], list):
        return data[0]
    if isinstance(data, dict) and "data" in data:
        return data["data"][0]["embedding"]
    raise RuntimeError(f"Unexpected TEI response shape: {type(data).__name__}")


client = QdrantClient(host="localhost", port=6333, timeout=30)
print("Collection points_count:")
for c in sorted(client.get_collections().collections, key=lambda x: x.name):
    info = client.get_collection(collection_name=c.name)
    print("  %-32s %8d" % (c.name, info.points_count))

with open(QUERIES_PATH, "r", encoding="utf-8") as f:
    queries = json.load(f)

print("\nQuerying TEI %s ..." % TEI_URL)
for q in queries:
    t0 = time.time()
    qv = embed_via_tei(q)
    embed_ms = (time.time() - t0) * 1000
    res = client.query_points(collection_name="bsl_code_v4", query=qv, limit=3, with_payload=True).points
    print("\nQuery: %r  (embed=%.1fms)" % (q, embed_ms))
    for r in res:
        name = r.payload.get("name", "?")
        mod = r.payload.get("module_name", "?")
        print("  score=%.4f  name=%s  module=%s" % (r.score, name, mod))

print("\nSmoke OK.")
'@ | Out-File -FilePath $smokePy -Encoding utf8

    $env:TEI_URL = $TeiUrl
    $smokeLog = Join-Path $LogDir '8.12.3_smoke.log'
    & $Python $smokePy | Tee-Utf8 -FilePath $smokeLog
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Smoke test exited with $LASTEXITCODE - review $smokeLog"
    } else {
        Write-Host 'Smoke passed.' -ForegroundColor Green
    }
}

# --- Final ---
Write-Host "`n------------------------------------------------" -ForegroundColor Cyan
Write-Host ' Phase 8.12.3 baseline complete' -ForegroundColor Green
Write-Host '------------------------------------------------' -ForegroundColor Cyan
Write-Host "Logs: $LogDir"
Write-Host 'TEI is still running. Stop with:' -ForegroundColor Yellow
Write-Host '  docker compose -f docker/docker-compose.yml -f docker/docker-compose.gpu.yml --profile tei stop tei'
Write-Host 'Next phase: 8.12.8 quality A/B (E5 vs Qwen3+A2 vs Qwen3+A2-alt) - see roadmap section 21.6.'
