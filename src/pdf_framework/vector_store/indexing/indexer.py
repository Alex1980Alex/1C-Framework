"""Document indexer: orchestrates embedding computation and vector storage.

Supports batched indexing with checkpointing for resume after interruption.
Provides progress callback for streaming endpoints.
"""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine
from src.pdf_framework.schemas.documents import DocumentChunk
from src.pdf_framework.schemas.responses import IndexResult
from src.pdf_framework.vector_store.base import BaseVectorStore

if TYPE_CHECKING:
    from src.pdf_framework.processing.versioning import DocumentVersionManager
    from src.pdf_framework.search.bm25_store import BM25Store

logger = logging.getLogger(__name__)

_INDEXING_BATCH_SIZE = 256

# Type alias for progress callback:
# async fn(batch_idx, total_batches, chunks_in_batch, elapsed_sec)
ProgressCallback = Callable[[int, int, int, float], Coroutine[Any, Any, None]]


class DocumentIndexer:
    """Orchestrate: compute embeddings → store in vector DB (+ BM25 index).

    Supports batched processing with checkpoint saves between batches
    for resume after interruption.
    """

    def __init__(
        self,
        embedding_engine: BaseEmbeddingEngine,
        vector_store: BaseVectorStore,
        bm25_store: BM25Store | None = None,
    ):
        self._embedding_engine = embedding_engine
        self._vector_store = vector_store
        self._bm25_store = bm25_store

    async def index_chunks(
        self,
        chunks: list[DocumentChunk],
        document_id: str = "",
        source_path: str = "",
        version_manager: DocumentVersionManager | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> IndexResult:
        """Embed and store document chunks in batches with checkpointing.

        Args:
            chunks: List of document chunks to index.
            document_id: Document identifier.
            source_path: Path to the source file (used for checkpointing).
            version_manager: Optional version manager for checkpoint saves.
            on_progress: Optional async callback(batch_idx, total_batches, batch_chunks, elapsed)
                         for streaming progress updates.

        Returns:
            IndexResult with counts of stored chunks and computed embeddings.
        """
        if not chunks:
            logger.info("[INDEXER] Нет чанков для индексации (document_id=%s)", document_id)
            return IndexResult(
                document_id=document_id,
                source_path=source_path,
                chunks_stored=0,
                embeddings_computed=0,
            )

        total_batches = math.ceil(len(chunks) / _INDEXING_BATCH_SIZE)
        start_batch = 0
        total_chars = sum(len(c.content) for c in chunks)

        logger.info(
            "[INDEXER] Начало индексации: %d чанков (%d символов), %d батчей по %d, "
            "document_id=%s, source='%s'",
            len(chunks), total_chars, total_batches, _INDEXING_BATCH_SIZE,
            document_id, source_path,
        )

        # Check for existing checkpoint to resume from
        if version_manager and source_path:
            checkpoint = await version_manager.start_indexing(
                file_path=source_path,
                document_id=document_id,
                total_batches=total_batches,
                total_chunks=len(chunks),
            )
            if checkpoint is not None and checkpoint.last_completed_batch >= 0:
                start_batch = checkpoint.last_completed_batch + 1
                logger.info(
                    "[INDEXER] Возобновление с батча %d/%d (пропуск %d уже обработанных чанков)",
                    start_batch + 1, total_batches,
                    start_batch * _INDEXING_BATCH_SIZE,
                )

        total_stored = 0
        total_embedded = 0
        indexing_start = time.time()

        try:
            for batch_idx in range(start_batch, total_batches):
                batch_start_time = time.time()
                batch_start = batch_idx * _INDEXING_BATCH_SIZE
                batch_end = min(batch_start + _INDEXING_BATCH_SIZE, len(chunks))
                batch_chunks = chunks[batch_start:batch_end]
                batch_chars = sum(len(c.content) for c in batch_chunks)

                # 1. Compute embeddings for this batch
                t_embed = time.time()
                texts = [
                    c.metadata.get("contextual_content", c.content)
                    for c in batch_chunks
                ]
                embeddings = await self._embedding_engine.embed_batch(texts)
                embed_elapsed = time.time() - t_embed

                # 2. Store in vector DB (upsert — idempotent with deterministic IDs)
                t_store = time.time()
                stored_ids = await self._vector_store.add_documents(batch_chunks, embeddings)
                store_elapsed = time.time() - t_store

                # 3. Store in BM25 index
                bm25_elapsed = 0.0
                if self._bm25_store is not None:
                    try:
                        t_bm25 = time.time()
                        sections = [
                            c.metadata.get("breadcrumb", "")
                            or c.section
                            or c.metadata.get("section_title", "")
                            for c in batch_chunks
                        ]
                        await self._bm25_store.add_chunks(
                            chunk_ids=[c.id for c in batch_chunks],
                            contents=[c.content for c in batch_chunks],
                            document_ids=[c.document_id for c in batch_chunks],
                            sources=[c.metadata.get("source", source_path) for c in batch_chunks],
                            sections=sections,
                        )
                        bm25_elapsed = time.time() - t_bm25
                    except Exception as e:
                        logger.warning(
                            "[INDEXER] BM25 батч %d/%d ошибка (vector OK): %s",
                            batch_idx + 1, total_batches, e,
                        )

                # 4. Save checkpoint after batch completes
                if version_manager and source_path:
                    await version_manager.save_checkpoint(
                        file_path=source_path,
                        batch_index=batch_idx,
                        batch_chunks=batch_chunks,
                    )

                total_stored += len(stored_ids)
                total_embedded += len(embeddings)

                batch_elapsed = time.time() - batch_start_time
                overall_elapsed = time.time() - indexing_start
                remaining_batches = total_batches - batch_idx - 1
                eta = (overall_elapsed / (batch_idx - start_batch + 1)) * remaining_batches if batch_idx > start_batch else 0

                logger.info(
                    "[INDEXER] Батч %d/%d: %d чанков (%d симв) за %.2f сек "
                    "(embed=%.2f, store=%.2f, bm25=%.2f) | "
                    "Прогресс: %d/%d чанков (%.0f%%) | ETA: %.0f сек",
                    batch_idx + 1, total_batches, len(stored_ids), batch_chars,
                    batch_elapsed, embed_elapsed, store_elapsed, bm25_elapsed,
                    total_stored, len(chunks),
                    total_stored / len(chunks) * 100,
                    eta,
                )

                # 5. Notify progress callback (for streaming)
                if on_progress is not None:
                    await on_progress(batch_idx, total_batches, len(stored_ids), batch_elapsed)

            # 6. Mark indexing as completed
            if version_manager and source_path:
                await version_manager.complete_indexing(
                    file_path=source_path,
                    document_id=document_id,
                    total_chunks=len(chunks),
                )

            total_elapsed = time.time() - indexing_start
            logger.info(
                "[INDEXER] Индексация завершена: %d чанков, %d эмбеддингов за %.2f сек "
                "(%.0f чанков/сек) | document_id=%s",
                total_stored, total_embedded, total_elapsed,
                total_stored / total_elapsed if total_elapsed > 0 else 0,
                document_id,
            )

        except Exception as e:
            total_elapsed = time.time() - indexing_start
            failed_batch = total_stored // _INDEXING_BATCH_SIZE + 1
            logger.error(
                "[INDEXER] Индексация прервана на батче %d/%d после %.2f сек "
                "(%d чанков сохранено): %s",
                failed_batch, total_batches, total_elapsed, total_stored, e,
            )
            # Mark indexing as failed so it can be resumed later
            if version_manager and source_path:
                await version_manager.fail_indexing(source_path)
            raise

        return IndexResult(
            document_id=document_id or chunks[0].document_id,
            source_path=source_path,
            chunks_stored=total_stored,
            embeddings_computed=total_embedded,
        )
