"""Contextual Retrieval: LLM-generated context for document chunks.

Phase 3.1 / Phase 50: At index time, generates a short context summary for each chunk
that places it within the broader document. The contextual content is stored
in chunk metadata and used for embedding + BM25, improving retrieval accuracy.

Flow:
    chunk.content (original text, preserved for display)
    chunk.metadata["context"] (LLM-generated summary)
    chunk.metadata["contextual_content"] (context + content, used for embedding/BM25)
"""

import asyncio
import logging
import sqlite3
import time
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.pdf_framework.config import AgentSettings, ContextualRetrievalSettings
from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument

logger = logging.getLogger(__name__)

_CONTEXT_PROMPT = """Here is the document titled "{title}".

<document>
{doc_excerpt}
</document>

Here is a chunk from that document:

<chunk>
{chunk_text}
</chunk>

Give a short context (1-2 sentences) that situates this chunk within the document.
Focus on what topic/section this chunk belongs to and what it discusses.
Write in the same language as the chunk. Return ONLY the context, nothing else."""


class _ContextCache:
    """SQLite cache for generated context summaries.

    Keyed by chunk_id (deterministic from Phase 18).
    Avoids redundant LLM calls on re-indexing.
    """

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS context_cache (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                context_text TEXT NOT NULL,
                model TEXT NOT NULL,
                created_at REAL NOT NULL
            )"""
        )
        self._conn.commit()

    def get(self, chunk_id: str) -> str | None:
        """Return cached context or None."""
        row = self._conn.execute(
            "SELECT context_text FROM context_cache WHERE chunk_id = ?",
            (chunk_id,),
        ).fetchone()
        return row[0] if row else None

    def put(self, chunk_id: str, document_id: str, context: str, model: str) -> None:
        """Insert or replace cached context."""
        self._conn.execute(
            """INSERT OR REPLACE INTO context_cache
               (chunk_id, document_id, context_text, model, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (chunk_id, document_id, context, model, time.time()),
        )
        self._conn.commit()

    def invalidate_document(self, document_id: str) -> int:
        """Remove all cached contexts for a document. Returns count deleted."""
        cursor = self._conn.execute(
            "DELETE FROM context_cache WHERE document_id = ?",
            (document_id,),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()


class ContextGenerator:
    """Generate contextual summaries for document chunks via LLM.

    Features:
    - SQLite cache (skip LLM for previously generated contexts)
    - Batch concurrency (asyncio.Semaphore)
    - Short chunk skip (< min_chunk_tokens words)
    - Anthropic prompt caching for document excerpt
    - Ralph Wiggum self-correcting retry
    """

    def __init__(
        self,
        settings: AgentSettings | None = None,
        context_settings: ContextualRetrievalSettings | None = None,
        api_key: str = "",
    ):
        self._settings = settings or AgentSettings()
        self._ctx = context_settings or ContextualRetrievalSettings()

        # Use context-specific model (fast/cheap) if set, else fall back to agent model
        model = self._ctx.model or self._settings.model

        llm_kwargs: dict = {
            "model": model,
            "temperature": 0.0,
            "max_tokens": self._ctx.max_context_tokens,
            "api_key": api_key or None,
        }
        if self._settings.base_url:
            llm_kwargs["base_url"] = self._settings.base_url
        self._llm = ChatAnthropic(**llm_kwargs)
        self._model_name = model

        # Concurrency limiter
        self._semaphore = asyncio.Semaphore(self._ctx.batch_concurrency)

        # SQLite cache
        self._cache: _ContextCache | None = None
        if self._ctx.cache_enabled:
            self._cache = _ContextCache(self._ctx.cache_db_path)

    def _build_messages(
        self,
        chunk: DocumentChunk,
        title: str,
        doc_excerpt: str,
        use_prompt_caching: bool = False,
    ) -> list:
        """Build LLM messages with optional Anthropic prompt caching."""
        # System message with prompt caching for document excerpt
        if use_prompt_caching and len(doc_excerpt) > 1024:
            system = SystemMessage(
                content=[
                    {
                        "type": "text",
                        "text": (
                            "You generate brief context summaries for document chunks. "
                            f"The document is titled \"{title}\".\n\n"
                            f"<document>\n{doc_excerpt}\n</document>"
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            )
            human_content = _CONTEXT_PROMPT.format(
                title=title,
                doc_excerpt="(see system message)",
                chunk_text=chunk.content[:1000],
            )
        else:
            system = SystemMessage(
                content="You generate brief context summaries for document chunks."
            )
            human_content = _CONTEXT_PROMPT.format(
                title=title,
                doc_excerpt=doc_excerpt,
                chunk_text=chunk.content[:1000],
            )

        return [system, HumanMessage(content=human_content)]

    async def generate_context(
        self,
        chunk: DocumentChunk,
        document: ProcessedDocument,
        use_prompt_caching: bool = False,
    ) -> str:
        """Generate a context summary for a single chunk."""
        doc_excerpt = document.raw_text[:2000] if document.raw_text else ""
        title = document.metadata.title or document.source_path

        messages = self._build_messages(chunk, title, doc_excerpt, use_prompt_caching)

        # Ralph Wiggum: self-correcting retry for context generation
        max_rw_retries = 2
        rw_feedback = ""

        for rw_attempt in range(1, max_rw_retries + 1):
            try:
                attempt_messages = list(messages)
                if rw_feedback:
                    attempt_messages.append(
                        HumanMessage(content=f"\u26a0\ufe0f CORRECTION: {rw_feedback}")
                    )

                async with self._semaphore:
                    response = await self._llm.ainvoke(attempt_messages)

                if isinstance(response.content, str):
                    context = response.content.strip()
                elif isinstance(response.content, list):
                    parts = []
                    for block in response.content:
                        if isinstance(block, dict):
                            parts.append(block.get("text", ""))
                        elif hasattr(block, "text"):
                            parts.append(getattr(block, "text"))
                        else:
                            parts.append(str(block))
                    context = "".join(parts).strip()
                else:
                    context = str(response.content).strip()

                # Validate: non-empty and reasonable length
                if len(context) < 15:
                    rw_feedback = (
                        "Context must be 1-2 sentences describing the chunk's topic. "
                        "Write in the same language as the chunk."
                    )
                    logger.warning(
                        "Context too short for chunk %s (attempt %d): %d chars",
                        chunk.id, rw_attempt, len(context),
                    )
                    continue

                # Validate: not a refusal
                refusal_patterns = ["i cannot", "i can't", "i'm unable", "не могу"]
                if any(p in context.lower() for p in refusal_patterns):
                    rw_feedback = (
                        "Do not refuse. Summarize the chunk topic in 1-2 sentences. "
                        "The chunk is real document text."
                    )
                    logger.warning("Context refusal for chunk %s (attempt %d)", chunk.id, rw_attempt)
                    continue

                return context

            except Exception as e:
                logger.warning("Context generation attempt %d failed for chunk %s: %s", rw_attempt, chunk.id, e)
                rw_feedback = f"Previous call failed: {e}. Try again."

        return ""

    async def _process_chunk(
        self,
        chunk: DocumentChunk,
        document: ProcessedDocument,
        use_prompt_caching: bool = False,
    ) -> None:
        """Process a single chunk: cache check → generate → store."""
        # Skip short chunks
        word_count = len(chunk.content.split())
        if word_count < self._ctx.min_chunk_tokens:
            chunk.metadata["context"] = ""
            chunk.metadata["contextual_content"] = chunk.content
            return

        # Check cache
        if self._cache is not None:
            cached = self._cache.get(chunk.id)
            if cached is not None:
                chunk.metadata["context"] = cached
                chunk.metadata["contextual_content"] = f"{cached}\n\n{chunk.content}" if cached else chunk.content
                return

        # Generate via LLM
        context = await self.generate_context(chunk, document, use_prompt_caching)
        chunk.metadata["context"] = context
        if context:
            chunk.metadata["contextual_content"] = f"{context}\n\n{chunk.content}"
        else:
            chunk.metadata["contextual_content"] = chunk.content

        # Store in cache
        if self._cache is not None and context:
            self._cache.put(chunk.id, chunk.document_id, context, self._model_name)

    async def enrich_chunks(
        self,
        chunks: list[DocumentChunk],
        document: ProcessedDocument,
    ) -> list[DocumentChunk]:
        """Add contextual content to all chunks (concurrent, cached).

        Sets:
            chunk.metadata["context"] — the LLM-generated context
            chunk.metadata["contextual_content"] — context + original content (for embedding/BM25)
        """
        t0 = time.time()
        total = len(chunks)

        # Enable prompt caching when processing many chunks from same document
        use_prompt_caching = total > 5

        # Process all chunks concurrently (bounded by semaphore)
        tasks = [
            self._process_chunk(chunk, document, use_prompt_caching)
            for chunk in chunks
        ]
        await asyncio.gather(*tasks)

        # Stats
        generated = sum(1 for c in chunks if c.metadata.get("context"))
        cached = sum(1 for c in chunks if c.metadata.get("context") and self._cache and self._cache.get(c.id))
        skipped = sum(1 for c in chunks if len(c.content.split()) < self._ctx.min_chunk_tokens)
        elapsed = time.time() - t0

        logger.info(
            "[CONTEXTUAL] Enriched %d/%d chunks in %.1fs "
            "(generated=%d, skipped_short=%d, model=%s, concurrency=%d)",
            generated, total, elapsed, generated - cached, skipped,
            self._model_name, self._ctx.batch_concurrency,
        )

        return chunks
