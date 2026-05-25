#!/usr/bin/env python3
"""Pre-Work worker: Stack Overflow / error-troubleshooting context.

Reads stdin {prompt} → fuzzy match prompt → topics in tech-research +
architecture-research caches filtered by SO/error/debugging signals →
freshness check → top-K items.

Called by shared/prework_dispatcher.py (parallel UPS via asyncio).
Standalone (CLI-callable for testing).

Per §14.5 Option C (roadmap 260523): cache-first warm path. Reactive
PostToolUse:Bash on error handled in separate hook
(posttooluse-stackoverflow-on-error.py — covers concrete failures).

Cache schemas differ:
- architecture-research/cache/_index.json — topics is a LIST.
- tech-research/cache/_index.json — topics is a DICT keyed by topic-id.

Both formats normalized to list[dict] before scoring.

Latency budget: ~0.5s (file reads + rapidfuzz). Timeout in dispatcher 1s.

References:
- Worker contract: shared/prework_dispatcher.py
- Cache indexes:
    .claude/skills/tech-research/cache/_index.json
    .claude/skills/architecture-research/cache/_index.json
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
TECH_INDEX = PROJECT_ROOT / ".claude" / "skills" / "tech-research" / "cache" / "_index.json"
ARCH_INDEX = PROJECT_ROOT / ".claude" / "skills" / "architecture-research" / "cache" / "_index.json"

# Signals indicating SO/troubleshooting relevance.
SO_SIGNALS = {
    "stackoverflow",
    "stack-overflow",
    "error",
    "exception",
    "traceback",
    "stacktrace",
    "bug",
    "fix",
    "troubleshoot",
    "debugging",
    "debug",
    "fail",
    "failure",
    "timeout",
    "crash",
    "regression",
    "issue",
    "workaround",
    "hotfix",
    "race-condition",
    "race",
    "deadlock",
    "leak",
    "incident",
    "post-mortem",
    "rollback",
    "hang",
    "stuck",
    "broken",
    "segfault",
    "panic",
    "errno",
    "errors",
    "exceptions",
}

MIN_SCORE = 60
TOP_K = 3
MAX_BODY_CHARS = 180
FRESHNESS_DAYS = 540  # SO answers stay relevant ~18 months


def _tokenize(text: str) -> list[str]:
    """Extract significant tokens (≥3 chars, lowercase)."""
    tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_\-]+", text.lower())
    return [t for t in tokens if len(t) >= 3]


def _normalize_topics(raw: object, source_label: str) -> list[dict]:
    """Coerce either list[dict] or dict[id, dict] schema into list[dict].

    Adds `_source` label so we can show provenance в title.
    """
    out: list[dict] = []
    if isinstance(raw, list):
        for t in raw:
            if isinstance(t, dict):
                t = dict(t)
                t.setdefault("_source", source_label)
                out.append(t)
    elif isinstance(raw, dict):
        for k, v in raw.items():
            if isinstance(v, dict):
                v = dict(v)
                v.setdefault("_id", k)
                v.setdefault("_source", source_label)
                out.append(v)
    return out


def _load_topics() -> list[dict]:
    """Load + merge topic lists from both research caches."""
    combined: list[dict] = []
    for path, label in [(TECH_INDEX, "tech"), (ARCH_INDEX, "arch")]:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        raw_topics = data.get("topics")
        if raw_topics is None:
            continue
        combined.extend(_normalize_topics(raw_topics, label))
    return combined


def _has_so_signal(topic: dict) -> bool:
    """True if topic mentions SO / error-handling keywords."""
    if not isinstance(topic, dict):
        return False
    haystack_tokens = set()
    for kw in topic.get("keywords", []) or []:
        for sub in str(kw).lower().replace("_", "-").split("-"):
            if sub:
                haystack_tokens.add(sub)
        haystack_tokens.add(str(kw).lower())
    title_tokens = re.findall(r"[a-zа-я0-9\-]+", str(topic.get("title", "")).lower())
    haystack_tokens.update(title_tokens)
    return bool(haystack_tokens & SO_SIGNALS)


def _is_fresh(topic: dict) -> bool:
    """True if topic verified within FRESHNESS_DAYS."""
    verified = topic.get("last_verified") or topic.get("created") or ""
    if not verified:
        return False
    try:
        verified_date = dt.date.fromisoformat(str(verified)[:10])
    except (ValueError, TypeError):
        return False
    return (dt.date.today() - verified_date).days <= FRESHNESS_DAYS


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
    """Filter SO-relevant + fresh topics, score, return top-K items."""
    tokens = _tokenize(prompt)
    if not tokens:
        return []

    scored: list[tuple[float, dict]] = []
    for topic in topics:
        if not _has_so_signal(topic):
            continue
        if not _is_fresh(topic):
            continue
        score = _score_topic(tokens, topic)
        if score >= MIN_SCORE:
            scored.append((score, topic))

    scored.sort(key=lambda x: x[0], reverse=True)

    items = []
    for score, topic in scored[:TOP_K]:
        title = topic.get("title", topic.get("file", topic.get("_id", "?")))
        cache_file = topic.get("file", "")
        source = topic.get("_source", "")
        body_parts = []
        if source:
            body_parts.append(f"[{source}-research]")
        if cache_file:
            body_parts.append(f"→ cache/{cache_file}")
        body = " ".join(body_parts)[:MAX_BODY_CHARS]
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
