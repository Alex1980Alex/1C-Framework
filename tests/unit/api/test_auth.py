"""Unit tests for JWT auth, RBAC, and rate limiting (F2.10).

Tests:
- F2.10.2: Test JWT create + verify
- F2.10.3: Test RBAC permission check
- F2.10.4: Test rate limiter (token bucket)
"""

from datetime import timedelta
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestJWTAuth:
    """Test JWT creation and verification (F2.10.2)."""

    def test_jwt_create_token(self):
        """F2.10.2: Should create valid JWT token."""
        from src.api.auth.jwt_handler import JWTHandler

        handler = JWTHandler(secret="test_secret", algorithm="HS256")

        token = handler.create_token(tenant_id="tenant123", role="editor")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_jwt_verify_valid_token(self):
        """F2.10.2: Should verify valid token."""
        from src.api.auth.jwt_handler import JWTHandler

        handler = JWTHandler(secret="test_secret", algorithm="HS256")

        token = handler.create_token(tenant_id="tenant123", role="viewer")
        payload = handler.verify_token(token)

        assert payload is not None
        assert payload.tenant_id == "tenant123"
        assert payload.role == "viewer"

    def test_jwt_verify_invalid_token(self):
        """F2.10.2: Should reject invalid token."""
        from src.api.auth.jwt_handler import JWTHandler

        handler = JWTHandler(secret="test_secret", algorithm="HS256")

        payload = handler.verify_token("invalid_token")

        assert payload is None

    def test_jwt_token_expiration(self):
        """F2.10.2: Handler with short expiration should create expiring tokens."""
        from src.api.auth.jwt_handler import JWTHandler

        handler = JWTHandler(secret="test_secret", algorithm="HS256", expire_hours=1)

        token = handler.create_token(tenant_id="tenant123")

        # Should be valid immediately
        payload = handler.verify_token(token)
        assert payload is not None
        assert payload.exp > datetime.now(payload.exp.tzinfo)

    def test_jwt_extract_tenant_id(self):
        """F2.10.2: Should extract tenant_id from token."""
        from src.api.auth.jwt_handler import JWTHandler

        handler = JWTHandler(secret="test_secret", algorithm="HS256")

        token = handler.create_token(tenant_id="tenant456", role="admin")
        tenant_id = handler.extract_tenant_id(token)

        assert tenant_id == "tenant456"

    def test_jwt_get_default_token(self):
        """F2.10.2: Should generate default dev token."""
        from src.api.auth.jwt_handler import JWTHandler

        handler = JWTHandler(secret="test_secret", algorithm="HS256")

        token = handler.get_default_token()
        payload = handler.verify_token(token)

        assert payload is not None
        assert payload.tenant_id == "default"
        assert payload.role == "admin"


