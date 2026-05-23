"""ForgetGate service for selective memory forgetting.

Implements confidence-based decay, surprise detection, and selective pruning
of low-value memory entries. Adapts to Qdrant payload format.

Migrated from: unified-memory-mcp/src/services/forgetgate.py (520 lines)
Simplified: removed direct Qdrant calls, works through abstract callbacks.

Version: 1.0 (2026-04-04) -- P2 migration
"""

import logging
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ForgetStrategy(str, Enum):
    """Strategy for deciding what to forget."""

    CONFIDENCE_DECAY = "confidence_decay"  # Exponential decay over time
    ACCESS_BASED = "access_based"  # Forget rarely accessed
    SURPRISE_BASED = "surprise_based"  # Keep surprising, forget routine
    COMPOSITE = "composite"  # Weighted combination of all


class ForgetAction(str, Enum):
    """Action to take on a forgettable entry."""

    ARCHIVE = "archive"  # Move to cold storage
    DECAY = "decay"  # Reduce confidence
    DELETE = "delete"  # Remove permanently
    KEEP = "keep"  # No action


@dataclass
class ForgetCandidate:
    """A memory entry evaluated for forgetting."""

    entity_id: str
    current_confidence: float
    last_accessed: datetime | None
    access_count: int
    created_at: datetime
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ForgetDecision:
    """Decision about a candidate."""

    entity_id: str
    action: ForgetAction
    new_confidence: float
    reason: str
    scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ForgetGateConfig:
    """Configuration for the ForgetGate."""

    # Decay parameters
    decay_rate: float = 0.05  # Per-day decay rate
    min_confidence: float = 0.1  # Below this -> archive/delete
    delete_threshold: float = 0.05  # Below this -> delete

    # Access-based parameters
    access_decay_days: int = 30  # Days without access before penalty
    access_weight: float = 0.3  # Weight in composite score

    # Surprise parameters
    surprise_weight: float = 0.2  # Weight in composite score
    routine_threshold: float = 0.3  # Below this surprise -> routine

    # General
    strategy: ForgetStrategy = ForgetStrategy.COMPOSITE
    batch_size: int = 100
    dry_run: bool = False


@dataclass
class ForgetGateStats:
    """Statistics from a forget pass."""

    total_evaluated: int = 0
    archived: int = 0
    decayed: int = 0
    deleted: int = 0
    kept: int = 0
    duration_ms: float = 0.0


# Type for callback that applies decisions to the actual storage
ApplyDecisionFn = Callable[[ForgetDecision], bool]


class SurpriseCalculator:
    """
    Compute surprise score for a memory entry.

    Surprise = how different this entry is from its neighbors.
    High surprise -> worth keeping (novel information).
    Low surprise -> routine, can be forgotten.
    """

    def __init__(self):
        self._tag_frequencies: dict[str, int] = {}
        self._total_entries: int = 0

    def update_frequencies(self, candidates: list[ForgetCandidate]) -> None:
        """Update tag frequency counts from candidates."""
        self._total_entries = len(candidates)
        self._tag_frequencies.clear()
        for c in candidates:
            for tag in c.tags:
                self._tag_frequencies[tag] = self._tag_frequencies.get(tag, 0) + 1

    def surprise_score(self, candidate: ForgetCandidate) -> float:
        """
        Compute surprise as inverse document frequency of tags.

        Rare tags -> high surprise. Common tags -> low surprise.
        Returns score in [0, 1].
        """
        if not candidate.tags or self._total_entries == 0:
            return 0.5  # neutral

        tag_idfs = []
        for tag in candidate.tags:
            freq = self._tag_frequencies.get(tag, 0)
            if freq > 0:
                idf = math.log(self._total_entries / freq)
                tag_idfs.append(idf)

        if not tag_idfs:
            return 0.5

        max_idf = math.log(self._total_entries) if self._total_entries > 1 else 1.0
        avg_idf = sum(tag_idfs) / len(tag_idfs)
        return min(avg_idf / max(max_idf, 1e-6), 1.0)


