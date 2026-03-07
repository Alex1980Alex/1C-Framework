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

__all__ = [
    "LLMRotationService",
    "ProviderConfig",
    "ProviderState",
    "ProviderStatus",
    "DEFAULT_PROVIDERS",
    "get_service",
]

__version__ = "1.0.0"
