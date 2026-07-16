"""§26 P2 D2.1 — reflection: consolidate repeated episodic facts → semantic patterns.

Generative-Agents-style consolidation: when several episodic rows in
``data/memory_ai.db`` (``important_messages``) cover the **same topic**, fold them
into a single ``learned_patterns`` semantic pattern instead of N near-duplicates.

  - Source: episodic rows, EXCLUDING ``session_summary`` (per-session logs, not
    repeatable facts — same exclusion as ``normalize_light_patterns`` CATEGORY_MAP).
  - Clustering: token-overlap (Jaccard ≥ threshold) union-find — cheap, no embedding.
  - Trigger (Q2: fixed, parameterised): cluster size ≥ ``min_cluster`` OR summed
    importance ≥ ``importance_theta``.
  - Each triggered cluster → 1 HarvestItem (canonical = highest-importance row),
    ingested via the shared ``ingest_items`` path (content_hash dedup, §22 seed
    0.70, cap). On creation, ``link_fn`` records DERIVES_FROM links to every source
    episodic id (§26 P2 D2.3) — trace which episodes a pattern was distilled from.

Safety: **dry-run by default** (reviewable plan, no writes); content_hash dedup
(re-run = 0 new); pure fail-soft. ``client``/``embed``/``link_fn`` injectable for tests.
"""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Sibling helper. `from shared.pattern_harvest` works in the hook/script context,
# but pattern_harvest inserts <repo>/src onto sys.path (for memory.orchestrator),
# and a second `src/shared` package can then shadow `.claude/hooks/shared`. Fall
# back to a direct file-path load so the import is robust under any path ordering.
try:
    from shared.pattern_harvest import HarvestItem, ingest_items
    from shared.pattern_harvest import _normalize_ptype as _normalize_ptype
except ImportError:  # pragma: no cover - path-ordering dependent
    import importlib.util as _ilu

    _ph_path = Path(__file__).resolve().parent / "pattern_harvest.py"
    _spec = _ilu.spec_from_file_location("pattern_harvest", str(_ph_path))
    assert _spec and _spec.loader
    _ph = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_ph)
    HarvestItem, ingest_items = _ph.HarvestItem, _ph.ingest_items
    _normalize_ptype = _ph._normalize_ptype

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# MEMORY_AI_DB_PATH override — test isolation (roadmap 260612 P0.3)
MEMORY_AI_DB = Path(os.environ.get("MEMORY_AI_DB_PATH") or PROJECT_ROOT / "data" / "memory_ai.db")

# session_summary = episodic log, not a repeatable fact → never consolidated.
EXCLUDE_CATEGORIES = {"session_summary"}
DEFAULT_MIN_CLUSTER = 3
DEFAULT_SIM_THRESHOLD = 0.5
DEFAULT_CAP = 10

# category (memory-ai) → pattern_type. Resolved through the ONE alias table in
# vector_memory.models (roadmap 260716 P0.1); this used to be a hand-kept copy of
# normalize_light_patterns.CATEGORY_MAP. Membership stays local — it decides which
# categories are patterns at all. `_normalize_ptype` is imported by pattern_harvest
# (above) with its own fail-soft fallback, so no extra import guard is needed here.
_MAPPED_CATEGORIES = (
    "decision",
    "preference",
    "bugfix",
    "implementation",
    "reference",
    "feedback",
    "project",
    "code-convention",
)
_CATEGORY_MAP = {c: _normalize_ptype(c)[0] for c in _MAPPED_CATEGORIES}

