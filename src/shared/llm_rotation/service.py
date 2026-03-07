"""
LLM Rotation Service — Multi-provider completion with automatic fallback.

Migrated from D:\\1C-Enterprise_Framework\\shared\\llm_rotation_service.py
Adapted: pydantic-settings config, project-local imports, async-first.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

from src.shared.llm_rotation.config import LLMRotationSettings, get_settings

logger = logging.getLogger("llm-rotation")


class ProviderStatus(str, Enum):
    """Provider health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    COOLDOWN = "cooldown"


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    name: str
    base_url: str
    api_key_env: str
    default_model: str
    models: List[str] = field(default_factory=list)
    format: str = "openai"  # "openai" | "ollama" | "gemini"
    requires_key: bool = True
    daily_limit: Optional[int] = None
    rate_limit_rpm: Optional[int] = None
    priority: int = 0


@dataclass
class ProviderState:
    """Runtime state tracking for a provider."""
    config: ProviderConfig
    status: ProviderStatus = ProviderStatus.HEALTHY
    requests_count: int = 0
    errors_count: int = 0
    consecutive_errors: int = 0
    last_error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    avg_response_time: float = 0.0
    cooldown_until: Optional[datetime] = None

    def record_success(self, response_time: float) -> None:
        """Record a successful request."""
        self.requests_count += 1
        self.consecutive_errors = 0
        self.status = ProviderStatus.HEALTHY
        self.last_success_time = datetime.now()
        # Running average
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (self.avg_response_time * 0.8) + (response_time * 0.2)

    def record_error(self, error: str, cooldown_seconds: int = 300, rate_limit_cooldown: int = 60) -> None:
        """Record an error and potentially enter cooldown."""
        self.errors_count += 1
        self.consecutive_errors += 1
        self.last_error = error
        self.last_error_time = datetime.now()

        if "429" in error or "rate limit" in error.lower():
            self.status = ProviderStatus.COOLDOWN
            self.cooldown_until = datetime.now() + timedelta(seconds=rate_limit_cooldown)
        elif self.consecutive_errors >= 3:
            self.status = ProviderStatus.COOLDOWN
            self.cooldown_until = datetime.now() + timedelta(seconds=cooldown_seconds)
        else:
            self.status = ProviderStatus.DEGRADED

    def is_available(self) -> bool:
        """Check if provider can accept requests."""
        if self.status == ProviderStatus.UNAVAILABLE:
            return False
        if self.status == ProviderStatus.COOLDOWN:
            if self.cooldown_until and datetime.now() < self.cooldown_until:
                return False
            # Cooldown expired
            self.status = ProviderStatus.DEGRADED
            self.consecutive_errors = 0
        return True


# Default provider configurations
DEFAULT_PROVIDERS: List[ProviderConfig] = [
    ProviderConfig(
        name="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key_env="ZHIPU_API_KEY",
        default_model="glm-4-flash",
        models=["glm-4-flash", "glm-4-plus"],
        priority=0,
        rate_limit_rpm=60,
    ),
    ProviderConfig(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env="GEMINI_API_KEY",
        default_model="gemini-2.0-flash",
        models=["gemini-2.0-flash", "gemini-1.5-flash"],
        priority=1,
        rate_limit_rpm=15,
        daily_limit=1500,
    ),
    ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        default_model="meta-llama/llama-3.3-70b-instruct:free",
        models=["meta-llama/llama-3.3-70b-instruct:free"],
        priority=2,
    ),
    ProviderConfig(
        name="mistral",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        default_model="mistral-small-latest",
        models=["mistral-small-latest"],
        priority=3,
        rate_limit_rpm=60,
    ),
    ProviderConfig(
        name="ollama-local",
        base_url="http://localhost:11434",
        api_key_env="",
        default_model="qwen2.5:7b",
        models=["qwen2.5:7b", "llama3.1:8b"],
        format="ollama",
        requires_key=False,
        priority=4,
    ),
    ProviderConfig(
        name="ollama-cloud",
        base_url="http://localhost:11434",
        api_key_env="",
        default_model="qwen2.5:7b",
        models=["qwen2.5:7b"],
        format="ollama",
        requires_key=False,
        priority=5,
    ),
]


