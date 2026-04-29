"""Phase 8.12.8 Step 5: eval harness for 3 retrieval arms vs golden set."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Protocol, Set

import httpx
from qdrant_client import QdrantClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase8_12_8 import config  # noqa: E402


class EmbedBackend(Protocol):
    def embed_query(self, text: str) -> List[float]: ...


class E5Backend:
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large") -> None:
        self.model_name = model_name
        self._model: Any = None

    def _load(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def embed_query(self, text: str) -> List[float]:
        self._load()
        return self._model.encode("query: " + text).tolist()


class TEIBackend:
    INSTRUCTION = (
        "Instruct: Given a web search query, retrieve relevant passages "
        "that answer the query\nQuery: "
    )

    def __init__(self, base_url: str = "http://localhost:8080") -> None:
        self.base_url = base_url.rstrip("/")

    def embed_query(self, text: str) -> List[float]:
        r = httpx.post(f"{self.base_url}/embed", json={
            "inputs": [self.INSTRUCTION + text], "normalize": True,
            "truncate": True, "truncation_direction": "Right",
        }, timeout=60.0)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data[0]
        if isinstance(data, dict) and "embeddings" in data:
            return data["embeddings"][0]
        raise ValueError(f"Unexpected TEI shape: {type(data).__name__}")


class Qwen3STBackend:
    def __init__(self, model_dir: str = "D:/hf-manual/Qwen3-Embedding-8B") -> None:
        self.model_dir = model_dir
        self._model: Any = None

    def _load(self) -> None:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_dir)

    def embed_query(self, text: str) -> List[float]:
        self._load()
        return self._model.encode(text, prompt_name="query").tolist()


def recall_at_k(retrieved: List[str], positives: Set[str], k: int = 10) -> float:
    if not positives:
        return 0.0
    return len(set(retrieved[:k]) & positives) / len(positives)


def mrr(retrieved: List[str], positives: Set[str]) -> float:
    for rank, rid in enumerate(retrieved):
        if rid in positives:
            return 1.0 / (rank + 1)
    return 0.0


def ndcg_at_k(retrieved: List[str], graded: Dict[str, int], k: int = 10) -> float:
    dcg = sum(graded.get(rid, 0) / math.log2(i + 2) for i, rid in enumerate(retrieved[:k]))
    ideal = sorted(graded.values(), reverse=True)[:k]
    idcg = sum(rel / math.log2(i + 2) for i, rel in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


def eval_arm(name: str, collection: str, backend: EmbedBackend,
             golden_path: Path, k: int = 10) -> Dict[str, Any]:
    client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT, timeout=30)
    golden: List[Dict[str, Any]] = []
    with open(golden_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                golden.append(json.loads(line))

    sum_recall = sum_mrr = sum_ndcg = 0.0
    n = len(golden)
    for item in golden:
        positives = set(item.get("secondary_positives", []))
        positives.add(item["primary_positive"])
        graded = {str(k_): int(v) for k_, v in item.get("graded", {}).items()}

        vec = backend.embed_query(item["query"])
        points = client.query_points(
            collection_name=collection, query=vec, limit=k, with_payload=False,
        ).points
        retrieved = [str(p.id) for p in points]
        sum_recall += recall_at_k(retrieved, positives, k)
        sum_mrr += mrr(retrieved, positives)
        sum_ndcg += ndcg_at_k(retrieved, graded, k)

    return {
        "arm": name, "collection": collection, "n_queries": n,
        "recall@10": sum_recall / n if n else 0.0,
        "ndcg@10": sum_ndcg / n if n else 0.0,
        "mrr": sum_mrr / n if n else 0.0,
    }


# Arm → (collection, backend factory). qwen3 was indexed via TEI;
# qwen3-late via qwen3-st (Late Chunking incompatible with TEI).
ARMS = {
    "e5": (config.COLL_E5, lambda: E5Backend()),
    "qwen3": (config.COLL_QWEN3, lambda: TEIBackend()),
    "qwen3-late": (config.COLL_QWEN3_LATE, lambda: Qwen3STBackend()),
}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--golden", type=Path, default=config.GOLDEN_SET)
    p.add_argument("--output", type=Path, default=config.EVAL_REPORT)
    p.add_argument("--skip-arm", action="append", choices=list(ARMS), default=[])
    args = p.parse_args()

    results: List[Dict[str, Any]] = []
    for arm, (coll, factory) in ARMS.items():
        if arm in args.skip_arm:
            print(f"[skip] {arm}")
            continue
        print(f"[eval] {arm} → {coll}")
        results.append(eval_arm(arm, coll, factory(), args.golden))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print(f"{'arm':<14}{'collection':<22}{'n':<5}{'recall@10':<12}{'ndcg@10':<12}{'mrr':<10}")
    print("-" * 70)
    for r in results:
        print(f"{r['arm']:<14}{r['collection']:<22}{r['n_queries']:<5}"
              f"{r['recall@10']:<12.4f}{r['ndcg@10']:<12.4f}{r['mrr']:<10.4f}")
    print("=" * 70)
    print(f"Report → {args.output}")


if __name__ == "__main__":
    main()
