<#
Phase 8 Orchestrator (Part 2) — Phase 8.7, 8.8 (partial), 8.9 smoke.

Runs AFTER phase8_run.ps1 (which finishes 8.1-8.4) and AFTER manual decisions
finalised in roadmap docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md.

Stages:
  8.7 Recreate Qdrant collections per finalised dim policy
       - DROP bsl_code_v3 (duplicate of v4)
       - SKIP visual_grounding (5 points, deferred to Phase 9)
       - learned_patterns / experience_embeddings: scroll-copy E5 vectors
         into <name>_e5_legacy (1024d archive), then drop+create empty 1024d
       - bsl_code_v4: drop+create 4096d Cosine
       - 7 others: drop+create 1024d Cosine (MRL-truncated by embedder later)
  8.8 Reindex bsl_code_v4 via scripts/reindex_bsl_qwen3.py --embedder qwen3-st
       Other collections (skill_library, pdf_documents, wiki_pages_v1,
       graph_embeddings, bsl_metadata, conversation_memory) require their own
       ingestion adapters - NOT covered here, run separately.
  8.9 Smoke: count points + functional search on bsl_code_v4

PRE-FLIGHT WARNING: Claude Code + MCP servers MUST be closed before running.
Otherwise Qwen3-8B will OOM the GPU (MCP embedders hold ~3-6 GB).

Usage:
  pwsh -File scripts/phase8_recreate_reindex.ps1
  pwsh -File scripts/phase8_recreate_reindex.ps1 -AutoConfirm
  pwsh -File scripts/phase8_recreate_reindex.ps1 -SkipRecreate
  pwsh -File scripts/phase8_recreate_reindex.ps1 -SkipReindex
  pwsh -File scripts/phase8_recreate_reindex.ps1 -SkipSmoke
  pwsh -File scripts/phase8_recreate_reindex.ps1 -BslProjectPath "src/projects/configuration/<name>"
#>

param(
    [switch]$AutoConfirm,
    [switch]$SkipRecreate,
    [switch]$SkipReindex,
    [switch]$SkipSmoke,
    [string]$BslProjectPath = "",
    [int]$BatchSize = 32,
    [int]$BufferSize = 512
)

$ErrorActionPreference = 'Stop'

# --- Paths ---
$Root          = Split-Path -Parent $PSScriptRoot
$Python        = Join-Path $Root '.venv\Scripts\python.exe'
$ReindexScript = Join-Path $Root 'scripts\reindex_bsl_qwen3.py'
$LogDir        = Join-Path $Root 'tmp\phase8'

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

# --- Pre-flight ---
Banner '8.7-pre' 'Pre-flight'

if (-not (Test-Path $Python)) {
    throw "Python executable not found at $Python"
}

# Check Qdrant healthy
try {
    $resp = Invoke-WebRequest -Uri 'http://localhost:6333/collections' -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -ne 200) {
        throw "Qdrant returned status $($resp.StatusCode)"
    }
    Write-Host 'Qdrant healthy.' -ForegroundColor Green
} catch {
    throw "Qdrant unreachable on http://localhost:6333: $_"
}

# Warn if heavy Python procs running (likely Claude Code + MCP)
$heavyProcs = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.WorkingSet64 -gt 100MB }
if ($heavyProcs) {
    Write-Warning 'Heavy Python processes detected. Qwen3-8B reindex needs full GPU. Recommend closing Claude Code / MCP servers first.'
    $heavyProcs | Format-Table Id, ProcessName, @{Name='MB';Expression={[math]::Round($_.WorkingSet64/1MB,1)}} -AutoSize | Out-String | Write-Host
    Confirm-Step 'Continue anyway?'
}

