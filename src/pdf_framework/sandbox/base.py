"""Abstract base class for sandbox backend implementations.

All sandbox providers (DryRun, LangSmith, E2B) must implement this interface.
Mirrors the pattern established in ``vector_store/base.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxResult:
    """Result of a sandbox code execution."""

    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    truncated: bool = field(default=False)
    """True if output exceeded ~100 KB and was cut."""


class SandboxQuotaExceeded(Exception):  # noqa: N818  # rename to SandboxQuotaExceededError deferred — 8 files impact; see roadmap 260523 §11 follow-up
    """Raised when the sandbox call quota for the current instance is exceeded."""


class SandboxBackend(ABC):
    """Abstract interface for sandboxed code execution backends."""

    @abstractmethod
    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: float = 30.0,
    ) -> SandboxResult:
        """Execute ``code`` in the sandbox and return the result.

        Args:
            code: Source code to run.
            language: Programming language (e.g. ``"python"``, ``"bash"``).
            timeout: Maximum wall-clock seconds before the execution is killed.
        """

    @abstractmethod
    async def install(self, packages: list[str]) -> None:
        """Install packages into the sandbox environment.

        Args:
            packages: Package names (pip-compatible specifiers).
        """

    @abstractmethod
    async def upload(self, local_path: Path, remote_path: str) -> None:
        """Upload a local file into the sandbox filesystem.

        Args:
            local_path: Path to the file on the host.
            remote_path: Destination path inside the sandbox.
        """

    @abstractmethod
    async def download(self, remote_path: str, local_path: Path) -> None:
        """Download a file from the sandbox filesystem to the host.

        Args:
            remote_path: Source path inside the sandbox.
            local_path: Destination path on the host.
        """

    @abstractmethod
    async def close(self) -> None:
        """Release sandbox resources.  Must be idempotent."""
