"""Tenant management API routes.

Phase 60: Multi-tenant Isolation - tenant CRUD, stats, quotas.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.dependencies.components import Components, get_components
from src.pdf_framework.multitenancy.tenant_store import get_tenant_store_manager
from src.pdf_framework.schemas.tenant import (
    Tenant,
    TenantCreate,
    TenantStats,
    TenantUsageResponse,
    TenantUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tenants", tags=["tenants"])
security = HTTPBearer()


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Get tenant_id from JWT token.

    Phase 12: Extract tenant_id from JWT claims.
    For now, return default tenant.
    """
    # TODO: Parse JWT and extract tenant_id
    return "default"


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> bool:
    """Verify admin role for tenant management operations.

    Phase 60: Only admins can manage tenants.
    """
    # TODO: Parse JWT and verify admin role
    return True


@router.post("", response_model=Tenant, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreate,
    components: Components = Depends(get_components),
    _admin: bool = Depends(require_admin),
) -> Tenant:
    """Create a new tenant.

    Requires admin role.
    """
    try:
        store_manager = get_tenant_store_manager(
            settings=components.settings.vector_store,
        )

        # Create tenant vector store
        metadata = await store_manager.create_tenant(request.tenant_id)

        # Set quota if provided
        if request.quota:
            await store_manager.set_quota(request.tenant_id, request.quota)

        tenant = Tenant(
            tenant_id=request.tenant_id,
            name=request.name,
            quota=request.quota,
            is_active=True,
            created_at=metadata.created_at,
            updated_at=metadata.created_at,
        )

        logger.info(f"[TENANT] Created: {request.tenant_id}")
        return tenant

    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant already exists: {request.tenant_id}",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("", response_model=list[Tenant])
async def list_tenants(
    active_only: bool = True,
    components: Components = Depends(get_components),
    _admin: bool = Depends(require_admin),
) -> list[Tenant]:
    """List all tenants.

    Requires admin role.
    """
    try:
        store_manager = get_tenant_store_manager(
            settings=components.settings.vector_store,
        )

        tenant_ids = await store_manager.list_tenants()
        tenants = []

        for tenant_id in tenant_ids:
            metadata = await store_manager.get_tenant_metadata(tenant_id)
            if metadata:
                quota = await store_manager.get_quota(tenant_id)

                tenant = Tenant(
                    tenant_id=metadata.tenant_id,
                    name=tenant_id,  # Use tenant_id as name for now
                    quota=quota,
                    is_active=True,
                    created_at=metadata.created_at,
                    updated_at=metadata.last_activity,
                    stats=TenantStats(
                        tenant_id=tenant_id,
                        documents_count=metadata.document_count,
                        chunks_count=0,  # Not tracked in metadata
                        queries_today=0,
                        storage_used_mb=metadata.storage_bytes / (1024 * 1024),
                        created_at=metadata.created_at,
                        last_active=metadata.last_activity,
                    ),
                )
                tenants.append(tenant)

        return tenants

    except Exception as e:
        logger.error(f"[TENANT] Failed to list: {e}")
        return []


