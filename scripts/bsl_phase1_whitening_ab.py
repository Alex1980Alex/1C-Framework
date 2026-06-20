#!/usr/bin/env python3
"""Phase 1 (post-hoc, sandbox/read-only) -- A/B of dense-vector post-processing.

Question
--------
Phase 0 established a real cross-vocabulary gap on the SEMANTIC golden set
(``data/eval/bsl/bsl_semantic_golden.json``): the dense arm carries the
vocab-mismatch regime (dense recall@10 ~0.42) but is far from healthy. The
``feedback_bsl_embedding_collapse`` memory shows Qwen3 dense vectors on BSL
are anisotropic (anisotropy ~0.59, low effective rank) -- a textbook target
for *whitening* / mean-removal, which de-correlate and isotropize an
embedding space and often recover recall WITHOUT re-embedding.

This script does a strictly post-hoc, in-memory A/B. It NEVER mutates the
production collection -- it pulls dense doc vectors via ``with_vector`` from
Qdrant, transforms them in numpy, and recomputes recall@10 locally against
the same TEI-embedded NL queries.

Variants
--------
1. ``baseline``       -- raw normalized dense vectors (reproduces Phase 0 dense).
2. ``mean_center``    -- subtract the sample mean from query+doc, renormalize.
3. ``soft_zca_0_1``   -- soft-ZCA whitening, eps = 0.1.
4. ``soft_zca_0_01``  -- soft-ZCA whitening, eps = 0.01.

Full ZCA (eps = 0) is deliberately NOT applied (it amplifies the smallest,
noisiest directions and is known to wreck recall on anisotropic spaces).

Whitening math (soft-ZCA)
-------------------------
Fit on a doc sample X (n x d), mu = mean(X):
    Xc = X - mu
    Sigma = Xc^T Xc / (n - 1)          (symmetric PSD)
    Sigma = U diag(lambda) U^T          (eigh)
    W = U diag((lambda + eps)^-1/2) U^T (symmetric whitening = ZCA)
Transform any vector v (query or doc):
    v' = W (v - mu)
then L2-normalize v' for cosine ranking. mu / W are FIT ON DOCS ONLY and
applied identically to queries (standard whitening protocol).

Recall protocol
---------------
Corpus = scope-filtered (``CommonModules``) doc sample, force-including all
golden positives so every positive is reachable. For each query: TEI embed ->
transform -> normalize -> dot-product vs (transformed, normalized) corpus ->
top-10 -> hit if the golden positive ``point_id`` is in top-10. Single
relevant per query, so mean recall@10 == hit-rate@10 (same semantics as
``bench_bsl_realistic_eval.py`` on this single-positive golden set). The
exact same corpus / query set / ranking are reused across all four variants,
so deltas are attributable purely to the transform.

Read-only contract
------------------
Qdrant access is ``scroll`` + ``retrieve`` (with_vector) only -- no writes,
no quantization changes, no alias touches. Writes one JSON report under
``data/eval/bsl/``. Nothing in the prod collection is mutated.

Run
---
    .venv\\Scripts\\python.exe scripts\\bsl_phase1_whitening_ab.py
    .venv\\Scripts\\python.exe scripts\\bsl_phase1_whitening_ab.py --sample 5000 --seed 42
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from qdrant_client import QdrantClient, models

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Identical query-side instruction to Phase 0 / bench_bsl_realistic_eval.py so
# the baseline reproduces the Phase 0 dense number byte-for-byte.
QWEN3_QUERY_INSTRUCT = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
)

DEFAULT_GOLDEN = PROJECT_ROOT / "data" / "eval" / "bsl" / "bsl_semantic_golden.json"
DEFAULT_OUT = PROJECT_ROOT / "data" / "eval" / "bsl" / "bsl_phase1_whitening_ab.json"


# ---------------------------------------------------------------------------
# TEI query embedding (same endpoint / prefix as the production harness)
# ---------------------------------------------------------------------------
def embed_query_tei(text: str, base_url: str, client: httpx.Client) -> list[float]:
    r = client.post(
        f"{base_url}/embed",
        json={"inputs": QWEN3_QUERY_INSTRUCT + text[:8000]},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json()[0]


# ---------------------------------------------------------------------------
# Vector math helpers
# ---------------------------------------------------------------------------
def l2_normalize(mat: np.ndarray) -> np.ndarray:
    """Row-wise L2 normalize (safe against zero rows)."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0.0] = 1.0
    return mat / norms


