"""Role-Based Access Control (Phase 12.4).

Author: Claude Code
Version: 1.3.0 - Phase 12.4: RBAC
"""

import logging
from functools import wraps
from typing import Callable, Literal

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


# Role hierarchy: higher role includes all lower role permissions
ROLE_LEVELS = {
    "viewer": 1,
    "editor": 2,
    "admin": 3,
}

# Permissions per role
ROLE_PERMISSIONS = {
    "viewer": [
        "search:read",
        "ask:read",
        "documents:get",
        "stats:read",
    ],
    "editor": [
        # Inherits viewer permissions
        "search:read",
        "ask:read",
        "documents:get",
        "stats:read",
        # Editor-specific
        "documents:index",
        "documents:delete",
        "documents:update",
    ],
    "admin": [
        # Inherits editor permissions
        "search:read",
        "ask:read",
        "documents:get",
        "stats:read",
        "documents:index",
        "documents:delete",
        "documents:update",
        # Admin-specific
        "tenants:create",
        "tenants:delete",
        "tenants:list",
        "users:manage",
        "metrics:read",
        "auth:token",
    ],
}


def has_permission(role: Literal["viewer", "editor", "admin"], permission: str) -> bool:
    """
    Check if role has permission.

    Args:
        role: User role
        permission: Permission to check

    Returns:
        True if role has permission
    """
    return permission in ROLE_PERMISSIONS.get(role, [])


def require_role(required_role: Literal["viewer", "editor", "admin"]):
    """
    Decorator to require a minimum role level.

    Usage:
        @require_role("editor")
        async def my_endpoint(payload: TokenPayloadDep):
            ...

    Args:
        required_role: Minimum required role
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract token payload from kwargs (injected by FastAPI)
            from src.api.auth.dependencies import TokenPayload

            payload = None
            for v in kwargs.values():
                if isinstance(v, TokenPayload):
                    payload = v
                    break

            if payload is None:
                # Try to get from args (first arg after self)
                if len(args) > 1 and isinstance(args[1], TokenPayload):
                    payload = args[1]

            if payload is None:
                logger.error("[RBAC] TokenPayload not found in route handler")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check role level
            user_level = ROLE_LEVELS.get(payload.role, 0)
            required_level = ROLE_LEVELS.get(required_role, 0)

            if user_level < required_level:
                logger.warning(
                    f"[RBAC] Access denied: user '{payload.tenant_id}' "
                    f"with role '{payload.role}' requires '{required_role}'"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Role '{required_role}' required",
                )

            # Call original function
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_permission(permission: str):
    """
    Decorator to require a specific permission.

    Usage:
        @require_permission("documents:delete")
        async def delete_document(payload: TokenPayloadDep):
            ...

    Args:
        permission: Required permission
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from src.api.auth.dependencies import TokenPayload

            payload = None
            for v in kwargs.values():
                if isinstance(v, TokenPayload):
                    payload = v
                    break

            if payload is None:
                logger.error("[RBAC] TokenPayload not found in route handler")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # Check permission
            if not has_permission(payload.role, permission):
                logger.warning(
                    f"[RBAC] Permission denied: user '{payload.tenant_id}' "
                    f"with role '{payload.role}' lacks '{permission}'"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission '{permission}' required",
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def get_role_permissions(role: Literal["viewer", "editor", "admin"]) -> list[str]:
    """Get all permissions for a role."""
    return ROLE_PERMISSIONS.get(role, []).copy()


def get_all_roles() -> list[str]:
    """Get all available roles."""
    return ["viewer", "editor", "admin"]
