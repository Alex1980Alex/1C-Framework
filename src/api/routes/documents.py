"""Document management endpoints."""

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.dependencies.components import Components, get_components

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

UPLOAD_DIR = Path("data/pdfs")


async def _remove_existing_document(components: "Components", source_path: str) -> int:
    """Remove existing chunks for a source_path to prevent duplicates on re-index.

    Returns the number of chunks deleted.
    Uses provider-agnostic BaseVectorStore methods (works with ChromaDB, Qdrant, etc.).
    """
    try:
        # Phase 17: Invalidate semantic cache before deleting
        semantic_cache = getattr(components, "semantic_cache", None)
        if semantic_cache is not None:
            try:
                existing_chunks = await components.vector_store.scroll(
                    filter={"source": source_path}, limit=10000,
                )
                doc_ids = {c.document_id for c in existing_chunks if c.document_id}
                for doc_id in doc_ids:
                    await semantic_cache.invalidate_by_document(doc_id)
            except Exception as e:
                logger.warning("Semantic cache invalidation failed: %s", e)

        # Delete from vector store using provider-agnostic filter
        deleted = await components.vector_store.delete_by_filter({"source": source_path})
        if deleted:
            logger.info("Dedup: removed %d old chunks for %s", deleted, Path(source_path).name)

        # Phase 16: Also remove from BM25 index
        bm25_store = getattr(components, "bm25_store", None)
        if bm25_store is not None:
            try:
                await bm25_store.delete_by_source(source_path)
            except Exception as e:
                logger.warning("BM25 dedup failed: %s", e)

        return deleted
    except Exception as e:
        logger.warning("Dedup check failed: %s", e)
        return 0


class IndexRequest(BaseModel):
    file_path: str
    loader: str = "default"  # "default" | "pymupdf" | "docling" | "pymupdf4llm" | "smart"
    build_graph: bool = False
    contextual: bool = False
    parent_child: bool = False
    raptor: bool = False
    summarize: bool = False
    extract_images: bool = True  # Phase 15: Extract and describe images via Claude Vision
    collection_id: str | None = None  # Phase 32: Assign to collection after indexing


class IndexResponse(BaseModel):
    document_id: str
    chunks_stored: int
    embeddings_computed: int
    graph_entities: int = 0
    graph_relations: int = 0
    image_chunks: int = 0


# Phase 32: Batch indexing models
class BatchIndexRequest(BaseModel):
    file_paths: list[str]
    loader: str = "default"
    build_graph: bool = False
    extract_images: bool = True
    collection_id: str | None = None  # Assign all to collection


class BatchFileResult(BaseModel):
    file_path: str
    document_id: str = ""
    chunks_stored: int = 0
    image_chunks: int = 0
    status: str = "pending"  # pending | indexing | done | error
    error: str = ""
    elapsed_seconds: float = 0.0


