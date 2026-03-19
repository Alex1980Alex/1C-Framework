"""
Integration tests for LLM Rotation Service (Phase 50).

Tests:
- Provider configuration and state management
- Fallback logic with mocked providers
- Health tracking and cooldown
- Service statistics
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.shared.llm_rotation.config import LLMRotationSettings
from src.shared.llm_rotation.service import (
    DEFAULT_PROVIDERS,
    LLMRotationService,
    ProviderConfig,
    ProviderState,
    ProviderStatus,
)


# ========== ProviderConfig Tests ==========


class TestProviderConfig:
    def test_default_providers_exist(self):
        assert len(DEFAULT_PROVIDERS) == 7
        names = [p.name for p in DEFAULT_PROVIDERS]
        assert "zai-glm5" in names
        assert "zhipu" in names
        assert "gemini" in names
        assert "mistral" in names
        assert "ollama-cloud" in names

    def test_provider_priority_order(self):
        priorities = [p.priority for p in DEFAULT_PROVIDERS]
        assert priorities == sorted(priorities)

    def test_provider_formats(self):
        for p in DEFAULT_PROVIDERS:
            assert p.format in ("openai", "ollama", "anthropic")

    def test_ollama_no_key_required(self):
        ollama = [p for p in DEFAULT_PROVIDERS if p.format == "ollama"]
        for p in ollama:
            assert p.requires_key is False


# ========== ProviderState Tests ==========


class TestProviderState:
    def test_initial_state(self):
        cfg = ProviderConfig(name="test", base_url="http://test", api_key_env="", default_model="m")
        state = ProviderState(config=cfg)
        assert state.status == ProviderStatus.HEALTHY
        assert state.is_available()
        assert state.requests_count == 0

    def test_record_success(self):
        cfg = ProviderConfig(name="test", base_url="http://test", api_key_env="", default_model="m")
        state = ProviderState(config=cfg)
        state.record_success(1.5)
        assert state.requests_count == 1
        assert state.avg_response_time == 1.5
        assert state.consecutive_errors == 0

    def test_record_error_degraded(self):
        cfg = ProviderConfig(name="test", base_url="http://test", api_key_env="", default_model="m")
        state = ProviderState(config=cfg)
        state.record_error("connection timeout")
        assert state.status == ProviderStatus.DEGRADED
        assert state.errors_count == 1
        assert state.consecutive_errors == 1

    def test_record_error_cooldown_after_3(self):
        cfg = ProviderConfig(name="test", base_url="http://test", api_key_env="", default_model="m")
        state = ProviderState(config=cfg)
        for _ in range(3):
            state.record_error("error")
        assert state.status == ProviderStatus.COOLDOWN
        assert not state.is_available()

    def test_rate_limit_cooldown(self):
        cfg = ProviderConfig(name="test", base_url="http://test", api_key_env="", default_model="m")
        state = ProviderState(config=cfg)
        state.record_error("HTTP 429 rate limit exceeded")
        assert state.status == ProviderStatus.COOLDOWN

    def test_cooldown_expires(self):
        cfg = ProviderConfig(name="test", base_url="http://test", api_key_env="", default_model="m")
        state = ProviderState(config=cfg)
        state.status = ProviderStatus.COOLDOWN
        state.cooldown_until = datetime.now() - timedelta(seconds=1)
        assert state.is_available()
        assert state.status == ProviderStatus.DEGRADED

    def test_unavailable_not_available(self):
        cfg = ProviderConfig(name="test", base_url="http://test", api_key_env="", default_model="m")
        state = ProviderState(config=cfg)
        state.status = ProviderStatus.UNAVAILABLE
        assert not state.is_available()

    def test_success_resets_errors(self):
        cfg = ProviderConfig(name="test", base_url="http://test", api_key_env="", default_model="m")
        state = ProviderState(config=cfg)
        state.record_error("err1")
        state.record_error("err2")
        assert state.consecutive_errors == 2
        state.record_success(1.0)
        assert state.consecutive_errors == 0
        assert state.status == ProviderStatus.HEALTHY


# ========== LLMRotationService Tests ==========


class TestLLMRotationService:
    def test_create_with_defaults(self):
        service = LLMRotationService()
        assert len(service._providers) == 7

    def test_create_with_custom_providers(self):
        configs = [
            ProviderConfig(name="test1", base_url="http://t1", api_key_env="", default_model="m1", requires_key=False),
            ProviderConfig(name="test2", base_url="http://t2", api_key_env="", default_model="m2", requires_key=False),
        ]
        service = LLMRotationService(providers=configs)
        assert len(service._providers) == 2

    def test_get_available_no_keys(self):
        """Providers requiring keys but without env vars are not available."""
        configs = [
            ProviderConfig(name="needs-key", base_url="http://t", api_key_env="NONEXISTENT_KEY_12345", default_model="m"),
        ]
        service = LLMRotationService(providers=configs)
        assert len(service.get_available_providers()) == 0

    def test_get_available_no_key_required(self):
        configs = [
            ProviderConfig(name="free", base_url="http://t", api_key_env="", default_model="m", requires_key=False),
        ]
        service = LLMRotationService(providers=configs)
        assert len(service.get_available_providers()) == 1

    def test_get_best_provider(self):
        configs = [
            ProviderConfig(name="p1", base_url="http://t", api_key_env="", default_model="m", requires_key=False, priority=2),
            ProviderConfig(name="p2", base_url="http://t", api_key_env="", default_model="m", requires_key=False, priority=1),
        ]
        service = LLMRotationService(providers=configs)
        best = service.get_best_provider()
        assert best is not None
        assert best.config.name == "p2"

    def test_get_best_prefers_healthy(self):
        configs = [
            ProviderConfig(name="degraded", base_url="http://t", api_key_env="", default_model="m", requires_key=False, priority=0),
            ProviderConfig(name="healthy", base_url="http://t", api_key_env="", default_model="m", requires_key=False, priority=1),
        ]
        service = LLMRotationService(providers=configs)
        service._providers["degraded"].status = ProviderStatus.DEGRADED
        best = service.get_best_provider()
        assert best.config.name == "healthy"

    def test_reset_provider(self):
        configs = [
            ProviderConfig(name="test", base_url="http://t", api_key_env="", default_model="m", requires_key=False),
        ]
        service = LLMRotationService(providers=configs)
        service._providers["test"].status = ProviderStatus.COOLDOWN
        service._providers["test"].consecutive_errors = 5
        assert service.reset_provider("test")
        assert service._providers["test"].status == ProviderStatus.HEALTHY
        assert service._providers["test"].consecutive_errors == 0

    def test_reset_nonexistent(self):
        service = LLMRotationService(providers=[])
        assert not service.reset_provider("nonexistent")

    def test_reset_all(self):
        configs = [
            ProviderConfig(name="p1", base_url="http://t", api_key_env="", default_model="m", requires_key=False),
            ProviderConfig(name="p2", base_url="http://t", api_key_env="", default_model="m", requires_key=False),
        ]
        service = LLMRotationService(providers=configs)
        service._providers["p1"].status = ProviderStatus.COOLDOWN
        service._providers["p2"].status = ProviderStatus.DEGRADED
        service.reset_all()
        assert all(s.status == ProviderStatus.HEALTHY for s in service._providers.values())

    def test_get_stats(self):
        configs = [
            ProviderConfig(name="test", base_url="http://t", api_key_env="", default_model="m", requires_key=False),
        ]
        service = LLMRotationService(providers=configs)
        service._providers["test"].record_success(1.5)
        stats = service.get_stats()
        assert "test" in stats
        assert stats["test"]["requests"] == 1
        assert stats["test"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_complete_no_providers(self):
        """Should raise if no providers available."""
        settings = LLMRotationSettings(max_retries=1)
        service = LLMRotationService(providers=[], settings=settings)
        with pytest.raises(RuntimeError, match="No available LLM providers"):
            await service.complete("test prompt")

    @pytest.mark.asyncio
    async def test_complete_with_mock(self):
        """Test successful completion with mocked HTTP."""
        configs = [
            ProviderConfig(name="mock", base_url="http://mock", api_key_env="", default_model="m", requires_key=False),
        ]
        service = LLMRotationService(providers=configs)

        mock_response = {
            "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
            "model": "m",
            "usage": {"prompt_tokens": 5, "completion_tokens": 2},
        }

        with patch.object(service, "_make_request_openai", new_callable=AsyncMock, return_value=mock_response):
            result = await service.complete("Say hello")
            assert result["provider"] == "mock"
            assert result["text"] == "Hello!"
            assert result["attempt"] == 1

    @pytest.mark.asyncio
    async def test_fallback_on_error(self):
        """Test automatic fallback when first provider fails."""
        configs = [
            ProviderConfig(name="failing", base_url="http://f", api_key_env="", default_model="m", requires_key=False, priority=0),
            ProviderConfig(name="working", base_url="http://w", api_key_env="", default_model="m", requires_key=False, priority=1),
        ]
        service = LLMRotationService(providers=configs)

        mock_ok = {
            "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
            "model": "m",
            "usage": {},
        }

        call_count = 0

        async def mock_request(state, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if state.config.name == "failing":
                raise RuntimeError("Connection refused")
            return mock_ok

        with patch.object(service, "_make_request_openai", side_effect=mock_request):
            result = await service.complete("test")
            assert result["provider"] == "working"
            assert result["attempt"] == 2

    @pytest.mark.asyncio
    async def test_close_session(self):
        service = LLMRotationService(providers=[])
        await service.close()  # Should not raise


# ========== Settings Tests ==========


class TestSettings:
    def test_defaults(self):
        settings = LLMRotationSettings()
        assert settings.primary_provider == "zai-glm5"
        assert settings.max_retries == 3
        assert settings.timeout in (30, 60)  # 30 default, 60 from .env override

    def test_custom_values(self):
        settings = LLMRotationSettings(max_retries=5, timeout=60)
        assert settings.max_retries == 5
        assert settings.timeout == 60


# ========== Z.AI Proxy Tests ==========


class TestZAIProxy:
    def test_openai_to_anthropic_basic(self):
        from src.shared.llm_rotation.zai_proxy import openai_to_anthropic

        result = openai_to_anthropic({
            "model": "glm-5",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
            "max_tokens": 100,
        })
        assert result["model"] == "glm-5"
        assert result["system"] == "You are helpful."
        assert len(result["messages"]) == 1
        assert result["messages"][0]["role"] == "user"
        assert result["max_tokens"] == 100

    def test_anthropic_to_openai_basic(self):
        from src.shared.llm_rotation.zai_proxy import anthropic_to_openai

        result = anthropic_to_openai({
            "id": "msg_123",
            "content": [{"type": "text", "text": "Hello back!"}],
            "stop_reason": "end_turn",
            "model": "glm-5",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        })
        assert result["choices"][0]["message"]["content"] == "Hello back!"
        assert result["choices"][0]["finish_reason"] == "stop"
        assert result["usage"]["total_tokens"] == 15

    def test_stop_reason_mapping(self):
        from src.shared.llm_rotation.zai_proxy import _map_stop_reason

        assert _map_stop_reason("end_turn") == "stop"
        assert _map_stop_reason("tool_use") == "tool_calls"
        assert _map_stop_reason("max_tokens") == "length"
        assert _map_stop_reason("unknown") == "stop"

    def test_tool_conversion(self):
        from src.shared.llm_rotation.zai_proxy import openai_to_anthropic

        result = openai_to_anthropic({
            "model": "glm-5",
            "messages": [{"role": "user", "content": "Search for X"}],
            "tools": [{
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search documents",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
                },
            }],
        })
        assert len(result["tools"]) == 1
        assert result["tools"][0]["name"] == "search"

    def test_thinking_response(self):
        from src.shared.llm_rotation.zai_proxy import anthropic_to_openai

        result = anthropic_to_openai({
            "id": "msg_456",
            "content": [
                {"type": "thinking", "thinking": "Let me think..."},
                {"type": "text", "text": "The answer is 42."},
            ],
            "stop_reason": "end_turn",
            "model": "glm-5",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        })
        msg = result["choices"][0]["message"]
        assert msg["content"] == "The answer is 42."
        assert msg["reasoning_content"] == "Let me think..."