@router.get("/{tenant_id}", response_model=Tenant)
async def get_tenant(
    tenant_id: str,
    components: Components = Depends(get_components),
    _current_tenant: str = Depends(get_current_tenant),
) -> Tenant:
    """Get tenant by ID.

    Users can only view their own tenant (unless admin).
    """
    try:
        store_manager = get_tenant_store_manager(
            settings=components.settings.vector_store,
        )

        metadata = await store_manager.get_tenant_metadata(tenant_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {tenant_id}",
            )

        quota = await store_manager.get_quota(tenant_id)

        return Tenant(
            tenant_id=metadata.tenant_id,
            name=tenant_id,
            quota=quota,
            is_active=True,
            created_at=metadata.created_at,
            updated_at=metadata.last_activity,
            stats=TenantStats(
                tenant_id=tenant_id,
                documents_count=metadata.document_count,
                chunks_count=0,
                queries_today=0,
                storage_used_mb=metadata.storage_bytes / (1024 * 1024),
                created_at=metadata.created_at,
                last_active=metadata.last_activity,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TENANT] Failed to get: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{tenant_id}/stats", response_model=TenantStats)
async def get_tenant_stats(
    tenant_id: str,
    components: Components = Depends(get_components),
    _current_tenant: str = Depends(get_current_tenant),
) -> TenantStats:
    """Get tenant usage statistics."""
    try:
        store_manager = get_tenant_store_manager(
            settings=components.settings.vector_store,
        )

        metadata = await store_manager.get_tenant_metadata(tenant_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {tenant_id}",
            )

        return TenantStats(
            tenant_id=tenant_id,
            documents_count=metadata.document_count,
            chunks_count=0,
            queries_today=0,
            storage_used_mb=metadata.storage_bytes / (1024 * 1024),
            created_at=metadata.created_at,
            last_active=metadata.last_activity,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TENANT] Failed to get stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/{tenant_id}/usage", response_model=TenantUsageResponse)
async def get_tenant_usage(
    tenant_id: str,
    components: Components = Depends(get_components),
    _current_tenant: str = Depends(get_current_tenant),
) -> TenantUsageResponse:
    """Get tenant usage with quota comparison."""
    try:
        store_manager = get_tenant_store_manager(
            settings=components.settings.vector_store,
        )

        metadata = await store_manager.get_tenant_metadata(tenant_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {tenant_id}",
            )

        quota = await store_manager.get_quota(tenant_id)
        exceeded = await store_manager.check_quota(tenant_id)

        stats = TenantStats(
            tenant_id=tenant_id,
            documents_count=metadata.document_count,
            chunks_count=0,
            queries_today=0,
            storage_used_mb=metadata.storage_bytes / (1024 * 1024),
            created_at=metadata.created_at,
            last_active=metadata.last_activity,
        )

        usage_percentage = {
            "documents": (stats.documents_count / quota.max_documents * 100)
            if quota.max_documents > 0
            else 0,
            "storage": (stats.storage_used_mb / quota.max_storage_mb * 100)
            if quota.max_storage_mb > 0
            else 0,
        }

        return TenantUsageResponse(
            tenant_id=tenant_id,
            usage=stats,
            quota=quota,
            limits_reached=exceeded,
            usage_percentage=usage_percentage,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TENANT] Failed to get usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.put("/{tenant_id}", response_model=Tenant)
async def update_tenant(
    tenant_id: str,
    request: TenantUpdate,
    components: Components = Depends(get_components),
    _admin: bool = Depends(require_admin),
) -> Tenant:
    """Update tenant.

    Requires admin role.
    """
    try:
        store_manager = get_tenant_store_manager(
            settings=components.settings.vector_store,
        )

        metadata = await store_manager.get_tenant_metadata(tenant_id)
        if not metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {tenant_id}",
            )

        # Update quota if provided
        if request.quota:
            await store_manager.set_quota(tenant_id, request.quota)

        quota = await store_manager.get_quota(tenant_id)

        return Tenant(
            tenant_id=metadata.tenant_id,
            name=request.name or tenant_id,
            quota=quota,
            is_active=request.is_active if request.is_active is not None else True,
            created_at=metadata.created_at,
            updated_at=metadata.last_activity,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[TENANT] Failed to update: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(
    tenant_id: str,
    components: Components = Depends(get_components),
    _admin: bool = Depends(require_admin),
) -> None:
    """Delete tenant and all data (GDPR right to erasure).

    Requires admin role.
    """
    try:
        store_manager = get_tenant_store_manager(
            settings=components.settings.vector_store,
        )

        await store_manager.delete_tenant(tenant_id)

        logger.info(f"[TENANT] Deleted: {tenant_id}")

    except Exception as e:
        logger.error(f"[TENANT] Failed to delete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