class DocumentInfo(BaseModel):
    document_id: str
    chunks_count: int


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF file to the server."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOAD_DIR / file.filename

    try:
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        return {"file_path": str(dest.resolve()), "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index", response_model=IndexResponse)
async def index_document(
    request: IndexRequest,
    components: Components = Depends(get_components),
):
    """Index a PDF document: load, split, embed, store. Optionally build graph.

    Loader options:
    - default: Use configured loader from settings
    - pymupdf: Fast PDF loader (no layout detection)
    - docling: IBM Docling with layout + OCR + tables (Phase 15.1)
    - pymupdf4llm: Fast PDF→Markdown (Phase 15.1)
    - smart: Auto-select best loader (Phase 15.1)
    """
    try:
        # Select loader based on request
        from src.pdf_framework.config import PDFSettings
        from src.pdf_framework.loaders import get_loader

        if request.loader != "default":
            # Validate loader choice
            valid_loaders = ["pymupdf", "pdfplumber", "unstructured", "docling", "pymupdf4llm", "smart"]
            if request.loader not in valid_loaders:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid loader: {request.loader}. Valid: {valid_loaders}"
                )
            # Create settings with selected loader using model_validate
            loader_settings = PDFSettings.model_validate({"loader": request.loader})
            loader = get_loader(loader_settings, components.settings.layout)
        else:
            loader = components.loader

        document = await loader.load(request.file_path)

        # Dedup: remove old chunks for this file before re-indexing
        await _remove_existing_document(components, document.source_path)

        chunks = components.pipeline.process(document)

        # Phase 15: Extract images and add as text chunks
        image_chunk_count = 0
        if request.extract_images and components.settings.pdf.extract_images:
            try:
                img_descriptions = await components.image_extractor.extract_all(request.file_path)
                if img_descriptions:
                    img_chunks = components.image_extractor.to_document_chunks(
                        img_descriptions,
                        document_id=document.id,
                        source_path=document.source_path,
                    )
                    # Phase 29: Inherit section metadata from nearest text chunk
                    from src.pdf_framework.processing.pipeline import ProcessingPipeline
                    ProcessingPipeline._inherit_image_sections(chunks, img_chunks)
                    chunks.extend(img_chunks)
                    image_chunk_count = len(img_chunks)
                    logger.info(f"[IMAGE] Added {image_chunk_count} image chunks for {Path(request.file_path).name}")
            except Exception as e:
                logger.warning(f"[IMAGE] Image extraction failed (text indexing continues): {e}")

        result = await components.indexer.index_chunks(
            chunks,
            document_id=document.id,
            source_path=document.source_path,
            version_manager=components.version_manager,
        )

        entities_added = 0
        relations_added = 0

        # Build knowledge graph if requested
        if request.build_graph:
            try:
                from src.pdf_framework.graph_store.construction.builder import GraphBuilder
                from src.pdf_framework.processing.extractors.entity_extractor import LLMEntityExtractor

                extractor = LLMEntityExtractor(
                    settings=components.settings.agent,
                    api_key=components.settings.anthropic_api_key,
                )
                builder = GraphBuilder(
                    extractor, components.graph_store,
                    concurrency=components.settings.agent.graph_concurrency,
                )
                graph_result = await builder.build_from_chunks(chunks)
                entities_added = graph_result.get("entities_added", 0)
                relations_added = graph_result.get("relations_added", 0)
            except Exception as e:
                logger.warning(f"Graph build failed (indexing succeeded): {e}")

        # Phase 32: Register document in registry
        doc_registry = getattr(components, "document_registry", None)
        if doc_registry is not None:
            try:
                await doc_registry.register(
                    document_id=result.document_id,
                    source_path=document.source_path,
                    chunk_count=result.chunks_stored,
                    page_count=getattr(document.metadata, "page_count", 0),
                )
            except Exception as e:
                logger.warning("[REGISTRY] Registration failed: %s", e)

        # Phase 32: Assign to collection if specified
        if request.collection_id:
            coll_store = getattr(components, "collection_store", None)
            if coll_store is not None:
                try:
                    await coll_store.add_document(request.collection_id, result.document_id)
                except Exception as e:
                    logger.warning("[COLLECTIONS] Assignment failed: %s", e)

        return IndexResponse(
            document_id=result.document_id,
            chunks_stored=result.chunks_stored,
            embeddings_computed=result.embeddings_computed,
            graph_entities=entities_added,
            graph_relations=relations_added,
            image_chunks=image_chunk_count,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
    except RuntimeError as e:
        # Concurrency guard: another indexing is in progress
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/stream")
async def index_document_stream(
    request: IndexRequest,
    components: Components = Depends(get_components),
):
    """Stream indexing progress as JSON lines (NDJSON)."""

    async def generate():
        def send(step: str, detail: str = "", **kwargs):
            data = {"step": step, "detail": detail, "ts": time.time(), **kwargs}
            return json.dumps(data, ensure_ascii=False) + "\n"

        try:
            # Step 1: Load PDF
            yield send("load", "Загрузка PDF...")
            t0 = time.time()

            from src.pdf_framework.config import PDFSettings
            from src.pdf_framework.loaders import get_loader

            if request.loader != "default":
                valid_loaders = ["pymupdf", "pdfplumber", "unstructured", "docling", "pymupdf4llm", "smart"]
                if request.loader not in valid_loaders:
                    yield send("error", f"Invalid loader: {request.loader}")
                    return
                loader_settings = PDFSettings.model_validate({"loader": request.loader})
                loader = get_loader(loader_settings, components.settings.layout)
            else:
                loader = components.loader

            document = await loader.load(request.file_path)
            yield send("load_done", f"PDF загружен за {time.time() - t0:.1f} сек",
                        pages=getattr(document, 'page_count', 0))

            # Step 1.5: Dedup — remove old chunks for this file
            removed = await _remove_existing_document(components, document.source_path)
            if removed:
                yield send("dedup", f"Удалено {removed} старых чанков (дедупликация)")

            # Step 2: Split into chunks
            yield send("split", "Разбиение на чанки...")
            t1 = time.time()
            chunks = components.pipeline.process(document)
            yield send("split_done", f"{len(chunks)} чанков за {time.time() - t1:.1f} сек",
                        chunk_count=len(chunks))

            # Step 2.5: Extract images (Phase 15)
            image_chunk_count = 0
            if request.extract_images and components.settings.pdf.extract_images:
                yield send("images", "Извлечение изображений из PDF (Claude Vision)...")
                t_img = time.time()
                try:
                    img_descriptions = await components.image_extractor.extract_all(request.file_path)
                    if img_descriptions:
                        img_chunks = components.image_extractor.to_document_chunks(
                            img_descriptions,
                            document_id=document.id,
                            source_path=document.source_path,
                        )
                        # Phase 29: Inherit section metadata from nearest text chunk
                        from src.pdf_framework.processing.pipeline import ProcessingPipeline
                        ProcessingPipeline._inherit_image_sections(chunks, img_chunks)
                        chunks.extend(img_chunks)
                        image_chunk_count = len(img_chunks)
                        yield send("images_done",
                                    f"{image_chunk_count} изображений описано за {time.time() - t_img:.1f} сек",
                                    image_chunks=image_chunk_count)
                    else:
                        yield send("images_done", "Изображений не найдено", image_chunks=0)
                except Exception as e:
                    yield send("images_error", f"Ошибка извлечения изображений: {e}")

            # Step 3: Embed + store (with checkpointing + real-time batch streaming)
            yield send("embed", f"Вычисление эмбеддингов для {len(chunks)} чанков...")
            t2 = time.time()

            # Real-time batch progress via asyncio.Queue
            batch_queue: asyncio.Queue[str | None] = asyncio.Queue()
            _indexing_exc: list[Exception] = []

            async def _on_batch(batch_idx: int, total: int, stored: int, elapsed: float):
                pct = (batch_idx + 1) / total * 100 if total > 0 else 100
                await batch_queue.put(send(
                    "batch", f"Батч {batch_idx + 1}/{total}: {stored} чанков за {elapsed:.1f} сек",
                    batch=batch_idx + 1, total_batches=total,
                    chunks_in_batch=stored, batch_seconds=round(elapsed, 2),
                    progress_percent=round(pct, 1),
                ))

            async def _run_indexing():
                try:
                    return await components.indexer.index_chunks(
                        chunks,
                        document_id=document.id,
                        source_path=document.source_path,
                        version_manager=components.version_manager,
                        on_progress=_on_batch,
                    )
                except Exception as exc:
                    _indexing_exc.append(exc)
                    return None
                finally:
                    await batch_queue.put(None)  # sentinel

            task = asyncio.create_task(_run_indexing())

            # Yield batch events in real-time as they arrive
            while True:
                event = await batch_queue.get()
                if event is None:
                    break
                yield event

            if _indexing_exc:
                raise _indexing_exc[0]
            result = task.result()

            yield send("embed_done",
                        f"{result.embeddings_computed} эмбеддингов за {time.time() - t2:.1f} сек",
                        chunks_stored=result.chunks_stored,
                        embeddings_computed=result.embeddings_computed)

            entities_added = 0
            relations_added = 0

            # Step 4: Graph (optional)
            if request.build_graph:
                yield send("graph", "Построение графа знаний (LLM извлекает сущности)...")
                t3 = time.time()
                try:
                    from src.pdf_framework.graph_store.construction.builder import GraphBuilder
                    from src.pdf_framework.processing.extractors.entity_extractor import LLMEntityExtractor

                    extractor = LLMEntityExtractor(
                        settings=components.settings.agent,
                        api_key=components.settings.anthropic_api_key,
                    )
                    builder = GraphBuilder(
                        extractor, components.graph_store,
                        concurrency=components.settings.agent.graph_concurrency,
                    )
                    graph_result = await builder.build_from_chunks(chunks)
                    entities_added = graph_result.get("entities_added", 0)
                    relations_added = graph_result.get("relations_added", 0)
                    yield send("graph_done",
                                f"{entities_added} сущностей, {relations_added} связей "
                                f"за {time.time() - t3:.1f} сек",
                                entities=entities_added, relations=relations_added)
                except Exception as e:
                    yield send("graph_error", f"Ошибка графа: {e}")

            # Phase 32: Register document in registry
            doc_registry = getattr(components, "document_registry", None)
            if doc_registry is not None:
                try:
                    await doc_registry.register(
                        document_id=result.document_id,
                        source_path=document.source_path,
                        chunk_count=result.chunks_stored,
                        page_count=getattr(document.metadata, "page_count", 0),
                    )
                except Exception as e:
                    logger.warning("[REGISTRY] Registration failed: %s", e)

            # Phase 32: Assign to collection if specified
            if request.collection_id:
                coll_store = getattr(components, "collection_store", None)
                if coll_store is not None:
                    try:
                        await coll_store.add_document(request.collection_id, result.document_id)
                    except Exception as e:
                        logger.warning("[COLLECTIONS] Assignment failed: %s", e)

            # Done
            yield send("done", "Индексация завершена",
                        document_id=result.document_id,
                        chunks_stored=result.chunks_stored,
                        embeddings_computed=result.embeddings_computed,
                        graph_entities=entities_added,
                        graph_relations=relations_added,
                        image_chunks=image_chunk_count)

        except Exception as e:
            yield send("error", str(e))

    return StreamingResponse(generate(), media_type="application/x-ndjson")


# ========== Phase 32: Batch Indexing ==========


@router.post("/index/batch/stream")
async def index_batch_stream(
    request: BatchIndexRequest,
    components: Components = Depends(get_components),
):
    """Index multiple PDF files sequentially with per-file NDJSON progress.

    Processes files one at a time with error isolation — a failure in one file
    does not affect others. Optionally assigns all documents to a collection.

    Phase 32: Multi-Document KB batch indexing.
    """

    async def generate():
        def send(step: str, detail: str = "", **kwargs):
            data = {"step": step, "detail": detail, "ts": time.time(), **kwargs}
            return json.dumps(data, ensure_ascii=False) + "\n"

        file_results: list[dict] = []
        total_files = len(request.file_paths)

        yield send("batch_start", f"Batch indexing: {total_files} files",
                    total_files=total_files)

        for file_idx, file_path in enumerate(request.file_paths):
            fname = Path(file_path).name
            yield send("file_start", f"[{file_idx + 1}/{total_files}] {fname}",
                        file_index=file_idx, filename=fname)

            file_result = {
                "file_path": file_path,
                "filename": fname,
                "document_id": "",
                "chunks_stored": 0,
                "image_chunks": 0,
                "status": "indexing",
                "error": "",
            }

            t_file = time.time()
            try:
                # Load PDF
                from src.pdf_framework.config import PDFSettings
                from src.pdf_framework.loaders import get_loader

                if request.loader != "default":
                    loader_settings = PDFSettings.model_validate({"loader": request.loader})
                    loader = get_loader(loader_settings, components.settings.layout)
                else:
                    loader = components.loader

                document = await loader.load(file_path)
                file_result["document_id"] = document.id

                # Register in document registry
                doc_registry = getattr(components, "document_registry", None)
                if doc_registry is not None:
                    await doc_registry.register(
                        document_id=document.id,
                        source_path=document.source_path,
                        page_count=getattr(document.metadata, "page_count", 0),
                        status="indexing",
                    )

                # Dedup
                removed = await _remove_existing_document(components, document.source_path)
                if removed:
                    yield send("file_dedup", f"Removed {removed} old chunks",
                                file_index=file_idx, removed=removed)

                # Split
                chunks = components.pipeline.process(document)

                # Extract images
                image_chunk_count = 0
                if request.extract_images and components.settings.pdf.extract_images:
                    try:
                        img_descriptions = await components.image_extractor.extract_all(file_path)
                        if img_descriptions:
                            img_chunks = components.image_extractor.to_document_chunks(
                                img_descriptions,
                                document_id=document.id,
                                source_path=document.source_path,
                            )
                            from src.pdf_framework.processing.pipeline import ProcessingPipeline
                            ProcessingPipeline._inherit_image_sections(chunks, img_chunks)
                            chunks.extend(img_chunks)
                            image_chunk_count = len(img_chunks)
                    except Exception as e:
                        yield send("file_warn", f"Image extraction failed: {e}",
                                    file_index=file_idx)

                # Embed + store
                result = await components.indexer.index_chunks(
                    chunks,
                    document_id=document.id,
                    source_path=document.source_path,
                    version_manager=components.version_manager,
                )

                file_result["chunks_stored"] = result.chunks_stored
                file_result["image_chunks"] = image_chunk_count
                file_result["status"] = "done"

                # Update registry
                if doc_registry is not None:
                    await doc_registry.register(
                        document_id=document.id,
                        source_path=document.source_path,
                        chunk_count=result.chunks_stored,
                        page_count=getattr(document.metadata, "page_count", 0),
                        status="indexed",
                    )

                # Assign to collection
                if request.collection_id:
                    coll_store = getattr(components, "collection_store", None)
                    if coll_store is not None:
                        await coll_store.add_document(request.collection_id, document.id)

                # Build graph
                if request.build_graph:
                    try:
                        from src.pdf_framework.graph_store.construction.builder import GraphBuilder
                        from src.pdf_framework.processing.extractors.entity_extractor import LLMEntityExtractor

                        extractor = LLMEntityExtractor(
                            settings=components.settings.agent,
                            api_key=components.settings.anthropic_api_key,
                        )
                        builder = GraphBuilder(
                            extractor, components.graph_store,
                            concurrency=components.settings.agent.graph_concurrency,
                        )
                        await builder.build_from_chunks(chunks)
                    except Exception as e:
                        yield send("file_warn", f"Graph build failed: {e}",
                                    file_index=file_idx)

                elapsed = time.time() - t_file
                file_result["elapsed_seconds"] = round(elapsed, 1)
                yield send("file_done",
                            f"[{file_idx + 1}/{total_files}] {fname}: "
                            f"{result.chunks_stored} chunks in {elapsed:.1f}s",
                            file_index=file_idx, **file_result)

            except Exception as e:
                elapsed = time.time() - t_file
                file_result["status"] = "error"
                file_result["error"] = str(e)
                file_result["elapsed_seconds"] = round(elapsed, 1)

                # Update registry on failure
                doc_registry = getattr(components, "document_registry", None)
                if doc_registry is not None and file_result["document_id"]:
                    await doc_registry.update_status(file_result["document_id"], "failed")

                yield send("file_error",
                            f"[{file_idx + 1}/{total_files}] {fname}: {e}",
                            file_index=file_idx, error=str(e))

            file_results.append(file_result)

        # Summary
        done = sum(1 for r in file_results if r["status"] == "done")
        failed = sum(1 for r in file_results if r["status"] == "error")
        total_chunks = sum(r["chunks_stored"] for r in file_results)

        yield send("batch_done",
                    f"Batch complete: {done}/{total_files} files, "
                    f"{total_chunks} chunks, {failed} errors",
                    files_done=done, files_failed=failed,
                    total_chunks=total_chunks, results=file_results)

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("/files")
async def list_pdf_files():
    """List all PDF files in the upload directory (on disk, not in vector store)."""
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(
            [
                {"filename": f.name, "file_path": str(f.resolve()), "size_mb": round(f.stat().st_size / 1048576, 2)}
                for f in UPLOAD_DIR.iterdir()
                if f.is_file() and f.suffix.lower() == ".pdf"
            ],
            key=lambda x: x["filename"],
        )
        return {"files": files, "total": len(files), "directory": str(UPLOAD_DIR.resolve())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/registry")
async def list_document_registry(
    status: str | None = None,
    components: Components = Depends(get_components),
):
    """List documents from the registry with rich metadata (Phase 32).

    Returns title, description, tags, chunk_count, page_count, file_size, status.
    Optionally filter by status: indexed | indexing | failed.
    """
    doc_registry = getattr(components, "document_registry", None)
    if doc_registry is None:
        raise HTTPException(status_code=501, detail="Document registry not available")

    documents = await doc_registry.list_all(status=status)
    return {
        "documents": [d.model_dump() for d in documents],
        "total": len(documents),
    }


@router.patch("/registry/{document_id}")
async def update_document_metadata(
    document_id: str,
    title: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    components: Components = Depends(get_components),
):
    """Update document metadata (title, description, tags) in the registry."""
    doc_registry = getattr(components, "document_registry", None)
    if doc_registry is None:
        raise HTTPException(status_code=501, detail="Document registry not available")

    updated = await doc_registry.update_metadata(
        document_id, title=title, description=description, tags=tags,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Document not found in registry")

    return updated.model_dump()


@router.get("/")
async def list_documents(components: Components = Depends(get_components)):
    """List all indexed documents grouped by document_id.

    Uses provider-agnostic scroll() method (works with ChromaDB, Qdrant, etc.).
    """
    try:
        total = await components.vector_store.count()
        if total == 0:
            return {"documents": [], "total_chunks": 0}

        # Get all chunks using provider-agnostic scroll (metadata only, no content)
        all_chunks = await components.vector_store.scroll(
            limit=total + 100,
            fields=["document_id", "source", "title", "language", "document_type", "original_id"],
        )

        # Group by document_id
        doc_map: dict[str, dict] = {}
        for chunk in all_chunks:
            doc_id = chunk.document_id or "unknown"
            if doc_id not in doc_map:
                doc_map[doc_id] = {
                    "id": doc_id,
                    "source_path": chunk.metadata.get("source", ""),
                    "title": chunk.metadata.get("title", ""),
                    "language": chunk.metadata.get("language", ""),
                    "document_type": chunk.metadata.get("document_type", ""),
                    "chunk_count": 0,
                }
            doc_map[doc_id]["chunk_count"] += 1

        documents = sorted(doc_map.values(), key=lambda d: d["chunk_count"], reverse=True)
        return {"documents": documents, "total_chunks": total}
    except Exception as e:
        logger.error(f"List documents error: {e}")
        return {"documents": [], "total_chunks": 0}


@router.get("/stats")
async def get_stats(components: Components = Depends(get_components)):
    """Get index statistics."""
    vector_count = await components.vector_store.count()
    graph_stats = await components.graph_store.get_statistics()
    return {
        "vector_store": {"document_count": vector_count},
        "graph_store": graph_stats,
    }


@router.delete("/clear")
async def clear_vector_store(
    components: Components = Depends(get_components),
):
    """Clear entire vector store (delete collection and recreate).

    Works with any provider (ChromaDB, Qdrant, etc.).
    """
    try:
        try:
            count_before = await components.vector_store.count()
        except Exception:
            count_before = -1

        try:
            await components.vector_store.clear()
        except Exception as clear_err:
            logger.warning(f"Collection clear failed ({clear_err}), trying fallback")
            # ChromaDB-specific fallback: remove persist dir
            persist_dir = getattr(
                getattr(components.vector_store, "_settings", None),
                "persist_dir", None,
            )
            if persist_dir and Path(str(persist_dir)).exists():
                shutil.rmtree(str(persist_dir), ignore_errors=True)
            await components.vector_store.initialize()

        logger.info(f"Vector store cleared: {count_before} chunks removed")
        return {"cleared_chunks": max(count_before, 0)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild-sparse")
async def rebuild_sparse_vectors(
    components: Components = Depends(get_components),
):
    """Rebuild Qdrant sparse BM25 vectors from existing dense vectors.

    Re-upserts all points to add/update BM25 sparse vectors.
    Useful after initial indexing or when BM25 config changes.
    """
    store = components.vector_store
    if not hasattr(store, "rebuild_sparse_vectors"):
        raise HTTPException(
            status_code=400,
            detail="Current vector store does not support sparse vector rebuild",
        )

    try:
        t0 = time.time()
        count = await store.rebuild_sparse_vectors()
        elapsed = time.time() - t0

        logger.info("[SPARSE] Rebuild complete: %d points in %.1fs", count, elapsed)
        return {
            "status": "ok",
            "updated": count,
            "elapsed_seconds": round(elapsed, 1),
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("[SPARSE] Rebuild failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rebuild-bm25")
async def rebuild_bm25(
    components: Components = Depends(get_components),
):
    """Rebuild BM25 FTS5 index from current Qdrant data.

    Reads all chunks from Qdrant and inserts them into the SQLite FTS5
    index with pymorphy3 lemmatization. Fixes BM25 <-> Qdrant desync.
    """
    bm25_store = getattr(components, "bm25_store", None)
    if bm25_store is None:
        raise HTTPException(status_code=400, detail="BM25 store is not enabled")

    try:
        t0 = time.time()

        # Count before
        old_count = await bm25_store.count()

        # Clear existing FTS5 index
        await bm25_store.clear()

        # Read all chunks from vector store
        total = await components.vector_store.count()
        if total == 0:
            return {
                "status": "empty",
                "message": "Vector store is empty, nothing to rebuild",
                "old_count": old_count,
                "new_count": 0,
            }

        all_chunks = await components.vector_store.scroll(limit=total + 100)

        # Insert into BM25 in batches
        batch_size = 500
        indexed = 0

        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            added = await bm25_store.add_chunks(
                chunk_ids=[c.id for c in batch],
                contents=[c.content for c in batch],
                document_ids=[c.document_id for c in batch],
                sources=[c.metadata.get("source", "") for c in batch],
                sections=[
                    c.metadata.get("breadcrumb", "") or c.section or c.metadata.get("section_title", "") or ""
                    for c in batch
                ],
            )
            indexed += added

        elapsed = time.time() - t0
        new_count = await bm25_store.count()

        logger.info(
            "[BM25] Rebuild complete: %d -> %d chunks (%.1fs)",
            old_count, new_count, elapsed,
        )

        return {
            "status": "ok",
            "old_count": old_count,
            "new_count": new_count,
            "elapsed_seconds": round(elapsed, 1),
        }

    except Exception as e:
        logger.error("[BM25] Rebuild failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    components: Components = Depends(get_components),
):
    """Delete a document and its chunks from the vector store.

    Uses provider-agnostic delete_by_filter (works with ChromaDB, Qdrant, etc.).
    """
    try:
        deleted = await components.vector_store.delete_by_filter(
            {"document_id": document_id}
        )
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        # Also clean BM25 index
        bm25_store = getattr(components, "bm25_store", None)
        if bm25_store is not None:
            try:
                await bm25_store.delete_by_document(document_id)
            except Exception as e:
                logger.warning("BM25 delete failed: %s", e)

        return {"deleted_chunks": deleted, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Phase 18: Incremental Indexing ==========

class DeltaIndexRequest(BaseModel):
    """Request for incremental indexing (Phase 18)."""

    file_paths: list[str]
    force_reindex: bool = False
    build_graph: bool = False
    extract_images: bool = True


class DeltaIndexResponse(BaseModel):
    """Response from incremental indexing."""

    added: int
    modified: int
    deleted: int
    errors: list[str]
    total_time: float
    delta_summary: str


@router.post("/index/delta", response_model=DeltaIndexResponse)
async def index_delta(
    request: DeltaIndexRequest,
    components: Components = Depends(get_components),
):
    """Incremental indexing: only process changed documents.

    Uses SHA-256 hashing to detect file changes and only indexes
    added/modified documents instead of full reindexing.

    Performance: 50+ minutes → <5 minutes for single file change.
    """
    try:
        from src.pdf_framework.indexing import DeltaIndexer

        # Create delta indexer
        indexer = DeltaIndexer(
            vector_store=components.vector_store,
            settings=components.settings,
        )

        # Detect changes
        delta = indexer.detect_delta(request.file_paths, force_reindex=request.force_reindex)

        if not delta.has_changes:
            return DeltaIndexResponse(
                added=0,
                modified=0,
                deleted=0,
                errors=[],
                total_time=0.0,
                delta_summary=delta.summary(),
            )

        # Process changes
        t0 = time.time()

        async def load_document(file_path: str):
            """Load a single document."""
            document = await components.loader.load(file_path)
            return document

        async def process_chunks(document, doc_hash):
            """Process document chunks into vector store."""
            chunks = components.pipeline.process(document)

            # Phase 15: Extract images if enabled
            if request.extract_images and components.settings.pdf.extract_images:
                try:
                    img_descriptions = await components.image_extractor.extract_all(document.source_path)
                    if img_descriptions:
                        img_chunks = components.image_extractor.to_document_chunks(
                            img_descriptions,
                            document_id=document.id,
                            source_path=document.source_path,
                        )
                        # Phase 29: Inherit section metadata from nearest text chunk
                        from src.pdf_framework.processing.pipeline import ProcessingPipeline
                        ProcessingPipeline._inherit_image_sections(chunks, img_chunks)
                        chunks.extend(img_chunks)
                except Exception as e:
                    logger.warning(f"[DELTA] Image extraction failed: {e}")

            # Index chunks (with checkpointing)
            await components.indexer.index_chunks(
                chunks,
                document_id=document.id,
                source_path=document.source_path,
                version_manager=components.version_manager,
            )

            # Build graph if enabled
            if request.build_graph:
                try:
                    await components.graph_builder.build_from_document(document)
                except Exception as e:
                    logger.warning(f"[DELTA] Graph building failed: {e}")

        stats = await indexer.process_delta(delta, load_document, process_chunks)
        stats["total_time"] = time.time() - t0
        stats["delta_summary"] = delta.summary()

        return DeltaIndexResponse(**stats)

    except Exception as e:
        logger.error(f"[DELTA] Incremental indexing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/index/delta/stats")
async def get_delta_stats(
    components: Components = Depends(get_components),
):
    """Get delta indexing statistics (hash database info)."""
    try:
        from src.pdf_framework.indexing import DeltaIndexer

        indexer = DeltaIndexer(
            vector_store=components.vector_store,
            settings=components.settings,
        )

        stats = indexer.get_hash_db_stats()
        return stats

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/index/delta/clear")
async def clear_delta_cache(
    components: Components = Depends(get_components),
):
    """Clear delta indexing hash database (forces full reindex next run)."""
    try:
        from src.pdf_framework.indexing import DeltaIndexer

        indexer = DeltaIndexer(
            vector_store=components.vector_store,
            settings=components.settings,
        )

        indexer.clear_hash_db()
        return {"message": "Hash database cleared"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