class ForgetGateService:
    """
    Selective memory forgetting with multi-strategy evaluation.

    Evaluates memory entries and decides which to keep, decay, archive, or delete.
    Works with any storage backend through callback functions.

    Usage:
        gate = ForgetGateService()
        candidates = [ForgetCandidate(...), ...]
        decisions = gate.evaluate(candidates)
        stats = gate.apply(decisions, apply_fn=my_storage_callback)
    """

    def __init__(self, config: ForgetGateConfig | None = None):
        self.config = config or ForgetGateConfig()
        self._surprise = SurpriseCalculator()
        self._last_run: datetime | None = None

    def evaluate(self, candidates: list[ForgetCandidate]) -> list[ForgetDecision]:
        """Evaluate candidates and decide what to forget."""
        if self.config.strategy == ForgetStrategy.SURPRISE_BASED:
            self._surprise.update_frequencies(candidates)

        if self.config.strategy == ForgetStrategy.COMPOSITE:
            self._surprise.update_frequencies(candidates)

        decisions = []
        for candidate in candidates:
            decision = self._evaluate_one(candidate)
            decisions.append(decision)

        return decisions

    def _evaluate_one(self, candidate: ForgetCandidate) -> ForgetDecision:
        """Evaluate a single candidate."""
        strategy = self.config.strategy

        if strategy == ForgetStrategy.CONFIDENCE_DECAY:
            return self._eval_confidence_decay(candidate)
        elif strategy == ForgetStrategy.ACCESS_BASED:
            return self._eval_access_based(candidate)
        elif strategy == ForgetStrategy.SURPRISE_BASED:
            return self._eval_surprise_based(candidate)
        else:
            return self._eval_composite(candidate)

    def _eval_confidence_decay(self, c: ForgetCandidate) -> ForgetDecision:
        """Exponential confidence decay over time."""
        now = datetime.now()
        age_days = (now - c.created_at).total_seconds() / 86400

        # Exponential decay: new_conf = conf * e^(-decay_rate * age_days)
        decay_factor = math.exp(-self.config.decay_rate * age_days)
        new_confidence = c.current_confidence * decay_factor

        action = self._decide_action(new_confidence)
        return ForgetDecision(
            entity_id=c.entity_id,
            action=action,
            new_confidence=new_confidence,
            reason=f"decay: age={age_days:.1f}d, factor={decay_factor:.3f}",
            scores={"decay_factor": decay_factor, "age_days": age_days},
        )

    def _eval_access_based(self, c: ForgetCandidate) -> ForgetDecision:
        """Penalize rarely accessed entries."""
        now = datetime.now()

        if c.last_accessed:
            days_since_access = (now - c.last_accessed).total_seconds() / 86400
        else:
            days_since_access = (now - c.created_at).total_seconds() / 86400

        # Access penalty: reduce confidence if not accessed recently
        if days_since_access > self.config.access_decay_days:
            over_threshold = days_since_access - self.config.access_decay_days
            penalty = min(over_threshold * 0.01, 0.5)  # max 50% penalty
            new_confidence = c.current_confidence * (1 - penalty)
        else:
            new_confidence = c.current_confidence

        # Boost for frequently accessed
        if c.access_count > 10:
            new_confidence = min(new_confidence * 1.1, 1.0)

        action = self._decide_action(new_confidence)
        return ForgetDecision(
            entity_id=c.entity_id,
            action=action,
            new_confidence=new_confidence,
            reason=f"access: days_since={days_since_access:.1f}, count={c.access_count}",
            scores={"days_since_access": days_since_access, "access_count": c.access_count},
        )

    def _eval_surprise_based(self, c: ForgetCandidate) -> ForgetDecision:
        """Keep surprising entries, forget routine ones."""
        surprise = self._surprise.surprise_score(c)

        if surprise < self.config.routine_threshold:
            # Routine content -> increase decay
            new_confidence = c.current_confidence * 0.8
        else:
            # Surprising content -> preserve
            new_confidence = c.current_confidence

        action = self._decide_action(new_confidence)
        return ForgetDecision(
            entity_id=c.entity_id,
            action=action,
            new_confidence=new_confidence,
            reason=f"surprise: score={surprise:.3f}, threshold={self.config.routine_threshold}",
            scores={"surprise": surprise},
        )

    def _eval_composite(self, c: ForgetCandidate) -> ForgetDecision:
        """Weighted combination of all strategies."""
        now = datetime.now()
        age_days = (now - c.created_at).total_seconds() / 86400

        # 1. Confidence decay component
        decay_factor = math.exp(-self.config.decay_rate * age_days)
        decay_score = c.current_confidence * decay_factor

        # 2. Access component
        if c.last_accessed:
            days_since = (now - c.last_accessed).total_seconds() / 86400
        else:
            days_since = age_days
        access_score = max(0, 1.0 - (days_since / max(self.config.access_decay_days * 2, 1)))
        if c.access_count > 5:
            access_score = min(access_score + 0.2, 1.0)

        # 3. Surprise component
        surprise_score = self._surprise.surprise_score(c)

        # Weighted combination
        confidence_weight = 1.0 - self.config.access_weight - self.config.surprise_weight
        new_confidence = (
            confidence_weight * decay_score
            + self.config.access_weight * access_score
            + self.config.surprise_weight * surprise_score
        )
        new_confidence = max(0.0, min(1.0, new_confidence))

        action = self._decide_action(new_confidence)
        return ForgetDecision(
            entity_id=c.entity_id,
            action=action,
            new_confidence=new_confidence,
            reason=f"composite: decay={decay_score:.3f} access={access_score:.3f} surprise={surprise_score:.3f}",
            scores={
                "decay_score": decay_score,
                "access_score": access_score,
                "surprise_score": surprise_score,
                "confidence_weight": confidence_weight,
            },
        )

    def _decide_action(self, confidence: float) -> ForgetAction:
        """Decide action based on confidence level."""
        if confidence < self.config.delete_threshold:
            return ForgetAction.DELETE
        elif confidence < self.config.min_confidence:
            return ForgetAction.ARCHIVE
        elif confidence < 0.3:
            return ForgetAction.DECAY
        else:
            return ForgetAction.KEEP

    def apply(
        self,
        decisions: list[ForgetDecision],
        apply_fn: ApplyDecisionFn | None = None,
    ) -> ForgetGateStats:
        """Apply forget decisions. Returns stats."""
        start = time.time()
        stats = ForgetGateStats(total_evaluated=len(decisions))

        for decision in decisions:
            if decision.action == ForgetAction.KEEP:
                stats.kept += 1
                continue

            if self.config.dry_run:
                # Count without applying
                if decision.action == ForgetAction.ARCHIVE:
                    stats.archived += 1
                elif decision.action == ForgetAction.DECAY:
                    stats.decayed += 1
                elif decision.action == ForgetAction.DELETE:
                    stats.deleted += 1
                continue

            if apply_fn:
                try:
                    apply_fn(decision)
                except Exception as e:
                    logger.error("Failed to apply decision for %s: %s", decision.entity_id, e)
                    continue

            if decision.action == ForgetAction.ARCHIVE:
                stats.archived += 1
            elif decision.action == ForgetAction.DECAY:
                stats.decayed += 1
            elif decision.action == ForgetAction.DELETE:
                stats.deleted += 1

        stats.duration_ms = (time.time() - start) * 1000
        self._last_run = datetime.now()

        logger.info(
            "ForgetGate: evaluated=%d kept=%d decayed=%d archived=%d deleted=%d (%.1fms%s)",
            stats.total_evaluated,
            stats.kept,
            stats.decayed,
            stats.archived,
            stats.deleted,
            stats.duration_ms,
            " DRY-RUN" if self.config.dry_run else "",
        )
        return stats

    def get_stats(self) -> dict[str, Any]:
        """Return service statistics."""
        return {
            "strategy": self.config.strategy.value,
            "decay_rate": self.config.decay_rate,
            "min_confidence": self.config.min_confidence,
            "delete_threshold": self.config.delete_threshold,
            "dry_run": self.config.dry_run,
            "last_run": self._last_run.isoformat() if self._last_run else None,
        }


__all__ = [
    "ForgetAction",
    "ForgetCandidate",
    "ForgetDecision",
    "ForgetGateConfig",
    "ForgetGateService",
    "ForgetGateStats",
    "ForgetStrategy",
    "SurpriseCalculator",
]
