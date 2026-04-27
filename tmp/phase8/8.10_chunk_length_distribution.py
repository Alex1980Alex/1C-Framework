"""Phase 8.10 - chunk length distribution measurement.

Reproduces the parser->chunker->context-enricher pipeline used by
scripts/reindex_bsl_qwen3.py, then tokenizes each chunk's content with
the Qwen3-Embedding-8B tokenizer and reports length distribution.

CPU-only (no GPU model load). Output stays in tmp/phase8/.

Usage:
    .venv/Scripts/python.exe tmp/phase8/8.10_chunk_length_distribution.py \
        --project "src/projects/configuration/260416_GKSTCPLK-2368 ..."
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.bsl.parser import BSLASTParser, BSLChunker, BSLContextEnricher

SKIP_PATTERNS = ["node_modules", "bin/", "build/"]


def should_skip(path: Path) -> bool:
    s = str(path).replace("\\", "/")
    return any(p in s for p in SKIP_PATTERNS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0,
                    help="Max chunks to measure (0=all)")
    ap.add_argument("--no-context", action="store_true")
    ap.add_argument("--out", type=Path,
                    default=Path("tmp/phase8/8.10_distribution.json"))
    args = ap.parse_args()

    project = args.project.resolve()
    if not project.is_dir():
        print(f"ERROR: {project} is not a directory")
        sys.exit(1)

    print("Loading Qwen3 tokenizer (CPU)...")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-Embedding-8B")

    parser = BSLASTParser()
    chunker = BSLChunker()

    enricher = None
    if not args.no_context:
        try:
            from src.bsl.knowledge_graph.metadata_extractor import MetadataExtractor
            from src.bsl.call_graph.store import CallGraphStore
            extractor = MetadataExtractor(project)
            cg_db = PROJECT_ROOT / "cache" / "bsl_call_graph.db"
            cg = CallGraphStore(cg_db) if cg_db.exists() else None
            enricher = BSLContextEnricher(metadata_extractor=extractor, call_graph=cg)
            stats = extractor.stats()
            print(f"Context enrichment ON: {stats['total']} objects"
                  f"{', call graph loaded' if cg else ''}")
        except Exception as e:
            print(f"Context enrichment unavailable: {e}")

    files = sorted(f for f in project.rglob("*.bsl") if not should_skip(f))
    print(f"Found {len(files)} BSL files")

    lengths: list[int] = []
    char_lengths: list[int] = []
    t0 = time.time()
    errors = 0

    for i, fp in enumerate(files, 1):
        try:
            module = parser.parse_file(str(fp))
            chunks = chunker.chunk_module(module)
            if enricher:
                enricher.enrich(chunks)
            for ch in chunks:
                content = ch.content[:32000]  # match production truncation
                ids = tok(content, add_special_tokens=True,
                          return_tensors=None)["input_ids"]
                lengths.append(len(ids))
                char_lengths.append(len(content))
                if args.limit and len(lengths) >= args.limit:
                    break
            if args.limit and len(lengths) >= args.limit:
                break
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"[ERR] {fp.name}: {e}")
        if i % 200 == 0:
            print(f"[{i}/{len(files)}] {len(lengths)} chunks, "
                  f"{time.time()-t0:.0f}s")

    if not lengths:
        print("No chunks measured")
        sys.exit(1)

    n = len(lengths)
    sorted_lens = sorted(lengths)

    def pct(p: float) -> int:
        idx = min(n - 1, int(p * n / 100))
        return sorted_lens[idx]

    buckets = [
        ("0-256",     0,    256),
        ("257-512",   257,  512),
        ("513-1024",  513,  1024),
        ("1025-2048", 1025, 2048),
        ("2049-4096", 2049, 4096),
        ("4097-8192", 4097, 8192),
        ("8193+",     8193, 10**9),
    ]

    summary = {
        "n_chunks": n,
        "n_files": len(files),
        "errors": errors,
        "tokens": {
            "min":    sorted_lens[0],
            "p10":    pct(10),
            "p25":    pct(25),
            "p50":    pct(50),
            "p75":    pct(75),
            "p90":    pct(90),
            "p95":    pct(95),
            "p99":    pct(99),
            "p999":   pct(99.9),
            "max":    sorted_lens[-1],
            "mean":   round(statistics.mean(lengths), 1),
            "stdev":  round(statistics.stdev(lengths), 1) if n > 1 else 0,
        },
        "chars": {
            "p50": sorted(char_lengths)[n // 2],
            "p99": sorted(char_lengths)[min(n - 1, int(0.99 * n))],
            "max": max(char_lengths),
        },
        "distribution_by_bucket": {
            label: sum(1 for l in lengths if lo <= l <= hi)
            for label, lo, hi in buckets
        },
        "elapsed_s": round(time.time() - t0, 1),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    print("\n" + "=" * 56)
    print(f"DISTRIBUTION  ({n} chunks, {summary['elapsed_s']}s)")
    print("=" * 56)
    t = summary["tokens"]
    print(f"  min     {t['min']:>6}")
    print(f"  p10     {t['p10']:>6}")
    print(f"  p50     {t['p50']:>6}")
    print(f"  p90     {t['p90']:>6}")
    print(f"  p95     {t['p95']:>6}")
    print(f"  p99     {t['p99']:>6}")
    print(f"  p99.9   {t['p999']:>6}")
    print(f"  max     {t['max']:>6}")
    print(f"  mean    {t['mean']:>6}  (stdev {t['stdev']})")

    print("\nBuckets:")
    for label, _, _ in buckets:
        v = summary["distribution_by_bucket"][label]
        pct_v = 100 * v / n
        bar = "#" * int(pct_v / 2)
        print(f"  {label:<10} {v:>6}  ({pct_v:5.1f}%)  {bar}")

    print(f"\nSaved: {args.out}")


if __name__ == "__main__":
    main()
