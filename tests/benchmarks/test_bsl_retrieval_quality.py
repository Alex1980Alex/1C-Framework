"""Phase 4 benchmark — BSL retrieval-quality comparison across Late Chunking variants.

Roadmap 260518 §6. Wired 2026-05-19 (Block A of follow-up plan).

Run:
  pytest tests/benchmarks/test_bsl_retrieval_quality.py::test_bsl_retrieval_quality_comparison -v -s

Inputs:
  - data/bsl_golden_set.json — produced by `python scripts/generate_bsl_golden_set.py`.
    Each item: {"id", "query", "expected": [{"module_path","line_start","line_end"}],
                "slice": "small|medium|god_object|cross_region"}.
  - VARIANTS table — maps human-readable variant names to Qdrant collection names.

Outputs:
  - Markdown table on stdout with per-slice metrics.
  - pytest assertion: per-slice threshold (god-object: -5pp, small/medium: -3pp,
    overall: warn at -2pp, fail at -5pp).

GPU caveat: loading Qwen3 embedder needs ~17 GB VRAM. Do NOT run this test
while `scripts/reindex_bsl_qwen3.py` is active — they will both OOM.
"""
from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

DEFAULT_GOLDEN_SET = REPO_ROOT / "data" / "bsl_golden_set.json"


# VARIANTS populated 2026-05-19 per roadmap §6.4. `baseline` is current
# production. `phase12` = Phase 1+2 sliding only (no region grouping).
# `phase123` = Phase 1+2+3 region-aware (proposed new default).
VARIANTS: dict[str, str] = {
    "baseline": "bsl_code_v4_late",
    "std_pool": "bsl_std_pool_bench",
    "phase12": "bsl_phase12_bench",
    "phase123": "bsl_phase123_bench",
    "phase5_prod": "bsl_code_v4_late_v2",
}

# Per-slice acceptance thresholds (roadmap §6.4 question e, recommended).
# (warn_pp, fail_pp): regression in percentage points triggers warn/fail.
PER_SLICE_THRESHOLDS: dict[str, tuple[float, float]] = {
    "god_object":   (3.0, 5.0),
    "small":        (1.0, 3.0),
    "medium":       (1.0, 3.0),
    "cross_region": (3.0, 5.0),
    "overall":      (2.0, 5.0),
}


