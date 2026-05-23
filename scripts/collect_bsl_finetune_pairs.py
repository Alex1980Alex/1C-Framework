#!/usr/bin/env python3
"""SKELETON: Collect BSL query-positive pairs for MRL fine-tuning Qwen3.

Reference: §4.1.13 future work. NOT EXECUTABLE without LLM provider config.

Pipeline:
    1. Scroll bsl_code_v4 (24455 chunks)
    2. For each chunk with doc_comment > 50 chars, generate 1-3 synthetic queries
       via LLM (e.g., "What does ПолучитьВнешниеМодули do? How is it called?")
    3. Pair each query with its source chunk_id as positive
    4. Save as JSONL: {query, positive_chunk_id, source_text}

Output target: data/eval/bsl_pairs_for_finetune.jsonl

Required volume: ≥10K pairs for stable MRL fine-tuning. With 24455 chunks ×
2 avg queries = ~49K pairs (target met).

Quality controls (must implement before training):
    - Dedupe queries (Levenshtein > 0.85 threshold)
    - Filter chunks without meaningful doc_comment (boilerplate)
    - Hold out 10% as eval split
    - Manual review of 100 random samples
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# === LLM client placeholder ===
# In production: from src.shared.llm_rotation.service import LLMRotationService
# For skeleton: just describe expected interface


def generate_queries_for_chunk(
    chunk_text: str,
    chunk_name: str,
    chunk_type: str,
    n_queries: int = 2,
) -> list[str]:
    """Generate N synthetic queries that should retrieve THIS chunk.

    Production prompt template:
        Given this BSL code chunk, generate {N} natural-language queries
        in Russian that a developer would type to find this exact symbol.

        Chunk type: {chunk_type}
        Symbol: {chunk_name}
        Code:
        {chunk_text[:1500]}

        Output JSON: [{"query": "..."}, ...]
        Queries should be diverse: factual ("Что делает X"),
        procedural ("Как использовать X"), error ("Ошибка при X").
    """
    # SKELETON: returns dummy queries; replace with real LLM call
    return [
        f"Как использовать {chunk_name}?",
        f"Что делает {chunk_type} {chunk_name}?",
    ][:n_queries]


def collect_pairs(qdrant_url: str, output_path: Path, sample: int = 0) -> int:
    """Scroll BSL collection, generate query-positive pairs, save JSONL."""
    from qdrant_client import QdrantClient

    client = QdrantClient(url=qdrant_url)
    written = 0
    next_offset = None
    with open(output_path, "w", encoding="utf-8") as f:
        while True:
            recs, next_offset = client.scroll(
                collection_name="bsl_code_v4",
                limit=256,
                with_payload=True,
                with_vectors=False,
                offset=next_offset,
            )
            if not recs:
                break
            for r in recs:
                p = r.payload or {}
                text = p.get("content", "")
                name = p.get("name", "")
                ctype = p.get("chunk_type", "")
                if len(text) < 100 or not name:
                    continue
                queries = generate_queries_for_chunk(text, name, ctype)
                for q in queries:
                    f.write(
                        json.dumps(
                            {
                                "query": q,
                                "positive_chunk_id": str(r.id),
                                "source_text": text[:500],
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    written += 1
                if sample and written >= sample:
                    return written
            if next_offset is None:
                break
    return written


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--output", default="data/eval/bsl_pairs_for_finetune.jsonl")
    ap.add_argument("--sample", type=int, default=100, help="Cap for skeleton testing (0=full)")
    args = ap.parse_args()

    n = collect_pairs(args.qdrant_url, Path(args.output), sample=args.sample)
    print(f"Wrote {n} pairs to {args.output}")
    print("NOTE: This is a SKELETON. Replace generate_queries_for_chunk() ")
    print("      with real LLM calls (Z.AI via llm_rotation) before training.")
