"""Section Summary Service (Phase 30).

Generates and caches LLM summaries for document sections.
Each section of the ToC gets a 2-3 sentence summary describing its content.
Summaries are stored in SQLite for fast retrieval.

Author: Claude Code
Version: 0.21.0 - Phase 30: Hierarchical RAG
"""

import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.shared.llm_rotation.adapter import cheap_llm_call, is_cheap_llm_enabled

logger = logging.getLogger(__name__)


class SectionSummaryService:
    """Generate and cache LLM summaries for document sections.

    Uses Claude Sonnet via Z.AI for fast summary generation.
    Summaries are persisted in SQLite for cross-session reuse.
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        db_path: str | Path = "data/section_summaries.db",
    ) -> None:
        self._model = model
        self._db_path = Path(db_path)
        self._initialized = False

        if api_key:
            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = Anthropic(**kwargs)
        else:
            self._client = None

    async def initialize(self) -> None:
        """Create SQLite tables if they don't exist."""
        if self._initialized:
            return
        await asyncio.to_thread(self._create_tables)
        self._initialized = True
        count = await self.count()
        logger.info("[SUMMARY] Section summary service initialized: %d summaries cached", count)

    def _create_tables(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS section_summaries (
                    document_id TEXT NOT NULL,
                    section_number TEXT NOT NULL,
                    section_title TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (document_id, section_number)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_summaries_doc "
                "ON section_summaries(document_id)"
            )
            conn.commit()
        finally:
            conn.close()

    async def generate_for_document(
        self,
        document_id: str,
        chunks: list[dict[str, Any]],
        sections: list[dict[str, Any]],
    ) -> int:
        """Generate summaries for sections that have chunks.

        Args:
            document_id: Document identifier
            chunks: List of chunk dicts with at least 'content' and 'metadata' keys
            sections: List of section dicts with 'number', 'title' keys

        Returns:
            Number of summaries generated
        """
        if not self._client:
            logger.warning("[SUMMARY] No API client — cannot generate summaries")
            return 0

        generated = 0
        for section in sections:
            section_number = section.get("number", "")
            section_title = section.get("title", "")
            if not section_number:
                continue

            # Check if already cached
            existing = await self.get_summary(document_id, section_number)
            if existing:
                continue

            # Find chunks belonging to this section
            section_chunks = [
                c for c in chunks
                if (c.get("metadata", {}).get("section_number", "") or "").startswith(section_number)
            ]
            if not section_chunks:
                continue

            # Generate summary
            full_title = f"{section_number}. {section_title}" if section_title else section_number
            summary = await self._summarize(full_title, section_chunks)
            if summary:
                await self._store(
                    document_id, section_number, section_title,
                    summary, len(section_chunks),
                )
                generated += 1

        logger.info(
            "[SUMMARY] Generated %d summaries for document %s",
            generated, document_id,
        )
        return generated

    async def get_summary(self, document_id: str, section_number: str) -> str | None:
        """Get cached summary for a specific section."""
        return await asyncio.to_thread(
            self._get_summary_sync, document_id, section_number,
        )

    def _get_summary_sync(self, document_id: str, section_number: str) -> str | None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                "SELECT summary FROM section_summaries "
                "WHERE document_id = ? AND section_number = ?",
                (document_id, section_number),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    async def get_all(self, document_id: str) -> list[dict[str, Any]]:
        """Get all summaries for a document."""
        return await asyncio.to_thread(self._get_all_sync, document_id)

    def _get_all_sync(self, document_id: str) -> list[dict[str, Any]]:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                "SELECT section_number, section_title, summary, chunk_count, created_at "
                "FROM section_summaries WHERE document_id = ? "
                "ORDER BY section_number",
                (document_id,),
            )
            return [
                {
                    "section_number": row[0],
                    "section_title": row[1],
                    "summary": row[2],
                    "chunk_count": row[3],
                    "created_at": row[4],
                }
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()

    async def count(self) -> int:
        """Return total number of cached summaries."""
        return await asyncio.to_thread(self._count_sync)

    def _count_sync(self) -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute("SELECT COUNT(*) FROM section_summaries")
            return cursor.fetchone()[0]
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    async def delete_by_document(self, document_id: str) -> int:
        """Delete all summaries for a document."""
        return await asyncio.to_thread(self._delete_by_document_sync, document_id)

    def _delete_by_document_sync(self, document_id: str) -> int:
        conn = sqlite3.connect(str(self._db_path))
        try:
            cursor = conn.execute(
                "DELETE FROM section_summaries WHERE document_id = ?",
                (document_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    async def _store(
        self,
        document_id: str,
        section_number: str,
        section_title: str,
        summary: str,
        chunk_count: int,
    ) -> None:
        await asyncio.to_thread(
            self._store_sync,
            document_id, section_number, section_title, summary, chunk_count,
        )

    def _store_sync(
        self,
        document_id: str,
        section_number: str,
        section_title: str,
        summary: str,
        chunk_count: int,
    ) -> None:
        conn = sqlite3.connect(str(self._db_path))
        try:
            conn.execute(
                "INSERT OR REPLACE INTO section_summaries "
                "(document_id, section_number, section_title, summary, chunk_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (document_id, section_number, section_title, summary, chunk_count,
                 datetime.utcnow().isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    async def _summarize(self, title: str, chunks: list[dict[str, Any]]) -> str:
        """Generate a 2-3 sentence summary of a section via LLM.

        Uses asyncio.to_thread to avoid blocking the event loop.
        """
        # Concatenate chunk content (up to 5000 chars)
        content_parts = []
        total_chars = 0
        for chunk in chunks:
            text = chunk.get("content", "")
            if total_chars + len(text) > 5000:
                remaining = 5000 - total_chars
                if remaining > 100:
                    content_parts.append(text[:remaining])
                break
            content_parts.append(text)
            total_chars += len(text)

        content = "\n\n".join(content_parts)

        try:
            result = await asyncio.to_thread(
                self._call_summary_api, title, content,
            )
            return result
        except Exception as e:
            logger.error("[SUMMARY] Error generating summary for '%s': %s", title, e)
            return ""

    def _call_summary_api(self, title: str, content: str) -> str:
        """Synchronous LLM call for section summary (runs in thread)."""
        response = self._client.messages.create(
            model=self._model,
            max_tokens=300,
            system=(
                "Ты — технический писатель. Твоя задача — написать краткое описание "
                "раздела документации (2-3 предложения). Отвечай ТОЛЬКО на русском языке. "
                "Не используй формулировки вроде 'В этом разделе...' — сразу описывай суть."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Раздел: {title}\n\n"
                    f"Содержание:\n{content}\n\n"
                    f"Напиши краткое описание этого раздела (2-3 предложения)."
                ),
            }],
        )
        block = response.content[0]
        return getattr(block, "text", str(block)).strip()
