#!/usr/bin/env python3
"""Pre-Work worker: Architecture context (cache lookup).

Reads stdin {prompt} → fuzzy match against architecture-research/cache/_index.json
keywords + titles → writes stdout {items: [{title, body, score}]}.

Called by shared/prework_dispatcher.py (parallel UPS via asyncio).
Standalone (CLI-callable for testing).

Per ADR-D1 (roadmap 260523 §17.1): low-latency local cache lookup, no network,
no LLM. rapidfuzz Rust-backed (3.14+).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    from rapidfuzz import fuzz, process

    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_INDEX = (
    PROJECT_ROOT / ".claude" / "skills" / "architecture-research" / "cache" / "_index.json"
)
ADR_DIR = PROJECT_ROOT / ".claude" / "skills" / "architecture-research" / "adr"

MIN_SCORE = 60  # 0-100 rapidfuzz threshold
TOP_K = 3
MAX_BODY_CHARS = 180


def _tokenize(text: str) -> list[str]:
    """Extract significant tokens from prompt (≥3 chars, lowercase)."""
    tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_\-]+", text.lower())
    return [t for t in tokens if len(t) >= 3]


def _load_cache_index() -> list[dict]:
    """Read architecture-research cache index."""
    if not CACHE_INDEX.exists():
        return []
    try:
        data = json.loads(CACHE_INDEX.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("topics", [])
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _score_topic(prompt_tokens: list[str], topic: dict) -> float:
    """Score topic relevance to prompt via rapidfuzz on keywords + title."""
    if not HAS_RAPIDFUZZ or not isinstance(topic, dict):
        return 0.0
    keywords = topic.get("keywords", []) or []
    title = topic.get("title", "") or ""
    if not keywords and not title:
        return 0.0

    haystack = list(keywords) + [title]
    best = 0.0
    for tok in prompt_tokens:
        if not tok:
            continue
        # token_set_ratio handles substring + multi-word
        match = process.extractOne(tok, haystack, scorer=fuzz.token_set_ratio)
        if match and match[1] > best:
            best = float(match[1])
    return best


def _build_items(topics: list[dict], prompt: str) -> list[dict]:
    """Score + rank topics, return top-K items."""
    if not topics:
        return []
    tokens = _tokenize(prompt)
    if not tokens:
        return []

    scored: list[tuple[float, dict]] = []
    for topic in topics:
        score = _score_topic(tokens, topic)
        if score >= MIN_SCORE:
            scored.append((score, topic))

    scored.sort(key=lambda x: x[0], reverse=True)

    items = []
    for score, topic in scored[:TOP_K]:
        title = topic.get("title", topic.get("file", "?"))
        keywords = topic.get("keywords", []) or []
        body_parts = []
        if keywords:
            body_parts.append(", ".join(keywords[:5]))
        cache_file = topic.get("file", "")
        if cache_file:
            body_parts.append(f"→ cache/{cache_file}")
        body = " | ".join(body_parts)[:MAX_BODY_CHARS]
        items.append({"title": title, "body": body, "score": round(score / 100.0, 3)})
    return items


def main() -> int:
    """CLI entry. Reads stdin JSON {prompt}, writes stdout JSON {items}."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, ValueError):
        payload = {}

    prompt = payload.get("prompt", "")
    if not prompt or not HAS_RAPIDFUZZ:
        # Empty / no-rapidfuzz → empty items, dispatcher проигнорирует
        print(json.dumps({"items": []}, ensure_ascii=False))
        return 0

    topics = _load_cache_index()
    items = _build_items(topics, prompt)
    print(json.dumps({"items": items}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
