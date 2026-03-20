"""
LLM Rotation Service — Multi-provider LLM with automatic fallback.

Providers: Zhipu (GLM-5), Gemini, OpenRouter, Mistral, Ollama.
Fallback: priority-based selection with health tracking and cooldown.
"""

from src.shared.llm_rotation.adapter import (
    COMPONENT_REGISTRY,
    QUALITY_CRITERIA,
    cheap_llm_call,
    discover_unregistered_components,
    evaluate_response,
    is_cheap_llm_enabled,
)
from src.shared.llm_rotation.circuit_breaker import CircuitBreaker, CircuitState
from src.shared.llm_rotation.service import (
    DEFAULT_PROVIDERS,
    LLMRotationService,
    ProviderConfig,
    ProviderState,
    ProviderStatus,
    get_service,
)

__all__ = [
    "LLMRotationService",
    "ProviderConfig",
    "ProviderState",
    "ProviderStatus",
    "DEFAULT_PROVIDERS",
    "get_service",
    "cheap_llm_call",
    "is_cheap_llm_enabled",
    "COMPONENT_REGISTRY",
    "QUALITY_CRITERIA",
    "evaluate_response",
    "discover_unregistered_components",
]

__version__ = "1.0.0"
