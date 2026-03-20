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
from datetime import UTC, datetime
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
            "ts": datetime.now(UTC).isoformat(),
            "component": component,
            "provider": provider,
            "response_time_s": round(response_time, 3),
            "success": success,
            "fallback": fallback,
            "text_len": text_len,
        }
        with open(_METRICS_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as exc:
        logger.debug("[CHEAP-LLM] Metrics write failed: %s", exc)


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
    resolved_temperature: float = (
        temperature if temperature is not None else reg.get("temperature", 0.7)
    )

    service = get_service()
    t0 = time.time()

    try:
        result = await service.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=resolved_temperature,
            max_tokens=resolved_max_tokens,
        )
        elapsed = time.time() - t0
        text = result.get("text", "")
        provider = result.get("provider", "unknown")

        if not text.strip():
            logger.warning(
                "[CHEAP-LLM] %s: empty response from %s (%.1fs)",
                component, provider, elapsed,
            )
            _log_metric(component, provider, elapsed, success=False, fallback=False, text_len=0)
            return ""

        logger.debug(
            "[CHEAP-LLM] %s: %s responded in %.1fs (%d chars)",
            component, provider, elapsed, len(text),
        )
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


# ---------------------------------------------------------------------------
# Quality evaluation criteria per component
# ---------------------------------------------------------------------------

QUALITY_CRITERIA: dict[str, dict[str, Any]] = {
    "grader": {
        "metric": "exact_match",
        "expected_format": "yes|no",
        "min_length": 2,
        "description": "Binary relevance grading — must output yes/no",
    },
    "hallucination_checker": {
        "metric": "exact_match",
        "expected_format": "grounded|not_grounded",
        "min_length": 5,
        "description": "Binary grounding check",
    },
    "rewriter": {
        "metric": "different_from_input",
        "min_length": 5,
        "description": "Must produce a rewritten query different from original",
    },
    "query_expansion": {
        "metric": "contains_keywords",
        "min_length": 10,
        "description": "Must produce expanded query with additional terms",
    },
    "hyde": {
        "metric": "min_length",
        "min_length": 30,
        "description": "Must produce a plausible hypothetical passage",
    },
    "search_classifier": {
        "metric": "valid_classification",
        "expected_format": (
            r"(simple|moderate|complex|thematic)\s+"
            r"(factual|analytical|comparative|thematic)\s+\d"
        ),
        "min_length": 10,
        "description": "Must output: complexity type confidence",
    },
    "section_summary": {
        "metric": "min_length",
        "min_length": 20,
        "description": "2-3 sentence section summary",
    },
    "context_generator": {
        "metric": "min_length",
        "min_length": 10,
        "description": "1-2 sentence context for chunk",
    },
    "entity_extractor": {
        "metric": "valid_json",
        "min_length": 10,
        "description": "Must produce valid JSON with entities/relations arrays",
    },
    "community_summarizer": {
        "metric": "min_length",
        "min_length": 30,
        "description": "2-3 sentence community theme summary",
    },
}


def evaluate_response(component: str, response: str, original_input: str = "") -> dict[str, Any]:
    """Evaluate cheap LLM response quality against component criteria.

    Args:
        component: Component name from COMPONENT_REGISTRY.
        response: The LLM response text.
        original_input: Original input (for 'different_from_input' metric).

    Returns:
        {"passed": bool, "metric": str, "reason": str}
    """
    criteria = QUALITY_CRITERIA.get(component)
    if not criteria:
        return {"passed": True, "metric": "none", "reason": "No criteria defined"}

    text = response.strip()
    min_len = criteria.get("min_length", 1)

    if len(text) < min_len:
        return {"passed": False, "metric": "min_length",
                "reason": f"Too short: {len(text)} < {min_len}"}

    metric = criteria.get("metric", "min_length")

    if metric == "exact_match":
        expected = criteria.get("expected_format", "")
        options = [o.strip() for o in expected.split("|")]
        if text.lower() not in options:
            return {"passed": False, "metric": metric,
                    "reason": f"Expected one of {options}, got '{text[:50]}'"}

    elif metric == "different_from_input":
        if original_input and text.lower().strip() == original_input.lower().strip():
            return {"passed": False, "metric": metric,
                    "reason": "Response identical to input"}

    elif metric == "valid_json":
        import json as _json
        try:
            _json.loads(text)
        except _json.JSONDecodeError:
            # Try stripping markdown code blocks
            cleaned = text
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
            try:
                _json.loads(cleaned)
            except _json.JSONDecodeError:
                return {"passed": False, "metric": metric,
                        "reason": "Not valid JSON"}

    elif metric == "valid_classification":
        import re
        pattern = criteria.get("expected_format", "")
        if pattern and not re.match(pattern, text):
            return {"passed": False, "metric": metric,
                    "reason": "Doesn't match classification pattern"}

    return {"passed": True, "metric": metric, "reason": "OK"}


# ---------------------------------------------------------------------------
# Auto-discovery: find LLM components not yet in COMPONENT_REGISTRY
# ---------------------------------------------------------------------------

def discover_unregistered_components() -> list[dict[str, str]]:
    """Scan framework source for ChatAnthropic/Anthropic usage not in COMPONENT_REGISTRY.

    Returns list of dicts with 'file', 'pattern', 'suggestion' keys.
    Useful for finding new components that could benefit from cheap LLM.
    """
    import re
    from pathlib import Path

    src_root = Path(__file__).parent.parent.parent  # src/
    patterns = [
        re.compile(r"ChatAnthropic\("),
        re.compile(r"Anthropic\("),
        re.compile(r"\.ainvoke\("),
    ]

    # Files already covered by COMPONENT_REGISTRY integrations
    known_files = {
        "grader.py", "hallucination_checker.py", "rewriter.py",
        "query_expansion.py", "hyde.py", "classifier.py",
        "section_summary.py", "context_generator.py",
        "entity_extractor.py", "summarizer.py",
        # Infrastructure (not candidates)
        "adapter.py", "service.py", "zai_proxy.py", "mcp.py",
    }

    candidates: list[dict[str, str]] = []
    seen_files: set[str] = set()

    for py_file in src_root.rglob("*.py"):
        if py_file.name in known_files:
            continue
        if "__pycache__" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for pattern in patterns:
            if pattern.search(content):
                rel = str(py_file.relative_to(src_root))
                if rel not in seen_files:
                    seen_files.add(rel)
                    candidates.append({
                        "file": rel,
                        "pattern": pattern.pattern,
                        "suggestion": f"Review {py_file.name} for cheap LLM integration",
                    })
                break

    return candidates
