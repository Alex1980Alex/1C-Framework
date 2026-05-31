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
from typing import Any

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

# §24 execution cache — memoize the surfacing pipeline by hash(query_tokens).
# The hook spawns a fresh process per UserPromptSubmit, so an in-process cache is
# useless → persist to disk. A repeated query (same normalized tokens) within TTL
# returns the cached fused result, skipping TEI-embed + Qdrant + RRF + rerank (~2s).
# Reinforcement side-effect (record_surfaced) is replayed on hit so §22 P1 still works.
SURFACE_CACHE_FILE = (
    PROJECT_ROOT / ".claude" / "cache" / "memory-first-surfacing-cache.json"
)
SURFACE_CACHE_ENABLED = os.environ.get("MEMORY_SURFACE_CACHE_DISABLE") != "1"
# TTL tradeoff: a pattern archived / confidence-dropped mid-TTL stays surfaced (and
# re-reinforced) for up to this window. Bounded to 5 min; lower it or key on a
# confidence-store epoch if staleness ever matters.
SURFACE_CACHE_TTL = float(os.environ.get("MEMORY_SURFACE_CACHE_TTL", "300"))  # 5 min
SURFACE_CACHE_CAP = 200  # max distinct query hashes retained (FIFO by timestamp)

# §24.4 acceptance "логирование всех процессов" — structured per-invocation trace.
# The whole pipeline is fail-soft (except: pass everywhere) and stdout is reserved
# for the context injection, so failures are otherwise invisible. We accumulate a
# single JSONL record per invocation covering every stage (cache/epoch/TEI/arms/
# gating/RRF/rerank/reinforce/outcome/timing) → queryable post-mortem of why a
# pattern did or didn't surface. Default ON (cheap append); opt-out below.
SURFACE_LOG_FILE = PROJECT_ROOT / ".claude" / "cache" / "memory-first-surfacing.log"
SURFACE_LOG_ENABLED = os.environ.get("MEMORY_SURFACE_LOG_DISABLE") != "1"
SURFACE_LOG_CAP_BYTES = 2_000_000  # ~2MB; tail-truncated when exceeded

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
_RERANK_TIMEOUT_WARNED = False  # one-shot stderr warning guard (env/timeout desync)

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
        _trace_gate("archived")
        return None                                        # archived → hard-exclude (§24.2.4)
    eff = _pattern_effective_confidence(payload)
    if eff < MIN_SURFACE_CONF:
        _trace_gate("below_floor")
        return None                                        # noise floor (§24.2.3 hard)
    _trace_gate("passed")
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
        _trace_set("tei", "ok" if embedding else "no_embedding")
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
    except Exception as exc:
        _trace_set("tei", "down")
        _trace_set("tei_error", f"{type(exc).__name__}: {exc}"[:160])

    # §24 P1: lexical arm — ALWAYS-ON (not fallback), catches BSL exact-term/CamelCase
    arms["pattern_lexical"] = _search_learned_patterns(query_tokens, start, limit)

    # Per-arm hit counts before fusion — shows which signals actually fired.
    _trace_set("arms", {k: len(v) for k, v in arms.items()})

    # Client-side RRF merge: content-hash dedup, lexical weighted > dense for BSL
    fused = rrf_merge(arms, SURFACE_RRF_WEIGHTS, k=60)
    _trace_set("rrf_fused", len(fused))
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


def _emit_stdout(text: str) -> None:
    """Write surfaced context as UTF-8 bytes — robust on Windows cp1251 consoles.

    `print(text)` raises UnicodeEncodeError when the surfaced memory contains
    Cyrillic (almost always in this project) and stdout is a cp1251 pipe, which
    silently drops the whole injection. Mirror HookOutput.emit()'s buffer write.
    """
    try:
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        sys.stdout.buffer.flush()
    except Exception:
        try:
            print(text)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# §24 pipeline trace — one structured JSONL record per invocation
# ---------------------------------------------------------------------------
# Module-global accumulator. Safe because every UserPromptSubmit spawns a fresh
# process (no concurrency within a single _TRACE). Stages write into it via
# _trace_set / _trace_gate; execute() resets it at entry and emits once per exit.
# The whole surfacing pipeline is fail-soft (except: pass everywhere) and stdout
# is reserved for the context injection, so without this trace every failure is
# invisible. This makes "why did/didn't a pattern surface" queryable post-mortem.
_TRACE: dict[str, Any] = {}


def _trace_reset() -> None:
    """Start a fresh trace for this invocation. Seeds nested gating counters."""
    _TRACE.clear()
    _TRACE["gate"] = {"archived": 0, "below_floor": 0, "passed": 0}


