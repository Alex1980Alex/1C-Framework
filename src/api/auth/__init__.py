"""Authentication and authorization (Phase 12.4 / 23.6)."""

# Phase 12.4: Functional RBAC
# Phase 23.6: Class-based SSO
from src.api.auth.rbac import (
    ROLE_LEVELS,
    ROLE_PERMISSIONS,
    Permission,
    RBACManager,
    Role,
    SSOManager,
    User,
    get_all_roles,
    get_role_permissions,
    get_sso_manager,
    has_permission,
    require_permission,
    require_role,
)

__all__ = [
    # Phase 12.4
    "ROLE_LEVELS",
    "ROLE_PERMISSIONS",
    "Permission",
    "get_all_roles",
    "get_role_permissions",
    "has_permission",
    "require_permission",
    "require_role",
    # Phase 23.6
    "RBACManager",
    "SSOManager",
    "User",
    "Role",
    "get_sso_manager",
]
