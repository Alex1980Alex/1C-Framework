"""
Adaptive routing and cost tracking for LLM providers.

Records quality, latency, and cost per provider.
Computes composite score for intelligent provider selection.
Tracks budget usage with configurable alerts.
"""

import logging
from dataclasses import dataclass, field

logger = logging.getLogger("llm-rotation")

# Cost per 1K tokens (input + output combined estimate)
PRICE_PER_1K_TOKENS: dict[str, float] = {
    "zai-glm5": 0.002,
    "zhipu": 0.001,
    "gemini": 0.0,
    "openrouter": 0.0,
    "mistral": 0.001,
    "ollama-local": 0.0,
    "ollama-cloud": 0.0,
}


@dataclass
class RequestOutcome:
    """Single request outcome for adaptive scoring."""
    latency: float
    tokens: int
    quality: float  # 0.0-1.0
    cost: float


@dataclass
class AdaptiveScorer:
    """Score providers based on historical performance.

    Composite: 0.4*quality + 0.3*latency_score + 0.3*cost_score.
    Requires >= min_samples outcomes before scoring (returns default_score otherwise).
    """

    min_samples: int = 5
    window_size: int = 20
    default_score: float = 0.5
    quality_weight: float = 0.4
    latency_weight: float = 0.3
    cost_weight: float = 0.3
    max_latency: float = 30.0  # seconds, for normalization
    max_cost: float = 0.01  # dollars per request, for normalization
    history: dict[str, list[RequestOutcome]] = field(default_factory=dict)

    def record(self, provider: str, latency: float, tokens: int, quality: float) -> None:
        """Record an outcome for a provider."""
        price = PRICE_PER_1K_TOKENS.get(provider, 0.0)
        cost = tokens * price / 1000.0
        outcome = RequestOutcome(latency=latency, tokens=tokens, quality=quality, cost=cost)
        self.history.setdefault(provider, []).append(outcome)

    def score(self, provider: str) -> float:
        """Compute composite score for provider (higher is better)."""
        records = self.history.get(provider, [])
        if len(records) < self.min_samples:
            return self.default_score

        recent = records[-self.window_size:]
        avg_quality = sum(r.quality for r in recent) / len(recent)
        avg_latency = sum(r.latency for r in recent) / len(recent)
        avg_cost = sum(r.cost for r in recent) / len(recent)

        latency_score = max(0.0, 1.0 - avg_latency / self.max_latency)
        cost_score = max(0.0, 1.0 - avg_cost / self.max_cost)

        return (
            self.quality_weight * avg_quality
            + self.latency_weight * latency_score
            + self.cost_weight * cost_score
        )

    def get_stats(self, provider: str) -> dict:
        """Get stats for a provider."""
        records = self.history.get(provider, [])
        if not records:
            return {"samples": 0, "score": self.default_score}
        recent = records[-self.window_size:]
        return {
            "samples": len(records),
            "score": round(self.score(provider), 4),
            "avg_quality": round(sum(r.quality for r in recent) / len(recent), 4),
            "avg_latency": round(sum(r.latency for r in recent) / len(recent), 3),
            "avg_cost": round(sum(r.cost for r in recent) / len(recent), 6),
            "total_cost": round(sum(r.cost for r in records), 6),
            "total_tokens": sum(r.tokens for r in records),
        }


@dataclass
class BudgetTracker:
    """Track token spending against budget with alerts."""

    daily_budget: float = 1.0  # dollars
    alert_threshold: float = 0.8  # warn at 80%
    _spending: dict[str, float] = field(default_factory=dict)
    _alerted: bool = False

    def record_cost(self, provider: str, cost: float) -> None:
        """Record cost and check budget."""
        self._spending[provider] = self._spending.get(provider, 0.0) + cost
        total = self.total_spent
        if not self._alerted and total >= self.daily_budget * self.alert_threshold:
            logger.warning(
                f"Budget alert: ${total:.4f} spent "
                f"({total / self.daily_budget * 100:.0f}% of ${self.daily_budget} daily budget)"
            )
            self._alerted = True

    @property
    def total_spent(self) -> float:
        return sum(self._spending.values())

    @property
    def budget_remaining(self) -> float:
        return max(0.0, self.daily_budget - self.total_spent)

    @property
    def is_over_budget(self) -> bool:
        return self.total_spent >= self.daily_budget

    def get_stats(self) -> dict:
        return {
            "daily_budget": self.daily_budget,
            "total_spent": round(self.total_spent, 6),
            "budget_remaining": round(self.budget_remaining, 6),
            "is_over_budget": self.is_over_budget,
            "per_provider": {k: round(v, 6) for k, v in self._spending.items()},
        }

    def reset(self) -> None:
        """Reset daily spending (call at start of new day)."""
        self._spending.clear()
        self._alerted = False