class LLMRotationService:
    """Multi-provider LLM service with automatic fallback rotation."""

    def __init__(
        self,
        providers: Optional[List[ProviderConfig]] = None,
        settings: Optional[LLMRotationSettings] = None,
    ):
        self._settings = settings or get_settings()
        configs = DEFAULT_PROVIDERS if providers is None else providers
        self._providers: Dict[str, ProviderState] = {
            cfg.name: ProviderState(config=cfg) for cfg in configs
        }
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._settings.timeout)
            )
        return self._session

    def get_available_providers(self) -> List[ProviderState]:
        """Return list of available providers sorted by priority."""
        available = []
        for state in self._providers.values():
            if not state.is_available():
                continue
            if state.config.requires_key:
                api_key = os.environ.get(state.config.api_key_env, "")
                if not api_key:
                    continue
            available.append(state)
        return sorted(available, key=lambda s: s.config.priority)

    def get_best_provider(self, exclude: Optional[List[str]] = None) -> Optional[ProviderState]:
        """Select the best available provider, optionally excluding names."""
        available = self.get_available_providers()
        if exclude:
            available = [s for s in available if s.config.name not in exclude]
        if not available:
            return None

        # Sort: healthy first, then fewer errors, then higher priority, then faster
        def score(s: ProviderState) -> tuple:
            return (
                0 if s.status == ProviderStatus.HEALTHY else 1,
                s.consecutive_errors,
                s.config.priority,
                s.avg_response_time,
            )

        return sorted(available, key=score)[0]

    async def _make_request_openai(
        self,
        state: ProviderState,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Make a request to an OpenAI-compatible API."""
        session = await self._get_session()
        url = f"{state.config.base_url}/chat/completions"
        api_key = os.environ.get(state.config.api_key_env, "")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or state.config.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
            return data

    async def _make_request_ollama(
        self,
        state: ProviderState,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Make a request to Ollama API."""
        session = await self._get_session()
        url = f"{state.config.base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or state.config.default_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with session.post(url, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
            # Convert Ollama format to OpenAI-like response
            return {
                "choices": [{
                    "message": {"content": data.get("message", {}).get("content", "")},
                    "finish_reason": "stop",
                }],
                "model": data.get("model", ""),
                "usage": {
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                },
            }

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """Generate completion with automatic provider rotation.

        Returns dict with: provider, model, text, response_time, usage.
        Raises RuntimeError if all providers fail.
        """
        tried: List[str] = []

        for attempt in range(self._settings.max_retries):
            # Select provider
            if preferred_provider and preferred_provider in self._providers:
                state = self._providers[preferred_provider]
                if not state.is_available():
                    state = self.get_best_provider()
            else:
                state = self.get_best_provider()

            if state is None:
                raise RuntimeError(
                    f"No available LLM providers. Tried: {tried}. "
                    "Check API keys and provider availability."
                )

            provider_name = state.config.name
            tried.append(provider_name)

            try:
                start = time.monotonic()

                if state.config.format == "ollama":
                    data = await self._make_request_ollama(
                        state, prompt, system_prompt, model, temperature, max_tokens
                    )
                else:
                    data = await self._make_request_openai(
                        state, prompt, system_prompt, model, temperature, max_tokens
                    )

                elapsed = time.monotonic() - start
                state.record_success(elapsed)

                text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})

                logger.info(
                    f"[{provider_name}] Completed in {elapsed:.2f}s "
                    f"(tokens: {usage.get('completion_tokens', '?')})"
                )

                return {
                    "provider": provider_name,
                    "model": data.get("model", model or state.config.default_model),
                    "text": text,
                    "response_time": round(elapsed, 3),
                    "usage": usage,
                    "attempt": attempt + 1,
                }

            except Exception as e:
                elapsed = time.monotonic() - start
                error_msg = str(e)[:200]
                state.record_error(
                    error_msg,
                    self._settings.cooldown_seconds,
                    self._settings.rate_limit_cooldown,
                )
                logger.warning(
                    f"[{provider_name}] Error (attempt {attempt + 1}): {error_msg}"
                )

        raise RuntimeError(
            f"All providers failed after {self._settings.max_retries} attempts. "
            f"Tried: {tried}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Return statistics for all providers."""
        stats = {}
        for name, state in self._providers.items():
            api_key = os.environ.get(state.config.api_key_env, "") if state.config.requires_key else "(not needed)"
            stats[name] = {
                "status": state.status.value,
                "priority": state.config.priority,
                "requests": state.requests_count,
                "errors": state.errors_count,
                "consecutive_errors": state.consecutive_errors,
                "avg_response_time": round(state.avg_response_time, 3),
                "last_error": state.last_error,
                "has_api_key": bool(api_key),
                "model": state.config.default_model,
                "available": state.is_available() and bool(api_key),
            }
        return stats

    def reset_provider(self, name: str) -> bool:
        """Reset a provider state to HEALTHY."""
        if name in self._providers:
            state = self._providers[name]
            state.status = ProviderStatus.HEALTHY
            state.consecutive_errors = 0
            state.cooldown_until = None
            state.last_error = None
            return True
        return False

    def reset_all(self) -> None:
        """Reset all providers to HEALTHY."""
        for state in self._providers.values():
            state.status = ProviderStatus.HEALTHY
            state.consecutive_errors = 0
            state.cooldown_until = None
            state.last_error = None

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


# Singleton
_service: Optional[LLMRotationService] = None


def get_service() -> LLMRotationService:
    """Get or create singleton service instance."""
    global _service
    if _service is None:
        _service = LLMRotationService()
    return _service
