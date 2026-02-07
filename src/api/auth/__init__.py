"""Authentication and authorization (Phase 12).

Provides:
- JWTHandler: JWT token creation and verification
- get_jwt_handler(): factory for JWT handler
- get_current_tenant: FastAPI dependency for tenant extraction
- get_current_role: FastAPI dependency for role extraction
- require_role: decorator for role-based access control
- require_permission: decorator for permission-based access control
"""

from src.api.auth.dependencies import (
    TokenPayloadDep,
    TenantId,
    UserRole,
    get_current_role,
    get_current_tenant,
    get_token_payload,
)
from src.api.auth.jwt_handler import JWTHandler, TokenPayload, get_jwt_handler
from src.api.auth.rbac import (
    get_all_roles,
    get_role_permissions,
    has_permission,
    require_permission,
    require_role,
)

__all__ = [
    # JWT
    "JWTHandler",
    "TokenPayload",
    "get_jwt_handler",
    # Dependencies
    "TenantId",
    "UserRole",
    "TokenPayloadDep",
    "get_current_tenant",
    "get_current_role",
    "get_token_payload",
    # RBAC
    "require_role",
    "require_permission",
    "has_permission",
    "get_role_permissions",
    "get_all_roles",
]
