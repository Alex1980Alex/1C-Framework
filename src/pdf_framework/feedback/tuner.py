"""Strategy Tuner for Self-Learning (Phase 22.4).

Automatically tunes RAG strategy weights based on user feedback.
Implements adaptive strategy selection.

Based on Vanna AI's feedback-driven optimization.

Author: Claude Code
Version: 1.0.0 - Phase 22: Self-Learning Feedback Loop
"""

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.pdf_framework.config import Settings, get_settings
from src.pdf_framework.feedback.collector import FeedbackCollector, FeedbackStats

logger = logging.getLogger(__name__)


class StrategyWeights(BaseModel):
    """Weights for different RAG strategies."""

    vector: float = 0.5
    hybrid: float = 0.3
    graphrag_local: float = 0.1
    graphrag_global: float = 0.1
    two_stage: float = 0.0

    def normalize(self) -> "StrategyWeights":
        """Normalize weights to sum to 1.0."""
        total = sum([self.vector, self.hybrid, self.graphrag_local, self.graphrag_global, self.two_stage])

        if total == 0:
            return StrategyWeights()

        return StrategyWeights(
            vector=self.vector / total,
            hybrid=self.hybrid / total,
            graphrag_local=self.graphrag_local / total,
            graphrag_global=self.graphrag_global / total,
            two_stage=self.two_stage / total,
        )


class StrategyTuner:
    """Tunes strategy weights based on feedback performance."""

    def __init__(
        self,
        feedback_collector: FeedbackCollector | None = None,
        settings: Settings | None = None,
    ):
        """Initialize the strategy tuner.

        Args:
            feedback_collector: Feedback collector instance
            settings: Application settings
        """
        self._collector = feedback_collector or FeedbackCollector(settings=settings)
        self._settings = settings or get_settings()
        self._weights_path = self._settings.data_dir / "strategy_weights.json"

        # Load current weights
        self._current_weights = self._load_weights()

    def _load_weights(self) -> StrategyWeights:
        """Load current strategy weights from file.

        Returns:
            StrategyWeights object
        """
        if self._weights_path.exists():
            try:
                data = json.loads(self._weights_path.read_text(encoding="utf-8"))
                return StrategyWeights(**data)
            except Exception as e:
                logger.warning(f"[TUNER] Failed to load weights: {e}")

        # Default weights
        return StrategyWeights()

    def _save_weights(self, weights: StrategyWeights):
        """Save strategy weights to file.

        Args:
            weights: StrategyWeights to save
        """
        self._weights_path.write_text(
            json.dumps(weights.model_dump(), indent=2),
            encoding="utf-8",
        )
        logger.info(f"[TUNER] Saved weights to {self._weights_path}")

    def tune_weights(
        self,
        min_samples: int = 20,
        learning_rate: float = 0.1,
    ) -> StrategyWeights:
        """Tune strategy weights based on feedback.

        Args:
            min_samples: Minimum feedback samples per strategy
            learning_rate: How much to adjust weights (0-1)

        Returns:
            Updated StrategyWeights
        """
        stats = self._collector.get_stats()

        if stats.total_feedback < min_samples:
            logger.info(
                f"[TUNER] Not enough samples ({stats.total_feedback} < {min_samples}), skipping tune"
            )
            return self._current_weights

        # Calculate performance scores
        strategy_scores = {}

        for strategy, perf in stats.strategy_performance.items():
            if perf["total"] < min_samples:
                continue

            # Positive rate * average score
            positive_rate = perf["positive"] / perf["total"] if perf["total"] > 0 else 0
            score = positive_rate * perf.get("avg_score", 0.5)

            strategy_scores[strategy] = score

        if not strategy_scores:
            logger.info("[TUNER] No strategies with enough samples")
            return self._current_weights

        # Normalize scores
        max_score = max(strategy_scores.values())
        if max_score > 0:
            strategy_scores = {
                k: v / max_score for k, v in strategy_scores.items()
            }

        # Update weights with learning rate
        new_weights = StrategyWeights()

        for strategy, score in strategy_scores.items():
            current_weight = getattr(self._current_weights, strategy, 0.0)

            # Update: current + learning_rate * (target - current)
            new_weight = current_weight + learning_rate * (score - current_weight)

            setattr(new_weights, strategy, max(0.0, new_weight))

        # Normalize
        normalized = new_weights.normalize()

        # Save and update
        self._save_weights(normalized)
        self._current_weights = normalized

        logger.info(
            f"[TUNER] Updated weights: vector={normalized.vector:.2f}, "
            f"hybrid={normalized.hybrid:.2f}, graph_local={normalized.graphrag_local:.2f}"
        )

        return normalized

    def get_best_strategy(
        self,
        query_type: str = "",
    ) -> str:
        """Get best strategy based on feedback.

        Args:
            query_type: Type of query (optional)

        Returns:
            Best strategy name
        """
        stats = self._collector.get_stats()

        best_strategy = "vector"  # Default
        best_score = 0.0

        for strategy, perf in stats.strategy_performance.items():
            if perf["total"] < 10:
                continue

            positive_rate = perf["positive"] / perf["total"] if perf["total"] > 0 else 0
            score = positive_rate * perf.get("avg_score", 0.5)

            if score > best_score:
                best_score = score
                best_strategy = strategy

        logger.debug(f"[TUNER] Best strategy: {best_strategy} (score: {best_score:.2f})")
        return best_strategy

    def get_adaptive_weights(self, query: str = "") -> dict[str, float]:
        """Get adaptive weights for the current query.

        Args:
            query: Current query (for analysis)

        Returns:
            Dict of strategy weights
        """
        # For now, return current weights
        # In production, could analyze query and adjust

        return {
            "vector": self._current_weights.vector,
            "hybrid": self._current_weights.hybrid,
            "graphrag_local": self._current_weights.graphrag_local,
            "graphrag_global": self._current_weights.graphrag_global,
            "two_stage": self._current_weights.two_stage,
        }

    def reset_weights(self):
        """Reset weights to defaults."""
        default = StrategyWeights()
        self._save_weights(default)
        self._current_weights = default
        logger.info("[TUNER] Reset weights to defaults")


def get_strategy_weights(
    settings: Settings | None = None,
) -> dict[str, float]:
    """Convenience function to get current strategy weights.

    Args:
        settings: Application settings

    Returns:
        Dict of strategy weights
    """
    tuner = StrategyTuner(settings=settings)
    return tuner.get_adaptive_weights()
