"""Search configuration for memory subsystem.

Simplified from: unified-memory-mcp/src/search/config.py (247 lines)
Removed: Qdrant, Ollama, external encoder configs.
Kept: BM25 params, fusion method, BSL scorer config.

Version: 1.0 (2026-04-04) -- P2 migration
"""

from dataclasses import dataclass, field
from enum import Enum


class FusionMethod(str, Enum):
    """Fusion methods for combining search results."""

    RRF = "rrf"  # Reciprocal Rank Fusion
    WEIGHTED_SUM = "weighted_sum"  # Weighted sum of normalized scores


class VectorType(str, Enum):
    """Search type."""

    SPARSE = "sparse"  # BM25 only
    DENSE = "dense"  # Embedding only (external)
    HYBRID = "hybrid"  # BM25 + embeddings


@dataclass
class SparseConfig:
    """BM25 configuration."""

    k1: float = 1.5
    b: float = 0.75
    min_token_length: int = 2

    bsl_stopwords: list[str] = field(
        default_factory=lambda: [
            "Если",
            "Тогда",
            "Иначе",
            "КонецЕсли",
            "Для",
            "Каждого",
            "Из",
            "Цикл",
            "КонецЦикла",
            "Пока",
            "Попытка",
            "Исключение",
            "КонецПопытки",
            "Процедура",
            "КонецПроцедуры",
            "Функция",
            "КонецФункции",
            "Возврат",
            "Перем",
            "Новый",
            "Неопределено",
            "Истина",
            "Ложь",
        ]
    )


@dataclass
class HybridSearchConfig:
    """Hybrid search configuration."""

    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    fusion_method: FusionMethod = FusionMethod.RRF
    rrf_k: int = 60
    top_k: int = 20
    min_score: float = 0.0


@dataclass
class BSLScorerConfig:
    """BSL-specific scoring configuration."""

    exact_match_weight: float = 2.0
    prefix_match_weight: float = 1.5
    function_boost: float = 1.5
    procedure_boost: float = 1.4
    export_boost: float = 1.3
    common_module_boost: float = 1.2

    prefix_patterns: list[str] = field(
        default_factory=lambda: [
            "гкс_",
            "упп_",
            "бсп_",
            "зуп_",
            "ут_",
        ]
    )

    object_type_weights: dict[str, float] = field(
        default_factory=lambda: {
            "CommonModule": 1.5,
            "DataProcessor": 1.3,
            "Report": 1.2,
            "Document": 1.1,
            "Catalog": 1.0,
            "InformationRegister": 1.0,
            "AccumulationRegister": 0.9,
        }
    )

    context_weights: dict[str, float] = field(
        default_factory=lambda: {
            "query": 1.5,
            "transaction": 1.4,
            "form": 1.2,
            "background": 1.1,
        }
    )


@dataclass
class SearchConfig:
    """Main search configuration."""

    sparse: SparseConfig = field(default_factory=SparseConfig)
    hybrid: HybridSearchConfig = field(default_factory=HybridSearchConfig)
    bsl_scorer: BSLScorerConfig = field(default_factory=BSLScorerConfig)
    default_vector_type: VectorType = VectorType.SPARSE


DEFAULT_SEARCH_CONFIG = SearchConfig()


__all__ = [
    "BSLScorerConfig",
    "DEFAULT_SEARCH_CONFIG",
    "FusionMethod",
    "HybridSearchConfig",
    "SearchConfig",
    "SparseConfig",
    "VectorType",
]
