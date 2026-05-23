#!/usr/bin/env python3
"""
Hook: memory-first-hook (P5.2 Federated Recall)
Event: UserPromptSubmit
Purpose: Auto-inject relevant memory context from 4 layers (SQLite + Qdrant + .md + wiki)
         into Claude's system message before processing user prompt.
Timeout: 2s (total budget 1.5s for searches)

4-layer federated search with RRF merge:
  - Layer 1: SQLite important_messages (weight 0.30, 200ms)
  - Layer 2: Qdrant SEMANTIC search (weight 0.35, 1500ms, 3 collections)
    - skill_library, experience_embeddings, conversation_memory
    - Embedding: TEI Qwen3-Embedding-8B (4096d) — Phase 9.1 alignment with retrieval
      stack. Was Ollama nomic 768d before 2026-04-30 (dim mismatch with 1024d
      collections — never worked correctly).
    - Fallback: token overlap on learned_patterns if TEI unavailable
    - Disable: MEMORY_HOOK_NO_SEMANTIC=1
  - Layer 3: .md memory files (weight 0.15, 500ms)
  - Layer 4: Wiki drafts search (weight 0.20, 200ms, docs/wiki/drafts/)

Exit codes:
  0 = always allow (advisory, non-blocking)

Pattern: Advisory (search + inject). Part of P5.2 Session Memory Bridge.
ClawMem-inspired: hook does 90% retrieval internally, agent calls MCP for remaining 10%.
"""

import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = Path(
    os.environ.get(
        "CLAUDE_MEMORY_DIR",
        Path.home() / ".claude" / "projects" / "D--1--Framework" / "memory",
    )
)
COOLDOWN_FILE = PROJECT_ROOT / ".claude" / "cache" / "memory-first-cooldown.json"
SQLITE_DB = PROJECT_ROOT / "data" / "memory_ai.db"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MIN_PROMPT_LEN = 20
COOLDOWN_SECONDS = 30
SCORE_THRESHOLD = 0.3
MAX_RESULTS = 5

LAYER_WEIGHTS = {"sqlite": 0.30, "qdrant": 0.35, "md": 0.15, "wiki": 0.20}
SOURCE_LABELS = {"sqlite": "SQLite", "qdrant": "Qdrant", "md": ".md", "wiki": "Wiki"}

# Qdrant semantic search collections (4096d Qwen3 Phase 9.1)
SEMANTIC_COLLECTIONS = [
    ("skill_library", "skill"),
    ("experience_embeddings", "experience"),
    ("conversation_memory", "conversation"),
]

# Timeout budgets (seconds). TEI cold ~600ms, warm ~80ms (vs Ollama ~2s cold).
SQLITE_TIMEOUT = 0.200
QDRANT_TIMEOUT = 2.000  # TEI embed (warm) + Qdrant queries
MD_TIMEOUT = 0.500
WIKI_TIMEOUT = 0.200
TOTAL_BUDGET = 3.0  # Hook timeout 5s, budget 3s (TEI faster than Ollama)

# Russian suffix stemming (29 suffixes, ordered by length desc)
_RU_SUFFIXES_3 = [
    "ами",
    "ями",
    "ого",
    "его",
    "ому",
    "ему",
    "ыми",
    "ими",
    "ать",
    "ять",
    "ить",
    "ует",
    "ных",
    "ной",
    "ную",
    "ном",
]
_RU_SUFFIXES_2 = [
    "ов",
    "ев",
    "ам",
    "ям",
    "ом",
    "ем",
    "ах",
    "ях",
    "ий",
    "ый",
    "ой",
    "ие",
    "ые",
]
_RU_SUFFIXES_1 = ["ы", "и", "а", "я", "е", "у", "ю", "о"]


def stem_token(token: str) -> str:
    """Simple Russian suffix stemmer. English tokens pass through."""
    if not token or len(token) < 4:
        return token
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


def should_skip(prompt: str) -> bool:
    """Check if prompt should skip memory search."""
    if not prompt or len(prompt.strip()) < MIN_PROMPT_LEN:
        return True
    stripped = prompt.strip()
    if stripped.startswith("/"):
        return True
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


