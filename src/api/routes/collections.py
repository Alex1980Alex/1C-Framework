"""Collection management REST API (Phase 32).

CRUD endpoints for document collections — groups of related documents
for cross-document analysis and scoped search.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.dependencies.components import get_components

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["collections"])


class CreateCollectionRequest(BaseModel):
    name: str
    description: str = ""
    tags: list[str] | None = None


class UpdateCollectionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class AddDocumentsRequest(BaseModel):
    document_ids: list[str]


# ---- CRUD ----


@router.post("/")
async def create_collection(request: CreateCollectionRequest):
    """Create a new document collection."""
    components = await get_components()
    coll_store = getattr(components, "collection_store", None)
    if coll_store is None:
        raise HTTPException(status_code=501, detail="Collection store not available")

    try:
        collection = await coll_store.create(
            name=request.name,
            description=request.description,
            tags=request.tags,
        )
        return collection.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/")
async def list_collections():
    """List all collections with document counts."""
    components = await get_components()
    coll_store = getattr(components, "collection_store", None)
    if coll_store is None:
        raise HTTPException(status_code=501, detail="Collection store not available")

    collections = await coll_store.list_all()
    return {
        "collections": [c.model_dump() for c in collections],
        "total": len(collections),
    }


@router.get("/{collection_id}")
async def get_collection(collection_id: str):
    """Get a collection by ID with details."""
    components = await get_components()
    coll_store = getattr(components, "collection_store", None)
    if coll_store is None:
        raise HTTPException(status_code=501, detail="Collection store not available")

    collection = await coll_store.get(collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get document details from registry
    doc_ids = await coll_store.get_document_ids(collection_id)
    doc_registry = getattr(components, "document_registry", None)
    documents = []
    if doc_registry is not None:
        for doc_id in doc_ids:
            record = await doc_registry.get(doc_id)
            if record:
                documents.append(record.model_dump())
            else:
                documents.append({"document_id": doc_id, "status": "unknown"})
    else:
        documents = [{"document_id": d} for d in doc_ids]

    result = collection.model_dump()
    result["documents"] = documents
    return result


@router.patch("/{collection_id}")
async def update_collection(collection_id: str, request: UpdateCollectionRequest):
    """Update collection metadata."""
    components = await get_components()
    coll_store = getattr(components, "collection_store", None)
    if coll_store is None:
        raise HTTPException(status_code=501, detail="Collection store not available")

    try:
        updated = await coll_store.update(
            collection_id,
            name=request.name,
            description=request.description,
            tags=request.tags,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    if updated is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    return updated.model_dump()


@router.delete("/{collection_id}")
async def delete_collection(collection_id: str):
    """Delete a collection (documents remain indexed, only grouping is removed)."""
    components = await get_components()
    coll_store = getattr(components, "collection_store", None)
    if coll_store is None:
        raise HTTPException(status_code=501, detail="Collection store not available")

    deleted = await coll_store.delete(collection_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Collection not found")

    return {"status": "ok", "deleted": collection_id}


# ---- Document association ----


@router.post("/{collection_id}/documents")
async def add_documents_to_collection(
    collection_id: str, request: AddDocumentsRequest
):
    """Add documents to a collection."""
    components = await get_components()
    coll_store = getattr(components, "collection_store", None)
    if coll_store is None:
        raise HTTPException(status_code=501, detail="Collection store not available")

    # Verify collection exists
    collection = await coll_store.get(collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    added = 0
    already_in = 0
    for doc_id in request.document_ids:
        result = await coll_store.add_document(collection_id, doc_id)
        if result:
            added += 1
        else:
            already_in += 1

    return {"added": added, "already_in_collection": already_in}


@router.delete("/{collection_id}/documents/{document_id}")
async def remove_document_from_collection(collection_id: str, document_id: str):
    """Remove a document from a collection."""
    components = await get_components()
    coll_store = getattr(components, "collection_store", None)
    if coll_store is None:
        raise HTTPException(status_code=501, detail="Collection store not available")

    removed = await coll_store.remove_document(collection_id, document_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Document not in collection")

    return {"status": "ok"}


@router.get("/{collection_id}/documents")
async def list_collection_documents(collection_id: str):
    """List all documents in a collection with metadata."""
    components = await get_components()
    coll_store = getattr(components, "collection_store", None)
    if coll_store is None:
        raise HTTPException(status_code=501, detail="Collection store not available")

    collection = await coll_store.get(collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")

    doc_ids = await coll_store.get_document_ids(collection_id)
    doc_registry = getattr(components, "document_registry", None)

    documents = []
    for doc_id in doc_ids:
        if doc_registry is not None:
            record = await doc_registry.get(doc_id)
            if record:
                documents.append(record.model_dump())
                continue
        documents.append({"document_id": doc_id})

    return {
        "collection_id": collection_id,
        "collection_name": collection.name,
        "documents": documents,
        "total": len(documents),
    }
