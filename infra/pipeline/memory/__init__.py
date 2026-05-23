"""
Memory & Learning Module for Development Pipeline.

Sprint 3.3: Memory & Learning

This module provides:
- Integration with unified-memory-mcp
- Pattern saving and retrieval
- Error learning and prevention
- History-based recommendations
"""

from models import (
    ErrorRecord,
    LearningContext,
    MemoryEntry,
    MemoryType,
    Pattern,
    PatternType,
    Recommendation,
)

from .error_learner import (
    ErrorAnalyzer,
    ErrorLearner,
)
from .pattern_saver import (
    PatternMatcher,
    PatternSaver,
)
from .recommender import (
    RecommendationEngine,
    Recommender,
)
from .unified_memory_client import (
    MemoryConfig,
    UnifiedMemoryClient,
)

__all__ = [
    # Models
    "MemoryEntry",
    "MemoryType",
    "PatternType",
    "Pattern",
    "ErrorRecord",
    "Recommendation",
    "LearningContext",
    # Memory Client
    "UnifiedMemoryClient",
    "MemoryConfig",
    # Pattern Saver
    "PatternSaver",
    "PatternMatcher",
    # Error Learner
    "ErrorLearner",
    "ErrorAnalyzer",
    # Recommender
    "Recommender",
    "RecommendationEngine",
]
