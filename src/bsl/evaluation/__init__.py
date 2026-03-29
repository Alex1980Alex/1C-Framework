"""
BSL Evaluation — Phase 58

Metrics and evaluation runner for BSL code search quality.
"""

from .metrics import EvalResult, mrr, ndcg, precision_at_k, recall_at_k

__all__ = ["recall_at_k", "mrr", "ndcg", "precision_at_k", "EvalResult"]