# ---------------------------------------------------------------------------
# Layer 1 — SQLite search
# ---------------------------------------------------------------------------
def search_sqlite(query_tokens: set, limit: int = 10) -> list:
    """Search SQLite important_messages: top-200 by importance, rank by token overlap."""
    if not query_tokens or not SQLITE_DB.exists():
        return []
    start = time.monotonic()
    results = []
    try:
        conn = sqlite3.connect(str(SQLITE_DB), timeout=0.5)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT id, content, importance, category, tags "
            "FROM important_messages "
            "ORDER BY importance DESC LIMIT 200"
        )
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            if time.monotonic() - start > SQLITE_TIMEOUT:
                break
            content = row["content"] or ""
            tags_str = (row["tags"] or "").lower()
            importance = row["importance"] or 0.0
            category = row["category"] or "general"
            row_id = row["id"] or ""

            content_tokens = set(tokenize(content))
            overlap = query_tokens & content_tokens
            if not overlap:
                continue
            score = len(overlap) / max(len(query_tokens), 1)

            # Tag boost
            for qt in query_tokens:
                if qt in tags_str:
                    score += 0.2
                    break

            if score >= SCORE_THRESHOLD:
                results.append(
                    {
                        "source": "sqlite",
                        "id": row_id,
                        "content": content[:200],
                        "category": category,
                        "score": round(score, 4),
                        "importance": importance,
                    }
                )

        results.sort(key=lambda x: -x["score"])
        return results[:limit]
    except Exception:
        return results[:limit]


# ---------------------------------------------------------------------------
# Layer 2 — Qdrant SEMANTIC search (default ON, disable via MEMORY_HOOK_NO_SEMANTIC=1)
# ---------------------------------------------------------------------------
def _extract_content(payload: dict, collection_type: str) -> str:
    """Extract displayable content from Qdrant payload by collection type."""
    if collection_type == "skill":
        name = payload.get("skill_name", "")
        desc = payload.get("description", "")
        return f"{name}: {desc}" if name else desc
    if collection_type == "experience":
        reason = payload.get("reason", "")
        task = payload.get("task_type", "")
        tool = payload.get("tool_preference", "")
        parts = [p for p in [task, tool, reason] if p]
        return " | ".join(parts)
    if collection_type == "conversation":
        return payload.get("content_preview", "")
    return payload.get("content") or payload.get("description") or ""


def _extract_category(payload: dict, collection_type: str) -> str:
    """Extract category from Qdrant payload by collection type."""
    if collection_type == "skill":
        return "skill"
    if collection_type == "experience":
        return payload.get("category", "experience")
    if collection_type == "conversation":
        return payload.get("role", "conversation")
    return "pattern"


def search_qdrant(query_tokens: set, limit: int = 10, prompt: str = "") -> list:
    """Semantic search across 3 Qdrant collections via TEI Qwen3 embeddings.

    Falls back to token overlap on learned_patterns if TEI is unavailable.
    """
    if os.environ.get("MEMORY_HOOK_NO_SEMANTIC") == "1":
        return []
    if not query_tokens:
        return []

    start = time.monotonic()
    query_text = prompt or " ".join(query_tokens)

    # Try semantic search first
    try:
        from shared.semantic_search import embed_query_tei, search_qdrant_semantic

        embedding = embed_query_tei(query_text, timeout=1.5)
        if embedding:
            results = []
            for collection, ctype in SEMANTIC_COLLECTIONS:
                if time.monotonic() - start > QDRANT_TIMEOUT:
                    break
                remaining = QDRANT_TIMEOUT - (time.monotonic() - start)
                hits = search_qdrant_semantic(
                    collection,
                    embedding,
                    limit=5,
                    timeout=max(0.2, remaining),
                )
                for hit in hits:
                    payload = hit.get("payload", {})
                    content = _extract_content(payload, ctype)
                    if not content:
                        continue
                    results.append(
                        {
                            "source": "qdrant",
                            "id": hit.get("id", ""),
                            "content": content[:200],
                            "category": _extract_category(payload, ctype),
                            "score": round(hit.get("score", 0.0), 4),
                        }
                    )
            if results:
                results.sort(key=lambda x: -x["score"])
                return results[:limit]
    except Exception:
        pass

    # Fallback: token overlap on learned_patterns (no embedding needed)
    results = []
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host="127.0.0.1", port=6333, timeout=1)
        scroll_result = client.scroll(
            collection_name="learned_patterns",
            limit=100,
            with_payload=True,
            with_vectors=False,
        )
        points, _ = scroll_result

        for point in points:
            if time.monotonic() - start > QDRANT_TIMEOUT:
                break
            payload = point.payload or {}
            content = payload.get("content") or payload.get("description") or ""
            if not content:
                continue
            content_tokens = set(tokenize(content))
            overlap = query_tokens & content_tokens
            if not overlap:
                continue
            score = len(overlap) / max(len(query_tokens), 1)
            if score >= SCORE_THRESHOLD:
                results.append(
                    {
                        "source": "qdrant",
                        "id": str(point.id),
                        "content": content[:200],
                        "category": payload.get("category", "pattern"),
                        "score": round(score, 4),
                    }
                )

        results.sort(key=lambda x: -x["score"])
        return results[:limit]
    except Exception:
        return results[:limit]


