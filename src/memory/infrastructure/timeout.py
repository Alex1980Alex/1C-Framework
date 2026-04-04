"""
Timeout configuration for the Unified Memory System.

Provides a simple dataclass-based configuration with sensible defaults.
No YAML dependency — values come from dataclass defaults or env vars.
"""

import os
from dataclasses import dataclass


@dataclass
class TimeoutConfig:
    """Centralized timeout values for memory operations (seconds)."""

    # General
    search: float = 5.0
    backend_default: float = 10.0
    backend_slow: float = 30.0

    # Orchestrator
    parallel_search: float = 15.0
    route_and_save: float = 10.0
    health_check: float = 5.0
    system_stats: float = 3.0

    # Infrastructure
    circuit_breaker_timeout: float = 60.0
    connection_timeout: float = 30.0
    tool_call_timeout: float = 60.0
    http_request_timeout: float = 30.0
    db_command_timeout: float = 60.0

    # Caches / pools
    cache_ttl: float = 300.0
    cache_short_ttl: float = 30.0
    cache_long_ttl: float = 600.0

    def __post_init__(self):
        """Override defaults from environment variables (MEMORY_TIMEOUT_*)."""
        env_map = {
            "MEMORY_TIMEOUT_SEARCH": "search",
            "MEMORY_TIMEOUT_BACKEND": "backend_default",
            "MEMORY_TIMEOUT_BACKEND_SLOW": "backend_slow",
            "MEMORY_TIMEOUT_PARALLEL_SEARCH": "parallel_search",
            "MEMORY_TIMEOUT_HEALTH_CHECK": "health_check",
            "MEMORY_TIMEOUT_CIRCUIT_BREAKER": "circuit_breaker_timeout",
            "MEMORY_TIMEOUT_CONNECTION": "connection_timeout",
            "MEMORY_TIMEOUT_TOOL_CALL": "tool_call_timeout",
            "MEMORY_TIMEOUT_CACHE_TTL": "cache_ttl",
        }
        for env_key, field_name in env_map.items():
            val = os.getenv(env_key)
            if val is not None:
                try:
                    setattr(self, field_name, float(val))
                except ValueError:
                    pass

    def to_dict(self) -> dict[str, float]:
        """Return all timeout values as a dict."""
        from dataclasses import fields

        return {f.name: getattr(self, f.name) for f in fields(self)}


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_timeout_config: TimeoutConfig | None = None


def get_timeout_config() -> TimeoutConfig:
    """Return the global TimeoutConfig instance (lazy-created)."""
    global _timeout_config
    if _timeout_config is None:
        _timeout_config = TimeoutConfig()
    return _timeout_config
