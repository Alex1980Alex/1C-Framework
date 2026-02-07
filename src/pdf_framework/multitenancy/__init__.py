"""Multi-tenancy support (Phase 12).

Provides:
- TenantVectorStoreManager: per-tenant ChromaDB collections
- TenantGraphManager: per-tenant NetworkX graphs
- get_tenant_store_manager(): factory for tenant vector stores
- get_tenant_graph_manager(): factory for tenant graphs
"""

from src.pdf_framework.multitenancy.tenant_graph import (
    TenantGraphManager,
    TenantGraphStore,
    get_tenant_graph_manager,
)
from src.pdf_framework.multitenancy.tenant_store import (
    TenantMetadata,
    TenantVectorStoreManager,
    get_tenant_store_manager,
)

__all__ = [
    "TenantVectorStoreManager",
    "TenantMetadata",
    "get_tenant_store_manager",
    "TenantGraphManager",
    "TenantGraphStore",
    "get_tenant_graph_manager",
]
