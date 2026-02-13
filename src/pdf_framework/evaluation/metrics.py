"""Ranking metrics for retrieval evaluation.

Pure functions — no LLM dependency. All functions operate on lists of
retrieved chunk IDs vs. ground-truth relevant IDs.
"""

import math


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Fraction of retrieved documents (top-k) that are relevant."""
    if k <= 0 or not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_set = set(relevant_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / k


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Fraction of relevant documents found in top-k results."""
    if k <= 0 or not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_set = set(relevant_ids)
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / len(relevant_set)


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """Mean Reciprocal Rank — 1/rank of the first relevant result."""
    relevant_set = set(relevant_ids)
    for rank, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in relevant_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """Normalized Discounted Cumulative Gain at k.

    Uses binary relevance (1 if relevant, 0 otherwise).
    """
    if k <= 0 or not relevant_ids:
        return 0.0
    relevant_set = set(relevant_ids)

    # DCG
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        if doc_id in relevant_set:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because rank starts at 1

    # Ideal DCG: all relevant docs at the top
    ideal_hits = min(len(relevant_set), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    return dcg / idcg if idcg > 0 else 0.0


def average_precision(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """Average Precision — mean of precision values at each relevant hit."""
    if not relevant_ids:
        return 0.0
    relevant_set = set(relevant_ids)
    hits = 0
    sum_precision = 0.0
    for rank, doc_id in enumerate(retrieved_ids, 1):
        if doc_id in relevant_set:
            hits += 1
            sum_precision += hits / rank
    return sum_precision / len(relevant_set) if relevant_set else 0.0
