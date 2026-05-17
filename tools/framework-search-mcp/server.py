"""
Framework-Search MCP Server — Stage 2.

Exposes framework_code_v1 Qdrant collection to Claude Code via MCP.
Tools:
  - search_code(query, k=5, language=None, path_glob=None) — semantic search
  - find_similar(file_path, k=5) — similar code by file content
  - index_status() — collection stats + last reindex info
  - reindex_changed() — manual incremental reindex

Lazy mtime check: before each search_code, if any indexed file's on-disk mtime
> the mtime stored in its Qdrant payload, those files are reindexed (throttled
to once per LAZY_CHECK_MIN_INTERVAL_SEC = 30s).

Stage 3 (file watcher) will eventually make lazy check redundant for hot files,
but lazy check is a safety net for cold starts and watcher downtime.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add repo root so `src.framework_search` imports work when run as MCP stdio.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from qdrant_client import QdrantClient  # noqa: E402
from qdrant_client.http import models  # noqa: E402

from src.framework_search.config import (  # noqa: E402
    DEFAULT_COLLECTION,
    DEFAULT_QDRANT_URL,
    DEFAULT_TEI_URL,
    REPO_ROOT as FW_REPO_ROOT,
)
from src.framework_search.embedder import FrameworkTEIEmbedder  # noqa: E402
from src.framework_search.file_walker import iter_indexable_files  # noqa: E402
from src.framework_search.indexer import (  # noqa: E402
    maybe_truncate_vectors,
    resolve_collection_dim,
    run_index,
)

logger = logging.getLogger("framework-search-mcp")

LAZY_CHECK_MIN_INTERVAL_SEC = 30
LAZY_CHECK_MAX_FILES_PER_RUN = 50  # cap to avoid huge stalls

mcp = FastMCP("framework-search")

# Module-level state.
_state: dict = {
    "client": None,
    "embedder": None,
    "last_lazy_check_ts": 0.0,
    "collection": DEFAULT_COLLECTION,
    "qdrant_url": DEFAULT_QDRANT_URL,
    "tei_url": DEFAULT_TEI_URL,
    "target_dim": None,  # cached: collection's vector dim (1024 for MRL alias)
}


def _client() -> QdrantClient:
    if _state["client"] is None:
        _state["client"] = QdrantClient(url=_state["qdrant_url"])
    return _state["client"]


def _embedder() -> FrameworkTEIEmbedder:
    if _state["embedder"] is None:
        _state["embedder"] = FrameworkTEIEmbedder(base_url=_state["tei_url"])
    return _state["embedder"]


def _query_vec(text: str, is_query: bool = True) -> list[float]:
    """Embed + truncate to collection dim (handles MRL-truncated aliases)."""
    qv = _embedder().embed_batch([text], is_query=is_query)[0]
    if _state["target_dim"] is None:
        try:
            _state["target_dim"] = resolve_collection_dim(_client(), _state["collection"])
        except Exception:
            _state["target_dim"] = len(qv)
    td = _state["target_dim"]
    if td and td < len(qv):
        qv = maybe_truncate_vectors([qv], td)[0]
    return qv


def _scan_stale_files() -> list[str]:
    """Return repo-relative paths whose on-disk mtime > indexed mtime.

    Caps at LAZY_CHECK_MAX_FILES_PER_RUN to avoid unbounded stalls.
    """
    client = _client()
    coll = _state["collection"]
    if not client.collection_exists(coll):
        return []

    # Scroll all points, collect (path -> max_mtime) — file may have multiple chunks.
    indexed: dict[str, float] = {}
    next_offset = None
    while True:
        recs, next_offset = client.scroll(
            collection_name=coll,
            limit=512,
            with_payload=["relative_path", "mtime"],
            with_vectors=False,
            offset=next_offset,
        )
        if not recs:
            break
        for r in recs:
            p = r.payload or {}
            rel = p.get("relative_path")
            mt = p.get("mtime", 0.0)
            if rel and (rel not in indexed or mt > indexed[rel]):
                indexed[rel] = float(mt)
        if next_offset is None:
            break

    stale: list[str] = []
    for fp, rel, _lang in iter_indexable_files():
        on_disk = fp.stat().st_mtime
        idx_mt = indexed.get(rel)
        if idx_mt is None:
            stale.append(rel)  # new file, never indexed
        elif on_disk > idx_mt + 1.0:  # 1s tolerance for FS clock skew
            stale.append(rel)
        if len(stale) >= LAZY_CHECK_MAX_FILES_PER_RUN:
            break
    return stale


def _maybe_lazy_check() -> int:
    """Throttled stale-file detection + incremental reindex. Returns # files reindexed."""
    now = time.time()
    if now - _state["last_lazy_check_ts"] < LAZY_CHECK_MIN_INTERVAL_SEC:
        return 0
    _state["last_lazy_check_ts"] = now
    stale = _scan_stale_files()
    if not stale:
        return 0
    logger.info("lazy-check: reindexing %d stale files", len(stale))
    run_index(
        only_paths=set(stale),
        collection=_state["collection"],
        qdrant_url=_state["qdrant_url"],
        tei_url=_state["tei_url"],
    )
    return len(stale)


# ---------------------------------------------------------------- MCP tools


