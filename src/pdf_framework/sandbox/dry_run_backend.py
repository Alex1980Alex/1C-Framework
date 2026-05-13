"""DryRunBackend — zero-dependency sandbox for CI and local development.

Records every call to an internal ``calls`` list without executing any code.
Useful for:
- CI pipelines without API keys (zero-cost smoke tests)
- Unit tests of higher-level code that depends on a sandbox
- Validating call shapes before paying for a live backend (E2B, LangSmith)

Quota: 50 execute() calls per instance.  On the 51st call
``SandboxQuotaExceeded`` is raised (mirrors the production limit).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.pdf_framework.sandbox.base import (
    SandboxBackend,
    SandboxQuotaExceeded,
    SandboxResult,
)

_DRY_RUN_STDOUT = "[dry-run] code not executed"
_QUOTA_LIMIT = 50


class DryRunBackend(SandboxBackend):
    """Sandbox backend that records calls without executing anything.

    All methods are no-ops except for quota tracking and call recording.

    Attributes:
        calls: Chronological list of recorded call dicts.  Each dict has a
            ``method`` key plus method-specific kwargs.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._execute_count: int = 0

    # ------------------------------------------------------------------
    # SandboxBackend interface
    # ------------------------------------------------------------------

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: float = 30.0,
    ) -> SandboxResult:
        """Record the call and return a fixed dry-run result.

        Raises:
            SandboxQuotaExceeded: After ``_QUOTA_LIMIT`` (50) calls.
        """
        if self._execute_count >= _QUOTA_LIMIT:
            raise SandboxQuotaExceeded(
                f"DryRunBackend quota of {_QUOTA_LIMIT} execute() calls exceeded."
            )

        self._execute_count += 1
        self.calls.append(
            {
                "method": "execute",
                "code": code,
                "language": language,
                "timeout": timeout,
            }
        )
        return SandboxResult(
            stdout=_DRY_RUN_STDOUT,
            stderr="",
            exit_code=0,
            duration_seconds=0.0,
            truncated=False,
        )

    async def install(self, packages: list[str]) -> None:
        """Record the install call; no-op."""
        self.calls.append({"method": "install", "packages": packages})

    async def upload(self, local_path: Path, remote_path: str) -> None:
        """Record the upload call; no-op."""
        self.calls.append(
            {
                "method": "upload",
                "local_path": str(local_path),
                "remote_path": remote_path,
            }
        )

    async def download(self, remote_path: str, local_path: Path) -> None:
        """Record the download call; no-op."""
        self.calls.append(
            {
                "method": "download",
                "remote_path": remote_path,
                "local_path": str(local_path),
            }
        )

    async def close(self) -> None:
        """No-op.  Safe to call multiple times."""
        self.calls.append({"method": "close"})