@pytest.mark.unit
class TestRBAC:
    """Test RBAC permission checks (F2.10.3)."""

    def test_rbac_admin_has_all_access(self):
        """F2.10.3: Admin role should have access to everything."""
        from src.api.auth.rbac import RBACManager

        rbac = RBACManager()
        admin = rbac.create_user("admin", "admin@test.com", "pass", roles=["admin"])

        assert rbac.check_permission(admin, "tenants", "create") is True
        assert rbac.check_permission(admin, "users", "manage") is True

    def test_rbac_viewer_limited_access(self):
        """F2.10.3: Viewer role should have limited access."""
        from src.api.auth.rbac import RBACManager

        rbac = RBACManager()
        viewer = rbac.create_user("viewer", "viewer@test.com", "pass", roles=["viewer"])

        # Viewer can read
        assert rbac.check_permission(viewer, "documents", "read") is True

        # But cannot write
        assert rbac.check_permission(viewer, "documents", "write") is False

    def test_rbac_editor_can_edit(self):
        """F2.10.3: Editor role can edit documents."""
        from src.api.auth.rbac import RBACManager

        rbac = RBACManager()
        user = rbac.create_user("editor", "editor@test.com", "pass")

        # Default "user" role can write documents
        assert rbac.check_permission(user, "documents", "write") is True

    def test_rbac_custom_role_denied(self):
        """F2.10.3: Unknown role should have no permissions."""
        from src.api.auth.rbac import RBACManager

        rbac = RBAC(
            roles={
                "custom_role": {
                    "permissions": ["read:analytics", "write:notes"],
                }
            }
        )

        assert rbac.check_permission(user, "documents", "read") is False

    def test_rbac_user_model_fields(self):
        """F2.10.3: User model should have correct fields."""
        from src.api.auth.rbac import RBACManager

        rbac = RBACManager()
        user = rbac.create_user("testuser", "test@test.com", "pass", roles=["admin"])

        # Owner can access their own resources
        assert (
            rbac.check_permission(
                "user123",
                "documents",
                "write",
                resource_owner_id="user123",
            )
            is True
        )

    def test_rbac_non_owner_denied(self):
        """F2.10.3: Non-owner should be denied."""
        from src.api.auth.rbac import RBAC

        rbac = RBAC()

        assert (
            rbac.check_permission(
                "user123",
                "documents",
                "write",
                resource_owner_id="user456",
            )
            is False
        )


@pytest.mark.unit
class TestRateLimiter:
    """Test rate limiting with token bucket (F2.10.4)."""

    def test_rate_limiter_within_limit(self):
        """F2.10.4: Should allow requests within limit."""
        from src.api.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(rate=10, window=60)

        user_id = "user123"

        # First request should be allowed
        assert limiter.is_allowed(user_id) is True

        # Up to 10 requests should be allowed
        for _ in range(9):
            assert limiter.is_allowed(user_id) is True

    def test_rate_limiter_exceeds_limit(self):
        """F2.10.4: Should block after limit exceeded."""
        from src.api.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(rate=5, window=60)

        user_id = "user123"

        # Use up the limit
        for _ in range(5):
            assert limiter.is_allowed(user_id) is True

        # Next request should be blocked
        assert limiter.is_allowed(user_id) is False

    def test_rate_limiter_refill_over_time(self):
        """F2.10.4: Tokens should refill over time."""

        from src.api.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(rate=10, per=60)  # 10 per minute

        with patch(target, return_value=0.0):
            limiter = RateLimiter(rate=10, window=60)
            user_id = "user123"

            # Use up all tokens at t=0
            for _ in range(10):
                limiter.is_allowed(user_id)

            assert limiter.is_allowed(user_id) is False

        # After 120 seconds, tokens fully refilled
        with patch(target, return_value=120.0):
            assert limiter.is_allowed(user_id) is True

    def test_rate_limiter_different_users(self):
        """F2.10.4: Rate limiting should be per-user."""
        from src.api.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(rate=2, window=60)

        # User 1 uses their limit
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is True
        assert limiter.is_allowed("user1") is False

        # User 2 should still have their full limit
        assert limiter.is_allowed("user2") is True
        assert limiter.is_allowed("user2") is True

    def test_rate_limiter_ip_based(self):
        """F2.10.4: Should support IP-based limiting."""
        from src.api.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(rate=5, window=60)

        # Limit by IP instead of user
        ip = "192.168.1.1"

        for _ in range(5):
            assert limiter.is_allowed(ip) is True

        assert limiter.is_allowed(ip) is False

    def test_rate_limiter_get_reset_time(self):
        """F2.10.4: Should report reset time."""
        from src.api.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(rate=3, window=60)

        # Exhaust tokens
        for _ in range(3):
            limiter.is_allowed("user1")

        reset_time = limiter.get_reset_time("user1")
        assert reset_time >= 0

    def test_rate_limiter_no_client_returns_zero(self):
        """F2.10.4: Unknown client should return 0 reset time."""
        from src.api.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(rate=5, window=60)

        assert limiter.get_reset_time("unknown") == 0.0