def fit_soft_zca(sample: np.ndarray, eps: float) -> tuple[np.ndarray, np.ndarray]:
    """Return (mu, W) for soft-ZCA whitening fit on a doc sample.

    mu: (d,) sample mean. W: (d, d) symmetric whitening matrix
    W = U (Lambda + eps)^-1/2 U^T  (eps > 0 -> soft, numerically stable).
    """
    mu = sample.mean(axis=0)
    xc = sample - mu
    n = xc.shape[0]
    cov = (xc.T @ xc) / max(1, n - 1)
    # Symmetric -> eigh (real eigenvalues, orthonormal eigenvectors).
    eigvals, eigvecs = np.linalg.eigh(cov)
    # Clamp tiny negative eigenvalues from float error; eps dominates anyway.
    eigvals = np.clip(eigvals, 0.0, None)
    inv_sqrt = 1.0 / np.sqrt(eigvals + eps)
    # (eigvecs * inv_sqrt) scales column k by inv_sqrt[k] == U diag(inv_sqrt);
    # @ U^T -> symmetric ZCA whitening matrix.
    w = (eigvecs * inv_sqrt) @ eigvecs.T
    return mu.astype(np.float64), w.astype(np.float64)


def recall_at_k_for_variant(
    doc_ids: list[str],
    doc_mat: np.ndarray,
    query_mat: np.ndarray,
    positive_ids: list[str],
    k: int = 10,
) -> tuple[float, list[int]]:
    """Mean recall@k (== hit-rate@k for single-relevant) + per-query rank.

    doc_mat / query_mat must already be transformed AND L2-normalized.
    Cosine ranking == dot product on normalized rows. Returns (mean_recall,
    ranks) where rank is 1-based position of the positive within top-k, 0 if
    outside top-k, -1 if the positive is missing from the corpus.
    """
    id_to_row = {pid: i for i, pid in enumerate(doc_ids)}
    scores = query_mat @ doc_mat.T  # (n_queries, n_docs)
    hits = 0
    ranks: list[int] = []
    for qi in range(scores.shape[0]):
        row = scores[qi]
        pos_row = id_to_row.get(positive_ids[qi])
        if pos_row is None:
            ranks.append(-1)
            continue
        if row.shape[0] > k:
            top_unord = np.argpartition(-row, k)[:k]
        else:
            top_unord = np.arange(row.shape[0])
        top_ord = top_unord[np.argsort(-row[top_unord])]
        top_set = {int(x) for x in top_ord}
        if pos_row in top_set:
            hits += 1
            ranks.append(int(np.where(top_ord == pos_row)[0][0]) + 1)
        else:
            ranks.append(0)
    return hits / max(1, scores.shape[0]), ranks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Phase 1 dense whitening A/B (read-only)")
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument("--tei-url", default="http://localhost:8080")
    ap.add_argument("--collection", default="bsl_code_v4_late")
    ap.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--sample", type=int, default=5000, help="doc-vector sample for fit+corpus")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument(
        "--no-scope-filter",
        action="store_true",
        help="drop the CommonModules scope filter (Phase 0 generated within it)",
    )
    args = ap.parse_args()

    t0 = time.time()

    golden = json.loads(args.golden.read_text(encoding="utf-8"))
    positive_ids = [g["_meta"]["point_id"] for g in golden]
    queries = [g["query"] for g in golden]
    print(f"[load] golden: {len(golden)} semantic queries from {args.golden.name}")

    # Read-only Qdrant access (scroll + retrieve only); see qdrant-operations skill.
    client = QdrantClient(url=args.qdrant_url, timeout=180)

    scope_filter = None
    if not args.no_scope_filter:
        scope_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="module_path",
                    match=models.MatchText(text="CommonModules"),
                )
            ]
        )

    # --- Pull a doc-vector sample (fit + search corpus) -------------------
    print(
        f"[scroll] pulling up to {args.sample} dense doc vectors (scope={scope_filter is not None})"
    )
    doc_ids: list[str] = []
    doc_vecs: list[list[float]] = []
    seen: set[str] = set()
    offset = None
    while len(doc_ids) < args.sample:
        pts, offset = client.scroll(
            collection_name=args.collection,
            limit=512,
            with_payload=False,
            with_vectors=["dense"],
            scroll_filter=scope_filter,
            offset=offset,
        )
        for p in pts:
            vec = p.vector
            # Named-vector collection -> r.vector is a dict {dense, bm25}
            # (see qdrant-operations skill); take the dense arm.
            dense = vec.get("dense") if isinstance(vec, dict) else vec
            if dense is None:
                continue
            pid = str(p.id)
            if pid in seen:
                continue
            seen.add(pid)
            doc_ids.append(pid)
            doc_vecs.append(dense)
        if offset is None:
            break
    print(f"[scroll] collected {len(doc_ids)} unique doc vectors")

    # --- Force-include every golden positive so it is reachable ----------
    missing = [pid for pid in positive_ids if pid not in seen]
    if missing:
        print(f"[retrieve] force-including {len(missing)} golden positives not in sample")
        recs = client.retrieve(
            collection_name=args.collection,
            ids=missing,
            with_payload=False,
            with_vectors=["dense"],
        )
        got: set[str] = set()
        for r in recs:
            vec = r.vector
            dense = vec.get("dense") if isinstance(vec, dict) else vec
            if dense is None:
                continue
            pid = str(r.id)
            if pid in seen:
                continue
            seen.add(pid)
            doc_ids.append(pid)
            doc_vecs.append(dense)
            got.add(pid)
        still = [pid for pid in missing if pid not in got]
        if still:
            print(f"[WARN] {len(still)} positives could not be retrieved: {still[:5]}")

    present = sum(1 for pid in positive_ids if pid in seen)
    print(f"[corpus] {len(doc_ids)} docs; {present}/{len(positive_ids)} positives reachable")

    doc_raw = np.asarray(doc_vecs, dtype=np.float64)  # (n_docs, d) -- already L2 from Qdrant
    d = doc_raw.shape[1]
    print(f"[corpus] matrix {doc_raw.shape}, dim={d}")

    # --- Embed all queries via TEI (same prefix as production) -----------
    print(f"[tei] embedding {len(queries)} queries via {args.tei_url}")
    with httpx.Client() as hc:
        q_list = []
        for i, q in enumerate(queries):
            q_list.append(embed_query_tei(q, args.tei_url, hc))
            if (i + 1) % 10 == 0:
                print(f"  [tei] {i + 1}/{len(queries)}")
    query_raw = np.asarray(q_list, dtype=np.float64)  # (n_q, d)
    print(f"[tei] query matrix {query_raw.shape}")

    # --- Fit transforms on the doc sample (docs only) --------------------
    mu = doc_raw.mean(axis=0)  # shared mean for mean_center variant
    print("[fit] soft-ZCA eps=0.1 ...")
    mu_z1, w_z1 = fit_soft_zca(doc_raw, eps=0.1)
    print("[fit] soft-ZCA eps=0.01 ...")
    mu_z01, w_z01 = fit_soft_zca(doc_raw, eps=0.01)

    # --- Build the four (doc, query) transformed+normalized matrices -----
    variants: dict[str, tuple[np.ndarray, np.ndarray]] = {
        # 1) baseline: raw vectors renormalized (docs already unit; queries -> unit)
        "baseline": (l2_normalize(doc_raw.copy()), l2_normalize(query_raw.copy())),
        # 2) mean-center: subtract sample mean, renormalize
        "mean_center": (l2_normalize(doc_raw - mu), l2_normalize(query_raw - mu)),
        # 3) soft-ZCA eps=0.1
        "soft_zca_0_1": (
            l2_normalize((doc_raw - mu_z1) @ w_z1.T),
            l2_normalize((query_raw - mu_z1) @ w_z1.T),
        ),
        # 4) soft-ZCA eps=0.01
        "soft_zca_0_01": (
            l2_normalize((doc_raw - mu_z01) @ w_z01.T),
            l2_normalize((query_raw - mu_z01) @ w_z01.T),
        ),
    }

    # --- Score every variant on the identical corpus/queries -------------
    results: dict[str, float] = {}
    ranks_by_variant: dict[str, list[int]] = {}
    for name, (dmat, qmat) in variants.items():
        rec, ranks = recall_at_k_for_variant(doc_ids, dmat, qmat, positive_ids, k=args.k)
        results[name] = round(rec, 4)
        ranks_by_variant[name] = ranks
        print(f"[score] {name:<14} recall@{args.k} = {rec:.4f}")

    base = results["baseline"]

    def delta_pp(name: str) -> float:
        return round((results[name] - base) * 100, 1)

    deltas = {
        "mean_center": delta_pp("mean_center"),
        "soft_zca_0_1": delta_pp("soft_zca_0_1"),
        "soft_zca_0_01": delta_pp("soft_zca_0_01"),
    }

    # --- Verdict ----------------------------------------------------------
    best_name = max(
        ("mean_center", "soft_zca_0_1", "soft_zca_0_01"),
        key=lambda n: results[n],
    )
    best_delta = deltas[best_name]
    # golden n=50 -> 1 query == 2pp resolution; require >= 2pp to call it real.
    THRESH = 2.0
    worst_delta = min(deltas.values())

    if best_delta >= THRESH:
        eps_label = {
            "soft_zca_0_1": "eps=0.1",
            "soft_zca_0_01": "eps=0.01",
            "mean_center": "mean-centering (no eps)",
        }[best_name]
        conclusion = (
            f"HELPS: {best_name} ({eps_label}) lifts dense recall@{args.k} "
            f"{base:.3f} -> {results[best_name]:.3f} ({best_delta:+.1f}pp). "
            f"Deltas (pp): mean_center={deltas['mean_center']:+.1f}, "
            f"zca_0.1={deltas['soft_zca_0_1']:+.1f}, "
            f"zca_0.01={deltas['soft_zca_0_01']:+.1f}. "
            f"Whitening de-anisotropizes the Qwen3 BSL dense space and recovers "
            f"vocab-mismatch recall post-hoc (no re-index)."
        )
    elif worst_delta <= -THRESH:
        conclusion = (
            f"HARMS: best variant only {best_delta:+.1f}pp while at least one "
            f"transform degrades recall (worst {worst_delta:+.1f}pp). Deltas (pp): "
            f"mean_center={deltas['mean_center']:+.1f}, "
            f"zca_0.1={deltas['soft_zca_0_1']:+.1f}, "
            f"zca_0.01={deltas['soft_zca_0_01']:+.1f}. "
            f"Post-hoc whitening is NOT a safe free win on this dense space."
        )
    else:
        conclusion = (
            f"NO EFFECT: all variants within +-{THRESH:.0f}pp of baseline "
            f"({base:.3f}). Deltas (pp): mean_center={deltas['mean_center']:+.1f}, "
            f"zca_0.1={deltas['soft_zca_0_1']:+.1f}, "
            f"zca_0.01={deltas['soft_zca_0_01']:+.1f}. Mean-removal/whitening does "
            f"not move recall -- the dense collapse is not fixable by a global "
            f"linear post-transform (consistent with feedback_bsl_embedding_collapse)."
        )

    elapsed = round(time.time() - t0, 1)
    payload: dict[str, Any] = {
        "config": {
            "collection": args.collection,
            "golden_path": str(args.golden),
            "n_queries": len(golden),
            "sample_requested": args.sample,
            "corpus_size": len(doc_ids),
            "positives_reachable": f"{present}/{len(positive_ids)}",
            "dim": int(d),
            "k": args.k,
            "scope_filter": (None if args.no_scope_filter else "CommonModules"),
            "seed": args.seed,
            "tei_url": args.tei_url,
            "zca_full_eps0": "NOT APPLIED (unstable by design)",
        },
        "recall_at_k": results,
        "deltas_pp": deltas,
        "best_variant": best_name,
        "best_delta_pp": best_delta,
        "conclusion": conclusion,
        "ranks_in_topk": ranks_by_variant,
        "elapsed_s": elapsed,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== Phase 1 whitening A/B ({elapsed}s) ===")
    print(f"  baseline       recall@{args.k} = {base:.4f}")
    print(
        f"  mean_center    recall@{args.k} = {results['mean_center']:.4f}  "
        f"({deltas['mean_center']:+.1f}pp)"
    )
    print(
        f"  soft_zca_0_1   recall@{args.k} = {results['soft_zca_0_1']:.4f}  "
        f"({deltas['soft_zca_0_1']:+.1f}pp)"
    )
    print(
        f"  soft_zca_0_01  recall@{args.k} = {results['soft_zca_0_01']:.4f}  "
        f"({deltas['soft_zca_0_01']:+.1f}pp)"
    )
    print(f"\n  -> {conclusion}")
    print(f"\n[out] {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