_TOKEN_RE = re.compile(r"\w{3,}", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def read_episodes(
    db_path: Path = MEMORY_AI_DB,
    exclude_categories: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Read fact-like episodic rows (id/content/importance/category/created_at)."""
    exclude = EXCLUDE_CATEGORIES if exclude_categories is None else exclude_categories
    if not db_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        conn = sqlite3.connect(str(db_path), timeout=2)
        cur = conn.execute(
            "SELECT id, content, importance, category, created_at FROM important_messages"
        )
        for rid, content, importance, category, created_at in cur.fetchall():
            if category in exclude:
                continue
            if not content or not str(content).strip():
                continue
            rows.append(
                {
                    "id": rid,
                    "content": str(content),
                    "importance": float(importance)
                    if isinstance(importance, (int, float))
                    else 0.5,
                    "category": category or "",
                    "created_at": created_at or "",
                }
            )
        conn.close()
    except Exception:
        return rows
    return rows


def cluster_episodes(
    rows: list[dict[str, Any]], sim_threshold: float
) -> list[list[dict[str, Any]]]:
    """Union-find clustering by token-overlap (Jaccard ≥ threshold)."""
    n = len(rows)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    toks = [_tokens(r["content"]) for r in rows]
    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(toks[i], toks[j]) >= sim_threshold:
                union(i, j)

    groups: dict[int, list[dict[str, Any]]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(rows[i])
    return list(groups.values())


def _build_cluster_item(cluster: list[dict[str, Any]]) -> tuple[HarvestItem, list[str]]:
    """Canonical pattern from a cluster + its source episodic ids (for DERIVES_FROM)."""
    canonical = max(cluster, key=lambda r: (r["importance"], len(r["content"])))
    # dominant category → pattern_type
    cats = [r["category"] for r in cluster]
    dominant = max(set(cats), key=cats.count) if cats else ""
    ptype = _CATEGORY_MAP.get(dominant, "workflow-pattern")
    # content is count-free (canonical row only): keeps content_hash stable when the
    # cluster later grows, so re-runs dedup instead of orphaning a "from N" variant.
    # The episode count lives in description (not hashed) + DERIVES_FROM links.
    content = canonical["content"].strip()
    item = HarvestItem(
        content=content,
        name=content.splitlines()[0][:60],
        description=f"Reflection-consolidated {dominant} ({len(cluster)} episodes)",
        pattern_type=ptype,
        source=f"reflection:memory_ai:{canonical['id']}",
        tags=["reflection", "consolidated", "harvested"],
    )
    return item, [r["id"] for r in cluster]


def reflect(
    *,
    db_path: Path = MEMORY_AI_DB,
    rows: list[dict[str, Any]] | None = None,
    min_cluster: int = DEFAULT_MIN_CLUSTER,
    sim_threshold: float = DEFAULT_SIM_THRESHOLD,
    importance_theta: float | None = None,
    cap: int = DEFAULT_CAP,
    dry_run: bool = True,
    client: Any = None,
    embed: Callable[[str], list[float] | None] | None = None,
    link_fn: Callable[[str, str], None] | None = None,
    exclude_categories: set[str] | None = None,
) -> dict[str, Any]:
    """Consolidate repeated episodic facts into semantic patterns.

    Trigger: cluster size ≥ ``min_cluster`` OR summed importance ≥ ``importance_theta``.
    Returns stats: clusters_found / clusters_triggered + ingest_items stats
    (created / skipped_dup / skipped_cap / errors / items). dry_run=True by default.
    """
    if rows is None:
        rows = read_episodes(db_path, exclude_categories)
    clusters = cluster_episodes(rows, sim_threshold) if rows else []

    def triggered(c: list[dict[str, Any]]) -> bool:
        if len(c) >= min_cluster:
            return True
        if importance_theta is not None and sum(r["importance"] for r in c) >= importance_theta:
            return True
        return False

    fired = [c for c in clusters if triggered(c)]

    items: list[HarvestItem] = []
    sources_by_hash: dict[str, list[str]] = {}
    for c in fired:
        item, src_ids = _build_cluster_item(c)
        items.append(item)
        sources_by_hash[item.content_hash] = src_ids

    def on_created(item: HarvestItem, pid: str) -> None:
        if link_fn is None:
            return
        for sid in sources_by_hash.get(item.content_hash, []):
            try:
                link_fn(pid, sid)
            except Exception:
                pass

    stats = ingest_items(
        items, cap=cap, dry_run=dry_run, client=client, embed=embed, on_created=on_created
    )
    stats["clusters_found"] = len(clusters)
    stats["clusters_triggered"] = len(fired)
    return stats


def make_link_fn() -> Callable[[str, str], None] | None:
    """Real DERIVES_FROM link recorder via LinkRegistry (None if unavailable)."""
    try:
        import sys

        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.orchestrator.link_registry import LinkRegistry, LinkType

        reg = LinkRegistry()

        def _link(pattern_pid: str, episodic_id: str) -> None:
            try:
                reg.create_link(
                    source_id=f"semantic:vector-memory:{pattern_pid}",
                    target_id=f"episodic:memory-ai:{episodic_id}",
                    link_type=LinkType.DERIVES_FROM,
                    created_by="reflection",
                )
            except Exception:
                pass  # already exists / store error — non-fatal

        return _link
    except Exception:
        return None
