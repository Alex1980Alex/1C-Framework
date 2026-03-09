"""
BSL Search Evaluation Metrics — Phase 58

Implements standard IR metrics: Recall@k, Precision@k, MRR, nDCG.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class EvalResult:
    """Result of evaluating one query."""

    query_id: str
    query: str
    category: str
    expected: List[str]
    retrieved: List[str]
    recall_5: float = 0.0
    recall_10: float = 0.0
    precision_5: float = 0.0
    mrr_val: float = 0.0
    ndcg_val: float = 0.0


def recall_at_k(retrieved: List[str], expected: Set[str], k: int) -> float:
    """Fraction of expected results found in top-k retrieved."""
    if not expected:
        return 0.0
    top_k = set(retrieved[:k])
    found = top_k & expected
    return len(found) / len(expected)


def precision_at_k(retrieved: List[str], expected: Set[str], k: int) -> float:
    """Fraction of top-k results that are relevant."""
    if k == 0:
        return 0.0
    top_k = retrieved[:k]
    relevant = sum(1 for r in top_k if r in expected)
    return relevant / k


def mrr(retrieved: List[str], expected: Set[str]) -> float:
    """Mean Reciprocal Rank — 1/rank of first relevant result."""
    for i, item in enumerate(retrieved):
        if item in expected:
            return 1.0 / (i + 1)
    return 0.0


def ndcg(retrieved: List[str], expected: Set[str], k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain at k."""
    if not expected:
        return 0.0

    # DCG
    dcg = 0.0
    for i, item in enumerate(retrieved[:k]):
        rel = 1.0 if item in expected else 0.0
        dcg += rel / math.log2(i + 2)  # i+2 because log2(1)=0

    # Ideal DCG (all relevant items at top)
    ideal_count = min(len(expected), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_count))

    return dcg / idcg if idcg > 0 else 0.0


def _normalize(s: str) -> str:
    """Normalize string for matching: lowercase, strip whitespace."""
    return s.strip().lower()


def _fuzzy_match(retrieved_item: str, expected_set: Set[str]) -> bool:
    """Check if retrieved item matches any expected (substring or exact)."""
    r = _normalize(retrieved_item)
    for e in expected_set:
        en = _normalize(e)
        if en in r or r in en or en == r:
            return True
    return False


def _build_fuzzy_set(retrieved: List[str], expected_set: Set[str]) -> List[str]:
    """Convert retrieved items: matched items become their expected name."""
    result = []
    for item in retrieved:
        r = _normalize(item)
        matched = None
        for e in expected_set:
            en = _normalize(e)
            if en in r or r in en or en == r:
                matched = e
                break
        result.append(matched if matched else item)
    return result


def evaluate_single(
    query_id: str,
    query: str,
    category: str,
    retrieved: List[str],
    expected: List[str],
) -> EvalResult:
    """Evaluate a single query against expected results."""
    expected_set = set(expected)
    # Use fuzzy matching: substring containment
    retrieved = _build_fuzzy_set(retrieved, expected_set)
    return EvalResult(
        query_id=query_id,
        query=query,
        category=category,
        expected=expected,
        retrieved=retrieved[:10],
        recall_5=recall_at_k(retrieved, expected_set, 5),
        recall_10=recall_at_k(retrieved, expected_set, 10),
        precision_5=precision_at_k(retrieved, expected_set, 5),
        mrr_val=mrr(retrieved, expected_set),
        ndcg_val=ndcg(retrieved, expected_set, 10),
    )


def aggregate_results(results: List[EvalResult]) -> Dict[str, Any]:
    """Aggregate eval results into summary statistics."""
    if not results:
        return {"error": "No results to aggregate"}

    total = len(results)
    avg = lambda vals: sum(vals) / len(vals) if vals else 0.0

    summary = {
        "total_queries": total,
        "recall_5": avg([r.recall_5 for r in results]),
        "recall_10": avg([r.recall_10 for r in results]),
        "precision_5": avg([r.precision_5 for r in results]),
        "mrr": avg([r.mrr_val for r in results]),
        "ndcg_10": avg([r.ndcg_val for r in results]),
        "zero_recall_count": sum(1 for r in results if r.recall_10 == 0.0),
    }

    # Per-category breakdown
    categories: Dict[str, List[EvalResult]] = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    summary["by_category"] = {}
    for cat, cat_results in sorted(categories.items()):
        summary["by_category"][cat] = {
            "count": len(cat_results),
            "recall_5": avg([r.recall_5 for r in cat_results]),
            "recall_10": avg([r.recall_10 for r in cat_results]),
            "mrr": avg([r.mrr_val for r in cat_results]),
            "ndcg_10": avg([r.ndcg_val for r in cat_results]),
        }

    return summary


def format_report(summary: Dict[str, Any], title: str = "BSL Search Eval") -> str:
    """Format summary as markdown report."""
    lines = [f"# {title}", ""]

    lines.append("## Overall Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Total queries | {summary['total_queries']} |")
    lines.append(f"| Recall@5 | {summary['recall_5']:.4f} |")
    lines.append(f"| Recall@10 | {summary['recall_10']:.4f} |")
    lines.append(f"| Precision@5 | {summary['precision_5']:.4f} |")
    lines.append(f"| MRR | {summary['mrr']:.4f} |")
    lines.append(f"| nDCG@10 | {summary['ndcg_10']:.4f} |")
    lines.append(f"| Zero recall queries | {summary['zero_recall_count']} |")
    lines.append("")

    if "by_category" in summary:
        lines.append("## By Category")
        lines.append("")
        lines.append("| Category | Count | Recall@5 | Recall@10 | MRR | nDCG@10 |")
        lines.append("|----------|-------|----------|-----------|-----|---------|")
        for cat, stats in summary["by_category"].items():
            lines.append(
                f"| {cat} | {stats['count']} | "
                f"{stats['recall_5']:.4f} | {stats['recall_10']:.4f} | "
                f"{stats['mrr']:.4f} | {stats['ndcg_10']:.4f} |"
            )
        lines.append("")

    return "\n".join(lines)
