"""Tenant management schemas.

Phase 60: Multi-tenant Isolation - tenant models and quotas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class TenantQuota(BaseModel):
    """Tenant resource limits."""

    max_documents: int = Field(default=1000, description="Maximum documents per tenant")
    max_chunks: int = Field(default=100000, description="Maximum chunks per tenant")
    max_queries_per_day: int = Field(default=10000, description="Maximum queries per day")
    max_storage_mb: int = Field(default=10240, description="Maximum storage in MB")


class TenantStats(BaseModel):
    """Tenant usage statistics."""

    tenant_id: str
    documents_count: int = 0
    chunks_count: int = 0
    queries_today: int = 0
    storage_used_mb: float = 0.0
    created_at: datetime
    last_active: Optional[datetime] = None


class Tenant(BaseModel):
    """Tenant model."""

    tenant_id: str
    name: str
    quota: TenantQuota = Field(default_factory=TenantQuota)
    stats: TenantStats | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class TenantCreate(BaseModel):
    """Request to create a new tenant."""

    tenant_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    quota: TenantQuota | None = None


class TenantUpdate(BaseModel):
    """Request to update tenant."""

    name: str | None = None
    quota: TenantQuota | None = None
    is_active: bool | None = None


class TenantUsageResponse(BaseModel):
    """Tenant usage with quota comparison."""

    tenant_id: str
    usage: TenantStats
    quota: TenantQuota
    limits_reached: list[str] = Field(default_factory=list)
    usage_percentage: dict[str, float] = Field(default_factory=dict)
