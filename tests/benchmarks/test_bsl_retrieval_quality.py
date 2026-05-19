"""SCAFFOLD — BSL retrieval-quality benchmark for roadmap 260518 Phase 4.

STATUS: stub only. Does NOT run a meaningful comparison yet. Created
2026-05-19 as Phase 4 entry-point. To make this real, fill the four
TODO sections below — see roadmap section 6 and section 6.4 for the
open questions list (added in the same commit as this file).

Run intent (when complete):
  pytest tests/benchmarks/test_bsl_retrieval_quality.py -v

Why a scaffold, not a full benchmark: roadmap section 6.4 lists 5
blocking questions that need user input (golden-set source, baseline
collection name, which Phase 1/2/3 variant snapshots exist, recall@10
acceptance threshold, etc.). Filling those is a separate task.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


# ---------------------------------------------------------------------------
# TODO #1 — Golden set. See roadmap section 6.4 question a.
# ---------------------------------------------------------------------------
# Format per item:
#   {
#     "id": "SM-1",                      # short stable identifier
#     "query": "...",                    # natural-language BSL query
#     "expected": [                       # at least 1 expected hit
#       {"module_path": "...", "line_start": 100, "line_end": 150},
#       ...
#     ],
#     "slice": "small" | "medium" | "god_object" | "cross_region",
#   }
GOLDEN_SET: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# TODO #2 — Collection variants to benchmark.
# ---------------------------------------------------------------------------
# Each variant maps to a Qdrant collection name produced by running
# scripts/reindex_bsl_qwen3.py with a specific config. See roadmap §6.4
# question b for which collections currently exist.
VARIANTS: dict[str, str] = {
    # "baseline":   "bsl_code_v4",
    # "phase1":     "bsl_code_v4_late",
    # "phase1_2":   "bsl_phase12_test",
    # "phase1_2_3": "bsl_phase123_test",
}


# ---------------------------------------------------------------------------
# Pure metric helpers — no I/O, ready to use once GOLDEN_SET is populated.
# ---------------------------------------------------------------------------

def recall_at_k(retrieved: list[str], expected: list[str], k: int = 10) -> float:
    if not expected:
        return 0.0
    hits = sum(1 for e in expected if e in retrieved[:k])
    return hits / len(expected)


def precision_at_k(retrieved: list[str], expected: list[str], k: int = 5) -> float:
    if k == 0:
        return 0.0
    return sum(1 for r in retrieved[:k] if r in expected) / k


def mrr(retrieved: list[str], expected: list[str]) -> float:
    for rank, r in enumerate(retrieved, 1):
        if r in expected:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], expected: list[str], k: int = 10) -> float:
    """Binary-relevance NDCG@k (relevant if in expected, else not)."""
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, r in enumerate(retrieved[:k], 1)
        if r in expected
    )
    ideal_hits = min(len(expected), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# TODO #3 — Search invocation. Needs decision on entry point.
# ---------------------------------------------------------------------------
def search_variant(collection: str, query: str, k: int = 10) -> list[str]:
    """Return a ranked list of chunk identifiers for the query.

    Identifier shape MUST match expected[*] style for recall/precision
    math. Suggested: f"{module_path}:{line_start}".

    Not implemented — see TODO #3 + roadmap section 6.4.
    """
    raise NotImplementedError(
        "Phase 4 benchmark not wired yet — see TODO #3 + roadmap section 6.4."
    )


# ---------------------------------------------------------------------------
# TODO #4 — Pytest entry that prints the comparison table.
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not GOLDEN_SET or not VARIANTS,
    reason="Phase 4 scaffold — golden set and variants not yet populated; "
           "see roadmap 260518 section 6.4 for blocking questions.",
)
def test_bsl_retrieval_quality_comparison() -> None:
    summary: list[dict[str, Any]] = []
    for variant_name, collection in VARIANTS.items():
        accum = {"recall@10": 0.0, "ndcg@10": 0.0, "mrr": 0.0, "p@5": 0.0}
        for item in GOLDEN_SET:
            expected_ids = [
                f"{e['module_path']}:{e['line_start']}" for e in item["expected"]
            ]
            retrieved = search_variant(collection, item["query"], k=10)
            accum["recall@10"] += recall_at_k(retrieved, expected_ids, 10)
            accum["ndcg@10"] += ndcg_at_k(retrieved, expected_ids, 10)
            accum["mrr"] += mrr(retrieved, expected_ids)
            accum["p@5"] += precision_at_k(retrieved, expected_ids, 5)
        n = max(1, len(GOLDEN_SET))
        averaged = {k: v / n for k, v in accum.items()}
        summary.append({"variant": variant_name, **averaged})

    print("\n| variant            | recall@10 | NDCG@10 | MRR   | p@5   |")
    print(  "|--------------------|-----------|---------|-------|-------|")
    for row in summary:
        print(
            f"| {row['variant']:<18} | {row['recall@10']:>9.3f} | "
            f"{row['ndcg@10']:>7.3f} | {row['mrr']:>5.3f} | {row['p@5']:>5.3f} |"
        )

    # Acceptance gate — uncomment once baseline known.