# ---------------------------------------------------------------------------
# Layer 3 — .md files search
# ---------------------------------------------------------------------------
def load_all_memories() -> list:
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
            parsed["name_tokens"] = set(tokenize(parsed["name"]))
            parsed["desc_tokens"] = set(tokenize(parsed["description"]))
            parsed["body_tokens"] = set(tokenize(parsed["body"][:2000]))
            memories.append(parsed)
        except Exception:
            continue
    return memories


def score_memory(query_tokens: set, memory: dict) -> float:
    """Weighted token overlap: name*3, description*2, body*1."""
    if not query_tokens:
        return 0.0
    name_hits = query_tokens & memory["name_tokens"]
    desc_hits = query_tokens & memory["desc_tokens"]
    body_hits = query_tokens & memory["body_tokens"]
    all_hits = name_hits | desc_hits | body_hits
    if not all_hits:
        return 0.0
    weighted = len(name_hits) * 3 + len(desc_hits) * 2 + len(body_hits) * 1
    max_possible = len(query_tokens) * 3
    query_coverage = len(all_hits) / len(query_tokens)
    memory_density = min(weighted / max_possible, 1.0) if max_possible > 0 else 0.0
    return 0.7 * query_coverage + 0.3 * memory_density


def search_md(query_tokens: set, limit: int = 10) -> list:
    """Search .md memory files with weighted overlap scoring."""
    if not query_tokens:
        return []
    start = time.monotonic()
    results = []
    try:
        memories = load_all_memories()
        for mem in memories:
            if time.monotonic() - start > MD_TIMEOUT:
                break
            sc = score_memory(query_tokens, mem)
            if sc >= SCORE_THRESHOLD:
                body = mem.get("body", "")
                title = mem.get("name") or mem.get("file", "?")
                snippet = (title + ": " + body[:150]) if title else body[:200]
                results.append(
                    {
                        "source": "md",
                        "id": mem["file"],
                        "content": snippet[:200],
                        "category": mem.get("type", "note"),
                        "score": round(sc, 4),
                    }
                )
        results.sort(key=lambda x: -x["score"])
        return results[:limit]
    except Exception:
        return results[:limit]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion merge
# ---------------------------------------------------------------------------
def rrf_merge(layers: dict, weights: dict, k: int = 60) -> list:
    """Merge results via weighted RRF, dedup by content hash."""
    scores = {}
    for source, items in layers.items():
        w = weights.get(source, 0.0)
        for rank, item in enumerate(items, start=1):
            chash = hashlib.sha1(item["content"].encode("utf-8", errors="replace")).hexdigest()[:16]
            rrf = w * (1.0 / (k + rank))
            if chash in scores:
                scores[chash]["fused_score"] += rrf
            else:
                scores[chash] = {"item": item, "fused_score": rrf}
    merged = [{**e["item"], "fused_score": e["fused_score"]} for e in scores.values()]
    merged.sort(key=lambda x: -x["fused_score"])
    return merged


