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
    """Smoke tests that the routes wire the guard.

    Source-text grep (not import) — robust to optional deps (`arq`, `qdrant`)
    that may be missing in the test environment. Cheap protection against
    accidental removal of the guard call.
    """

    @pytest.mark.parametrize(
        "file_path",
        [
            "src/api/routes/documents.py",
            "src/api/routes/jobs.py",
            "src/api/routes/graph.py",
        ],
    )
    def test_route_file_calls_guard(self, file_path: str):
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        source = (repo_root / file_path).read_text(encoding="utf-8")
        assert "assert_tenant_access(" in source, (
            f"{file_path} must call assert_tenant_access(...) — IDOR guard removed?"
        )
        assert "from src.api.auth.dependencies import" in source, (
            f"{file_path} must import the shared auth dependencies"
        )

    def test_tenants_py_has_local_guard(self):
        """tenants.py keeps its in-file `_assert_tenant_access` (predates shared helper)."""
        from pathlib import Path

        repo_root = Path(__file__).resolve().parents[3]
        source = (repo_root / "src/api/routes/tenants.py").read_text(encoding="utf-8")
        assert "_assert_tenant_access" in source
