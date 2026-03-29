#!/usr/bin/env python3
"""
Hook: posttooluse-web-cache
Event: PostToolUse
Matcher: WebSearch|WebFetch
Purpose: Cache WebSearch/WebFetch results for 24h TTL.
         Saves results to .claude/cache/web-search/{hash}.json.
         No feedback to Claude (pure side effect, exit 0).
Timeout: 3s
"""

import hashlib
import json
import os
import sys
import time

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput


def _get_cache_dir() -> str:
    """Get cache directory for web search results."""
    project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
    cache_dir = os.path.join(project_dir, ".claude", "cache", "web-search")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _make_cache_key(query: str) -> str:
    """Create deterministic cache key from query."""
    return hashlib.sha256(query.lower().strip().encode("utf-8")).hexdigest()[:16]


def _save_to_cache(cache_dir: str, key: str, query: str,
                   tool_name: str, response: str, ttl: int = 86400) -> None:
    """Save search result to cache file."""
    entry = {
        "query": query,
        "tool": tool_name,
        "response": response,
        "timestamp": time.time(),
        "ttl": ttl,
    }
    path = os.path.join(cache_dir, f"{key}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)


def _cleanup_expired(cache_dir: str) -> int:
    """Remove expired cache entries. Returns count of removed entries."""
    removed = 0
    now = time.time()
    try:
        for fname in os.listdir(cache_dir):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(cache_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                if now - entry.get("timestamp", 0) > entry.get("ttl", 86400):
                    os.remove(fpath)
                    removed += 1
            except (json.JSONDecodeError, OSError):
                pass
    except OSError:
        pass
    return removed


class PostToolUseWebCache(BaseHook):
    """PostToolUse hook for WebSearch/WebFetch: cache results with TTL."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.tool_name not in ("WebSearch", "WebFetch"):
            return None

        # Extract query from tool_input
        tool_input = inp.tool_input
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except (json.JSONDecodeError, AttributeError):
                return None

        if not isinstance(tool_input, dict):
            return None

        query = tool_input.get("query", tool_input.get("url", ""))
        if not query:
            return None

        # Get tool_response
        tool_response = inp.raw.get("tool_response", "")
        if not tool_response:
            return None

        response_text = str(tool_response) if tool_response else ""
        if len(response_text) < 20:
            return None

        # Save to cache
        cache_dir = _get_cache_dir()
        key = _make_cache_key(query)
        _save_to_cache(cache_dir, key, query, inp.tool_name, response_text)

        # Cleanup expired entries (lightweight, runs on every call)
        _cleanup_expired(cache_dir)

        return None


if __name__ == "__main__":
    PostToolUseWebCache().run()
