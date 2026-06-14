"""RETIRED 2026-06-12 (roadmap 260612 pdf-docs full verification, P0.1 / D1).

DocsRag Adapter — SQLite chunks + optional Qdrant embeddings for documentation search.

Почему ретирован, а не rewire:
- Production-RAG для документации уже есть в `pdf_framework` (`pdf_documents` /
  `wiki_pages_v1`, alias-дисциплина, MRL 1024d) — дублирующая SQLite-вселенная не нужна.
- Контур был мёртв с рождения: default `chunks_db_path=""`, Qdrant-коллекция
  `docs_chunks` никогда не существовала, эмбеддер заимствован у vector_memory
  (Qwen3 4096d) против собственного дизайна; `_vector_search` глотал все ошибки.
- Жил только в `tests/integration/test_memory_p3_deferred.py` (docs-часть удалена
  той же правкой) — зелёные тесты создавали иллюзию живого контура.

Relative imports ниже мертвы по построению (файл вне пакета) — НЕ запускать;
хранится как референс дизайна FTS5+vector merge.

Version: 1.0 (2026-04-04) -- P3 migration
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ...orchestrator.unified_id import MemoryType, SourceServer
from ...orchestrator.unified_search import BaseSearchAdapter, SearchResultItem

logger = logging.getLogger(__name__)


@dataclass
class DocsRagConfig:
    """Configuration for the DocsRag adapter."""

    chunks_db_path: str = ""
    qdrant_collection: str = "docs_chunks"
    enable_vector_search: bool = True
    fts_weight: float = 0.6
    vector_weight: float = 0.4
    chunk_size: int = 512
    chunk_overlap: int = 64


class DocsRagSearchAdapter(BaseSearchAdapter):
    """Search adapter for documentation chunks (SQLite FTS + Qdrant vectors).

    Architecture:
      - **SQLite FTS5**: Full-text search over document chunks for keyword matching.
      - **Qdrant** (optional): Vector similarity for semantic matching.
      - Results are merged using weighted scoring (FTS × fts_weight + vector × vector_weight).

    The SQLite database stores document chunks with metadata (source file, position,
    section title). FTS5 provides fast keyword search. When Qdrant is available,
    vector search adds semantic understanding.

    Usage::

        adapter = DocsRagSearchAdapter(DocsRagConfig(
            chunks_db_path="data/docs_chunks.db",
        ))
        await adapter.initialize()
        results = await adapter.search("BSL query syntax", limit=5)
    """

    def __init__(self, config: DocsRagConfig) -> None:
        self._config = config
        self._db: sqlite3.Connection | None = None

    def source_name(self) -> str:
        return "docs-rag"

    async def initialize(self) -> None:
        """Create SQLite tables and FTS index if they don't exist."""
        Path(self._config.chunks_db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await asyncio.to_thread(self._open_db)
        logger.info("DocsRagSearchAdapter initialized: %s", self._config.chunks_db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await asyncio.to_thread(self._db.close)
            self._db = None

    async def search(self, query: str, limit: int = 10, **kwargs: Any) -> list[SearchResultItem]:
        """Search documentation chunks using FTS and optional vector similarity.

        Args:
            query: Search query text.
            limit: Maximum results to return.
            **kwargs: Additional options (e.g., ``source_filter``, ``section_filter``).

        Returns:
            Ranked list of :class:`SearchResultItem`.
        """
        fts_results = await self._fts_search(query, limit=limit * 2, **kwargs)
        vector_results: list[SearchResultItem] = []

        if self._config.enable_vector_search:
            vector_results = await self._vector_search(query, limit=limit * 2)

        merged = self._merge_results(fts_results, vector_results, limit)
        return merged

    async def ingest_document(
        self,
        source_path: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Split a document into chunks and store in SQLite + optionally Qdrant.

        Args:
            source_path: Path or identifier of the source document.
            content: Full text content.
            metadata: Optional metadata (section, tags, etc.).

        Returns:
            Number of chunks created.
        """
        chunks = self._split_into_chunks(content)
        meta = metadata or {}

        def _insert():
            assert self._db is not None
            count = 0
            for i, chunk_text in enumerate(chunks):
                self._db.execute(
                    "INSERT INTO chunks (source_path, chunk_index, content, section, tags, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        source_path,
                        i,
                        chunk_text,
                        meta.get("section", ""),
                        json.dumps(meta.get("tags", []), ensure_ascii=False),
                        datetime.now().isoformat(),
                    ),
                )
                count += 1
            self._db.commit()
            return count

        chunk_count = await asyncio.to_thread(_insert)

        # Optionally index in Qdrant
        if self._config.enable_vector_search and chunks:
            await self._index_vectors(source_path, chunks, meta)

        logger.info("Ingested %d chunks from %s", chunk_count, source_path)
        return chunk_count

    async def delete_document(self, source_path: str) -> int:
        """Remove all chunks for a source document.

        Returns:
            Number of chunks deleted.
        """

        def _delete():
            assert self._db is not None
            cursor = self._db.execute("DELETE FROM chunks WHERE source_path = ?", (source_path,))
            self._db.commit()
            return cursor.rowcount

        return await asyncio.to_thread(_delete)

    async def get_stats(self) -> dict[str, Any]:
        """Return adapter statistics."""

        def _stats():
            assert self._db is not None
            (total,) = self._db.execute("SELECT COUNT(*) FROM chunks").fetchone()
            (sources,) = self._db.execute(
                "SELECT COUNT(DISTINCT source_path) FROM chunks"
            ).fetchone()
            return {"total_chunks": total, "source_documents": sources}

        if self._db is None:
            return {"status": "not_initialized"}
        stats = await asyncio.to_thread(_stats)
        stats["vector_search_enabled"] = self._config.enable_vector_search
        return stats

    # -- SQLite helpers ------------------------------------------------------

    def _open_db(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._config.chunks_db_path, check_same_thread=False)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content     TEXT NOT NULL,
                section     TEXT DEFAULT '',
                tags        TEXT DEFAULT '[]',
                created_at  TEXT NOT NULL
            )
            """
        )
        db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks (source_path)")
        # FTS5 virtual table
        db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content, section, tags,
                content=chunks,
                content_rowid=id
            )
            """
        )
        # Triggers to keep FTS in sync
        db.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, content, section, tags)
                VALUES (new.id, new.content, new.section, new.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content, section, tags)
                VALUES ('delete', old.id, old.content, old.section, old.tags);
            END;
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, content, section, tags)
                VALUES ('delete', old.id, old.content, old.section, old.tags);
                INSERT INTO chunks_fts(rowid, content, section, tags)
                VALUES (new.id, new.content, new.section, new.tags);
            END;
            """
        )
        db.commit()
        return db

    async def _fts_search(
        self, query: str, limit: int = 20, **kwargs: Any
    ) -> list[SearchResultItem]:
        """Full-text search using SQLite FTS5."""

        source_filter = kwargs.get("source_filter")
        section_filter = kwargs.get("section_filter")

        def _search():
            assert self._db is not None
            # FTS5 match query — escape special characters
            fts_query = " ".join(f'"{w}"' for w in query.split() if w.strip())
            if not fts_query:
                return []

            sql = (
                "SELECT c.id, c.source_path, c.chunk_index, c.content, c.section, "
                "c.tags, c.created_at, rank "
                "FROM chunks_fts fts "
                "JOIN chunks c ON c.id = fts.rowid "
                "WHERE chunks_fts MATCH ? "
            )
            params: list[Any] = [fts_query]

            if source_filter:
                sql += "AND c.source_path LIKE ? "
                params.append(f"%{source_filter}%")
            if section_filter:
                sql += "AND c.section LIKE ? "
                params.append(f"%{section_filter}%")

            sql += "ORDER BY rank LIMIT ?"
            params.append(limit)

            results = []
            try:
                cursor = self._db.execute(sql, params)
                for row in cursor.fetchall():
                    # FTS5 rank is negative (lower = better match)
                    raw_rank = abs(row[7]) if row[7] else 0.0
                    score = 1.0 / (1.0 + raw_rank)  # normalize to 0-1
                    tags = json.loads(row[5]) if row[5] else []
                    results.append(
                        SearchResultItem(
                            unified_id=f"docs:docs-rag:chunk-{row[0]}",
                            source=SourceServer.PDF_DOCS,
                            memory_type=MemoryType.DOCUMENTATION,
                            content=row[3],
                            title=f"{row[1]}#{row[2]} — {row[4]}"
                            if row[4]
                            else f"{row[1]}#{row[2]}",
                            raw_score=score,
                            created_at=datetime.fromisoformat(row[6]) if row[6] else None,
                            tags=tags,
                            metadata={
                                "source_path": row[1],
                                "chunk_index": row[2],
                                "section": row[4],
                                "search_method": "fts",
                            },
                        )
                    )
            except sqlite3.OperationalError as e:
                logger.warning("FTS search failed: %s", e)
            return results

        return await asyncio.to_thread(_search)

    async def _vector_search(self, query: str, limit: int = 20) -> list[SearchResultItem]:
        """Vector similarity search using Qdrant (optional)."""
        try:
            from ...vector_memory.server import _get_embedding, _get_qdrant

            client = await asyncio.to_thread(_get_qdrant)
            vector = await _get_embedding(query)

            qresults = client.query_points(
                collection_name=self._config.qdrant_collection,
                query=vector,
                limit=limit,
                with_payload=True,
            )

            results = []
            for point in qresults.points:
                payload = point.payload or {}
                similarity = point.score or 0.0
                results.append(
                    SearchResultItem(
                        unified_id=f"docs:docs-rag:vec-{point.id}",
                        source=SourceServer.PDF_DOCS,
                        memory_type=MemoryType.DOCUMENTATION,
                        content=payload.get("content", ""),
                        title=payload.get("title", ""),
                        raw_score=similarity,
                        tags=payload.get("tags", []),
                        metadata={
                            "source_path": payload.get("source_path", ""),
                            "chunk_index": payload.get("chunk_index", 0),
                            "search_method": "vector",
                        },
                    )
                )
            return results

        except Exception as e:
            logger.debug("Vector search unavailable: %s", e)
            return []

    async def _index_vectors(
        self, source_path: str, chunks: list[str], metadata: dict[str, Any]
    ) -> None:
        """Index chunks in Qdrant for vector search."""
        try:
            from qdrant_client.http import models as qmodels

            from ...vector_memory.server import _get_embedding, _get_qdrant

            client = await asyncio.to_thread(_get_qdrant)
            points = []
            for i, chunk_text in enumerate(chunks):
                vector = await _get_embedding(chunk_text)
                point_id = f"{source_path}:{i}"
                import hashlib

                numeric_id = int(hashlib.md5(point_id.encode()).hexdigest()[:16], 16)
                points.append(
                    qmodels.PointStruct(
                        id=numeric_id,
                        vector=vector,
                        payload={
                            "content": chunk_text,
                            "source_path": source_path,
                            "chunk_index": i,
                            "title": metadata.get("section", ""),
                            "tags": metadata.get("tags", []),
                        },
                    )
                )

            if points:
                await asyncio.to_thread(
                    client.upsert,
                    collection_name=self._config.qdrant_collection,
                    points=points,
                )
        except Exception as e:
            logger.debug("Vector indexing skipped: %s", e)

    # -- Chunking ------------------------------------------------------------

    def _split_into_chunks(self, content: str) -> list[str]:
        """Split content into overlapping text chunks."""
        size = self._config.chunk_size
        overlap = self._config.chunk_overlap
        if len(content) <= size:
            return [content] if content.strip() else []

        chunks = []
        start = 0
        while start < len(content):
            end = start + size
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += size - overlap
        return chunks

    def _merge_results(
        self,
        fts_results: list[SearchResultItem],
        vector_results: list[SearchResultItem],
        limit: int,
    ) -> list[SearchResultItem]:
        """Merge FTS and vector results with weighted scoring."""
        if not vector_results:
            return fts_results[:limit]
        if not fts_results:
            return vector_results[:limit]

        # Index by content hash for dedup
        seen: dict[str, SearchResultItem] = {}

        for item in fts_results:
            key = item.content[:100]
            if key not in seen:
                item.raw_score *= self._config.fts_weight
                seen[key] = item
            else:
                seen[key].raw_score += item.raw_score * self._config.fts_weight

        for item in vector_results:
            key = item.content[:100]
            if key not in seen:
                item.raw_score *= self._config.vector_weight
                seen[key] = item
            else:
                seen[key].raw_score += item.raw_score * self._config.vector_weight

        merged = sorted(seen.values(), key=lambda x: x.raw_score, reverse=True)
        return merged[:limit]


__all__ = ["DocsRagConfig", "DocsRagSearchAdapter"]
