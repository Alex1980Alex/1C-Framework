"""AutoRAG Runner — executes grid search experiments (Phase 20).

Author: Claude Code
Version: 1.0.0 - Phase 20: AutoRAG Optimization
"""

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from src.pdf_framework.evaluation.autorag import ParameterGrid

logger = logging.getLogger(__name__)


class GridResult(BaseModel):
    """Result of a single grid experiment."""

    config: dict[str, Any] = Field(default_factory=dict)
    mrr: float = 0.0
    recall: float = 0.0
    precision: float = 0.0
    latency_ms: float = 0.0
    errors: list[str] = Field(default_factory=list)


class AutoRAGRunner:
    """Run grid search over RAG configurations."""

    def __init__(self, components: Any = None, benchmark: Any = None):
        self._components = components
        self._benchmark = benchmark

    async def run_grid(self, grid: ParameterGrid) -> list[GridResult]:
        """Execute all configurations in the grid."""
        configs = grid.configs()
        results: list[GridResult] = []

        for i, cfg in enumerate(configs):
            logger.info(f"[AUTORAG] Running config {i + 1}/{len(configs)}: {cfg}")
            t0 = time.time()

            try:
                # If components are available, run real search
                if self._components and self._benchmark:
                    result = await self._run_real(cfg)
                else:
                    # Simulation mode
                    result = self._simulate(cfg)

                result.latency_ms = (time.time() - t0) * 1000
                results.append(result)

            except Exception as e:
                results.append(GridResult(
                    config=cfg,
                    errors=[str(e)],
                    latency_ms=(time.time() - t0) * 1000,
                ))

        return results

    async def _run_real(self, config: dict[str, Any]) -> GridResult:
        """Run a real search experiment."""
        search_manager = self._components.search_manager
        strategy = config.get("strategy", "vector")
        k = config.get("k", 5)

        hits = 0
        total = 0
        mrr_sum = 0.0

        for item in self._benchmark:
            question = item.get("question", "")
            expected_keywords = item.get("relevant_keywords", [])

            response = await search_manager.search(query=question, strategy=strategy, k=k)

            for rank, r in enumerate(response.results, 1):
                content_lower = r.chunk.content.lower()
                if any(kw.lower() in content_lower for kw in expected_keywords):
                    hits += 1
                    mrr_sum += 1.0 / rank
                    break
            total += 1

        recall = hits / total if total else 0.0
        mrr = mrr_sum / total if total else 0.0

        return GridResult(config=config, mrr=mrr, recall=recall, precision=recall)

    def _simulate(self, config: dict[str, Any]) -> GridResult:
        """Simulate experiment results for testing."""
        import random

        # Better strategies get slightly better scores
        strategy_bonus = {
            "vector": 0.0,
            "hybrid": 0.1,
            "bm25": 0.05,
            "graphrag_local": 0.08,
        }
        bonus = strategy_bonus.get(config.get("strategy", ""), 0.0)
        base = 0.5 + bonus + random.uniform(-0.1, 0.1)

        return GridResult(
            config=config,
            mrr=max(0, min(1, base)),
            recall=max(0, min(1, base * 0.9)),
            precision=max(0, min(1, base * 0.85)),
        )
