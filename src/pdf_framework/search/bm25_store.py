"""BM25 Index Store using SQLite FTS5 with multi-column search.

Persistent full-text search index for lexical (BM25) retrieval.
Uses SQLite's built-in FTS5 extension with unicode61 tokenizer.
Phase 16.2: pymorphy3 lemmatization for Russian morphology support.
Phase 27: Multi-column FTS5 (title + body) with 10x title boost.

Author: Claude Code
Version: 0.8.0 - Phase 27: Multi-Column FTS5 + Two-Pass RRF
"""

import asyncio
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Common Russian stop-words — filtered from BM25 queries to improve recall
RUSSIAN_STOP_WORDS = frozenset({
    "и", "в", "на", "с", "к", "о", "у", "а", "но", "или", "не", "ни",
    "же", "бы", "ли", "что", "как", "это", "для", "по", "из", "от",
    "до", "за", "при", "все", "его", "так", "она", "он", "они",
    "мы", "вы", "ее", "их", "том", "тем", "нет", "да",
})

# Word boundary pattern for lemmatization
_WORD_RE = re.compile(r"[а-яёА-ЯЁa-zA-Z0-9_]+")


def _init_morph() -> Any:
    """Lazy-init pymorphy3 MorphAnalyzer (singleton)."""
    try:
        import pymorphy3
        return pymorphy3.MorphAnalyzer()
    except ImportError:
        logger.info("[BM25] pymorphy3 not installed — using prefix stemming fallback")
        return None


# Module-level singleton — initialized once on first use
_morph: Any = None
_morph_initialized = False
_lemma_cache: dict[str, str] = {}


def _get_morph() -> Any:
    """Get or create the MorphAnalyzer singleton."""
    global _morph, _morph_initialized
    if not _morph_initialized:
        _morph = _init_morph()
        _morph_initialized = True
    return _morph


def lemmatize_word(word: str) -> str:
    """Lemmatize a single word using pymorphy3 with caching."""
    lower = word.lower()
    if lower in _lemma_cache:
        return _lemma_cache[lower]

    morph = _get_morph()
    if morph is None:
        _lemma_cache[lower] = lower
        return lower

    parsed = morph.parse(lower)
    lemma = parsed[0].normal_form if parsed else lower
    _lemma_cache[lower] = lemma
    return lemma


def lemmatize_text(text: str) -> str:
    """Lemmatize all words in text, preserving non-word characters."""
    morph = _get_morph()
    if morph is None:
        return text  # No lemmatization available
    return _WORD_RE.sub(lambda m: lemmatize_word(m.group()), text)