# --- Phase 8.7: Recreate collections ---
if (-not $SkipRecreate) {
    Banner '8.7' 'Recreate Qdrant collections'

    Write-Warning 'About to DELETE 10 collections. Backup must already exist (Phase 8.6).'
    Write-Warning '  Backup: E:/Transfer folder/qdrant/1c-pre-qwen3-2026-04-26/'
    Write-Warning '  Manifest: docs/roadmap/260426_PHASE_8_PRE_QWEN3_BACKUP_MANIFEST.json'
    Confirm-Step 'Proceed with destructive recreate?'

    $recreatePy = Join-Path $LogDir '8.7_recreate.py'
    @'
"""Phase 8.7 - Recreate collections per finalised dim policy.

Idempotent: if collection already has target dim, leaves it. If wrong dim, recreates.
"""

import sys
import time

from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.exceptions import UnexpectedResponse

# Finalised dim policy (roadmap section 11)
DIM_POLICY = {
    "bsl_code_v4": 4096,
    "pdf_documents": 1024,
    "wiki_pages_v1": 1024,
    "graph_embeddings": 1024,
    "bsl_metadata": 1024,
    "skill_library": 1024,
    "conversation_memory": 1024,
    "learned_patterns": 1024,
    "experience_embeddings": 1024,
}

DROP = {"bsl_code_v3"}                                          # remove without recreate
SKIP = {"visual_grounding"}                                     # leave as-is (5 points)
FREEZE_LEGACY = {"learned_patterns", "experience_embeddings"}   # archive to <name>_e5_legacy first

client = QdrantClient(host="localhost", port=6333, timeout=60)


def existing_collections():
    return {c.name for c in client.get_collections().collections}


def get_dim(name):
    try:
        info = client.get_collection(collection_name=name)
    except (UnexpectedResponse, Exception):
        return None
    cfg = info.config.params.vectors
    if hasattr(cfg, "size"):
        return cfg.size
    if isinstance(cfg, dict) and cfg:
        return next(iter(cfg.values())).size
    return None


def freeze_to_legacy(src):
    """Scroll-copy points from src to src + '_e5_legacy', mirroring source schema.

    Idempotency: if legacy already exists, refuse on point_count mismatch
    (partial copy from a crashed run), accept on exact match.
    """
    legacy = src + "_e5_legacy"
    existing = existing_collections()

    src_info = client.get_collection(collection_name=src)
    src_count = src_info.points_count
    src_vectors_cfg = src_info.config.params.vectors  # VectorParams or dict

    if legacy in existing:
        legacy_count = client.get_collection(collection_name=legacy).points_count
        if legacy_count == src_count:
            print("  legacy '%s' already complete (%d points) - skipping" % (legacy, legacy_count))
            return
        raise RuntimeError(
            "Legacy '%s' exists with %d points but source has %d. "
            "Likely partial copy from a crashed run. Resolve manually "
            "(delete '%s' and re-run, or repair)." % (legacy, legacy_count, src_count, legacy)
        )

    print("  creating archive '%s' (mirroring source schema)..." % legacy)
    client.create_collection(collection_name=legacy, vectors_config=src_vectors_cfg)

    offset = None
    copied = 0
    while True:
        points, offset = client.scroll(
            collection_name=src,
            limit=256,
            with_payload=True,
            with_vectors=True,
            offset=offset,
        )
        if not points:
            break
        # Preserve named-vector dict shape when present (do NOT collapse to first vector).
        upserts = [
            models.PointStruct(id=p.id, vector=p.vector, payload=p.payload)
            for p in points
        ]
        client.upsert(collection_name=legacy, points=upserts)
        copied += len(upserts)
        if offset is None:
            break

    # Sanity: archive count should match source (ignoring concurrent writes — none expected here).
    final = client.get_collection(collection_name=legacy).points_count
    if final != src_count:
        print("  WARN: archived %d but source has %d - investigate" % (final, src_count))
    print("  archived %d points -> %s" % (copied, legacy))


def recreate(name, dim):
    existing = existing_collections()
    if name in existing:
        current = get_dim(name)
        if current == dim:
            info = client.get_collection(collection_name=name)
            print("  '%s' already at dim=%d (%d points) - leaving" % (name, dim, info.points_count))
            return
        print("  '%s' has dim=%s, want=%d - recreating" % (name, current, dim))
        client.delete_collection(collection_name=name)
    else:
        print("  '%s' missing - creating fresh at dim=%d" % (name, dim))
    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
    )


