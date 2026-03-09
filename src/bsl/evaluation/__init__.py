"""
BSL Evaluation — Phase 58

Metrics and evaluation runner for BSL code search quality.
"""

from .metrics import recall_at_k, mrr, ndcg, precision_at_k, EvalResult

__all__ = ["recall_at_k", "mrr", "ndcg", "precision_at_k", "EvalResult"]
