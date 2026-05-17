"""Main indexing pipeline: walk -> chunk -> embed -> upsert into Qdrant."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models

from .chunker_base import Chunk
from .config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_COLLECTION,
    DEFAULT_QDRANT_URL,
    DEFAULT_TEI_URL,
    REPO_ROOT,
)
from .embedder import FrameworkTEIEmbedder
from .file_walker import iter_indexable_files
from .markdown_chunker import chunk_markdown
from .python_chunker import chunk_python
from .text_chunker import chunk_text

logger = logging.getLogger(__name__)


def _read_file(fp: Path) -> str | None:
    try:
        return fp.read_text(encoding="utf-8", errors="ignore")
    except OSError as e:
        logger.warning("indexer: cannot read %s: %s", fp, e)
        return None


def _chunks_for(fp: Path, rel: str, language: str) -> list[Chunk]:
    content = _read_file(fp)
    if content is None or not content.strip():
        return []
    try:
        mtime = fp.stat().st_mtime
    except OSError:
        return []

    if language == "python":
        return chunk_python(rel, content, mtime)
    if language == "markdown":
        return chunk_markdown(rel, content, mtime)
    if language in ("json", "javascript", "typescript", "text"):
        chunk_type = "config" if language == "json" else "text"
        return chunk_text(rel, content, mtime, language=language, chunk_type=chunk_type)
    return []


def collect_chunks(
    roots: list[str] | None = None,
    extra_files: list[str] | None = None,
    repo_root: Path = REPO_ROOT,
    only_paths: set[str] | None = None,
) -> tuple[list[Chunk], dict[str, int]]:
    """Walk filesystem and produce chunks.

    only_paths: if provided, restrict to these repo-relative POSIX paths
    (used by --changed-only and watcher incremental updates).

    Returns (chunks, stats) where stats has files / chunks / by_language counts.
    """
    chunks: list[Chunk] = []
    stats: dict[str, int] = {
        "files_seen": 0,
        "files_indexed": 0,
        "chunks": 0,
    }
    by_lang: dict[str, int] = {}

    for fp, rel, language in iter_indexable_files(roots, extra_files, repo_root):
        stats["files_seen"] += 1
        if only_paths is not None and rel not in only_paths:
            continue
        file_chunks = _chunks_for(fp, rel, language)
        if not file_chunks:
            continue
        stats["files_indexed"] += 1
        stats["chunks"] += len(file_chunks)
        by_lang[language] = by_lang.get(language, 0) + len(file_chunks)
        chunks.extend(file_chunks)

    stats["by_language"] = by_lang  # type: ignore[assignment]
    return chunks, stats


def resolve_physical_collection(client: QdrantClient, name: str) -> str:
    """If `name` is an alias, return underlying physical collection name."""
    try:
        aliases = client.get_aliases().aliases
    except Exception as e:
        logger.debug("resolve_physical_collection: get_aliases failed: %s", e)
        return name
    for a in aliases:
        if a.alias_name == name:
            return str(a.collection_name)
    return name


def recreate_collection_preserving_alias(
    client: QdrantClient,
    name: str,
    dims: int,
    *,
    distance: models.Distance = models.Distance.COSINE,
) -> str:
    """Atomically recreate a collection while preserving its alias.

    Performs four steps:
      1. Resolve physical collection name (detect if `name` is an alias).
      2. Drop the physical collection (this also wipes the alias mapping).
      3. Create a new collection with the specified dimensions and distance.
      4. If `name` was an alias, restore the alias mapping to the new physical.

    Returns the physical collection name (== `name` for non-aliased collections).

    Precondition: collection or alias must exist (caller verifies via
    `client.collection_exists(name)`). For a dangling alias (alias mapping
    pointing to a deleted physical), step 2 will raise — use `ensure_collection`
    instead, which falls through to creation when `collection_exists` is False.
    """
    physical = resolve_physical_collection(client, name)
    was_alias = physical != name

    if was_alias:
        logger.info("indexer: '%s' is alias -> '%s'; recreating physical", name, physical)

    logger.info("indexer: dropping collection %s for recreation", physical)
    client.delete_collection(physical)

    logger.info("indexer: creating collection %s (dims=%d %s)", physical, dims, distance.value)
    client.create_collection(
        collection_name=physical,
        vectors_config=models.VectorParams(size=dims, distance=distance),
    )

    if was_alias:
        logger.info("indexer: restoring alias '%s' -> '%s'", name, physical)
        client.update_collection_aliases(
            change_aliases_operations=[
                models.CreateAliasOperation(
                    create_alias=models.CreateAlias(
                        collection_name=physical,
                        alias_name=name,
                    ),
                ),
            ],
        )

    return physical


def ensure_collection(
    client: QdrantClient,
    collection: str,
    dims: int,
    recreate: bool = False,
) -> None:
    """Create collection if missing; drop+create if recreate=True.

    Alias-aware via `recreate_collection_preserving_alias`: if `collection`
    is an alias, recreate operates on the underlying physical and restores
    the alias afterwards. For a dangling alias (alias listed in get_aliases
    but physical missing), `collection_exists` returns False and the fresh
    create path is taken under the resolved physical name.
    """
    exists = client.collection_exists(collection)

    if exists and recreate:
        recreate_collection_preserving_alias(client, collection, dims)
        return

    if not exists:
        physical = resolve_physical_collection(client, collection)
        logger.info("indexer: creating collection %s (dims=%d cosine)", physical, dims)
        client.create_collection(
            collection_name=physical,
            vectors_config=models.VectorParams(size=dims, distance=models.Distance.COSINE),
        )


def resolve_collection_dim(client: QdrantClient, collection: str) -> int | None:
    """Return target dim of existing collection or None for multi-vector.

    Used to detect MRL-truncated collections (§4.1.6: framework_code_v1 aliased
    to framework_code_v1_mrl_1024 at 1024d).
    """
    info = client.get_collection(collection)
    cfg = info.config.params.vectors
    if cfg is None or isinstance(cfg, dict):
        return None
    return int(cfg.size)


def _mrl_truncate(v: list[float], target_dim: int) -> list[float]:
    """Truncate + L2-renorm one vector (helper for maybe_truncate_vectors)."""
    arr = np.asarray(v[:target_dim], dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    out = (arr / norm).tolist() if norm > 0 else arr.tolist()
    return list(out)


def maybe_truncate_vectors(vectors: list[list[float]], target_dim: int) -> list[list[float]]:
    """MRL-truncate batch; no-op if vectors already <= target_dim.

    Assumes already-short vectors are normalized (TEI returns L2-normalized
    embeddings via normalize=True). We only renorm after truncation.
    """
    return [v if len(v) <= target_dim else _mrl_truncate(v, target_dim) for v in vectors]


def upsert_chunks(
    client: QdrantClient,
    collection: str,
    chunks: list[Chunk],
    vectors: list[list[float]],
    sub_batch: int = 64,
) -> None:
    """Idempotent upsert keyed on chunk_id (UUID5)."""
    if len(chunks) != len(vectors):
        raise ValueError(f"chunks/vectors size mismatch: {len(chunks)} vs {len(vectors)}")

    points = [
        models.PointStruct(id=c.chunk_id, vector=v, payload=c.to_payload())
        for c, v in zip(chunks, vectors)
    ]
    for s in range(0, len(points), sub_batch):
        client.upsert(collection_name=collection, points=points[s : s + sub_batch], wait=True)


def delete_stale_paths(
    client: QdrantClient,
    collection: str,
    paths: Iterable[str],
    keep_ids: set[str] | None = None,
) -> int:
    """Drop chunks under `paths` whose chunk_id is NOT in keep_ids.

    With keep_ids: deletes only stale points (e.g. chunks of removed
    functions after a file edit). Without keep_ids: deletes ALL points
    under those paths (full-file-removal semantics).
    """
    paths = list(paths)
    if not paths:
        return 0
    must_clauses: list[Any] = [
        models.FieldCondition(key="relative_path", match=models.MatchAny(any=paths)),
    ]
    must_not_clauses: list[Any] = []
    if keep_ids:
        must_not_clauses.append(models.HasIdCondition(has_id=list(keep_ids)))
    flt = models.Filter(must=must_clauses, must_not=must_not_clauses or None)
    res = client.delete(
        collection_name=collection, points_selector=models.FilterSelector(filter=flt), wait=True
    )
    logger.info(
        "indexer: delete by paths status=%s (paths=%d, kept=%d)",
        getattr(res, "status", "?"),
        len(paths),
        len(keep_ids or ()),
    )
    return len(paths)


def run_index(
    *,
    roots: list[str] | None = None,
    extra_files: list[str] | None = None,
    only_paths: set[str] | None = None,
    collection: str = DEFAULT_COLLECTION,
    qdrant_url: str = DEFAULT_QDRANT_URL,
    tei_url: str = DEFAULT_TEI_URL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    recreate: bool = False,
    dry_run: bool = False,
    limit: int = 0,
) -> dict[str, Any]:
    """Top-level pipeline.

    Returns stats dict with files_indexed, chunks, by_language, embeddings_done.
    """
    chunks, stats = collect_chunks(roots, extra_files, only_paths=only_paths)
    if limit and len(chunks) > limit:
        chunks = chunks[:limit]
        stats["chunks"] = len(chunks)

    logger.info(
        "indexer: collected %d chunks from %d files (by_language=%s)",
        stats["chunks"],
        stats["files_indexed"],
        stats.get("by_language"),
    )

    if dry_run or not chunks:
        stats["embeddings_done"] = 0
        return stats

    client = QdrantClient(url=qdrant_url)

    with FrameworkTEIEmbedder(base_url=tei_url) as embedder:
        # Probe dims with a single embed to size the collection correctly.
        first = embedder.embed_batch([chunks[0].content])
        dims = len(first[0])
        ensure_collection(client, collection, dims=dims, recreate=recreate)
        target_dim = resolve_collection_dim(client, collection)
        truncate = target_dim is not None and target_dim < dims
        if truncate:
            logger.info("indexer: MRL truncation %dd -> %dd active", dims, target_dim)

        all_vectors: list[list[float]] = []
        for s in range(0, len(chunks), batch_size):
            batch = chunks[s : s + batch_size]
            texts = [c.content for c in batch]
            vectors = embedder.embed_batch(texts)
            if truncate:
                vectors = maybe_truncate_vectors(vectors, target_dim)  # type: ignore[arg-type]
            all_vectors.extend(vectors)
            logger.info("indexer: embedded %d/%d", s + len(batch), len(chunks))

    # Upsert FIRST (idempotent on UUID5), then drop stale points whose
    # chunk_id is gone from the new set. This avoids a lossy window between
    # delete and upsert if anything fails mid-flight.
    upsert_chunks(client, collection, chunks, all_vectors)
    if only_paths is not None and only_paths:
        delete_stale_paths(client, collection, only_paths, keep_ids={c.chunk_id for c in chunks})
    stats["embeddings_done"] = len(all_vectors)
    return stats