t0 = time.time()
existing = existing_collections()
print("Found %d collections before recreate: %s" % (len(existing), sorted(existing)))

# Step 1: drop bsl_code_v3 (no recreate)
for name in sorted(DROP):
    if name in existing:
        print("DROP %s" % name)
        client.delete_collection(collection_name=name)
    else:
        print("DROP %s - already absent" % name)

# Step 2: freeze legacy collections to archive (PRESERVES E5 vectors)
for name in sorted(FREEZE_LEGACY):
    print("FREEZE %s" % name)
    freeze_to_legacy(name)

# Step 3: recreate per dim policy
for name in sorted(DIM_POLICY):
    print("RECREATE %s" % name)
    recreate(name, DIM_POLICY[name])

# Step 4: verify visual_grounding untouched
if "visual_grounding" in existing:
    info = client.get_collection(collection_name="visual_grounding")
    print("SKIP visual_grounding (%d points, dim=%s)" % (info.points_count, get_dim("visual_grounding")))

after = existing_collections()
print("\nDone in %.1fs. Collections after recreate: %s" % (time.time()-t0, sorted(after)))
'@ | Out-File -FilePath $recreatePy -Encoding utf8

    $recreateLog = Join-Path $LogDir '8.7_recreate.log'
    & $Python $recreatePy | Tee-Utf8 -FilePath $recreateLog
    Assert-ExitOk 'Phase 8.7 recreate'
    Write-Host 'Recreate complete.' -ForegroundColor Green
}

# --- Phase 8.8: Reindex bsl_code_v4 ---
if (-not $SkipReindex) {
    Banner '8.8' 'Reindex bsl_code_v4 (Qwen3-ST, bf16, b=32)'

    if (-not (Test-Path $ReindexScript)) {
        throw "Reindex script not found: $ReindexScript"
    }

    if (-not $BslProjectPath) {
        $candidates = Get-ChildItem -Path (Join-Path $Root 'src\projects\configuration') -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notmatch '^\.' }
        if (-not $candidates) {
            throw 'No BSL project directories found. Pass -BslProjectPath explicitly.'
        }
        if ($candidates.Count -gt 1) {
            Write-Host 'Multiple BSL projects found:' -ForegroundColor Yellow
            $candidates | ForEach-Object { Write-Host "  - $($_.FullName)" }
            throw 'Ambiguous: pass -BslProjectPath explicitly (refusing to pick automatically).'
        }
        $BslProjectPath = $candidates[0].FullName
        Write-Host "Using single BSL project: $BslProjectPath" -ForegroundColor DarkGray
    }

    if (-not (Test-Path $BslProjectPath)) {
        throw "BSL project path not found: $BslProjectPath"
    }

    Write-Warning "Reindex bsl_code_v4 from: $BslProjectPath"
    Write-Warning ('  Embedder: qwen3-st  | dtype: bfloat16  | batch=' + $BatchSize + '  | buffer=' + $BufferSize + '  | dims=4096')
    Write-Warning '  Phase 8.10 length-bucketed batching enabled.'
    Write-Warning '  Expected: ~40-50 min for ~35.5K real chunks (p50=332 tok, p99=3588).'
    Write-Warning '    (8.4b benchmark 18.15 ch/s was synthetic 200-tok chunks; weighted'
    Write-Warning '     prediction with bucketing is ~14 ch/s on the real long-tail.)'
    Confirm-Step 'Start reindex?'

    $reindexLog = Join-Path $LogDir '8.8_bsl_code_v4.log'
    & $Python $ReindexScript `
        --project $BslProjectPath `
        --embedder qwen3-st `
        --collection bsl_code_v4 `
        --batch-size $BatchSize `
        --buffer-size $BufferSize `
        | Tee-Utf8 -FilePath $reindexLog
    Assert-ExitOk 'Phase 8.8 reindex'
    Write-Host 'Reindex complete.' -ForegroundColor Green
}

