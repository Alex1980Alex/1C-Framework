"""Tests for Role-Based Access Control (Phase 12.4)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.api.auth.rbac import (
    ROLE_LEVELS,
    ROLE_PERMISSIONS,
    get_all_roles,
    get_role_permissions,
    has_permission,
    require_permission,
    require_role,
)


# ---------------------------------------------------------------------------
# ROLE_LEVELS
# ---------------------------------------------------------------------------

class TestRoleLevels:
    def test_viewer_lowest(self):
        assert ROLE_LEVELS["viewer"] == 1

    def test_editor_middle(self):
        assert ROLE_LEVELS["editor"] == 2

    def test_admin_highest(self):
        assert ROLE_LEVELS["admin"] == 3

    def test_hierarchy_order(self):
        assert ROLE_LEVELS["viewer"] < ROLE_LEVELS["editor"] < ROLE_LEVELS["admin"]


# ---------------------------------------------------------------------------
# ROLE_PERMISSIONS
# ---------------------------------------------------------------------------

class TestRolePermissions:
    def test_viewer_has_read_permissions(self):
        perms = ROLE_PERMISSIONS["viewer"]
        assert "search:read" in perms
        assert "ask:read" in perms
        assert "documents:get" in perms
        assert "stats:read" in perms

    def test_viewer_cannot_write(self):
        perms = ROLE_PERMISSIONS["viewer"]
        assert "documents:index" not in perms
        assert "documents:delete" not in perms

    def test_editor_includes_viewer_permissions(self):
        editor_perms = set(ROLE_PERMISSIONS["editor"])
        viewer_perms = set(ROLE_PERMISSIONS["viewer"])
        assert viewer_perms.issubset(editor_perms)

    def test_editor_has_write_permissions(self):
        perms = ROLE_PERMISSIONS["editor"]
        assert "documents:index" in perms
        assert "documents:delete" in perms
        assert "documents:update" in perms

    def test_admin_includes_editor_permissions(self):
        admin_perms = set(ROLE_PERMISSIONS["admin"])
        editor_perms = set(ROLE_PERMISSIONS["editor"])
        assert editor_perms.issubset(admin_perms)

    def test_admin_has_management_permissions(self):
        perms = ROLE_PERMISSIONS["admin"]
        assert "tenants:create" in perms
        assert "tenants:delete" in perms
        assert "users:manage" in perms
        assert "auth:token" in perms


# ---------------------------------------------------------------------------
# has_permission
# ---------------------------------------------------------------------------

class TestHasPermission:
    def test_viewer_can_search(self):
        assert has_permission("viewer", "search:read") is True

    def test_viewer_cannot_index(self):
        assert has_permission("viewer", "documents:index") is False

    def test_editor_can_index(self):
        assert has_permission("editor", "documents:index") is True

    def test_admin_can_manage_tenants(self):
        assert has_permission("admin", "tenants:create") is True

    def test_unknown_role_returns_false(self):
        assert has_permission("unknown", "search:read") is False

    def test_unknown_permission_returns_false(self):
        assert has_permission("admin", "nonexistent:perm") is False


# ---------------------------------------------------------------------------
# get_role_permissions
# ---------------------------------------------------------------------------

class TestGetRolePermissions:
    def test_returns_list(self):
        perms = get_role_permissions("viewer")
        assert isinstance(perms, list)

    def test_returns_copy(self):
        perms = get_role_permissions("admin")
        perms.append("fake:permission")
        # Original should be unchanged
        assert "fake:permission" not in ROLE_PERMISSIONS["admin"]

    def test_unknown_role_returns_empty(self):
        assert get_role_permissions("unknown") == []


# ---------------------------------------------------------------------------
# get_all_roles
# ---------------------------------------------------------------------------

class TestGetAllRoles:
    def test_returns_three_roles(self):
        roles = get_all_roles()
        assert len(roles) == 3

    def test_contains_expected_roles(self):
        roles = get_all_roles()
        assert "viewer" in roles
        assert "editor" in roles
        assert "admin" in roles

    def test_order(self):
        roles = get_all_roles()
        assert roles == ["viewer", "editor", "admin"]


# ---------------------------------------------------------------------------
# require_role decorator
# ---------------------------------------------------------------------------

class TestRequireRole:
    @pytest.mark.asyncio
    async def test_allows_sufficient_role(self):
        from src.api.auth.jwt_handler import TokenPayload
        from datetime import datetime, timezone, timedelta

        payload = TokenPayload(
            tenant_id="t",
            role="admin",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            iat=datetime.now(timezone.utc),
        )

        @require_role("editor")
        async def handler(payload=None):
            return "ok"

        result = await handler(payload=payload)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_denies_insufficient_role(self):
        from fastapi import HTTPException
        from src.api.auth.jwt_handler import TokenPayload
        from datetime import datetime, timezone, timedelta

        payload = TokenPayload(
            tenant_id="t",
            role="viewer",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            iat=datetime.now(timezone.utc),
        )

        @require_role("admin")
        async def handler(payload=None):
            return "ok"

        with pytest.raises(HTTPException) as exc_info:
            await handler(payload=payload)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_denies_missing_payload(self):
        from fastapi import HTTPException

        @require_role("viewer")
        async def handler():
            return "ok"

        with pytest.raises(HTTPException) as exc_info:
            await handler()
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_same_role_level_passes(self):
        from src.api.auth.jwt_handler import TokenPayload
        from datetime import datetime, timezone, timedelta

        payload = TokenPayload(
            tenant_id="t",
            role="editor",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            iat=datetime.now(timezone.utc),
        )

        @require_role("editor")
        async def handler(payload=None):
            return "ok"

        result = await handler(payload=payload)
        assert result == "ok"


# ---------------------------------------------------------------------------
# require_permission decorator
# ---------------------------------------------------------------------------

class TestRequirePermission:
    @pytest.mark.asyncio
    async def test_allows_with_permission(self):
        from src.api.auth.jwt_handler import TokenPayload
        from datetime import datetime, timezone, timedelta

        payload = TokenPayload(
            tenant_id="t",
            role="admin",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            iat=datetime.now(timezone.utc),
        )

        @require_permission("tenants:create")
        async def handler(payload=None):
            return "created"

        result = await handler(payload=payload)
        assert result == "created"

    @pytest.mark.asyncio
    async def test_denies_without_permission(self):
        from fastapi import HTTPException
        from src.api.auth.jwt_handler import TokenPayload
        from datetime import datetime, timezone, timedelta

        payload = TokenPayload(
            tenant_id="t",
            role="viewer",
            exp=datetime.now(timezone.utc) + timedelta(hours=1),
            iat=datetime.now(timezone.utc),
        )

        @require_permission("tenants:create")
        async def handler(payload=None):
            return "created"

        with pytest.raises(HTTPException) as exc_info:
            await handler(payload=payload)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_denies_missing_payload(self):
        from fastapi import HTTPException

        @require_permission("search:read")
        async def handler():
            return "ok"

        with pytest.raises(HTTPException) as exc_info:
            await handler()
        assert exc_info.value.status_code == 401
