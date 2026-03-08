"""CheapLLM Adapter — bridge between LLM Rotation and framework components.

Provides cheap_llm_call() for components that don't need Claude quality.
Auto-fallback to Claude on failure. Quality metrics logged to JSONL.

Usage:
    from src.shared.llm_rotation.adapter import cheap_llm_call, is_cheap_llm_enabled

    if is_cheap_llm_enabled("grader"):
        text = await cheap_llm_call(prompt, system_prompt, max_tokens=50)
    else:
        # use original ChatAnthropic
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Component categories with default max_tokens and quality thresholds
COMPONENT_REGISTRY: dict[str, dict[str, Any]] = {
    # Category 1: Ideal candidates (simple tasks, short output)
    "grader": {"category": 1, "max_tokens": 50, "temperature": 0.0},
    "hallucination_checker": {"category": 1, "max_tokens": 100, "temperature": 0.0},
    "rewriter": {"category": 1, "max_tokens": 200, "temperature": 0.7},
    "query_expansion": {"category": 1, "max_tokens": 300, "temperature": 0.7},
    "hyde": {"category": 1, "max_tokens": 512, "temperature": 0.3},
    "search_classifier": {"category": 1, "max_tokens": 100, "temperature": 0.0},
    # Category 2: Possible candidates (medium complexity)
    "section_summary": {"category": 2, "max_tokens": 300, "temperature": 0.3},
    "context_generator": {"category": 2, "max_tokens": 200, "temperature": 0.0},
    "entity_extractor": {"category": 2, "max_tokens": 4096, "temperature": 0.0},
    "community_summarizer": {"category": 2, "max_tokens": 1024, "temperature": 0.0},
}

# Metrics log path
_METRICS_PATH = Path("data/llm-rotation-metrics.jsonl")

# Cached enabled components (parsed once from env)
_enabled_components: set[str] | None = None


def _get_enabled_components() -> set[str]:
    """Parse LLM_ROTATION_COMPONENTS from env. Default: all Category 1."""
    global _enabled_components
    if _enabled_components is not None:
        return _enabled_components

    env_val = os.environ.get("LLM_ROTATION_COMPONENTS", "").strip()
    if env_val:
        _enabled_components = {c.strip() for c in env_val.split(",") if c.strip()}
    else:
        # Default: all Category 1 components
        _enabled_components = {
            name for name, cfg in COMPONENT_REGISTRY.items()
            if cfg["category"] == 1
        }

    if _enabled_components:
        logger.info("[CHEAP-LLM] Enabled for: %s", ", ".join(sorted(_enabled_components)))
    return _enabled_components


def is_cheap_llm_enabled(component: str) -> bool:
    """Check if a component should use cheap LLM.

    Args:
        component: Component name from COMPONENT_REGISTRY.

    Returns:
        True if LLM Rotation is enabled globally and for this component.
    """
    if os.environ.get("LLM_ROTATION_ENABLED", "true").lower() not in ("true", "1", "yes"):
        return False
    return component in _get_enabled_components()


def _log_metric(component: str, provider: str, response_time: float,
                success: bool, fallback: bool, text_len: int) -> None:
    """Append metric entry to JSONL log."""
    try:
        _METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "provider": provider,
            "response_time_s": round(response_time, 3),
            "success": success,
            "fallback": fallback,
            "text_len": text_len,
        }
        with open(_METRICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # metrics are best-effort


async def cheap_llm_call(
    prompt: str,
    system_prompt: str | None = None,
    component: str = "unknown",
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """Call LLM Rotation service for cheap inference.

    Args:
        prompt: User prompt text.
        system_prompt: Optional system prompt.
        component: Component name for metrics/config lookup.
        max_tokens: Override max_tokens (default from COMPONENT_REGISTRY).
        temperature: Override temperature (default from COMPONENT_REGISTRY).

    Returns:
        Response text. Empty string on total failure.
    """
    from src.shared.llm_rotation.service import get_service

    # Resolve defaults from registry
    reg = COMPONENT_REGISTRY.get(component, {})
    resolved_max_tokens: int = max_tokens if max_tokens is not None else reg.get("max_tokens", 200)
    resolved_temperature: float = temperature if temperature is not None else reg.get("temperature", 0.7)

    service = get_service()
    t0 = time.time()

    try:
        result = await service.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        elapsed = time.time() - t0
        text = result.get("text", "")
        provider = result.get("provider", "unknown")

        if not text.strip():
            logger.warning("[CHEAP-LLM] %s: empty response from %s (%.1fs)", component, provider, elapsed)
            _log_metric(component, provider, elapsed, success=False, fallback=False, text_len=0)
            return ""

        logger.debug("[CHEAP-LLM] %s: %s responded in %.1fs (%d chars)", component, provider, elapsed, len(text))
        _log_metric(component, provider, elapsed, success=True, fallback=False, text_len=len(text))
        return text

    except Exception as e:
        elapsed = time.time() - t0
        logger.error("[CHEAP-LLM] %s: rotation failed (%.1fs): %s", component, elapsed, e)
        _log_metric(component, "error", elapsed, success=False, fallback=True, text_len=0)
        return ""


def reset_enabled_cache() -> None:
    """Reset cached enabled components (for testing)."""
    global _enabled_components
    _enabled_components = None
