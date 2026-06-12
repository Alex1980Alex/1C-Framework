"""Golden eval v23 (pdf_documents) + v24 (wiki_pages_v1) — baseline & acceptance runner.

Roadmap 260612 pdf-docs full verification, P0.2 (B5-baseline) + P4 acceptance.

Прогоняет golden_v1 items с target_collection in {pdf_documents, wiki_pages_v1}:
TEI Qwen3 embed (4096d, Instruct-prefix) → truncate+renorm до dim коллекции
(alias → physical resolve) → query_points → NDCG@10 + chunk-recall@10 +
keyword-recall@10.

Usage:
    python scripts/eval_pdf_docs_golden.py [--report data/eval/pdf_docs_golden_baseline.json]
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _eval_common import QDRANT_URL, embed_query

REPO = Path(__file__).resolve().parent.parent
GOLDEN_PATH = REPO / "data" / "eval" / "golden_v1.json"
COLLECTIONS = ("pdf_documents", "wiki_pages_v1")
TOP_K = 10


def ndcg_at_k(retrieved: list[str], expected: set[str], k: int = TOP_K) -> float:
    dcg = 0.0
    for rank, rid in enumerate(retrieved[:k], 1):
        if rid in expected:
            dcg += 1.0 / math.log2(rank + 1)
    ideal = min(len(expected), k)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal + 1))
    return dcg / idcg if idcg else 0.0


def truncate_renorm(vec: list[float], dim: int) -> list[float]:
    arr = np.asarray(vec[:dim], dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def resolve_dim(http: httpx.Client, collection: str) -> int:
    """Alias-aware: collection info endpoint works for aliases too."""
    resp = http.get(f"{QDRANT_URL}/collections/{collection}")
    resp.raise_for_status()
    vectors = resp.json()["result"]["config"]["params"]["vectors"]
    if isinstance(vectors, dict) and "size" in vectors:
        return int(vectors["size"])
    # named vectors → берём dense
    dense = vectors.get("dense") or next(iter(vectors.values()))
    return int(dense["size"])


def keyword_recall(hits_payloads: list[dict[str, Any]], keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    blob = " ".join(
        str(p.get("content") or p.get("text") or "") + " " + str(p.get("title") or "")
        for p in hits_payloads
    ).lower()
    found = sum(1 for kw in keywords if kw.lower() in blob)
    return found / len(keywords)


def run_eval(report_path: Path | None) -> dict[str, Any]:
    golden = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "golden_version": golden.get("version"),
        "top_k": TOP_K,
        "collections": {},
    }

    with httpx.Client(timeout=60.0) as http:
        for coll in COLLECTIONS:
            items = [i for i in golden["items"] if i.get("target_collection") == coll]
            dim = resolve_dim(http, coll)
            ndcgs: list[float] = []
            chunk_recalls: list[float] = []
            kw_recalls: list[float] = []
            errors: list[str] = []
            for item in items:
                try:
                    vec = truncate_renorm(embed_query(item["query"], http), dim)
                    resp = http.post(
                        f"{QDRANT_URL}/collections/{coll}/points/query",
                        json={"query": vec, "limit": TOP_K, "with_payload": True},
                    )
                    resp.raise_for_status()
                    points = resp.json()["result"]["points"]
                except (httpx.HTTPError, KeyError) as e:
                    errors.append(f"{item['id']}: {type(e).__name__}: {e}")
                    continue
                retrieved = [str(p["id"]) for p in points]
                payloads = [p.get("payload") or {} for p in points]
                expected = {str(x) for x in item.get("expected_chunk_ids") or []}
                if expected:
                    ndcgs.append(ndcg_at_k(retrieved, expected))
                    chunk_recalls.append(
                        len(expected & set(retrieved)) / len(expected)
                    )
                kw_recalls.append(keyword_recall(payloads, item.get("expected_keywords") or []))

            report["collections"][coll] = {
                "dim": dim,
                "items_total": len(items),
                "items_with_gt": len(ndcgs),
                "ndcg_at_10": round(sum(ndcgs) / len(ndcgs), 4) if ndcgs else None,
                "chunk_recall_at_10": round(sum(chunk_recalls) / len(chunk_recalls), 4)
                if chunk_recalls
                else None,
                "keyword_recall_at_10": round(sum(kw_recalls) / len(kw_recalls), 4)
                if kw_recalls
                else None,
                "errors": errors,
            }

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=None, help="Write JSON report")
    args = parser.parse_args()
    report = run_eval(args.report)
    out = json.dumps(report, ensure_ascii=False, indent=2)
    sys.stdout.buffer.write(out.encode("utf-8") + b"\n")
    failed = any(
        c["errors"] or c["items_with_gt"] == 0 for c in report["collections"].values()
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
