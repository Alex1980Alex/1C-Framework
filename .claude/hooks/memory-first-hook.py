#!/usr/bin/env python3
"""
Hook: memory-first-hook
Event: UserPromptSubmit
Purpose: Auto-inject relevant memory context into Claude's system message
         before it starts processing the user's prompt.
Timeout: 2s

Searches local .md memory files using weighted token overlap with Russian stemming.
Returns top-3 relevant memories as systemMessage.

Exit codes:
  0 = always allow (advisory, non-blocking)

Pattern: Advisory (search + inject). Part of P0.5 Memory-First Hook.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = Path(os.environ.get(
    "CLAUDE_MEMORY_DIR",
    Path.home() / ".claude" / "projects" / "D--1--Framework" / "memory",
))
COOLDOWN_FILE = PROJECT_ROOT / ".claude" / "cache" / "memory-first-cooldown.json"

MIN_PROMPT_LEN = 20
COOLDOWN_SECONDS = 30
SCORE_THRESHOLD = 0.3
MAX_RESULTS = 3

# Russian suffix stemming (29 suffixes, ordered by length desc)
_RU_SUFFIXES_3 = [
    "ами", "ями", "ого", "его", "ому", "ему",
    "ыми", "ими", "ать", "ять", "ить", "ует",
    "ных", "ной", "ную", "ном",
]
_RU_SUFFIXES_2 = [
    "ов", "ев", "ам", "ям", "ом", "ем",
    "ах", "ях", "ий", "ый", "ой", "ие", "ые",
]
_RU_SUFFIXES_1 = ["ы", "и", "а", "я", "е", "у", "ю", "о"]


def stem_token(token: str) -> str:
    """Simple Russian suffix stemmer. English tokens pass through."""
    if not token or len(token) < 4:
        return token
    # Only stem Cyrillic tokens
    if not any("\u0400" <= c <= "\u04ff" for c in token):
        return token
    for suf in _RU_SUFFIXES_3:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    for suf in _RU_SUFFIXES_2:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    for suf in _RU_SUFFIXES_1:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def tokenize(text: str) -> list[str]:
    """Tokenize, lowercase, stem. Returns list of stemmed tokens."""
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_\-]+", text.lower())
    return [stem_token(t) for t in tokens if len(t) >= 2]


def parse_frontmatter(content: str) -> dict:
    """Parse YAML-like frontmatter from memory file."""
    result = {"name": "", "description": "", "type": "", "body": ""}
    if not content.startswith("---"):
        result["body"] = content
        return result
    parts = content.split("---", 2)
    if len(parts) < 3:
        result["body"] = content
        return result
    fm = parts[1]
    result["body"] = parts[2].strip()
    for line in fm.strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ("name", "description", "type"):
                result[key] = val
    return result


def load_all_memories() -> list[dict]:
    """Load all .md memory files from MEMORY_DIR."""
    memories = []
    if not MEMORY_DIR.exists():
        return memories
    for md_file in MEMORY_DIR.glob("*.md"):
        if md_file.name == "MEMORY.md":
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            parsed = parse_frontmatter(content)
            parsed["file"] = md_file.name
            # Pre-tokenize for search
            parsed["name_tokens"] = set(tokenize(parsed["name"]))
            parsed["desc_tokens"] = set(tokenize(parsed["description"]))
            parsed["body_tokens"] = set(tokenize(parsed["body"][:2000]))
            memories.append(parsed)
        except Exception:
            continue
    return memories


def score_memory(query_tokens: set[str], memory: dict) -> float:
    """Score memory against query using weighted token overlap.

    Weights: name×3, description×2, body×1.
    Final: 0.7 × query_coverage + 0.3 × memory_density.
    """
    if not query_tokens:
        return 0.0

    name_hits = query_tokens & memory["name_tokens"]
    desc_hits = query_tokens & memory["desc_tokens"]
    body_hits = query_tokens & memory["body_tokens"]
    all_hits = name_hits | desc_hits | body_hits

    if not all_hits:
        return 0.0

    # Weighted score
    weighted = len(name_hits) * 3 + len(desc_hits) * 2 + len(body_hits) * 1
    max_possible = len(query_tokens) * 3  # best case: all in name

    # Query coverage: what fraction of query tokens matched somewhere
    query_coverage = len(all_hits) / len(query_tokens)

    # Memory density: weighted hits relative to max possible
    memory_density = min(weighted / max_possible, 1.0) if max_possible > 0 else 0.0

    return 0.7 * query_coverage + 0.3 * memory_density


def search_memories(prompt: str, memories: list[dict]) -> list[tuple[dict, float]]:
    """Search memories by prompt, return sorted (memory, score) pairs."""
    query_tokens = set(tokenize(prompt))
    if not query_tokens:
        return []

    scored = []
    for mem in memories:
        score = score_memory(query_tokens, mem)
        if score >= SCORE_THRESHOLD:
            scored.append((mem, score))

    scored.sort(key=lambda x: -x[1])
    return scored[:MAX_RESULTS]


def format_memory_context(results: list[tuple[dict, float]]) -> str:
    """Format search results into systemMessage text."""
    if not results:
        return ""
    lines = [f"[MEMORY CONTEXT] Found {len(results)} relevant memories for your query:"]
    for i, (mem, score) in enumerate(results, 1):
        mtype = mem.get("type", "unknown")
        title = mem.get("name", mem.get("file", "?"))
        # Snippet: first 150 chars of body
        body = mem.get("body", "")
        snippet = body[:150].replace("\n", " ").strip()
        if len(body) > 150:
            snippet += "..."
        lines.append(f"{i}. [{mtype}] {title} — {snippet} (confidence: {score:.2f})")
    lines.append(
        "Use this context to inform your response. "
        "If memory conflicts with current code, trust current code."
    )
    return "\n".join(lines)


def should_skip(prompt: str) -> bool:
    """Check if prompt should skip memory search."""
    if not prompt or len(prompt.strip()) < MIN_PROMPT_LEN:
        return True
    stripped = prompt.strip()
    # Skip slash commands
    if stripped.startswith("/"):
        return True
    # Skip single-word prompts
    if len(stripped.split()) <= 1:
        return True
    return False


def check_cooldown() -> bool:
    """Return True if within cooldown period."""
    try:
        if not COOLDOWN_FILE.exists():
            return False
        data = json.loads(COOLDOWN_FILE.read_text(encoding="utf-8"))
        last = data.get("last_run", 0)
        return (time.time() - last) < COOLDOWN_SECONDS
    except Exception:
        return False


def update_cooldown():
    """Update cooldown timestamp."""
    try:
        COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOLDOWN_FILE.write_text(
            json.dumps({"last_run": time.time()}),
            encoding="utf-8",
        )
    except Exception:
        pass


class MemoryFirstHook(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if should_skip(prompt):
            return None

        if check_cooldown():
            return None

        memories = load_all_memories()
        if not memories:
            return None

        results = search_memories(prompt, memories)
        if not results:
            return None

        msg = format_memory_context(results)
        if not msg:
            return None

        update_cooldown()
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    MemoryFirstHook().run()
