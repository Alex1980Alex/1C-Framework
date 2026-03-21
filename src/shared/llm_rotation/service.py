"""
LLM Rotation Service — Multi-provider completion with automatic fallback.

Migrated from D:\\1C-Enterprise_Framework\\shared\\llm_rotation_service.py
Adapted: pydantic-settings config, project-local imports, async-first.
"""

import asyncio
import json as _json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import aiohttp

from src.shared.llm_rotation.adaptive import AdaptiveScorer, BudgetTracker, PRICE_PER_1K_TOKENS
from src.shared.llm_rotation.backoff import BackoffStrategy, RateLimitError
from src.shared.llm_rotation.circuit_breaker import CircuitBreaker, CircuitState
from src.shared.llm_rotation.config import LLMRotationSettings, get_settings
from src.shared.llm_rotation.rate_limiter import ProviderRateLimiter

logger = logging.getLogger("llm-rotation")

_COMPLETIONS_LOG = Path("data/llm-rotation-completions.jsonl")


def _log_completion(**kwargs) -> None:
    """Append completion metric to JSONL (fire-and-forget)."""
    try:
        _COMPLETIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
        kwargs["ts"] = datetime.now().isoformat()
        with open(_COMPLETIONS_LOG, "a", encoding="utf-8") as f:
            f.write(_json.dumps(kwargs, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _parse_retry_after(value: str | None) -> float | None:
    """Parse Retry-After header value to seconds."""
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


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
    models: list[str] = field(default_factory=list)
    format: str = "openai"  # "openai" | "ollama" | "anthropic"
    requires_key: bool = True
    daily_limit: int | None = None
    rate_limit_rpm: int | None = None
    priority: int = 0


@dataclass
class ProviderState:
    """Runtime state tracking for a provider."""
    config: ProviderConfig
    status: ProviderStatus = ProviderStatus.HEALTHY
    requests_count: int = 0
    errors_count: int = 0
    consecutive_errors: int = 0
    last_error: str | None = None
    last_error_time: datetime | None = None
    last_success_time: datetime | None = None
    avg_response_time: float = 0.0
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    def record_success(self, response_time: float) -> None:
        """Record a successful request."""
        self.requests_count += 1
        self.consecutive_errors = 0
        self.circuit_breaker.record_success()
        self.status = self._status_from_cb()
        self.last_success_time = datetime.now()
        # Running average
        if self.avg_response_time == 0:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (self.avg_response_time * 0.8) + (response_time * 0.2)

    def record_error(
        self, error: str, cooldown_seconds: int = 300, rate_limit_cooldown: int = 60,
    ) -> None:
        """Record an error. CB handles state transitions."""
        self.errors_count += 1
        self.consecutive_errors += 1
        self.last_error = error
        self.last_error_time = datetime.now()

        if "429" in error or "rate limit" in error.lower():
            # Rate limit → trip CB immediately with shorter timeout
            self.circuit_breaker.force_open(reset_timeout=rate_limit_cooldown)
        else:
            self.circuit_breaker.record_failure()

        self.status = self._status_from_cb()

    def is_available(self) -> bool:
        """Check if provider can accept requests."""
        if self.status == ProviderStatus.UNAVAILABLE:
            return False
        available = self.circuit_breaker.can_execute()
        self.status = self._status_from_cb()
        return available

    def _status_from_cb(self) -> ProviderStatus:
        """Derive ProviderStatus from circuit breaker state."""
        if self.status == ProviderStatus.UNAVAILABLE:
            return ProviderStatus.UNAVAILABLE
        cb = self.circuit_breaker
        if cb.state == CircuitState.CLOSED:
            return ProviderStatus.HEALTHY if cb.fail_count == 0 else ProviderStatus.DEGRADED
        if cb.state == CircuitState.OPEN:
            return ProviderStatus.COOLDOWN
        # HALF_OPEN
        return ProviderStatus.DEGRADED


# Default provider configurations
DEFAULT_PROVIDERS: list[ProviderConfig] = [
    ProviderConfig(
        name="zai-glm5",
        base_url="https://api.z.ai/api/anthropic",
        api_key_env="ZAI_API_KEY",
        default_model="glm-5",
        models=["glm-5", "glm-4.6", "glm-4.5-air"],
        format="anthropic",
        priority=0,
        rate_limit_rpm=30,
    ),
    ProviderConfig(
        name="zhipu",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key_env="ZHIPU_API_KEY",
        default_model="glm-4-flash",
        models=["glm-4-flash", "glm-4-plus"],
        priority=1,
        rate_limit_rpm=60,
    ),
    ProviderConfig(
        name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        api_key_env="GEMINI_API_KEY",
        default_model="gemini-2.5-flash",
        models=["gemini-2.5-flash", "gemini-2.5-flash-lite"],
        priority=2,
        rate_limit_rpm=10,
        daily_limit=250,
    ),
    ProviderConfig(
        name="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        default_model="google/gemma-3-27b-it:free",
        models=[
            "google/gemma-3-27b-it:free",
            "meta-llama/llama-3.3-70b-instruct:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
        ],
        priority=3,
        rate_limit_rpm=20,
        daily_limit=200,
    ),
    ProviderConfig(
        name="mistral",
        base_url="https://api.mistral.ai/v1",
        api_key_env="MISTRAL_API_KEY",
        default_model="mistral-small-latest",
        models=["mistral-small-latest"],
        priority=4,
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
        priority=5,
    ),
    ProviderConfig(
        name="ollama-cloud",
        base_url="http://localhost:11434",
        api_key_env="",
        default_model="qwen2.5:7b",
        models=["qwen2.5:7b"],
        format="ollama",
        requires_key=False,
        priority=6,
    ),
]


class LLMRotationService:
    """Multi-provider LLM service with automatic fallback rotation."""

    def __init__(
        self,
        providers: list[ProviderConfig] | None = None,
        settings: LLMRotationSettings | None = None,
    ):
        self._settings = settings or get_settings()
        configs = DEFAULT_PROVIDERS if providers is None else providers
        self._providers: dict[str, ProviderState] = {
            cfg.name: ProviderState(
                config=cfg,
                circuit_breaker=CircuitBreaker(
                    fail_threshold=self._settings.cb_fail_threshold,
                    success_threshold=self._settings.cb_success_threshold,
                    reset_timeout=self._settings.cb_reset_timeout,
                ),
            )
            for cfg in configs
        }
        self._backoff = BackoffStrategy(
            base_delay=self._settings.backoff_base_delay,
            max_delay=self._settings.backoff_max_delay,
            jitter=self._settings.backoff_jitter,
            multiplier=self._settings.backoff_multiplier,
        )
        self._scorer = AdaptiveScorer()
        self._budget = BudgetTracker(
            daily_budget=self._settings.daily_budget,
            alert_threshold=self._settings.budget_alert_threshold,
        )
        self._rate_limiter = ProviderRateLimiter()
        if self._settings.rate_limiting_enabled:
            for cfg in configs:
                self._rate_limiter.register(cfg.name, cfg.rate_limit_rpm)
        # Load persisted state
        if self._settings.persist_adaptive:
            self._scorer.load(self._settings.adaptive_data_path)
            self._budget.load(self._settings.budget_data_path)
        self._session: aiohttp.ClientSession | None = None
        self._health_task: asyncio.Task | None = None

    def _request_timeout(self, timeout: int | None = None) -> aiohttp.ClientTimeout:
        """Build per-request timeout."""
        return aiohttp.ClientTimeout(total=timeout or self._settings.timeout)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session (no default timeout — set per-request)."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def get_available_providers(self) -> list[ProviderState]:
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
        # Check daily budget auto-reset
        self._budget.check_daily_reset()
        return sorted(available, key=lambda s: s.config.priority)

    def get_best_provider(self, exclude: list[str] | None = None) -> ProviderState | None:
        """Select the best available provider, optionally excluding names."""
        available = self.get_available_providers()
        if exclude:
            available = [s for s in available if s.config.name not in exclude]
        if not available:
            return None

        # Sort: healthy first, then by adaptive score (if enough data), then priority
        def sort_key(s: ProviderState) -> tuple:
            adaptive = self._scorer.score(s.config.name) if self._settings.adaptive_routing else 0.5
            return (
                0 if s.status == ProviderStatus.HEALTHY else 1,
                -adaptive,  # higher adaptive score = better (negate for ascending sort)
                s.consecutive_errors,
                s.config.priority,
                s.avg_response_time,
            )

        return sorted(available, key=sort_key)[0]

    def _save_state(self) -> None:
        """Save adaptive scorer and budget state to disk."""
        try:
            self._scorer.save(self._settings.adaptive_data_path)
            self._budget.save(self._settings.budget_data_path)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")

    async def _make_request_openai(
        self,
        state: ProviderState,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int | None = None,
    ) -> dict[str, Any]:
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

        async with session.post(url, json=payload, headers=headers,
                               timeout=self._request_timeout(timeout)) as resp:
            if resp.status == 429:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                text = await resp.text()
                raise RateLimitError(f"HTTP 429: {text[:200]}", retry_after=retry_after)
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json()
            return data

    async def _make_request_ollama(
        self,
        state: ProviderState,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int | None = None,
    ) -> dict[str, Any]:
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

        async with session.post(url, json=payload,
                               timeout=self._request_timeout(timeout)) as resp:
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

    async def _make_request_anthropic(
        self,
        state: ProviderState,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Make a request to Anthropic-compatible API (Z.AI with GLM-5)."""
        session = await self._get_session()
        url = f"{state.config.base_url}/v1/messages"
        api_key = os.environ.get(state.config.api_key_env, "")

        messages = [{"role": "user", "content": prompt}]

        payload: dict[str, Any] = {
            "model": model or state.config.default_model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if temperature != 1.0:
            payload["temperature"] = temperature

        # GLM-5 thinking mode — disabled (eats output token budget, returns empty text)
        # If needed, add explicit thinking parameter to method signature

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }

        async with session.post(url, json=payload, headers=headers,
                               timeout=self._request_timeout(timeout)) as resp:
            if resp.status == 429:
                retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
                text_resp = await resp.text()
                raise RateLimitError(f"HTTP 429: {text_resp[:200]}", retry_after=retry_after)
            if resp.status != 200:
                text_resp = await resp.text()
                raise RuntimeError(f"HTTP {resp.status}: {text_resp[:200]}")
            data = await resp.json()

        # Convert Anthropic response to OpenAI-like format
        content_blocks = data.get("content", [])
        text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        usage = data.get("usage", {})

        return {
            "choices": [{
                "message": {"content": "\n".join(text_parts)},
                "finish_reason": "stop",
            }],
            "model": data.get("model", ""),
            "usage": {
                "prompt_tokens": usage.get("input_tokens", 0),
                "completion_tokens": usage.get("output_tokens", 0),
            },
        }

    async def _call_provider(
        self,
        state: ProviderState,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Make a single request to a provider. Returns normalized result dict."""
        start = time.monotonic()

        if state.config.format == "anthropic":
            data = await self._make_request_anthropic(
                state, prompt, system_prompt, model, temperature, max_tokens, timeout
            )
        elif state.config.format == "ollama":
            data = await self._make_request_ollama(
                state, prompt, system_prompt, model, temperature, max_tokens, timeout
            )
        else:
            data = await self._make_request_openai(
                state, prompt, system_prompt, model, temperature, max_tokens, timeout
            )

        elapsed = time.monotonic() - start
        state.record_success(elapsed)

        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})

        total_tokens = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
        logger.info(
            f"[{state.config.name}] Completed in {elapsed:.2f}s "
            f"(tokens: {usage.get('completion_tokens', '?')})"
        )

        # Adaptive scoring: estimate quality from response characteristics
        quality = 0.0
        if text:
            length_score = min(1.0, len(text) / 100.0)
            error_penalty = 0.5 if any(kw in text.lower() for kw in ("error", "sorry", "i cannot")) else 0.0
            quality = max(0.0, length_score - error_penalty)
        self._scorer.record(state.config.name, elapsed, total_tokens, quality)

        # Budget tracking
        price = PRICE_PER_1K_TOKENS.get(state.config.name, 0.0)
        cost = total_tokens * price / 1000.0
        self._budget.record_cost(state.config.name, cost)

        # Persist adaptive data periodically (every 10 requests)
        if self._settings.persist_adaptive and state.requests_count % 10 == 0:
            self._save_state()

        return {
            "provider": state.config.name,
            "model": data.get("model", model or state.config.default_model),
            "text": text,
            "response_time": round(elapsed, 3),
            "usage": usage,
        }

    async def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        model: str | None = None,
        preferred_provider: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Generate completion with automatic provider rotation.

        When force_primary is enabled, retries the primary provider
        (with delay) before falling back to other providers.

        Returns dict with: provider, model, text, response_time, usage.
        Raises RuntimeError if all providers fail.
        """
        tried: list[str] = []
        total_attempts = 0
        primary_retries = 0
        primary_name = self._settings.primary_provider

        # Auto-select timeout by max_tokens tier
        if timeout is None:
            if max_tokens > 3000:
                timeout = self._settings.timeout_heavy       # 180s
            elif max_tokens > 1024:
                timeout = self._settings.timeout_generation  # 90s
            else:
                timeout = self._settings.timeout             # 60s

        # Budget advisory check
        self._budget.check_daily_reset()
        if self._budget.is_over_budget:
            logger.warning(f"Daily budget exceeded (${self._budget.total_spent:.4f}/${self._budget.daily_budget})")

        # --- Phase 1: Force-retry primary provider ---
        if self._settings.force_primary and primary_name in self._providers:
            primary_state = self._providers[primary_name]
            can_try = True
            if primary_state.config.requires_key:
                can_try = bool(os.environ.get(primary_state.config.api_key_env, ""))

            if can_try:
                # Rate limit check for primary
                if self._settings.rate_limiting_enabled:
                    wait = self._rate_limiter.wait_time(primary_name)
                    if wait > 0:
                        logger.info(f"[{primary_name}] Rate limit: waiting {wait:.2f}s")
                        await asyncio.sleep(wait)

                for retry in range(self._settings.primary_max_retries):
                    if not primary_state.is_available():
                        logger.info(f"[{primary_name}] Unavailable, skipping to fallback")
                        break

                    total_attempts += 1
                    primary_retries += 1
                    try:
                        result = await self._call_provider(
                            primary_state, prompt, system_prompt, model,
                            temperature, max_tokens, timeout=timeout,
                        )
                        result["attempt"] = total_attempts
                        usage = result.get("usage", {})
                        _log_completion(
                            provider=result["provider"], model=result["model"],
                            response_time=result["response_time"], attempt=total_attempts,
                            primary_retries=primary_retries, fallback=False,
                            prompt_tokens=usage.get("prompt_tokens", 0),
                            completion_tokens=usage.get("completion_tokens", 0),
                        )
                        return result

                    except Exception as e:
                        error_msg = str(e)[:200]
                        retry_after = e.retry_after if isinstance(e, RateLimitError) else None
                        # Use reduced cooldown for primary provider
                        primary_state.record_error(
                            error_msg,
                            self._settings.primary_cooldown_seconds,
                            self._settings.rate_limit_cooldown,
                        )
                        logger.warning(
                            f"[{primary_name}] Force-primary retry "
                            f"{retry + 1}/{self._settings.primary_max_retries}: {error_msg}"
                        )

                        # Exponential backoff with jitter before retrying
                        if retry < self._settings.primary_max_retries - 1:
                            delay = self._backoff.compute_delay(retry, retry_after=retry_after)
                            logger.info(f"[{primary_name}] Backoff {delay:.2f}s before retry...")
                            await asyncio.sleep(delay)

                tried.append(primary_name)

        # --- Phase 2: Fallback rotation with model-level failover ---
        for _ in range(self._settings.max_retries):
            if preferred_provider and preferred_provider in self._providers:
                state = self._providers[preferred_provider]
                if not state.is_available() or preferred_provider in tried:
                    state = self.get_best_provider(exclude=tried)
            else:
                state = self.get_best_provider(exclude=tried)

            if state is None:
                break

            provider_name = state.config.name
            tried.append(provider_name)

            # Rate limit check: wait if needed
            if self._settings.rate_limiting_enabled:
                wait = self._rate_limiter.wait_time(provider_name)
                if wait > 0:
                    logger.info(f"[{provider_name}] Rate limit: waiting {wait:.2f}s")
                    await asyncio.sleep(wait)
                if not self._rate_limiter.can_request(provider_name):
                    logger.info(f"[{provider_name}] Rate limited, skipping")
                    continue

            # Level 2: try default model, then alternative models
            models_to_try = [model or state.config.default_model] + [
                m for m in state.config.models
                if m != (model or state.config.default_model)
            ]
            for model_idx, try_model in enumerate(models_to_try):
                total_attempts += 1
                try:
                    result = await self._call_provider(
                        state, prompt, system_prompt, try_model,
                        temperature, max_tokens, timeout=timeout,
                    )
                    result["attempt"] = total_attempts
                    usage = result.get("usage", {})
                    _log_completion(
                        provider=result["provider"], model=result["model"],
                        response_time=result["response_time"], attempt=total_attempts,
                        primary_retries=primary_retries, fallback=True,
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                    )
                    return result

                except Exception as e:
                    error_msg = str(e)[:200]
                    is_transient = self._is_transient(e)
                    if model_idx < len(models_to_try) - 1 and is_transient:
                        logger.warning(
                            f"[{provider_name}/{try_model}] Failed, "
                            f"trying alt model: {error_msg}"
                        )
                        continue
                    state.record_error(
                        error_msg,
                        self._settings.cooldown_seconds,
                        self._settings.rate_limit_cooldown,
                    )
                    logger.warning(
                        f"[{provider_name}/{try_model}] Fallback error "
                        f"(attempt {total_attempts}): {error_msg}"
                    )
                    break  # move to next provider

        if total_attempts == 0:
            _log_completion(
                provider="none", model="none", response_time=0,
                attempt=0, primary_retries=0, fallback=False,
                error="No available providers",
            )
            raise RuntimeError(
                f"No available LLM providers. Tried: {tried}. "
                "Check API keys and provider availability."
            )
        _log_completion(
            provider="none", model="none", response_time=0,
            attempt=total_attempts, primary_retries=primary_retries,
            fallback=True, error=f"All failed. Tried: {tried}",
        )
        raise RuntimeError(
            f"All providers failed after {total_attempts} attempts. "
            f"Tried: {tried}"
        )

    def get_stats(self) -> dict[str, Any]:
        """Return statistics for all providers."""
        stats: dict[str, Any] = {}
        for name, state in self._providers.items():
            api_key = (
                os.environ.get(state.config.api_key_env, "")
                if state.config.requires_key else "(not needed)"
            )
            cb = state.circuit_breaker
            provider_stats: dict[str, Any] = {
                "status": state.status.value,
                "circuit_breaker": cb.state.value,
                "cb_fail_count": cb.fail_count,
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
            if self._settings.adaptive_routing:
                provider_stats["adaptive"] = self._scorer.get_stats(name)
            if self._settings.rate_limiting_enabled:
                provider_stats["rate_limit"] = self._rate_limiter.get_stats(name)
            stats[name] = provider_stats
        if self._settings.adaptive_routing:
            stats["_budget"] = self._budget.get_stats()
        return stats

    def reset_provider(self, name: str) -> bool:
        """Reset a provider state to HEALTHY."""
        if name in self._providers:
            state = self._providers[name]
            state.circuit_breaker.reset()
            state.status = ProviderStatus.HEALTHY
            state.consecutive_errors = 0
            state.last_error = None
            return True
        return False

    def reset_all(self) -> None:
        """Reset all providers to HEALTHY."""
        for state in self._providers.values():
            state.circuit_breaker.reset()
            state.status = ProviderStatus.HEALTHY
            state.consecutive_errors = 0
            state.last_error = None

    @staticmethod
    def _is_transient(error: Exception) -> bool:
        """Check if error is transient (retry-worthy)."""
        msg = str(error).lower()
        return any(kw in msg for kw in (
            "timeout", "timed out", "429", "rate limit",
            "500", "502", "503", "504",
            "connection", "temporarily",
        ))

    def start_health_checks(self) -> None:
        """Start background health check loop (if enabled in settings)."""
        if not self._settings.health_check_enabled:
            return
        if self._health_task is not None and not self._health_task.done():
            return
        self._health_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"Health check loop started (interval={self._settings.health_check_interval}s)")

    def stop_health_checks(self) -> None:
        """Stop the background health check loop."""
        if self._health_task is not None and not self._health_task.done():
            self._health_task.cancel()
            self._health_task = None
            logger.info("Health check loop stopped")

    async def _health_check_loop(self) -> None:
        """Background loop: probe OPEN providers for recovery."""
        while True:
            await asyncio.sleep(self._settings.health_check_interval)
            try:
                await self._health_check_loop_once()
            except asyncio.CancelledError:
                return

    async def _health_check_loop_once(self) -> None:
        """Single pass: probe OPEN providers that have timed out."""
        for name, state in self._providers.items():
            if state.circuit_breaker.state != CircuitState.OPEN:
                continue
            if not state.circuit_breaker.can_execute():
                continue  # still within reset_timeout
            # Half-Open: send lightweight probe
            # _call_provider already calls state.record_success() which updates CB
            try:
                await self._call_provider(state, "ping", max_tokens=5)
                logger.info(f"[{name}] Health check PASSED, recovered")
                _log_completion(
                    provider=name, model=state.config.default_model,
                    response_time=0, attempt=0, health_check=True,
                    result="recovered",
                )
            except Exception as e:
                state.record_error(str(e)[:200])
                logger.info(f"[{name}] Health check FAILED: {e}")
                _log_completion(
                    provider=name, model=state.config.default_model,
                    response_time=0, attempt=0, health_check=True,
                    result="failed", error=str(e)[:200],
                )

    async def close(self) -> None:
        """Close the HTTP session, stop health checks, save state."""
        self.stop_health_checks()
        if self._settings.persist_adaptive:
            self._save_state()
        if self._session and not self._session.closed:
            await self._session.close()


# Singleton
_service: LLMRotationService | None = None


def get_service() -> LLMRotationService:
    """Get or create singleton service instance."""
    global _service
    if _service is None:
        _service = LLMRotationService()
    return _service
