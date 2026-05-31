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
HOOK_NAME = "memory-first-hook"
MIN_PROMPT_LEN = 20
COOLDOWN_SECONDS = 30
SCORE_THRESHOLD = 0.3
MAX_RESULTS = 5

LAYER_WEIGHTS = {"sqlite": 0.30, "qdrant": 0.35, "md": 0.15, "wiki": 0.20}
SOURCE_LABELS = {"sqlite": "SQLite", "qdrant": "Qdrant", "md": ".md", "wiki": "Wiki"}

# §24 P1 ADR-D6: per-arm RRF weights for hybrid surfacing inside search_qdrant.
# lexical > dense for BSL (CamelCase/Cyrillic dense recall-collapse, §24.2.2).
SURFACE_RRF_WEIGHTS: dict = {
    "skill": 0.5,
    "experience": 0.5,
    "conversation": 0.5,
    "pattern_dense": 0.3,
    "pattern_lexical": 0.7,
}

# Qdrant semantic search collections (4096d Qwen3 Phase 9.1)
# learned_patterns included for semantic surfacing (§24 P0 ADR-D6)
SEMANTIC_COLLECTIONS = [
    ("skill_library", "skill"),
    ("experience_embeddings", "experience"),
    ("conversation_memory", "conversation"),
    ("learned_patterns", "pattern"),
]

# §24 P0 — confidence gating thresholds
MIN_SURFACE_CONF = 0.15   # hard noise floor: below this → never surface
CONF_FLOOR = 0.30          # soft floor for floored-multiply score adjustment

# Timeout budgets (seconds). TEI cold ~600ms, warm ~80ms (vs Ollama ~2s cold).
SQLITE_TIMEOUT = 0.200
QDRANT_TIMEOUT = 2.000  # TEI embed (warm) + Qdrant queries
MD_TIMEOUT = 0.500
WIKI_TIMEOUT = 0.200
TOTAL_BUDGET = 3.0  # Hook timeout 5s, budget 3s (TEI faster than Ollama)

# §24 P2 ADR-D6 — optional post-fusion LLM rerank (Ollama qwen2.5-coder).
# OFF by default: measured ~2.5s warm / ~6.5s cold (model load), which the hot-path
# UserPromptSubmit budget (TOTAL_BUDGET=3.0s) cannot absorb — a cold call exceeds the
# 5s hook hard-kill in settings.json and would surface NOTHING. The httpx read-timeout
# is best-effort only (Ollama holds the connection during model load), so enabling this
# REQUIRES raising the settings.json hook timeout to >=10s. Use only when precision >
# latency. Any failure/timeout/no-budget degrades silently to the RRF-fused order
# (skippable — §24.2.6 "rerank after fusion, top-N"). Keep Ollama warm to stay ~2.5s.
RERANK_ENABLED = os.environ.get("MEMORY_RERANK") == "1"
RERANK_MODEL = os.environ.get("MEMORY_RERANK_MODEL", "qwen2.5-coder:7b")
RERANK_ENDPOINT = os.environ.get(
    "MEMORY_RERANK_ENDPOINT", "http://localhost:11434/api/generate"
)
RERANK_MIN_CANDIDATES = 3   # below this nothing to reorder meaningfully
RERANK_HARD_TIMEOUT = 5.0   # mirror settings.json hook timeout (hard-kill ceiling)
RERANK_SAFETY = 0.5         # margin before hard-kill so the hook still emits

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


