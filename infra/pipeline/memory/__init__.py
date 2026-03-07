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
    MemoryEntry,
    MemoryType,
    PatternType,
    Pattern,
    ErrorRecord,
    Recommendation,
    LearningContext,
)
from .unified_memory_client import (
    UnifiedMemoryClient,
    MemoryConfig,
)
from .pattern_saver import (
    PatternSaver,
    PatternMatcher,
)
from .error_learner import (
    ErrorLearner,
    ErrorAnalyzer,
)
from .recommender import (
    Recommender,
    RecommendationEngine,
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