@mcp.tool()
def search_code(
    query: str,
    k: int = 5,
    language: str | None = None,
    path_glob: str | None = None,
) -> dict:
    """Semantic search over the framework's own codebase.

    Args:
        query: Natural-language description of what you're looking for.
        k: Number of results (default 5, max 20).
        language: Optional filter — 'python', 'markdown', 'json', 'typescript', 'javascript', 'text'.
        path_glob: Optional substring filter on relative_path (e.g. 'hooks/' or 'embedder').

    Returns:
        {
          "results": [{score, relative_path, line_start, line_end, language,
                       chunk_type, symbol_name, content_preview}, ...],
          "lazy_reindexed": <count>,
        }
    """
    k = max(1, min(int(k), 20))
    reindexed = _maybe_lazy_check()

    qv = _query_vec(query, is_query=True)

    must: list = []
    if language:
        must.append(models.FieldCondition(
            key="language", match=models.MatchValue(value=language),
        ))
    if path_glob:
        must.append(models.FieldCondition(
            key="relative_path", match=models.MatchText(text=path_glob),
        ))
    flt = models.Filter(must=must) if must else None

    points = _client().query_points(
        collection_name=_state["collection"],
        query=qv, limit=k, query_filter=flt, with_payload=True,
    ).points

    results = []
    for p in points:
        pl = p.payload or {}
        content = pl.get("content", "")
        results.append({
            "score": round(float(p.score), 4),
            "relative_path": pl.get("relative_path"),
            "line_start": pl.get("line_start"),
            "line_end": pl.get("line_end"),
            "language": pl.get("language"),
            "chunk_type": pl.get("chunk_type"),
            "symbol_name": pl.get("symbol_name"),
            "content_preview": content[:400],
        })
    return {"results": results, "lazy_reindexed": reindexed}


@mcp.tool()
def find_similar(file_path: str, k: int = 5) -> dict:
    """Find code semantically similar to the content of a given file.

    Args:
        file_path: Repo-relative POSIX path (e.g. 'src/framework_search/embedder.py').
        k: Number of results.
    """
    fp = (FW_REPO_ROOT / file_path).resolve()
    try:
        fp.relative_to(FW_REPO_ROOT)
    except ValueError:
        return {"error": f"path {file_path!r} is outside repo_root", "results": []}
    if not fp.exists() or not fp.is_file():
        return {"error": f"file not found: {file_path}", "results": []}

    content = fp.read_text(encoding="utf-8", errors="ignore")[:8000]
    if not content.strip():
        return {"error": "file is empty", "results": []}

    qv = _query_vec(content, is_query=False)

    points = _client().query_points(
        collection_name=_state["collection"],
        query=qv, limit=int(k) + 1, with_payload=True,  # +1 to skip self-match
    ).points

    results = []
    rel = file_path.replace("\\", "/").lstrip("./")
    for p in points:
        pl = p.payload or {}
        if pl.get("relative_path") == rel:
            continue  # skip self
        results.append({
            "score": round(float(p.score), 4),
            "relative_path": pl.get("relative_path"),
            "line_start": pl.get("line_start"),
            "line_end": pl.get("line_end"),
            "language": pl.get("language"),
            "chunk_type": pl.get("chunk_type"),
            "symbol_name": pl.get("symbol_name"),
            "content_preview": (pl.get("content") or "")[:400],
        })
        if len(results) >= int(k):
            break
    return {"results": results, "queried_file": rel}


@mcp.tool()
def index_status() -> dict:
    """Return current collection stats + lazy-check status."""
    client = _client()
    coll = _state["collection"]
    if not client.collection_exists(coll):
        return {"collection": coll, "exists": False}
    info = client.get_collection(coll)

    # Aggregate by language (sample 1024 random points to estimate distribution).
    by_lang: dict[str, int] = {}
    by_type: dict[str, int] = {}
    next_offset = None
    seen = 0
    while seen < 1024:
        recs, next_offset = client.scroll(
            collection_name=coll, limit=512,
            with_payload=["language", "chunk_type"],
            with_vectors=False, offset=next_offset,
        )
        if not recs:
            break
        for r in recs:
            pl = r.payload or {}
            by_lang[pl.get("language", "?")] = by_lang.get(pl.get("language", "?"), 0) + 1
            by_type[pl.get("chunk_type", "?")] = by_type.get(pl.get("chunk_type", "?"), 0) + 1
            seen += 1
        if next_offset is None:
            break

    last_lazy = _state["last_lazy_check_ts"]
    return {
        "collection": coll,
        "exists": True,
        "points_count": info.points_count,
        "dimensions": info.config.params.vectors.size,
        "distance": str(info.config.params.vectors.distance),
        "sample_by_language": by_lang,
        "sample_by_chunk_type": by_type,
        "last_lazy_check_seconds_ago": (
            round(time.time() - last_lazy, 1) if last_lazy else None
        ),
        "lazy_check_min_interval_sec": LAZY_CHECK_MIN_INTERVAL_SEC,
    }


@mcp.tool()
def reindex_changed() -> dict:
    """Manually trigger lazy-check (bypasses throttle). Reindex all stale files."""
    _state["last_lazy_check_ts"] = 0.0  # force run
    n = _maybe_lazy_check()
    return {"reindexed_files": n}


# ---------------------------------------------------------------- entrypoint


def main() -> None:
    ap = argparse.ArgumentParser(description="framework-search MCP server")
    ap.add_argument("--collection", default=DEFAULT_COLLECTION)
    ap.add_argument("--qdrant-url", default=DEFAULT_QDRANT_URL)
    ap.add_argument("--tei-url", default=DEFAULT_TEI_URL)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(
        level=args.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,  # stdout is reserved for MCP protocol
    )

    _state["collection"] = args.collection
    _state["qdrant_url"] = args.qdrant_url
    _state["tei_url"] = args.tei_url
    logger.info("framework-search MCP starting (collection=%s)", args.collection)

    mcp.run()  # stdio transport


if __name__ == "__main__":
    main()