# ---------------------------------------------------------------------------
# Output formatter
# ---------------------------------------------------------------------------
def format_federated_context(merged: list) -> str:
    """Format merged results into systemMessage text."""
    sources = sorted({item.get("source", "md") for item in merged})
    lines = [f"[MEMORY CONTEXT] Top {len(merged)} results across {len(sources)} source(s):"]
    for i, item in enumerate(merged, start=1):
        source = item.get("source", "md")
        label = SOURCE_LABELS.get(source, source)
        category = item.get("category", "general")
        content = item.get("content", "")
        confidence = item.get("fused_score", 0.0)
        display = content[:100].replace("\n", " ").strip()
        if len(content) > 100:
            display += "..."
        lines.append(f'{i}. [{label}|{confidence:.3f}] {category}: "{display}"')
    lines.append(
        "Use this context to inform your response. "
        "If memory conflicts with current code, trust current code."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Langfuse observation (roadmap §5c.4) — never blocks hook
# ---------------------------------------------------------------------------
def _emit_langfuse_span(
    status: str,
    *,
    prompt_len: int = 0,
    layer_counts: dict | None = None,
    merged_count: int = 0,
    duration_ms: float = 0.0,
) -> None:
    """Эмитит Langfuse observation. Никогда не raise — graceful skip on failure."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from src.pdf_framework.observability.langfuse_setup import emit_observation

        emit_observation(
            name=HOOK_NAME,
            input={"prompt_len": prompt_len},
            output={
                "status": status,
                "layers": layer_counts or {},
                "merged": merged_count,
                "duration_ms": round(duration_ms, 1),
            },
            metadata={"hook": HOOK_NAME, "event": "UserPromptSubmit"},
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Hook class
# ---------------------------------------------------------------------------
class MemoryFirstHook(BaseHook):
    """P5.2 Federated Recall hook — 3-layer memory search on UserPromptSubmit."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        prompt_len = len(prompt or "")
        if should_skip(prompt):
            _emit_langfuse_span("skipped-trivial", prompt_len=prompt_len)
            return None
        if check_cooldown():
            _emit_langfuse_span("skipped-cooldown", prompt_len=prompt_len)
            return None

        query_tokens = set(tokenize(prompt))
        if not query_tokens:
            _emit_langfuse_span("skipped-no-tokens", prompt_len=prompt_len)
            return None

        t0 = time.monotonic()
        deadline = t0 + TOTAL_BUDGET

        sqlite_results = (
            search_sqlite(query_tokens, limit=10) if time.monotonic() < deadline else []
        )
        qdrant_results = (
            search_qdrant(query_tokens, limit=10, prompt=prompt)
            if time.monotonic() < deadline
            else []
        )
        md_results = search_md(query_tokens, limit=10) if time.monotonic() < deadline else []
        wiki_results = search_wiki(query_tokens, limit=10) if time.monotonic() < deadline else []

        layer_counts = {
            "sqlite": len(sqlite_results),
            "qdrant": len(qdrant_results),
            "md": len(md_results),
            "wiki": len(wiki_results),
        }

        merged = rrf_merge(
            {
                "sqlite": sqlite_results,
                "qdrant": qdrant_results,
                "md": md_results,
                "wiki": wiki_results,
            },
            LAYER_WEIGHTS,
        )[:MAX_RESULTS]

        duration_ms = (time.monotonic() - t0) * 1000

        if not merged:
            _emit_langfuse_span(
                "no-results",
                prompt_len=prompt_len,
                layer_counts=layer_counts,
                duration_ms=duration_ms,
            )
            return None

        msg = format_federated_context(merged)
        update_cooldown()
        _emit_langfuse_span(
            "injected",
            prompt_len=prompt_len,
            layer_counts=layer_counts,
            merged_count=len(merged),
            duration_ms=duration_ms,
        )
        # Output via stdout (100% injection rate vs 55% for systemMessage).
        # For UserPromptSubmit hooks, stdout is added as context Claude sees,
        # while `systemMessage` is a user-facing warning that Claude never reads.
        # See skill-router.py:502 for the same pattern.
        print(msg)
        return None


if __name__ == "__main__":
    MemoryFirstHook().run()
