"""
LLM Rotation Service — Multi-provider LLM with automatic fallback.

Providers: Zhipu (GLM-5), Gemini, OpenRouter, Mistral, Ollama.
Fallback: priority-based selection with health tracking and cooldown.
"""

from src.shared.llm_rotation.service import (
    LLMRotationService,
    ProviderConfig,
    ProviderState,
    ProviderStatus,
    DEFAULT_PROVIDERS,
    get_service,
)
from src.shared.llm_rotation.adapter import (
    cheap_llm_call,
    is_cheap_llm_enabled,
    COMPONENT_REGISTRY,
    QUALITY_CRITERIA,
    evaluate_response,
    discover_unregistered_components,
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
