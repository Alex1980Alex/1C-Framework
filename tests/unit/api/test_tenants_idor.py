"""IDOR (Insecure Direct Object Reference) protection tests.

Roadmap 260509 §2.3 — verify that non-admin callers cannot access other
tenants via path/query/body `tenant_id` parameters across:

- /tenants/{id} (already covered by tenants.py local guard)
- /documents/index-async (added 2026-05-09)
- /jobs/enqueue (added 2026-05-09)
- /graph/incremental-update (added 2026-05-09)

Two layers:
  1. Unit-level: directly exercise `assert_tenant_access` helper
  2. Integration-level: smoke test the helper is wired via Depends in routes
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException


@pytest.mark.unit
class TestAssertTenantAccess:
    """Unit tests for `src.api.auth.dependencies.assert_tenant_access`.

    Invariant: only admin or matching-tenant callers pass; everyone else gets 403.
    """

    def _call(self, path_tenant: str, current_tenant: str, role: str) -> None:
        from src.api.auth.dependencies import assert_tenant_access

        assert_tenant_access(path_tenant, current_tenant, role)

    def test_admin_can_access_any_tenant(self):
        """admin role bypasses IDOR check."""
        self._call("tenant_other", "tenant_admin_home", "admin")  # no raise

    def test_admin_can_access_own_tenant(self):
        self._call("tenant_a", "tenant_a", "admin")  # no raise

    def test_viewer_can_access_own_tenant(self):
        self._call("tenant_a", "tenant_a", "viewer")  # no raise

    def test_editor_can_access_own_tenant(self):
        self._call("tenant_a", "tenant_a", "editor")  # no raise

    def test_viewer_blocked_from_other_tenant(self):
        """Non-admin + tenant_id mismatch → HTTP 403."""
        with pytest.raises(HTTPException) as ei:
            self._call("tenant_other", "tenant_a", "viewer")
        assert ei.value.status_code == 403
        assert "other tenant" in ei.value.detail.lower()

    def test_editor_blocked_from_other_tenant(self):
        with pytest.raises(HTTPException) as ei:
            self._call("tenant_other", "tenant_a", "editor")
        assert ei.value.status_code == 403

    def test_unknown_role_treated_as_non_admin(self):
        """Defence-in-depth: any role string != 'admin' is non-privileged."""
        with pytest.raises(HTTPException):
            self._call("tenant_other", "tenant_a", "guest")

    def test_empty_tenant_strings_blocked_when_role_not_admin(self):
        """Empty current_tenant should not match a non-empty path tenant."""
        with pytest.raises(HTTPException):
            self._call("tenant_a", "", "viewer")

    def test_role_case_sensitive_admin(self):
        """'Admin' (capital A) is NOT 'admin' — defence against future enum drift."""
        with pytest.raises(HTTPException):
            self._call("tenant_other", "tenant_a", "Admin")


@pytest.mark.unit
class TestIDORGuardWiring:
    """Smoke tests that the routes import and reference the guard.

    These don't spin up a TestClient (integration would need ARQ/Redis/Qdrant
    fixtures). Instead they verify the guard call is present in the source —
    cheap protection against accidental removal.
    """

    @pytest.mark.parametrize("module_path", [
        "src.api.routes.documents",
        "src.api.routes.jobs",
        "src.api.routes.graph",
    ])
    def test_route_module_imports_guard(self, module_path: str):
        import importlib

        mod = importlib.import_module(module_path)
        assert hasattr(mod, "assert_tenant_access"), (
            f"{module_path} must import assert_tenant_access (IDOR guard)"
        )

    def test_tenants_py_has_local_guard(self):
        """tenants.py keeps its in-file `_assert_tenant_access` (legacy, predates shared helper)."""
        from src.api.routes import tenants

        assert hasattr(tenants, "_assert_tenant_access")
