#!/usr/bin/env python3
"""Pre-Work worker: GitHub best-practices via architecture-research cache.

Reads stdin {prompt} → fuzzy match prompt → topics in architecture-research
cache filtered by `github_repos_count > 0` (significant GitHub content) →
freshness check (`last_verified` <= 365 days) → top-K items.

Called by shared/prework_dispatcher.py (parallel UPS via asyncio).
Standalone (CLI-callable for testing).

Per §14.4 Option B (roadmap 260523): cache-first warm path. Cold-path
(WebSearch + cache write) НЕ запускается из worker — это задача
отдельного background batch dispatcher (§14.6 P2 item 8). Worker emit
empty items когда cache miss/stale, dispatcher показывает остальные источники.

Latency budget: ~0.5s (file read + rapidfuzz). Timeout в dispatcher 4s
(запас на возможный future cold-path).

References:
- Worker contract: shared/prework_dispatcher.py
- Cache index: .claude/skills/architecture-research/cache/_index.json
"""

from __future__ import annotations

import datetime as dt
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
CACHE_DIR = CACHE_INDEX.parent

MIN_SCORE = 60  # rapidfuzz 0-100 threshold
TOP_K = 3
MAX_BODY_CHARS = 180
FRESHNESS_DAYS = 365  # best-practices research stays relevant ~1 year


def _tokenize(text: str) -> list[str]:
    """Extract significant tokens (≥3 chars, lowercase)."""
    tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_\-]+", text.lower())
    return [t for t in tokens if len(t) >= 3]


def _load_topics() -> list[dict]:
    """Read cache _index.json topics list."""
    if not CACHE_INDEX.exists():
        return []
    try:
        data = json.loads(CACHE_INDEX.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("topics", []) or []
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def _has_github_signal(topic: dict) -> bool:
    """True if topic includes GitHub research content."""
    if not isinstance(topic, dict):
        return False
    if int(topic.get("github_repos_count") or 0) > 0:
        return True
    # Fallback: keyword/title containing 'github' (some older entries
    # don't carry github_repos_count but reference GitHub directly).
    haystack = " ".join(
        [
            str(topic.get("title", "")),
            " ".join(topic.get("keywords", []) or []),
        ]
    ).lower()
    return "github" in haystack


def _is_fresh(topic: dict) -> bool:
    """True if topic verified within FRESHNESS_DAYS (else stale)."""
    verified = topic.get("last_verified") or topic.get("created") or ""
    if not verified:
        return False
    try:
        verified_date = dt.date.fromisoformat(str(verified)[:10])
    except (ValueError, TypeError):
        return False
    age = (dt.date.today() - verified_date).days
    return age <= FRESHNESS_DAYS


def _score_topic(prompt_tokens: list[str], topic: dict) -> float:
    """rapidfuzz token_set_ratio against keywords + title."""
    if not HAS_RAPIDFUZZ:
        return 0.0
    keywords = topic.get("keywords", []) or []
    title = topic.get("title", "") or ""
    haystack = list(keywords) + [title]
    if not haystack:
        return 0.0
    best = 0.0
    for tok in prompt_tokens:
        if not tok:
            continue
        match = process.extractOne(tok, haystack, scorer=fuzz.token_set_ratio)
        if match and match[1] > best:
            best = float(match[1])
    return best


def _build_items(topics: list[dict], prompt: str) -> list[dict]:
    """Score + filter github topics, return top-K items."""
    tokens = _tokenize(prompt)
    if not tokens:
        return []

    scored: list[tuple[float, dict]] = []
    for topic in topics:
        if not _has_github_signal(topic):
            continue
        if not _is_fresh(topic):
            continue
        score = _score_topic(tokens, topic)
        if score >= MIN_SCORE:
            scored.append((score, topic))

    scored.sort(key=lambda x: x[0], reverse=True)

    items = []
    for score, topic in scored[:TOP_K]:
        title = topic.get("title", topic.get("file", "?"))
        cache_file = topic.get("file", "")
        repos_count = int(topic.get("github_repos_count") or 0)
        sources_count = int(topic.get("sources_count") or 0)

        body_parts = []
        if repos_count:
            body_parts.append(f"{repos_count} GitHub repos")
        if sources_count:
            body_parts.append(f"{sources_count} sources")
        if cache_file:
            body_parts.append(f"→ cache/{cache_file}")
        body = " | ".join(body_parts)[:MAX_BODY_CHARS]

        items.append({"title": title, "body": body, "score": round(score / 100.0, 3)})
    return items


def main() -> int:
    """CLI entry. stdin JSON {prompt} → stdout JSON {items}."""
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
        print(json.dumps({"items": []}, ensure_ascii=False))
        return 0

    topics = _load_topics()
    items = _build_items(topics, prompt)
    print(json.dumps({"items": items}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