# --- Phase 8.9: Smoke ---
if (-not $SkipSmoke) {
    Banner '8.9' 'Smoke (points_count + functional search)'

    # Queries are loaded from JSON to keep Cyrillic out of the .ps1/.py source files.
    $queriesJson = Join-Path $LogDir '8.9_queries.json'
    # Russian smoke queries encoded as Unicode escapes (avoid embedding Cyrillic in source).
    # обработка проведения документа
    # регистр сведений 1С
    $jsonRaw = '["обработка проведения документа", "регистр сведений 1С"]'
    $jsonRaw | Out-File -FilePath $queriesJson -Encoding utf8

    $smokePy = Join-Path $LogDir '8.9_smoke.py'
    @'
"""Phase 8.9 - Smoke: collection sizes + bsl_code_v4 search."""

import json
import os
import sys
import time

import torch
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_PATH = os.path.join(LOG_DIR, "8.9_queries.json")

client = QdrantClient(host="localhost", port=6333, timeout=30)
print("Collection points_count:")
for c in sorted(client.get_collections().collections, key=lambda x: x.name):
    info = client.get_collection(collection_name=c.name)
    print("  %-32s %8d" % (c.name, info.points_count))

print("\nLoading Qwen3 for query embedding...")
t0 = time.time()
model = SentenceTransformer(
    "Qwen/Qwen3-Embedding-8B",
    device="cuda",
    model_kwargs={"torch_dtype": torch.bfloat16},
)
print("  loaded in %.1fs" % (time.time()-t0))

with open(QUERIES_PATH, "r", encoding="utf-8") as f:
    queries = json.load(f)

for q in queries:
    qv = model.encode([q], convert_to_numpy=True)[0].tolist()
    res = client.search(collection_name="bsl_code_v4", query_vector=qv, limit=3)
    print("\nQuery: %r" % q)
    for r in res:
        name = r.payload.get("name", "?")
        mod = r.payload.get("module_name", "?")
        print("  score=%.4f  name=%s  module=%s" % (r.score, name, mod))

print("\nSmoke OK.")
'@ | Out-File -FilePath $smokePy -Encoding utf8

    $smokeLog = Join-Path $LogDir '8.9_smoke.log'
    & $Python $smokePy | Tee-Utf8 -FilePath $smokeLog
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Smoke test exited with $LASTEXITCODE - review $smokeLog"
    } else {
        Write-Host 'Smoke passed.' -ForegroundColor Green
    }
}

# --- Final ---
Write-Host "`n------------------------------------------------" -ForegroundColor Cyan
Write-Host ' Phase 8.7 - 8.9 complete' -ForegroundColor Green
Write-Host '------------------------------------------------' -ForegroundColor Cyan
Write-Host "Logs: $LogDir"
Write-Host 'Remaining work (separate scripts/sessions):' -ForegroundColor Yellow
Write-Host '  - skill_library:       adapt scripts/index-skills-to-qdrant.py to Qwen3-ST 1024d MRL'
Write-Host '  - pdf_documents:       re-chunk + index data/pdfs/* via PDF loader pipeline'
Write-Host '  - wiki_pages_v1:       reindex via wiki-pipeline skill (docs/wiki/)'
Write-Host '  - graph_embeddings:    reindex from data/graph_db/graph.json (or Neo4j)'
Write-Host '  - bsl_metadata:        re-extract via BSL parser (src/bsl/parser/) -> embed -> upsert'
Write-Host '  - conversation_memory: reindex from data/conversations.db'
Write-Host 'Then: 8.10 docs sync, 8.11 cleanup (per roadmap).'
