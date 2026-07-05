"""§БП G4 (audit 260705) — end-to-end memory WRITE→RECALL benchmark.

The existing golden harness (``memory_golden_harness.py``) measures the SURFACING
/fusion stage against FROZEN captures — it never exercises the write path. This
benchmark closes that gap: it *writes* facts through the real embedder into an
ISOLATED Qdrant collection, then *recalls* them with paraphrased queries and
measures retrieval quality. It catches the class of bug the surfacing harness
cannot — a write path that silently stores nothing (cf. the 2026-07-05 P1
``index_page`` bug: awaited a sync method, indexed 0, all tests still green).

Isolation: seeds ``MEMORY_E2E_COLLECTION`` (default ``memory_e2e_eval``), NEVER
the production ``learned_patterns``. ``run`` drops it afterwards unless --keep.

Live deps: TEI (embedder) + Qdrant. If either is down, the benchmark reports
``{"status": "live-deps-unavailable"}`` and exits 0 (like the harness capture) —
a cold CI never fails on missing infra.

Metric functions (``content_hash``, ``hit_at_k``, ``recall_at_k``, ``mrr``,
``ndcg_at_k``) are imported from ``memory_golden_harness`` — single source, no
re-implementation.

Sensitivity: the seed facts are deliberately DISTINCT (mutual distractors), so a
healthy loop scores near hit_rate=1.0 — this benchmark detects *catastrophic*
write-path failure (silently indexing 0), NOT fine-grained ranking regressions.
To make it a sensitive ranking gate, add near-duplicate distractor facts.

Usage:
  python scripts/memory_e2e_benchmark.py run   --k 5           # seed + evaluate + drop
  python scripts/memory_e2e_benchmark.py seed                  # seed only (keep collection)
  python scripts/memory_e2e_benchmark.py evaluate --k 5        # evaluate existing seed
  python scripts/memory_e2e_benchmark.py run --keep            # seed + evaluate, keep collection
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATASET = PROJECT_ROOT / "data" / "memory" / "e2e" / "dataset.jsonl"
REPORT_DIR = PROJECT_ROOT / "data" / "memory" / "e2e"
COLLECTION = os.getenv("MEMORY_E2E_COLLECTION", "memory_e2e_eval")
VECTOR_SIZE = int(os.getenv("LEARNING_VECTOR_SIZE", "4096"))
DEFAULT_K = 5

# --- reuse metric functions from the surfacing harness (single source) -------
_HARNESS = PROJECT_ROOT / "scripts" / "memory_golden_harness.py"


def _load_harness():
    spec = importlib.util.spec_from_file_location("memory_golden_harness", str(_HARNESS))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================ pure logic (testable) ==========================


def load_dataset(path: Path = DATASET) -> list[dict[str, Any]]:
    """Load the JSONL dataset. Each row: {id, fact, query}."""
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def score_query(
    ranked_hashes: list[str], target_hash: str, k: int, harness: Any
) -> dict[str, float]:
    """Metrics for one query: the ranked recall list vs the single relevant fact."""
    rel = {target_hash: 1}
    return {
        "hit": harness.hit_at_k(ranked_hashes, rel, k),
        "recall": harness.recall_at_k(ranked_hashes, rel, k),
        "mrr": harness.mrr(ranked_hashes, rel),
        "ndcg": harness.ndcg_at_k(ranked_hashes, rel, k),
        "rank": _first_rank(ranked_hashes, target_hash),
    }


def _first_rank(ranked: list[str], target: str) -> int:
    """1-indexed rank of target in ranked list; 0 if absent."""
    for i, h in enumerate(ranked, 1):
        if h == target:
            return i
    return 0


def aggregate(per_query: list[dict[str, Any]]) -> dict[str, Any]:
    """Mean each metric over all evaluated queries."""
    if not per_query:
        return {"n": 0, "hit_rate": 0.0, "recall": 0.0, "mrr": 0.0, "ndcg": 0.0, "misses": []}
    n = len(per_query)

    def _mean(key: str) -> float:
        return round(sum(q["metrics"][key] for q in per_query) / n, 4)

    return {
        "n": n,
        "hit_rate": _mean("hit"),
        "recall": _mean("recall"),
        "mrr": _mean("mrr"),
        "ndcg": _mean("ndcg"),
        "misses": [q["id"] for q in per_query if q["metrics"]["hit"] == 0.0],
    }


def evaluate_offline(
    rows: list[dict[str, Any]], ranked_by_id: dict[str, list[str]], k: int, harness: Any
) -> dict[str, Any]:
    """Pure evaluation: given precomputed ranked-hash lists per query id, score.

    Separated from live I/O so it is unit-testable with a mock search.
    """
    per_query = []
    for row in rows:
        target = harness.content_hash(row["fact"])
        ranked = ranked_by_id.get(row["id"], [])
        per_query.append({"id": row["id"], "metrics": score_query(ranked, target, k, harness)})
    return {"per_query": per_query, "aggregate": aggregate(per_query)}


# ============================ live I/O (TEI + Qdrant) ========================


def _live_fns() -> tuple[Callable, Callable] | None:
    """Return (embed_fn, search_fn) or None if the hook helpers can't import."""
    hooks_dir = PROJECT_ROOT / ".claude" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    try:
        from shared.semantic_search import embed_query_tei, search_qdrant_semantic

        return embed_query_tei, search_qdrant_semantic
    except Exception:
        return None


def _qdrant():
    from qdrant_client import QdrantClient

    return QdrantClient(host="127.0.0.1", port=6333, timeout=15)