def _pattern_effective_confidence(payload: dict) -> float:
    """§24 P0: lazy-import §22 pure function; graceful degrade on any failure."""
    try:
        src_path = str(PROJECT_ROOT / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        from memory.vector_memory.confidence import payload_effective_confidence
        return payload_effective_confidence(payload)
    except Exception:
        return float(payload.get("confidence", 0.5))


def _pattern_score_gate(payload: dict, base_score: float) -> "float | None":
    """§24 ADR-D6 gating: archived hard-exclude + hard floor + floored-multiply.

    Returns None to suppress the result, or an adjusted score to surface it.
    """
    if payload.get("expired_at") and os.environ.get("MEMORY_INCLUDE_ARCHIVED") != "1":
        return None                                        # archived → hard-exclude (§24.2.4)
    eff = _pattern_effective_confidence(payload)
    if eff < MIN_SURFACE_CONF:
        return None                                        # noise floor (§24.2.3 hard)
    return base_score * max(CONF_FLOOR, eff)              # floored-multiply (§24.2.3 soft)


def _search_learned_patterns(query_tokens: set, start: float, limit: int) -> list:
    """Token-overlap surfacing of learned_patterns — ALWAYS-ON lexical arm (§24 P1).

    Runs unconditionally as the 'pattern_lexical' arm in search_qdrant hybrid RRF.
    Catches CamelCase/Cyrillic/exact-term patterns where dense embeddings underperform
    (BSL recall-collapse). When TEI is down, this is the sole populated arm (graceful
    degradation to lexical-only). Results tagged _collection='learned_patterns'.
    Fail-soft → []. Applies §24 confidence gating (_pattern_score_gate) per candidate."""
    out: list = []
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
            if score < SCORE_THRESHOLD:
                continue
            adj = _pattern_score_gate(payload, score)
            if adj is None:
                continue
            out.append(
                {
                    "source": "qdrant",
                    "id": str(point.id),
                    "content": content[:200],
                    "category": payload.get("category", "pattern"),
                    "score": round(adj, 4),
                    "_collection": "learned_patterns",
                }
            )

        out.sort(key=lambda x: -x["score"])
        return out[:limit]
    except Exception:
        return out[:limit]


def search_qdrant(query_tokens: set, limit: int = 10, prompt: str = "") -> list:
    """Hybrid RRF search across SEMANTIC_COLLECTIONS + always-on lexical arm (§24 P1).

    Arms dict fed into rrf_merge(k=60):
      - "skill", "experience", "conversation": TEI semantic hits per collection.
      - "pattern_dense": learned_patterns semantic hits (§24 ADR-D6 gated, _collection tagged).
      - "pattern_lexical": token-overlap on learned_patterns — ALWAYS-ON (not fallback).
        Catches CamelCase/Cyrillic/exact-term where dense underperforms (BSL recall-collapse).

    Weights (SURFACE_RRF_WEIGHTS): lexical 0.7 > dense 0.3 for BSL arms.
    RRF dedup by content-hash: pattern in both arms fuses → boosted rank (correct behaviour).
    Graceful degradation: TEI down → dense arms empty, pattern_lexical still populated.

    Disable all searches: MEMORY_HOOK_NO_SEMANTIC=1.
    """
    if os.environ.get("MEMORY_HOOK_NO_SEMANTIC") == "1":
        return []
    if not query_tokens:
        return []

    start = time.monotonic()
    query_text = prompt or " ".join(query_tokens)

    # Build per-source arms (each list already score-desc from its source)
    arms: dict = {
        "skill": [],
        "experience": [],
        "conversation": [],
        "pattern_dense": [],
        "pattern_lexical": [],
    }

    try:
        from shared.semantic_search import embed_query_tei, search_qdrant_semantic

        embedding = embed_query_tei(query_text, timeout=1.5)
        if embedding:
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
                    base_score = hit.get("score", 0.0)
                    if ctype == "pattern":
                        # §24 ADR-D6: gate learned_patterns hits by confidence
                        adj = _pattern_score_gate(payload, base_score)
                        if adj is None:
                            continue
                        entry = {
                            "source": "qdrant",
                            "id": hit.get("id", ""),
                            "content": content[:200],
                            "category": _extract_category(payload, ctype),
                            "score": round(adj, 4),
                            "_collection": "learned_patterns",
                        }
                        arms["pattern_dense"].append(entry)
                    else:
                        entry = {
                            "source": "qdrant",
                            "id": hit.get("id", ""),
                            "content": content[:200],
                            "category": _extract_category(payload, ctype),
                            "score": round(base_score, 4),
                        }
                        # Route by collection type to its arm
                        arm_key = {
                            "skill": "skill",
                            "experience": "experience",
                            "conversation": "conversation",
                        }.get(ctype, "skill")
                        arms[arm_key].append(entry)
    except Exception:
        pass

    # §24 P1: lexical arm — ALWAYS-ON (not fallback), catches BSL exact-term/CamelCase
    arms["pattern_lexical"] = _search_learned_patterns(query_tokens, start, limit)

    # Client-side RRF merge: content-hash dedup, lexical weighted > dense for BSL
    fused = rrf_merge(arms, SURFACE_RRF_WEIGHTS, k=60)
    return fused[:limit]


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


def search_wiki(query_tokens: set, limit: int = 10) -> list:
    """Layer 4 wiki search — stub returning [] (full impl deferred).

    Called from RRF merge in execute(); empty result means layer 'wiki' simply
    contributes nothing to the merge, other layers (sqlite/qdrant/md) still work.
    """
    return []


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


def _rerank_results(query_text: str, results: list, t0: float) -> list:
    """§24 P2 ADR-D6: optional LLM rerank of the post-fusion result list.

    Reorders ``results`` (already RRF-fused, top-N) by relevance to ``query_text``
    via local Ollama qwen2.5-coder. Mirrors the proven BSL ``_llm_rerank`` pattern
    (numbered prompt → comma-separated index list → reorder, graceful fallback).

    Contract (honest hot-path design):
      - OFF unless ``MEMORY_RERANK=1`` — a 7b rerank (~1.5s) exceeds TOTAL_BUDGET.
      - Timeout-bounded by the remaining slack before the 5s hook hard-kill, so an
        enabled-but-slow Ollama never starves the hook of emitting anything.
      - Skippable: any exception / no-ranking / no-budget → original fused order.
    """
    if not RERANK_ENABLED or len(results) < RERANK_MIN_CANDIDATES:
        return results
    # Budget = time left before hard-kill, minus a safety margin to still emit.
    remaining = RERANK_HARD_TIMEOUT - (time.monotonic() - t0) - RERANK_SAFETY
    if remaining < 0.8:  # not enough to attempt a useful rerank
        return results

    lines = []
    for i, c in enumerate(results, 1):
        text = (c.get("content") or "").replace("\n", " ")[:200]
        cat = c.get("category") or c.get("source") or ""
        lines.append(f"{i}. [{cat}] {text}")
    prompt = (
        "You are a developer-memory reranker. Given a query and candidate memory "
        "snippets (past patterns, lessons, skills, notes), rank them by relevance "
        "to the query.\n\n"
        "Output ONLY a comma-separated list of the candidate numbers, most relevant "
        'first. Example: "3,1,4,2".\n\n'
        f"Query: {query_text}\n\nCandidates:\n" + "\n".join(lines) + "\n\nRanking:"
    )
    try:
        import httpx

        resp = httpx.post(
            RERANK_ENDPOINT,
            json={
                "model": RERANK_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 64},
            },
            timeout=min(remaining, 4.0),
        )
        text = resp.json().get("response", "")
    except Exception:
        return results

    match = re.search(r"\d+(?:\s*,\s*\d+)+", text)
    if not match:
        return results
    try:
        order = [int(x.strip()) - 1 for x in match.group(0).split(",")]
    except ValueError:
        return results

    seen: set = set()
    reranked: list = []
    for idx in order:
        if 0 <= idx < len(results) and idx not in seen:
            reranked.append(results[idx])
            seen.add(idx)
    # Append any candidate the LLM omitted, preserving fused order (no silent drop).
    for i, c in enumerate(results):
        if i not in seen:
            reranked.append(c)
    return reranked


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
        try:
            from shared.pattern_reinforce import record_surfaced
            _sid = inp.session_id or ""
            record_surfaced(
                _sid,
                [(r["id"], r["score"]) for r in qdrant_results
                 if r.get("_collection") == "learned_patterns" and r.get("id")],
            )
        except Exception:
            pass
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

        # §24 P2: optional LLM rerank of the final top-N (opt-in, skippable, bounded).
        if merged:
            merged = _rerank_results(prompt, merged, t0)

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