class BM25Store:
    """SQLite FTS5-based BM25 index for document chunks.

    Uses multi-column FTS5 (title + body) for field-weighted BM25 scoring.
    Title column gets 10x weight boost for section-aware ranking.
    All I/O is run via asyncio.to_thread() for non-blocking operation.
    """

    # FTS5 column weights: chunk_id=0, title=10, body=1, document_id=0, source=0
    _COLUMN_WEIGHTS = "bm25(chunks_fts, 0, 10.0, 1.0, 0, 0)"

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = Path.cwd() / "data" / "bm25_index.db"
        self._db_path = db_path
        self._initialized = False

    async def initialize(self) -> None:
        """Create the FTS5 table if it doesn't exist."""
        if self._initialized:
            return
        await asyncio.to_thread(self._create_tables)
        self._initialized = True
        count = await self.count()
        has_morph = _get_morph() is not None
        logger.info(
            "[BM25] Initialized: %s (%d chunks, lemmatization=%s, multi-column=true)",
            self._db_path, count, has_morph,
        )

    def _create_tables(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            # Check if old single-column schema exists and migrate
            self._migrate_fts_schema(conn)

            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    chunk_id,
                    title,
                    body,
                    document_id,
                    source,
                    tokenize='unicode61'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunk_meta (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    original_content TEXT NOT NULL DEFAULT '',
                    section_title TEXT NOT NULL DEFAULT ''
                )
                """
            )
            # Migrate: add original_content column if missing (existing DBs)
            try:
                conn.execute("SELECT original_content FROM chunk_meta LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute(
                    "ALTER TABLE chunk_meta ADD COLUMN original_content TEXT NOT NULL DEFAULT ''"
                )
                logger.info("[BM25] Migrated chunk_meta: added original_content column")
            # Migrate: add section_title column if missing
            try:
                conn.execute("SELECT section_title FROM chunk_meta LIMIT 1")
            except sqlite3.OperationalError:
                conn.execute(
                    "ALTER TABLE chunk_meta ADD COLUMN section_title TEXT NOT NULL DEFAULT ''"
                )
                logger.info("[BM25] Migrated chunk_meta: added section_title column")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_meta_doc ON chunk_meta(document_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_chunk_meta_source ON chunk_meta(source)"
            )
            conn.commit()
        finally:
            conn.close()

    def _migrate_fts_schema(self, conn: sqlite3.Connection) -> None:
        """Detect old single-column FTS5 schema and drop it for recreation."""
        try:
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='chunks_fts'"
            )
            row = cursor.fetchone()
            if row is None:
                return  # Table doesn't exist yet — will be created fresh

            create_sql = row[0] or ""
            # Old schema has 'content' column but no 'title'/'body' columns
            if "title" not in create_sql.lower() and "content" in create_sql.lower():
                logger.info(
                    "[BM25] Detected old single-column FTS5 schema — dropping for migration"
                )
                conn.execute("DROP TABLE chunks_fts")
                conn.execute("DELETE FROM chunk_meta")
                conn.commit()
                logger.info("[BM25] Schema migration complete — rebuild index required")
        except sqlite3.OperationalError as e:
            logger.warning("[BM25] Schema migration check failed: %s", e)

    # ------------------------------------------------------------------
    # Add
    # ------------------------------------------------------------------

    async def add_chunks(
        self,
        chunk_ids: list[str],
        contents: list[str],
        document_ids: list[str],
        sources: list[str],
        sections: list[str] | None = None,
    ) -> int:
        """Insert chunks into the FTS5 index with separate title/body columns.

        Args:
            sections: Optional section headers stored as title column (10x weight).

        Returns number of chunks inserted.
        """
        if not chunk_ids:
            return 0
        return await asyncio.to_thread(
            self._add_chunks_sync, chunk_ids, contents, document_ids, sources, sections
        )

    def _add_chunks_sync(
        self,
        chunk_ids: list[str],
        contents: list[str],
        document_ids: list[str],
        sources: list[str],
        sections: list[str] | None = None,
    ) -> int:
        conn = sqlite3.connect(str(self._db_path))
        inserted = 0
        try:
            cursor = conn.cursor()
            for i, (cid, content, doc_id, source) in enumerate(
                zip(chunk_ids, contents, document_ids, sources)
            ):
                if not content or not content.strip():
                    continue

                # Extract title (section header) and body (content)
                section_title = ""
                if sections and i < len(sections) and sections[i]:
                    section_title = sections[i]

                # Lemmatize title and body separately for FTS5
                lemma_title = lemmatize_text(section_title) if section_title else ""
                lemma_body = lemmatize_text(content)

                # Store original content with section prepended (for retrieval)
                original = f"{section_title}\n{content}" if section_title else content

                cursor.execute(
                    "INSERT OR REPLACE INTO chunk_meta "
                    "(chunk_id, document_id, source, original_content, section_title) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (cid, doc_id, source, original, section_title),
                )
                cursor.execute(
                    "DELETE FROM chunks_fts WHERE chunk_id = ?", (cid,)
                )
                cursor.execute(
                    "INSERT INTO chunks_fts (chunk_id, title, body, document_id, source) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (cid, lemma_title, lemma_body, doc_id, source),
                )
                inserted += 1
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("[BM25] Error adding chunks: %s", e)
            raise
        finally:
            conn.close()
        return inserted

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, query: str, k: int = 10) -> list[tuple[str, float]]:
        """Search the FTS5 index with weighted columns.

        Returns list of (chunk_id, bm25_score).
        Uses column weights: title=10x, body=1x.
        Scores are negative (lower = better) — caller normalizes.
        """
        if not query or not query.strip():
            return []
        return await asyncio.to_thread(self._search_sync, query, k)

    def _search_sync(self, query: str, k: int) -> list[tuple[str, float]]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            and_query = self._make_fts_query(query)
            if not and_query:
                return []

            cursor = conn.cursor()

            # Step 1: AND query with column weights (title=10x, body=1x)
            cursor.execute(
                f"SELECT chunk_id, {self._COLUMN_WEIGHTS} as score "
                "FROM chunks_fts "
                "WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?",
                (and_query, k),
            )
            results = [(row[0], row[1]) for row in cursor.fetchall()]

            # Step 2: If AND returned fewer than k, supplement with OR
            if len(results) < k:
                or_query = self._make_fts_query_or(query)
                if or_query and or_query != and_query:
                    seen = {r[0] for r in results}
                    cursor.execute(
                        f"SELECT chunk_id, {self._COLUMN_WEIGHTS} as score "
                        "FROM chunks_fts "
                        "WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?",
                        (or_query, k * 3),
                    )
                    for row in cursor.fetchall():
                        if row[0] not in seen:
                            results.append((row[0], row[1]))
                            seen.add(row[0])
                            if len(results) >= k:
                                break

            return results
        except sqlite3.OperationalError as e:
            logger.warning("[BM25] Search query error: %s (query=%r)", e, query)
            return []
        finally:
            conn.close()

    async def search_two_pass(
        self, query: str, k: int = 10,
    ) -> list[tuple[str, float]]:
        """Two-pass search: title-only + body-only merged via RRF.

        Pass 1: Search title column only (exact section matches).
        Pass 2: Search body column only (content matches).
        Merge via Reciprocal Rank Fusion (k=60).

        Returns list of (chunk_id, normalized_score) where score is 0-1 (higher=better).
        """
        if not query or not query.strip():
            return []
        return await asyncio.to_thread(self._search_two_pass_sync, query, k)

    def _search_two_pass_sync(self, query: str, k: int) -> list[tuple[str, float]]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            fts_query = self._make_fts_query(query)
            if not fts_query:
                return []

            cursor = conn.cursor()
            rrf_k = 60  # RRF smoothing constant

            # Pass 1: Title-only search
            title_query = f"title : ({fts_query})"
            title_results = []
            try:
                cursor.execute(
                    "SELECT chunk_id, rank FROM chunks_fts "
                    "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
                    (title_query, k * 2),
                )
                title_results = cursor.fetchall()
            except sqlite3.OperationalError:
                pass  # No title matches

            # Pass 2: Body-only search
            body_query = f"body : ({fts_query})"
            body_results = []
            try:
                cursor.execute(
                    "SELECT chunk_id, rank FROM chunks_fts "
                    "WHERE chunks_fts MATCH ? ORDER BY rank LIMIT ?",
                    (body_query, k * 2),
                )
                body_results = cursor.fetchall()
            except sqlite3.OperationalError:
                pass

            # Merge via RRF
            rrf_scores: dict[str, float] = {}
            for rank_pos, (cid, _) in enumerate(title_results):
                rrf_scores[cid] = rrf_scores.get(cid, 0) + 1.0 / (rrf_k + rank_pos + 1)
            for rank_pos, (cid, _) in enumerate(body_results):
                rrf_scores[cid] = rrf_scores.get(cid, 0) + 1.0 / (rrf_k + rank_pos + 1)

            if not rrf_scores:
                # Fallback to standard weighted search
                return self._search_sync(query, k)

            # Sort by RRF score (descending) and return top-k
            sorted_results = sorted(rrf_scores.items(), key=lambda x: -x[1])[:k]

            # Normalize to 0-1 range (higher = better)
            max_rrf = sorted_results[0][1] if sorted_results else 1.0
            return [(cid, score / max_rrf) for cid, score in sorted_results]

        except sqlite3.OperationalError as e:
            logger.warning("[BM25] Two-pass search error: %s (query=%r)", e, query)
            return self._search_sync(query, k)
        finally:
            conn.close()

    async def search_by_section(
        self, query: str, section_prefix: str, k: int = 10,
    ) -> list[tuple[str, float]]:
        """Search within a specific section by prefix match on title column (Phase 29).

        Combines section filter (title column) with content search (body column).
        Example: query="агрегаты", section_prefix="5.14" finds only within section 5.14.*.

        Returns list of (chunk_id, normalized_score) where score is 0-1 (higher=better).
        """
        if not query or not query.strip():
            return []
        return await asyncio.to_thread(
            self._search_by_section_sync, query, section_prefix, k,
        )

    def _search_by_section_sync(
        self, query: str, section_prefix: str, k: int,
    ) -> list[tuple[str, float]]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            body_query = self._make_fts_query(query)
            if not body_query:
                return []

            cursor = conn.cursor()

            # FTS5 column filter: title contains section prefix AND body matches query
            # Use body column for content search, filter by section prefix in title
            fts_match = f'title : "{section_prefix}" AND body : ({body_query})'
            try:
                cursor.execute(
                    f"SELECT chunk_id, {self._COLUMN_WEIGHTS} as score "
                    "FROM chunks_fts "
                    "WHERE chunks_fts MATCH ? ORDER BY score LIMIT ?",
                    (fts_match, k),
                )
                results = [(row[0], row[1]) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                # Fallback: standard search + post-filter
                results = self._search_sync(query, k * 3)

            if not results:
                return []

            # Normalize scores (BM25 scores are negative, lower = better)
            min_score = results[0][1]  # best score (most negative)
            if min_score == 0:
                return [(cid, 1.0) for cid, _ in results[:k]]
            return [
                (cid, abs(min_score / score) if score != 0 else 0)
                for cid, score in results[:k]
            ]

        except sqlite3.OperationalError as e:
            logger.warning("[BM25] Section search error: %s (query=%r, section=%r)", e, query, section_prefix)
            return []
        finally:
            conn.close()

    @staticmethod
    def _tokenize_query(query: str) -> list[str]:
        """Extract meaningful tokens from a query, filtering stop-words."""
        cleaned = query.replace('"', "").replace("'", "")
        tokens = []
        for token in cleaned.split():
            t = "".join(c for c in token if c.isalnum() or c == "_")
            if t and t.lower() not in RUSSIAN_STOP_WORDS and len(t) > 1:
                tokens.append(t)
        return tokens

    @staticmethod
    def _stem_token(token: str) -> str:
        """Crude Russian stemming fallback (used when pymorphy3 is not available)."""
        t = token.lower()
        if len(t) > 4 and any("\u0400" <= c <= "\u04ff" for c in t):
            if t.endswith(("ов", "ев", "ей", "ий", "ый", "ой", "ая", "яя",
                           "ое", "ее", "ых", "их", "ам", "ям", "ом", "ем",
                           "ах", "ях", "ую", "юю")):
                return t[:-2]
            if t.endswith(("а", "я", "о", "е", "и", "ы", "у", "ю", "ь")):
                return t[:-1]
        return t

    @staticmethod
    def _make_fts_query(query: str) -> str:
        """Convert user query to FTS5 MATCH expression (AND).

        Uses pymorphy3 lemmatization if available, falls back to prefix stemming.
        """
        tokens = BM25Store._tokenize_query(query)
        if not tokens:
            return ""

        morph = _get_morph()
        if morph is not None:
            # Lemmatize tokens — exact match against lemmatized index
            return " ".join(f'"{lemmatize_word(t)}"' for t in tokens)

        # Fallback: crude prefix stemming
        parts = []
        for t in tokens:
            stem = BM25Store._stem_token(t)
            if stem != t.lower():
                parts.append(f'"{stem}"*')
            else:
                parts.append(f'"{t}"')
        return " ".join(parts)

    @staticmethod
    def _make_fts_query_or(query: str) -> str:
        """Convert user query to FTS5 MATCH expression (OR).

        Uses pymorphy3 lemmatization if available, falls back to prefix stemming.
        """
        tokens = BM25Store._tokenize_query(query)
        if not tokens:
            return ""

        morph = _get_morph()
        if morph is not None:
            return " OR ".join(f'"{lemmatize_word(t)}"' for t in tokens)

        parts = []
        for t in tokens:
            stem = BM25Store._stem_token(t)
            if stem != t.lower():
                parts.append(f'"{stem}"*')
            else:
                parts.append(f'"{t}"')
        return " OR ".join(parts)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_by_source(self, source: str) -> int:
        """Delete all chunks with the given source path. Returns count deleted."""
        return await asyncio.to_thread(self._delete_by_source_sync, source)

    def _delete_by_source_sync(self, source: str) -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chunk_id FROM chunk_meta WHERE source = ?", (source,)
            )
            ids = [row[0] for row in cursor.fetchall()]
            if not ids:
                return 0
            for cid in ids:
                cursor.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (cid,))
            placeholders = ",".join("?" * len(ids))
            cursor.execute(
                f"DELETE FROM chunk_meta WHERE chunk_id IN ({placeholders})", ids
            )
            conn.commit()
            logger.info("[BM25] Deleted %d chunks for source %s", len(ids), Path(source).name)
            return len(ids)
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("[BM25] Error deleting by source: %s", e)
            return 0
        finally:
            conn.close()

    async def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document_id. Returns count deleted."""
        return await asyncio.to_thread(self._delete_by_document_sync, document_id)

    def _delete_by_document_sync(self, document_id: str) -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT chunk_id FROM chunk_meta WHERE document_id = ?", (document_id,)
            )
            ids = [row[0] for row in cursor.fetchall()]
            if not ids:
                return 0
            for cid in ids:
                cursor.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (cid,))
            placeholders = ",".join("?" * len(ids))
            cursor.execute(
                f"DELETE FROM chunk_meta WHERE chunk_id IN ({placeholders})", ids
            )
            conn.commit()
            logger.info("[BM25] Deleted %d chunks for document %s", len(ids), document_id)
            return len(ids)
        except sqlite3.Error as e:
            conn.rollback()
            logger.error("[BM25] Error deleting by document: %s", e)
            return 0
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def clear(self) -> None:
        """Delete all data from the BM25 index."""
        await asyncio.to_thread(self._clear_sync)
        logger.info("[BM25] Cleared all data")

    def _clear_sync(self) -> None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute("DELETE FROM chunks_fts")
            conn.execute("DELETE FROM chunk_meta")
            conn.commit()
        finally:
            conn.close()

    async def get_chunks_by_ids(
        self, chunk_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Get original content + metadata for chunk IDs from chunk_meta.

        Returns list of dicts with keys: chunk_id, document_id, source,
        original_content, section_title.
        """
        if not chunk_ids:
            return []
        return await asyncio.to_thread(self._get_chunks_by_ids_sync, chunk_ids)

    def _get_chunks_by_ids_sync(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(chunk_ids))
            cursor.execute(
                f"SELECT chunk_id, document_id, source, original_content, section_title "
                f"FROM chunk_meta WHERE chunk_id IN ({placeholders})",
                chunk_ids,
            )
            results = []
            for row in cursor.fetchall():
                results.append({
                    "chunk_id": row[0],
                    "document_id": row[1],
                    "source": row[2],
                    "original_content": row[3] or "",
                    "section_title": row[4] or "",
                })
            return results
        except sqlite3.OperationalError as e:
            logger.warning("[BM25] Error getting chunks by IDs: %s", e)
            return []
        finally:
            conn.close()

    async def count(self) -> int:
        """Return total number of indexed chunks."""
        return await asyncio.to_thread(self._count_sync)

    def _count_sync(self) -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM chunk_meta")
            return cursor.fetchone()[0]
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()