# Pure metric helpers — no I/O, deterministic.
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
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, r in enumerate(retrieved[:k], 1)
        if r in expected
    )
    ideal_hits = min(len(expected), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def _id_from_expected(expected_item: dict[str, Any]) -> str:
    return f"{expected_item['module_path']}:{expected_item['line_start']}"


def _id_from_qdrant_point(point: Any) -> str:
    payload = getattr(point, "payload", {}) or {}
    return f"{payload.get('module_path','?')}:{payload.get('line_start',0)}"


# Fixtures — heavy resources loaded once per pytest module.
@pytest.fixture(scope="module")
def golden_set() -> list[dict[str, Any]]:
    if not DEFAULT_GOLDEN_SET.exists():
        pytest.skip(
            f"Golden set not found at {DEFAULT_GOLDEN_SET}. "
            f"Run `python scripts/generate_bsl_golden_set.py` first."
        )
    with DEFAULT_GOLDEN_SET.open(encoding="utf-8") as fh:
        items = json.load(fh)
    if not items:
        pytest.skip("Golden set is empty.")
    return items


@pytest.fixture(scope="module")
def qdrant_client():
    from qdrant_client import QdrantClient
    return QdrantClient(host="localhost", port=6333, timeout=120)


@pytest.fixture(scope="module")
def query_embedder():
    """Load Qwen3 embedder ONCE per test module. ~17 GB VRAM."""
    from reindex_bsl_qwen3 import Qwen3STEmbedder
    emb = Qwen3STEmbedder(dtype="bfloat16", batch_size=1, enable_fa2=True)
    yield emb
    emb.close()


def search_variant(
    qdrant_client: Any,
    embedder: Any,
    collection: str,
    query: str,
    k: int = 10,
) -> list[str]:
    """Embed query → Qdrant top-k → list of `module_path:line_start` IDs.

    Fair-scope filter (added 2026-05-20 evening, §1.2.6 follow-up): all
    variants are CommonModules-only (14k chunks), but baseline has full
    `ИБTransportManagementDevelop` (54k chunks). To make the A/B fair we
    restrict baseline search to module_path containing "CommonModules" —
    same effective corpus as variants. Filter is a no-op on phase12/123
    collections since they already only contain CommonModules chunks.
    """
    from qdrant_client.http import models as qm

    qvec = embedder.embed_batch([query], is_query=True)[0]
    scope_filter = qm.Filter(
        must=[qm.FieldCondition(
            key="module_path",
            match=qm.MatchText(text="CommonModules"),
        )]
    )
    res = qdrant_client.query_points(
        collection_name=collection,
        query=qvec,
        limit=k,
        with_payload=True,
        query_filter=scope_filter,
    )
    return [_id_from_qdrant_point(pt) for pt in res.points]


def _averaged_per_slice(
    raw: dict[str, dict[str, list[float]]],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for slc, metrics in raw.items():
        out[slc] = {m: sum(vs) / max(1, len(vs)) for m, vs in metrics.items()}
    return out


def _evaluate_gates(
    baseline: dict[str, dict[str, float]],
    variant: dict[str, dict[str, float]],
) -> list[str]:
    failures: list[str] = []
    for slc, b_metrics in baseline.items():
        if slc not in variant:
            continue
        b_recall = b_metrics.get("recall@10", 0.0)
        v_recall = variant[slc].get("recall@10", 0.0)
        regression_pp = (b_recall - v_recall) * 100.0
        warn_pp, fail_pp = PER_SLICE_THRESHOLDS.get(slc, (2.0, 5.0))
        if regression_pp > fail_pp:
            failures.append(
                f"FAIL slice={slc}: recall@10 regressed {regression_pp:.2f}pp "
                f"(baseline={b_recall:.3f} -> variant={v_recall:.3f}); "
                f"fail threshold = {fail_pp:.1f}pp"
            )
        elif regression_pp > warn_pp:
            print(
                f"WARN slice={slc}: recall@10 regressed {regression_pp:.2f}pp "
                f"(baseline={b_recall:.3f} -> variant={v_recall:.3f}); "
                f"warn threshold = {warn_pp:.1f}pp"
            )
    return failures


@pytest.mark.skipif(
    not all(VARIANTS.values()) or len(VARIANTS) < 2,
    reason="VARIANTS dict requires at least 2 entries (baseline + 1 variant).",
)
def test_bsl_retrieval_quality_comparison(
    golden_set: list[dict[str, Any]],
    qdrant_client: Any,
    query_embedder: Any,
) -> None:
    raw: dict[str, dict[str, dict[str, list[float]]]] = {
        v: defaultdict(lambda: defaultdict(list)) for v in VARIANTS
    }
    overall: dict[str, dict[str, list[float]]] = {
        v: defaultdict(list) for v in VARIANTS
    }

    for item in golden_set:
        slc = item.get("slice", "overall")
        expected_ids = [_id_from_expected(e) for e in item["expected"]]
        if not expected_ids:
            continue
        for variant_name, collection in VARIANTS.items():
            retrieved = search_variant(
                qdrant_client, query_embedder, collection, item["query"], k=10,
            )
            metrics = {
                "recall@10": recall_at_k(retrieved, expected_ids, 10),
                "ndcg@10":   ndcg_at_k(retrieved, expected_ids, 10),
                "mrr":       mrr(retrieved, expected_ids),
                "p@5":       precision_at_k(retrieved, expected_ids, 5),
            }
            for metric, value in metrics.items():
                raw[variant_name][slc][metric].append(value)
                overall[variant_name][metric].append(value)

    averaged: dict[str, dict[str, dict[str, float]]] = {}
    for variant_name in VARIANTS:
        per_slice = _averaged_per_slice(raw[variant_name])
        per_slice["overall"] = {
            m: sum(vs) / max(1, len(vs)) for m, vs in overall[variant_name].items()
        }
        averaged[variant_name] = per_slice

    all_slices = sorted({s for v in averaged.values() for s in v.keys()})
    print(f"\n\n=== Phase 4 benchmark — {len(golden_set)} queries ===\n")
    print("| variant   | slice         | recall@10 | NDCG@10 | MRR   | p@5   |")
    print("|-----------|---------------|-----------|---------|-------|-------|")
    for variant_name in VARIANTS:
        for slc in all_slices:
            metrics = averaged[variant_name].get(slc, {})
            if not metrics:
                continue
            print(
                f"| {variant_name:<9} | {slc:<13} | "
                f"{metrics.get('recall@10', 0):>9.3f} | "
                f"{metrics.get('ndcg@10', 0):>7.3f} | "
                f"{metrics.get('mrr', 0):>5.3f} | "
                f"{metrics.get('p@5', 0):>5.3f} |"
            )

    if "phase123" in averaged and "baseline" in averaged:
        failures = _evaluate_gates(averaged["baseline"], averaged["phase123"])
        if failures:
            pytest.fail(
                "Phase 4 acceptance gate FAILED for phase123:\n  "
                + "\n  ".join(failures)
            )
