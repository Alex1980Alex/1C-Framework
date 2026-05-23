from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..types import WorkspaceEdit


@runtime_checkable
class RenameBackend(Protocol):
    """Contract for rename backends (multilspy, ast-grep, etc.)."""

    def can_handle(self, uri: str) -> bool:
        """Return True if this backend can attempt rename for the given file URI."""
        ...

    def confidence_for(self, symbol_kind: str) -> float:
        """Return 0.0..1.0 confidence for renaming a symbol of this kind."""
        ...

    def plan_rename(self, uri: str, line: int, character: int, new_name: str) -> WorkspaceEdit:
        """Return a WorkspaceEdit describing the rename, without applying it.

        Raise BackendError on protocol errors (LSP unreachable, invalid position, etc.).
        """
        ...
