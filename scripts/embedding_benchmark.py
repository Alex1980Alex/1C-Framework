"""Embedding Benchmark Script (Phase 47).

Compares embedding models on retrieval quality metrics:
- recall@5, recall@10
- MRR (Mean Reciprocal Rank)
- NDCG@10 (Normalized Discounted Cumulative Gain)

Usage:
    # Benchmark current model
    python scripts/embedding_benchmark.py

    # Benchmark specific provider
    python scripts/embedding_benchmark.py --provider jina --jina-key jina_xxxxx

    # Compare two providers
    python scripts/embedding_benchmark.py --compare local jina --jina-key jina_xxxxx

    # Custom dataset
    python scripts/embedding_benchmark.py --dataset data/eval/my_dataset.json
"""

import argparse
import asyncio
import json
import logging
import math
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pdf_framework.config import EmbeddingSettings, get_settings
from src.pdf_framework.embeddings import get_embedding_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

_DEFAULT_DATASET = project_root / "data" / "eval" / "embedding_benchmark.json"
_RESULTS_DIR = project_root / "data" / "eval"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _recall_at_k(relevant: set[int], retrieved: list[int], k: int) -> float:
    retrieved_k = set(retrieved[:k])
    if not relevant:
        return 0.0
    return len(relevant & retrieved_k) / len(relevant)


def _mrr(relevant: set[int], retrieved: list[int]) -> float:
    for i, idx in enumerate(retrieved):
        if idx in relevant:
            return 1.0 / (i + 1)
    return 0.0


def _ndcg_at_k(relevant: set[int], retrieved: list[int], k: int) -> float:
    dcg = 0.0
    for i, idx in enumerate(retrieved[:k]):
        if idx in relevant:
            dcg += 1.0 / math.log2(i + 2)
    # Ideal DCG
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg == 0:
        return 0.0
    return dcg / idcg


async def run_benchmark(
    provider: str,
    dataset_path: Path,
    jina_key: str = "",
    jina_truncate_dim: int | None = None,
) -> dict:
    """Run embedding benchmark for a given provider."""
    settings_kwargs: dict = {"provider": provider}
    if provider == "jina":
        settings_kwargs["jina_api_key"] = jina_key
        settings_kwargs["model"] = "jina-embeddings-v3"
        if jina_truncate_dim:
            settings_kwargs["jina_truncate_dim"] = jina_truncate_dim

    settings = EmbeddingSettings(**settings_kwargs)
    engine = get_embedding_engine(settings)

    logger.info("Loading dataset from %s", dataset_path)
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    queries = dataset["queries"]
    corpus = dataset["corpus"]

    logger.info("Provider: %s, Model: %s, Dims: %d",
                provider, engine.get_model_name(), engine.get_dimensions())
    logger.info("Corpus: %d passages, Queries: %d", len(corpus), len(queries))

    # Embed corpus
    t0 = time.perf_counter()
    corpus_texts = [c["text"] for c in corpus]
    corpus_embeddings = await engine.embed_batch(corpus_texts)
    embed_time = time.perf_counter() - t0
    logger.info("Corpus embedded in %.2fs (%.0f texts/sec)",
                embed_time, len(corpus_texts) / embed_time if embed_time > 0 else 0)

    # Evaluate each query
    recall_5_scores = []
    recall_10_scores = []
    mrr_scores = []
    ndcg_10_scores = []

    for q in queries:
        query_emb = await engine.embed_text(q["query"])
        relevant_ids = set(q["relevant_indices"])

        # Compute similarities
        sims = [
            (i, _cosine_similarity(query_emb, ce))
            for i, ce in enumerate(corpus_embeddings)
        ]
        sims.sort(key=lambda x: x[1], reverse=True)
        retrieved = [idx for idx, _ in sims]

        recall_5_scores.append(_recall_at_k(relevant_ids, retrieved, 5))
        recall_10_scores.append(_recall_at_k(relevant_ids, retrieved, 10))
        mrr_scores.append(_mrr(relevant_ids, retrieved))
        ndcg_10_scores.append(_ndcg_at_k(relevant_ids, retrieved, 10))

    # Close engine if needed
    if hasattr(engine, "close"):
        await engine.close()

    results = {
        "provider": provider,
        "model": engine.get_model_name(),
        "dimensions": engine.get_dimensions(),
        "corpus_size": len(corpus),
        "query_count": len(queries),
        "embed_time_sec": round(embed_time, 2),
        "metrics": {
            "recall@5": round(sum(recall_5_scores) / len(recall_5_scores), 4),
            "recall@10": round(sum(recall_10_scores) / len(recall_10_scores), 4),
            "mrr": round(sum(mrr_scores) / len(mrr_scores), 4),
            "ndcg@10": round(sum(ndcg_10_scores) / len(ndcg_10_scores), 4),
        },
    }

    logger.info("Results for %s:", provider)
    for metric, value in results["metrics"].items():
        logger.info("  %s: %.4f", metric, value)

    return results


async def main():
    parser = argparse.ArgumentParser(description="Embedding Benchmark (Phase 47)")
    parser.add_argument("--provider", default="local", help="Embedding provider (local/jina/giga)")
    parser.add_argument("--dataset", type=Path, default=_DEFAULT_DATASET, help="Dataset JSON path")
    parser.add_argument("--jina-key", default="", help="Jina API key")
    parser.add_argument("--jina-truncate-dim", type=int, default=None, help="Jina Matryoshka dim (512/256)")
    parser.add_argument("--compare", nargs="+", help="Compare multiple providers")
    parser.add_argument("--output", type=Path, default=None, help="Output JSON path")
    args = parser.parse_args()

    if not args.dataset.exists():
        logger.error("Dataset not found: %s", args.dataset)
        logger.info("Create a benchmark dataset with format:")
        logger.info('  {"corpus": [{"text": "..."}], "queries": [{"query": "...", "relevant_indices": [0,1]}]}')
        sys.exit(1)

    if args.compare:
        all_results = {}
        for prov in args.compare:
            results = await run_benchmark(prov, args.dataset, args.jina_key, args.jina_truncate_dim)
            all_results[prov] = results

        # Comparison table
        logger.info("\n=== Comparison ===")
        header = f"{'Metric':<12}"
        for prov in args.compare:
            header += f" {prov:>10}"
        logger.info(header)
        logger.info("-" * len(header))

        for metric in ["recall@5", "recall@10", "mrr", "ndcg@10"]:
            row = f"{metric:<12}"
            for prov in args.compare:
                val = all_results[prov]["metrics"][metric]
                row += f" {val:>10.4f}"
            logger.info(row)

        output = args.output or _RESULTS_DIR / "embedding_comparison.json"
    else:
        all_results = await run_benchmark(args.provider, args.dataset, args.jina_key, args.jina_truncate_dim)
        output = args.output or _RESULTS_DIR / f"embedding_baseline_{args.provider}.json"

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    logger.info("Results saved to %s", output)


if __name__ == "__main__":
    asyncio.run(main())
