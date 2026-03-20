"""
LLM Rotation configuration via pydantic-settings.

Environment variables with LLM_ROTATION_ prefix.
"""

from pydantic_settings import BaseSettings


class LLMRotationSettings(BaseSettings):
    """Settings for LLM Rotation Service."""

    primary_provider: str = "zai-glm5"
    max_retries: int = 3
    timeout: int = 30
    cooldown_seconds: int = 300
    rate_limit_cooldown: int = 60

    # Force-primary mode: retry primary provider before any fallback
    force_primary: bool = True
    primary_max_retries: int = 2
    primary_retry_delay: float = 3.0
    primary_cooldown_seconds: int = 30

    # Circuit Breaker
    cb_fail_threshold: int = 3
    cb_success_threshold: int = 1
    cb_reset_timeout: float = 60.0

    # API Keys (from environment)
    zhipu_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    mistral_api_key: str = ""

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_cloud_url: str = "http://localhost:11434"

    # Z.AI
    zai_api_key: str = ""
    zai_base_url: str = "https://api.z.ai/api/anthropic"

    model_config = {
        "env_prefix": "LLM_ROTATION_",
        "env_file": ".env",
        "extra": "ignore",
    }


_settings: LLMRotationSettings | None = None


def get_settings() -> LLMRotationSettings:
    """Get or create singleton settings."""
    global _settings
    if _settings is None:
        _settings = LLMRotationSettings()
    return _settings
