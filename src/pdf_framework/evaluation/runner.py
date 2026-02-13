"""Evaluation benchmark runner.

Phase 4: Runs an EvalDataset against a search strategy, computes ranking
metrics, and optionally evaluates RAG quality via the RAG Triad.
"""

import logging
import time
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from src.pdf_framework.evaluation.dataset import EvalDataset
from src.pdf_framework.evaluation.metrics import (
    average_precision,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from src.pdf_framework.evaluation.rag_evaluator import RAGEvaluator
from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)


class EvalReport(BaseModel):
    """Aggregated evaluation report."""

    dataset_name: str
    strategy: str
    num_queries: int
    precision_at_5: float = 0.0
    recall_at_5: float = 0.0
    mrr: float = 0.0
    ndcg_at_10: float = 0.0
    map_score: float = 0.0
    context_relevance: float | None = None
    groundedness: float | None = None
    answer_relevance: float | None = None
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    details: list[dict[str, Any]] = Field(default_factory=list)


class EvalRunner:
    """Run evaluation benchmarks against a search strategy."""

    def __init__(
        self,
        search_manager: SearchManager,
        rag_evaluator: RAGEvaluator | None = None,
        qa_chain: Any = None,
    ):
        self._search_manager = search_manager
        self._rag_evaluator = rag_evaluator
        self._qa_chain = qa_chain

    async def run(
        self,
        dataset: EvalDataset,
        strategy: str = "vector",
        k: int = 5,
    ) -> EvalReport:
        """Run all test cases and aggregate metrics."""
        precisions: list[float] = []
        recalls: list[float] = []
        mrrs: list[float] = []
        ndcgs: list[float] = []
        aps: list[float] = []
        latencies: list[float] = []

        ctx_relevances: list[float] = []
        groundedness_scores: list[float] = []
        answer_relevances: list[float] = []

        details: list[dict[str, Any]] = []

        for case in dataset.test_cases:
            start = time.perf_counter()

            response = await self._search_manager.search(
                query=case.query,
                strategy=strategy,
                k=k,
            )

            latency = (time.perf_counter() - start) * 1000
            latencies.append(latency)

            retrieved_ids = [r.chunk.id for r in response.results]

            # Ranking metrics
            p = precision_at_k(retrieved_ids, case.relevant_chunk_ids, k)
            r = recall_at_k(retrieved_ids, case.relevant_chunk_ids, k)
            m = mrr(retrieved_ids, case.relevant_chunk_ids)
            n = ndcg_at_k(retrieved_ids, case.relevant_chunk_ids, 10)
            ap = average_precision(retrieved_ids, case.relevant_chunk_ids)

            precisions.append(p)
            recalls.append(r)
            mrrs.append(m)
            ndcgs.append(n)
            aps.append(ap)

            detail: dict[str, Any] = {
                "query": case.query,
                "category": case.category,
                "precision_at_k": p,
                "recall_at_k": r,
                "mrr": m,
                "ndcg_at_10": n,
                "average_precision": ap,
                "latency_ms": latency,
                "retrieved_ids": retrieved_ids,
            }

            # RAG Triad evaluation (optional)
            if self._rag_evaluator and self._qa_chain:
                contexts = [r.chunk.content for r in response.results]
                answer = await self._qa_chain.answer(case.query, response)

                ctx_rel = await self._rag_evaluator.evaluate_context_relevance(
                    case.query, contexts,
                )
                grounded = await self._rag_evaluator.evaluate_groundedness(
                    answer, contexts,
                )
                ans_rel = await self._rag_evaluator.evaluate_answer_relevance(
                    case.query, answer,
                )

                ctx_relevances.append(ctx_rel)
                groundedness_scores.append(grounded)
                answer_relevances.append(ans_rel)

                detail["context_relevance"] = ctx_rel
                detail["groundedness"] = grounded
                detail["answer_relevance"] = ans_rel
                detail["answer"] = answer

            details.append(detail)

        latencies_arr = np.array(latencies) if latencies else np.array([0.0])

        report = EvalReport(
            dataset_name=dataset.name,
            strategy=strategy,
            num_queries=len(dataset.test_cases),
            precision_at_5=float(np.mean(precisions)) if precisions else 0.0,
            recall_at_5=float(np.mean(recalls)) if recalls else 0.0,
            mrr=float(np.mean(mrrs)) if mrrs else 0.0,
            ndcg_at_10=float(np.mean(ndcgs)) if ndcgs else 0.0,
            map_score=float(np.mean(aps)) if aps else 0.0,
            avg_latency_ms=float(np.mean(latencies_arr)),
            p95_latency_ms=float(np.percentile(latencies_arr, 95)),
            details=details,
        )

        if ctx_relevances:
            report.context_relevance = float(np.mean(ctx_relevances))
        if groundedness_scores:
            report.groundedness = float(np.mean(groundedness_scores))
        if answer_relevances:
            report.answer_relevance = float(np.mean(answer_relevances))

        return report
