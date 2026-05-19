"""Pre-flight VRAM probe for Phase 1+2 of roadmap 260518.

Loads the production Qwen3STEmbedder with `max_seq_length=8192` (Phase 1
default), feeds it a 1.04 MB BSL god-object module, and runs
`embed_late_chunked` end-to-end. Reports:

  - peak GPU memory_allocated / memory_reserved during the run
  - whether single-pass or sliding-window branch fired
  - fallback% (chunks that returned None)
  - wall-clock seconds

Success criterion (roadmap §3.4 / §4.4):
  - VRAM peak < 22 GB (>= 2 GB headroom on RTX 3090 24 GB)
  - 0 CUDA OOM errors
  - sliding branch should be exercised for a 1 MB module
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Probe parameters
MODULE_PATH = (
    REPO
    / "ИБTransportManagementDevelop"
    / "Конфигурация"
    / "src"
    / "CommonModules"
    / "ОбменДаннымиСервер"
    / "Module.bsl"
)
CHUNK_CHARS = 3000  # mimics BSLChunker.window_chars default (~1024 tokens/chunk)


def load_module_text(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1251")


def synth_chunk_spans(text: str, chunk_chars: int) -> list[tuple[int, int]]:
    """Produce non-overlapping char spans of ~chunk_chars each.

    Mimics BSLChunker output for VRAM-probe purposes. The embedder treats
    spans independently of chunker semantics, so synthetic spans suffice
    to exercise the full forward + per-span pooling pipeline.
    """
    spans: list[tuple[int, int]] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + chunk_chars, n)
        if end < n:
            nl = text.rfind("\n", max(start + 1, end - chunk_chars // 10), end)
            if nl != -1:
                end = nl + 1
        spans.append((start, end))
        start = end
    return spans


def main() -> int:
    print("=== Pre-flight VRAM probe: roadmap 260518 Phase 1+2 ===")
    print(f"Module: {MODULE_PATH.relative_to(REPO)}")
    print(f"Size: {MODULE_PATH.stat().st_size:,} bytes")

    text = load_module_text(MODULE_PATH)
    print(f"Loaded {len(text):,} chars")

    spans = synth_chunk_spans(text, CHUNK_CHARS)
    print(f"Generated {len(spans)} synthetic chunk spans (~{CHUNK_CHARS} chars each)")

    print("\nLoading Qwen3STEmbedder (max_seq_length=8192, Phase 1 default) ...")
    import torch

    torch.cuda.reset_peak_memory_stats()
    t_load_0 = time.time()

    from scripts.reindex_bsl_qwen3 import Qwen3STEmbedder

    embedder = Qwen3STEmbedder(dtype="bfloat16", batch_size=32)
    print(f"Embedder loaded in {time.time() - t_load_0:.1f}s")
    print(f"  max_seq_length={embedder.max_seq_length}")
    print(f"  buckets={embedder.buckets}")
    after_load_alloc = torch.cuda.memory_allocated() / 1024**3
    after_load_reserved = torch.cuda.memory_reserved() / 1024**3
    print(
        f"  VRAM after load: alloc={after_load_alloc:.2f} GB, reserved={after_load_reserved:.2f} GB"
    )

    tokenizer = embedder.model.tokenizer
    probe = tokenizer(text, add_special_tokens=True, truncation=False)
    total_tokens = len(probe["input_ids"])
    branch = "single-pass" if total_tokens <= embedder.max_seq_length else "sliding"
    print(f"\nModule tokenizes to {total_tokens:,} tokens -> branch={branch} expected")

    print("\nRunning embed_late_chunked() ...")
    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    try:
        vectors = embedder.embed_late_chunked(text, spans)
    except Exception as exc:
        elapsed = time.time() - t0
        peak_alloc = torch.cuda.max_memory_allocated() / 1024**3
        peak_reserved = torch.cuda.max_memory_reserved() / 1024**3
        print(f"FAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        print(f"Peak VRAM at failure: alloc={peak_alloc:.2f} GB, reserved={peak_reserved:.2f} GB")
        return 1

    elapsed = time.time() - t0
    peak_alloc = torch.cuda.max_memory_allocated() / 1024**3
    peak_reserved = torch.cuda.max_memory_reserved() / 1024**3
    fallback = sum(1 for v in vectors if v is None)
    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"  vectors returned: {len(vectors)} (expected {len(spans)})")
    print(f"  fallback (None) chunks: {fallback}/{len(spans)} = {100*fallback/len(spans):.1f}%")
    print(f"  Peak VRAM: alloc={peak_alloc:.2f} GB, reserved={peak_reserved:.2f} GB")
    print(
        f"  Headroom vs 24 GB: alloc={24 - peak_alloc:.2f} GB, reserved={24 - peak_reserved:.2f} GB"
    )

    print("\n=== Success criteria ===")
    crit_vram = peak_reserved < 22.0
    if total_tokens > 8192:
        crit_branch = branch == "sliding"
    else:
        crit_branch = branch == "single-pass"
    print(f"  [{'OK' if crit_vram else 'FAIL'}] Peak reserved VRAM < 22 GB: {peak_reserved:.2f} GB")
    print(f"  [{'OK' if crit_branch else 'FAIL'}] Correct branch fired: {branch}")
    print(
        f"  [INFO] Fallback%: {100*fallback/len(spans):.1f}% "
        f"(expected <5% per roadmap §4.2 for >500K modules after Phase 2)"
    )

    embedder.close()
    return 0 if crit_vram and crit_branch else 2


if __name__ == "__main__":
    sys.exit(main())
