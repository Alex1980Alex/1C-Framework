"""Sandbox module — agent code-execution backends.

Provides an abstract ``SandboxBackend`` interface and concrete implementations:
- ``DryRunBackend`` — zero-dependency, records calls without executing (CI / no-key fallback)

LangSmith / E2B backends are implemented in separate sessions (require API keys).
"""

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
]
