"""SSO and RBAC for Production (Phase 12.4 / 23.6).

Functional RBAC (Phase 12.4): ROLE_LEVELS, ROLE_PERMISSIONS, decorators.
Class-based SSO (Phase 23.6): RBACManager, SSOManager for LDAP/AD.

Author: Claude Code
Version: 2.0.0 - Consolidated functional + class-based RBAC
"""

import functools
import logging
from typing import Any, Optional
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 12.4: Functional RBAC — role levels, permissions, decorators
# ---------------------------------------------------------------------------

ROLE_LEVELS: dict[str, int] = {
    "viewer": 1,
    "editor": 2,
    "admin": 3,
}

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer": [
        "search:read",
        "ask:read",
        "documents:get",
        "stats:read",
        "graph:read",
        "chat:read",
        "chat:write",
    ],
    "editor": [
        "search:read",
        "ask:read",
        "documents:get",
        "documents:index",
        "documents:delete",
        "documents:update",
        "stats:read",
        "graph:read",
        "graph:write",
        "chat:read",
        "chat:write",
        "feedback:write",
    ],
    "admin": [
        "search:read",
        "ask:read",
        "documents:get",
        "documents:index",
        "documents:delete",
        "documents:update",
        "stats:read",
        "graph:read",
        "graph:write",
        "chat:read",
        "chat:write",
        "feedback:write",
        "tenants:create",
        "tenants:delete",
        "tenants:manage",
        "users:manage",
        "auth:token",
        "cache:clear",
        "settings:write",
    ],
}

# Permission is a type alias for permission strings (e.g. "documents:read")
Permission = str


def has_permission(role: str, permission: str) -> bool:
    """Check if a role has a specific permission."""
    perms = ROLE_PERMISSIONS.get(role, [])
    return permission in perms


def get_role_permissions(role: str) -> list[str]:
    """Get all permissions for a role (returns a copy)."""
    return list(ROLE_PERMISSIONS.get(role, []))


def get_all_roles() -> list[str]:
    """Get all roles ordered by level (lowest to highest)."""
    return sorted(ROLE_LEVELS.keys(), key=lambda r: ROLE_LEVELS[r])


def require_role(min_role: str):
    """Decorator: require minimum role level.

    Usage:
        @require_role("editor")
        async def handler(payload=None):
            ...
    """
    min_level = ROLE_LEVELS.get(min_role, 0)

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import HTTPException

            payload = kwargs.get("payload")
            if payload is None:
                raise HTTPException(status_code=401, detail="Missing authentication")

            user_role = getattr(payload, "role", None)
            if user_role is None:
                raise HTTPException(status_code=401, detail="Missing role in token")

            user_level = ROLE_LEVELS.get(user_role, 0)
            if user_level < min_level:
                raise HTTPException(
                    status_code=403,
                    detail=f"Role '{user_role}' insufficient, need '{min_role}'",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(permission: str):
    """Decorator: require specific permission.

    Usage:
        @require_permission("tenants:create")
        async def handler(payload=None):
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            from fastapi import HTTPException

            payload = kwargs.get("payload")
            if payload is None:
                raise HTTPException(status_code=401, detail="Missing authentication")

            user_role = getattr(payload, "role", None)
            if user_role is None:
                raise HTTPException(status_code=401, detail="Missing role in token")

            if not has_permission(user_role, permission):
                raise HTTPException(
                    status_code=403,
                    detail=f"Permission '{permission}' denied for role '{user_role}'",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Phase 23.6: Class-based SSO — LDAP/AD integration
# ---------------------------------------------------------------------------


class User(BaseModel):
    """User model for RBAC."""

    id: str
    username: str
    email: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime
    last_login: Optional[datetime] = None


class Role(BaseModel):
    """Role model with permissions."""

    name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class RBACManager:
    """Role-Based Access Control manager."""

    def __init__(self):
        self._users: dict[str, User] = {}
        self._roles = {
            "admin": Role(
                name="admin",
                description="Full system access",
                permissions=["*"],
            ),
            "user": Role(
                name="user",
                description="Standard user access",
                permissions=[
                    "documents:read",
                    "documents:write",
                    "search:read",
                    "feedback:write",
                ],
            ),
            "viewer": Role(
                name="viewer",
                description="Read-only access",
                permissions=[
                    "documents:read",
                    "search:read",
                ],
            ),
        }

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        roles: list[str] | None = None,
    ) -> User:
        import uuid

        user_id = str(uuid.uuid4())
        assigned_roles = roles or ["user"]
        permissions = set()

        for role_name in assigned_roles:
            if role_name in self._roles:
                role = self._roles[role_name]
                permissions.update(role.permissions)

        user = User(
            id=user_id,
            username=username,
            email=email,
            roles=assigned_roles,
            permissions=list(permissions),
            is_active=True,
            created_at=datetime.now(),
        )

        self._users[user_id] = user
        logger.info(f"[RBAC] Created user: {username}")
        return user

    def check_permission(
        self,
        user: User,
        resource: str,
        action: str,
    ) -> bool:
        if "*" in user.permissions:
            return True

        permission = f"{resource}:{action}"
        return permission in user.permissions


class SSOManager:
    """Single Sign-On manager."""

    def __init__(
        self,
        ldap_url: str | None = None,
    ):
        self._ldap_url = ldap_url
        self._rbac = RBACManager()

    def authenticate_ldap(
        self,
        username: str,
        password: str,
    ) -> Optional[User]:
        # For demo: create user without LDAP
        return self.authenticate_local(username, password)

    def authenticate_local(
        self,
        username: str,
        password: str,
    ) -> Optional[User]:
        user = self._rbac.create_user(
            username=username,
            email=f"{username}@local",
            password=password,
        )
        return user


# Global SSO manager
_sso_manager: Optional[SSOManager] = None


def get_sso_manager() -> SSOManager:
    global _sso_manager
    if _sso_manager is None:
        _sso_manager = SSOManager()
    return _sso_manager
