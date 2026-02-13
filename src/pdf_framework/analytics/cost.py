"""Cost tracking for LLM API usage (Phase 40).

Estimates costs per query, per agent, per session based on token counts.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Cost per 1M tokens (USD) as of 2026
_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0},
    "claude-haiku-3-5-20241022": {"input": 0.8, "output": 4.0},
}


class CostTracker:
    """Estimate and track API costs."""

    def __init__(self) -> None:
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._total_cost_usd: float = 0.0
        self._by_model: dict[str, dict[str, float]] = {}

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Record token usage and return estimated cost (USD)."""
        pricing = _PRICING.get(model)
        if pricing is None:
            # Estimate based on sonnet pricing
            pricing = _PRICING["claude-sonnet-4-5-20250929"]

        cost_input = (input_tokens / 1_000_000) * pricing["input"]
        cost_output = (output_tokens / 1_000_000) * pricing["output"]
        total = cost_input + cost_output

        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cost_usd += total

        if model not in self._by_model:
            self._by_model[model] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
            }
        self._by_model[model]["input_tokens"] += input_tokens
        self._by_model[model]["output_tokens"] += output_tokens
        self._by_model[model]["cost_usd"] += total

        return total

    def get_stats(self) -> dict[str, Any]:
        """Get cost summary."""
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "total_cost_usd": round(self._total_cost_usd, 4),
            "by_model": {
                model: {
                    "input_tokens": int(data["input_tokens"]),
                    "output_tokens": int(data["output_tokens"]),
                    "cost_usd": round(data["cost_usd"], 4),
                }
                for model, data in self._by_model.items()
            },
        }

    @staticmethod
    def estimate_cost(
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost without recording."""
        pricing = _PRICING.get(model, _PRICING["claude-sonnet-4-5-20250929"])
        return (
            (input_tokens / 1_000_000) * pricing["input"]
            + (output_tokens / 1_000_000) * pricing["output"]
        )
