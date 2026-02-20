"""Cost Budget for Model Routing (Phase 54.2).

Tracks per-request and daily costs, auto-downgrades to cheaper models
when budget limits are reached.
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Approximate cost per 1M tokens (USD) — input / output
MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-haiku-3-5": (0.25, 1.25),
}

# Fallback order: Opus → Sonnet → Haiku
_DOWNGRADE_ORDER = [
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-3-5",
]


@dataclass
class CostRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: float


@dataclass
class BudgetStatus:
    daily_spent: float
    daily_limit: float
    per_query_limit: float
    remaining_daily: float
    recommended_model: str
    is_over_budget: bool


class CostBudget:
    """Track and enforce cost budgets for LLM usage.

    Features:
        - Per-request budget limit
        - Daily budget limit
        - Auto-downgrade to cheaper model when budget is low
    """

    def __init__(
        self,
        per_query_limit: float = 0.10,  # USD
        daily_limit: float = 50.0,      # USD
    ):
        self.per_query_limit = per_query_limit
        self.daily_limit = daily_limit
        self._records: list[CostRecord] = []
        self._day_start: float = self._get_day_start()

    @staticmethod
    def _get_day_start() -> float:
        """Get Unix timestamp for the start of today (UTC)."""
        now = time.time()
        return now - (now % 86400)

    def _cleanup_old_records(self) -> None:
        """Remove records from previous days."""
        day_start = self._get_day_start()
        if day_start != self._day_start:
            self._records = [r for r in self._records if r.timestamp >= day_start]
            self._day_start = day_start

    @property
    def daily_spent(self) -> float:
        """Total cost spent today."""
        self._cleanup_old_records()
        return sum(r.cost_usd for r in self._records)

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request."""
        costs = MODEL_COSTS.get(model, (3.0, 15.0))
        input_cost = (input_tokens / 1_000_000) * costs[0]
        output_cost = (output_tokens / 1_000_000) * costs[1]
        return input_cost + output_cost

    def record_usage(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Record actual usage and return cost."""
        cost = self.estimate_cost(model, input_tokens, output_tokens)
        self._records.append(CostRecord(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=time.time(),
        ))
        return cost

    def check_budget(self, requested_model: str) -> str:
        """Check if model is within budget, downgrade if necessary.

        Returns the model to actually use (may be cheaper than requested).
        """
        self._cleanup_old_records()
        remaining = self.daily_limit - self.daily_spent

        if remaining <= 0:
            logger.warning("[BUDGET] Daily budget exhausted (spent $%.2f)", self.daily_spent)
            return _DOWNGRADE_ORDER[-1]  # Cheapest model

        # Estimate cost for typical request (~2K input, ~1K output)
        est_cost = self.estimate_cost(requested_model, 2000, 1000)

        # If single request would exceed per-query limit, downgrade
        if est_cost > self.per_query_limit:
            for cheaper in _DOWNGRADE_ORDER:
                cheaper_cost = self.estimate_cost(cheaper, 2000, 1000)
                if cheaper_cost <= self.per_query_limit:
                    if cheaper != requested_model:
                        logger.info(
                            "[BUDGET] Downgraded %s → %s (est $%.4f > limit $%.2f)",
                            requested_model, cheaper, est_cost, self.per_query_limit,
                        )
                    return cheaper
            return _DOWNGRADE_ORDER[-1]

        # If daily budget is running low (< 10%), downgrade
        if remaining < self.daily_limit * 0.1:
            for cheaper in _DOWNGRADE_ORDER:
                if cheaper == requested_model:
                    return cheaper
                # Use one step cheaper
                idx = _DOWNGRADE_ORDER.index(requested_model)
                if idx < len(_DOWNGRADE_ORDER) - 1:
                    downgraded = _DOWNGRADE_ORDER[idx + 1]
                    logger.info(
                        "[BUDGET] Low daily budget ($%.2f remaining), downgraded %s → %s",
                        remaining, requested_model, downgraded,
                    )
                    return downgraded

        return requested_model

    def get_status(self) -> BudgetStatus:
        """Get current budget status."""
        self._cleanup_old_records()
        remaining = max(0, self.daily_limit - self.daily_spent)

        # Determine recommended model based on remaining budget
        if remaining > self.daily_limit * 0.5:
            recommended = _DOWNGRADE_ORDER[0]
        elif remaining > self.daily_limit * 0.1:
            recommended = _DOWNGRADE_ORDER[1]
        else:
            recommended = _DOWNGRADE_ORDER[2]

        return BudgetStatus(
            daily_spent=round(self.daily_spent, 4),
            daily_limit=self.daily_limit,
            per_query_limit=self.per_query_limit,
            remaining_daily=round(remaining, 4),
            recommended_model=recommended,
            is_over_budget=remaining <= 0,
        )