def _trace_set(key: str, value: Any) -> None:
    """Record a top-level trace field. Fail-soft (never raises into the pipeline)."""
    try:
        _TRACE[key] = value
    except Exception:
        pass


def _trace_gate(reason: str) -> None:
    """Increment a confidence-gating drop/pass counter. Defensive if not reset."""
    try:
        g = _TRACE.get("gate")
        if isinstance(g, dict):
            g[reason] = g.get(reason, 0) + 1
    except Exception:
        pass


def _surface_log(outcome: str, t0: float, **extra: Any) -> None:
    """Append one JSONL pipeline-trace record. Fail-soft; never raises.

    Captures the accumulated _TRACE plus the terminal outcome + wall-clock. Size-
    rotated (tail-keep) so the log can't grow unbounded on the hot path. Default
    ON (cheap append); opt-out via MEMORY_SURFACE_LOG_DISABLE=1.
    """
    if not SURFACE_LOG_ENABLED:
        return
    try:
        from datetime import datetime

        record: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "hook": HOOK_NAME,
            "outcome": outcome,
            "duration_ms": round((time.monotonic() - t0) * 1000, 1),
        }
        record.update(_TRACE)
        record.update(extra)

        SURFACE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Naive size-based rotation: keep the tail half, drop the partial head line.
        try:
            if (
                SURFACE_LOG_FILE.exists()
                and SURFACE_LOG_FILE.stat().st_size > SURFACE_LOG_CAP_BYTES
            ):
                data = SURFACE_LOG_FILE.read_bytes()[-(SURFACE_LOG_CAP_BYTES // 2):]
                nl = data.find(b"\n")
                if nl != -1:
                    data = data[nl + 1:]
                SURFACE_LOG_FILE.write_bytes(data)
        except Exception:
            pass

        with open(SURFACE_LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _confidence_epoch() -> float:
    """§24: last confidence-store mutation timestamp (lazy import, fail-soft -> 0.0).

    Folded into the cache key so any confidence/archive change (reinforce, apply,
    decay) instantly invalidates memoized surfacing — no Qdrant roundtrip here,
    just a local file read. 0.0 degrades to the legacy TTL-only behaviour.
    """
    try:
        src_path = str(PROJECT_ROOT / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
        from memory.vector_memory.epoch import read as _read_epoch
        return _read_epoch()
    except Exception:
        return 0.0


def _surface_cache_key(query_tokens: set[str]) -> str:
    """Stable hash of the retrieval input — order/case-insensitive (tokenize lowercases).

    Keyed on (confidence-epoch, query_tokens): a confidence mutation bumps the
    epoch -> different key -> instant cache miss -> recompute (§24 stale-window fix).
    """
    payload = f"{_confidence_epoch()!r}|{' '.join(sorted(query_tokens))}"
    return hashlib.sha256(
        payload.encode("utf-8", errors="replace")
    ).hexdigest()[:32]


def _surface_cache_get(key: str) -> dict[str, Any] | None:
    """Return the stored envelope ``{ts, results, pids}`` if fresh (within-TTL), else None.

    Caller reads ``entry["results"]`` / ``entry["pids"]`` — the full envelope is returned,
    not just results. Fail-soft: any IO/parse error → None (treated as a miss).
    """
    if not SURFACE_CACHE_ENABLED:
        return None
    try:
        if not SURFACE_CACHE_FILE.exists():
            return None
        data = json.loads(SURFACE_CACHE_FILE.read_text(encoding="utf-8"))
        entry = (data.get("entries") or {}).get(key)
        if not entry:
            return None
        if (time.time() - float(entry.get("ts", 0))) >= SURFACE_CACHE_TTL:
            return None  # expired → treat as miss (lazy; overwritten on next put)
        return entry
    except Exception:
        return None


def _surface_cache_put(key: str, results: list[Any], pids: list[Any]) -> None:
    """Store the fused surfacing result + surfaced pattern ids. Atomic, FIFO-capped, fail-soft."""
    if not SURFACE_CACHE_ENABLED:
        return
    try:
        SURFACE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data: dict[str, Any] = {}
        if SURFACE_CACHE_FILE.exists():
            try:
                data = json.loads(SURFACE_CACHE_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        entries = data.get("entries") or {}
        entries[key] = {"ts": time.time(), "results": results, "pids": pids}
        # FIFO cap: drop oldest by timestamp when over capacity.
        if len(entries) > SURFACE_CACHE_CAP:
            ordered = sorted(entries, key=lambda k: entries[k].get("ts", 0))
            for old in ordered[: len(entries) - SURFACE_CACHE_CAP]:
                entries.pop(old, None)
        data["entries"] = entries
        # Per-process temp (mkstemp) so concurrent hook processes can't clobber each
        # other's in-flight write; os.replace is atomic on the same filesystem.
        import tempfile

        fd, tmp_name = tempfile.mkstemp(
            dir=str(SURFACE_CACHE_FILE.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(data, ensure_ascii=False))
            os.replace(tmp_name, SURFACE_CACHE_FILE)
        except Exception:
            try:
                os.unlink(tmp_name)
            except Exception:
                pass
            raise
    except Exception:
        pass


def _rerank_results(query_text: str, results: list[Any], t0: float) -> list[Any]:
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
        _trace_set("rerank", "off" if not RERANK_ENABLED else "too_few_candidates")
        return results
    # Operability: warn once if enabled without raising the settings.json timeout —
    # otherwise the budget-guard below silently skips almost every call (~6.5s cold
    # cannot fit a 5s hard-kill), and the operator never learns why.
    global _RERANK_TIMEOUT_WARNED
    if not _RERANK_TIMEOUT_WARNED and RERANK_HARD_TIMEOUT <= 5.0:
        _RERANK_TIMEOUT_WARNED = True
        print(
            "[memory-first] MEMORY_RERANK=1 but hook timeout <=5s — rerank will be "
            "skipped on cold/slow Ollama; raise settings.json timeout to >=10s.",
            file=sys.stderr,
        )
    # Budget = time left before hard-kill, minus a safety margin to still emit.
    remaining = RERANK_HARD_TIMEOUT - (time.monotonic() - t0) - RERANK_SAFETY
    if remaining < 0.8:  # not enough to attempt a useful rerank
        _trace_set("rerank", "skipped_no_budget")
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
    except Exception as exc:
        _trace_set("rerank", "error")
        _trace_set("rerank_error", f"{type(exc).__name__}: {exc}"[:160])
        return results

    match = re.search(r"\d+(?:\s*,\s*\d+)+", text)
    if not match:
        _trace_set("rerank", "no_ranking")
        return results
    try:
        order = [int(x.strip()) - 1 for x in match.group(0).split(",")]
    except ValueError:
        _trace_set("rerank", "parse_error")
        return results

    seen: set[int] = set()
    reranked: list[Any] = []
    for idx in order:
        if 0 <= idx < len(results) and idx not in seen:
            reranked.append(results[idx])
            seen.add(idx)
    # Append any candidate the LLM omitted, preserving fused order (no silent drop).
    for i, c in enumerate(results):
        if i not in seen:
            reranked.append(c)
    _trace_set("rerank", "applied")
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
        _trace_reset()
        _trace_set("prompt_len", prompt_len)
        _trace_set("token_count", len(query_tokens))

        # §24 execution cache: hash(query_tokens) → cached fused result within TTL.
        # Skips the whole pipeline (TEI+Qdrant+RRF+rerank) on a repeated query.
        cache_key = _surface_cache_key(query_tokens)
        cached = _surface_cache_get(cache_key)
        if cached is not None:
            merged = cached.get("results") or []
            # Replay reinforcement so §22 P1 still counts surfaced patterns on hits.
            try:
                from shared.pattern_reinforce import record_surfaced
                record_surfaced(
                    inp.session_id or "",
                    [tuple(p) for p in cached.get("pids", [])],
                )
            except Exception:
                pass
            _cdur = (time.monotonic() - t0) * 1000
            if not merged:
                _emit_langfuse_span("cached-empty", prompt_len=prompt_len, duration_ms=_cdur)
                _surface_log("cached-empty", t0, cache="hit")
                return None
            update_cooldown()
            _emit_langfuse_span(
                "injected-cached",
                prompt_len=prompt_len,
                merged_count=len(merged),
                duration_ms=_cdur,
            )
            _surface_log("injected-cached", t0, cache="hit", merged_count=len(merged))
            _emit_stdout(format_federated_context(merged))
            return None

        _trace_set("cache", "miss")
        deadline = t0 + TOTAL_BUDGET

        sqlite_results = (
            search_sqlite(query_tokens, limit=10) if time.monotonic() < deadline else []
        )
        qdrant_results = (
            search_qdrant(query_tokens, limit=10, prompt=prompt)
            if time.monotonic() < deadline
            else []
        )
        pids = [
            (r["id"], r["score"]) for r in qdrant_results
            if r.get("_collection") == "learned_patterns" and r.get("id")
        ]
        try:
            from shared.pattern_reinforce import record_surfaced
            record_surfaced(inp.session_id or "", pids)
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

        # §24 execution cache: store fused result + surfaced pattern ids (empty cached
        # too → avoids re-running the pipeline for queries that yield nothing).
        _surface_cache_put(cache_key, merged, pids)

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
        _emit_stdout(msg)
        return None


if __name__ == "__main__":
    MemoryFirstHook().run()