# Production collections the benchmark must NEVER drop — defense-in-depth guard
# against a mis-set MEMORY_E2E_COLLECTION clobbering real memory.
_PROD_COLLECTIONS = frozenset(
    {"learned_patterns", "skill_library", "framework_code_v1", "wiki_pages_v1", "pdf_documents"}
)


def seed_live(rows: list[dict[str, Any]], embed_fn: Callable, harness: Any) -> dict[str, Any]:
    """Embed each fact and upsert into the isolated eval collection (recreated).

    Qdrant errors (server down / connection refused) degrade to
    ``live-deps-unavailable`` — the docstring contract is "either dep down → exit 0",
    so a Qdrant outage must not raise (only TEI-down was handled before).
    """
    if COLLECTION in _PROD_COLLECTIONS:
        return {
            "status": "error",
            "reason": f"refusing to seed a production collection: {COLLECTION}",
        }

    from qdrant_client import models as qm

    try:
        client = _qdrant()
        # recreate_collection is deprecated in qdrant-client >=1.13 → explicit drop+create
        if client.collection_exists(COLLECTION):
            client.delete_collection(COLLECTION)
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qm.VectorParams(size=VECTOR_SIZE, distance=qm.Distance.COSINE),
        )
    except Exception as exc:  # Qdrant down / connection refused
        return {"status": "live-deps-unavailable", "reason": f"qdrant: {type(exc).__name__}"}

    points = []
    seeded = 0
    for i, row in enumerate(rows):
        vec = embed_fn(row["fact"], timeout=15.0)
        if not vec:
            return {"status": "live-deps-unavailable", "reason": f"embed failed at {row['id']}"}
        points.append(
            qm.PointStruct(
                id=i,
                vector=vec,
                payload={
                    "content": row["fact"],
                    "content_hash": harness.content_hash(row["fact"]),
                    "eid": row["id"],
                },
            )
        )
        seeded += 1
    try:
        client.upsert(collection_name=COLLECTION, points=points)
    except Exception as exc:
        return {"status": "live-deps-unavailable", "reason": f"qdrant upsert: {type(exc).__name__}"}
    return {"status": "ok", "seeded": seeded, "collection": COLLECTION}


def recall_live(
    rows: list[dict[str, Any]], k: int, embed_fn: Callable, search_fn: Callable, harness: Any
) -> dict[str, Any]:
    """For each query, return the ranked content_hashes retrieved from the eval collection."""
    ranked_by_id: dict[str, list[str]] = {}
    for row in rows:
        vec = embed_fn(row["query"], timeout=15.0)
        if not vec:
            return {
                "status": "live-deps-unavailable",
                "reason": f"embed query failed at {row['id']}",
            }
        try:
            hits = search_fn(COLLECTION, vec, limit=k, timeout=10.0)
        except Exception as exc:
            return {
                "status": "live-deps-unavailable",
                "reason": f"qdrant search: {type(exc).__name__}",
            }
        ranked_by_id[row["id"]] = [(h.get("payload") or {}).get("content_hash", "") for h in hits]
    return {"status": "ok", "ranked_by_id": ranked_by_id}


def _drop():
    try:
        _qdrant().delete_collection(COLLECTION)
    except Exception:
        pass


# ================================ CLI ========================================


def _print_utf8(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8"))


def _write_report(report: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "e2e_result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="BP G4 end-to-end memory write->recall benchmark")
    ap.add_argument("cmd", choices=["run", "seed", "evaluate"], help="run = seed+evaluate")
    ap.add_argument("--k", type=int, default=DEFAULT_K)
    ap.add_argument("--keep", action="store_true", help="keep the eval collection after run")
    ap.add_argument("--drop", action="store_true", help="drop the eval collection and exit")
    args = ap.parse_args()

    if args.drop:
        _drop()
        _print_utf8(f"dropped {COLLECTION}\n")
        return 0

    harness = _load_harness()
    rows = load_dataset()
    fns = _live_fns()
    if fns is None:
        _print_utf8(json.dumps({"status": "live-deps-unavailable", "reason": "hook import"}) + "\n")
        return 0
    embed_fn, search_fn = fns

    if args.cmd in ("run", "seed"):
        seed_res = seed_live(rows, embed_fn, harness)
        if seed_res.get("status") != "ok":
            _print_utf8(json.dumps(seed_res, ensure_ascii=False) + "\n")
            return 0
        if args.cmd == "seed":
            _print_utf8(json.dumps(seed_res, ensure_ascii=False) + "\n")
            return 0

    recalled = recall_live(rows, args.k, embed_fn, search_fn, harness)
    if recalled.get("status") != "ok":
        _print_utf8(json.dumps(recalled, ensure_ascii=False) + "\n")
        return 0

    result = evaluate_offline(rows, recalled["ranked_by_id"], args.k, harness)
    report = {"status": "ok", "k": args.k, "collection": COLLECTION, **result}
    _write_report(report)

    if args.cmd == "run" and not args.keep:
        _drop()

    agg = report["aggregate"]
    lines = [
        f"# Memory E2E benchmark (BP G4) — k={args.k}, n={agg['n']}",
        f"hit_rate={agg['hit_rate']}  recall@{args.k}={agg['recall']}  mrr={agg['mrr']}  ndcg@{args.k}={agg['ndcg']}",
    ]
    if agg["misses"]:
        lines.append(f"misses: {', '.join(agg['misses'])}")
    _print_utf8("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
