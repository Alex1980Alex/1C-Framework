"""Sandbox module — agent code-execution backends.

Provides an abstract ``SandboxBackend`` interface and concrete implementations:

- ``DryRunBackend`` — zero-dependency, records calls without executing (CI / no-key fallback)
- ``LangSmithBackend`` — Firecracker microVM via langsmith[sandbox] (GA May 2026)
- ``E2BBackend`` — Firecracker microVM with stateful Jupyter Kernel (e2b-code-interpreter)

Use ``select_backend()`` for env-driven auto-selection.
"""

import os

from src.pdf_framework.sandbox.base import (
    SandboxBackend,
    SandboxQuotaExceeded,
    SandboxResult,
)
from src.pdf_framework.sandbox.dry_run_backend import DryRunBackend

__all__ = [
    "SandboxBackend",
    "SandboxQuotaExceeded",
    "SandboxResult",
    "DryRunBackend",
    "select_backend",
]


def select_backend(prefer: str = "auto") -> SandboxBackend:
    """Select a sandbox backend.

    Args:
        prefer: One of ``"auto"`` (default), ``"langsmith"``, ``"e2b"``, ``"dryrun"``.
            ``"auto"`` picks the first available: LangSmith → E2B → DryRun.

    Returns:
        Configured ``SandboxBackend`` instance.
    """
    if prefer == "dryrun":
        return DryRunBackend()

    if prefer == "langsmith" or (prefer == "auto" and os.getenv("LANGSMITH_API_KEY")):
        from src.pdf_framework.sandbox.langsmith_backend import LangSmithBackend
        return LangSmithBackend()

    if prefer == "e2b" or (prefer == "auto" and os.getenv("E2B_API_KEY")):
        from src.pdf_framework.sandbox.e2b_backend import E2BBackend
        return E2BBackend()

    return DryRunBackend()
