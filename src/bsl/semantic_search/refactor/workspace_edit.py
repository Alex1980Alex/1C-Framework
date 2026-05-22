from __future__ import annotations

import pathlib
import urllib.parse
import urllib.request
from pathlib import Path

from .types import BackendError, WorkspaceEdit


class WorkspaceEditApplier:
    """Applies WorkspaceEdit atomically with snapshot-based rollback."""

    def __init__(self, workspace_root: pathlib.Path) -> None:
        self._workspace_root = workspace_root.resolve()
        self._snapshots: dict[Path, str | None] = {}

    def apply(self, edit: WorkspaceEdit) -> None:
        """Apply the workspace edit, rolling back on any failure."""
        try:
            for file_edit in edit.file_edits:
                path = self._resolve_within_workspace(file_edit.uri)
                if path not in self._snapshots:
                    self._snapshots[path] = (
                        path.read_text(encoding="utf-8") if path.exists() else None
                    )

                text = self._snapshots[path] or ""
                sorted_edits = sorted(
                    file_edit.edits,
                    key=lambda e: (e.range.start.line, e.range.start.character),
                    reverse=True,
                )

                for te in sorted_edits:
                    start_offset = self._line_col_to_offset(
                        text, te.range.start.line, te.range.start.character
                    )
                    end_offset = self._line_col_to_offset(
                        text, te.range.end.line, te.range.end.character
                    )
                    text = text[:start_offset] + te.new_text + text[end_offset:]

                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(text.encode("utf-8"))
        except Exception:
            self.rollback()
            raise

    def rollback(self) -> None:
        """Revert all applied changes; best-effort across per-file failures."""
        errors: list[tuple[Path, Exception]] = []
        for path, original in self._snapshots.items():
            try:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(original.encode("utf-8"))
            except OSError as e:
                errors.append((path, e))
        self._snapshots.clear()
        if errors:
            details = "; ".join(f"{p}: {e}" for p, e in errors)
            raise BackendError(
                f"rollback failed for {len(errors)} file(s): {details}",
                code="rollback_partial",
                details={"failures": [str(p) for p, _ in errors]},
            )

    def _resolve_within_workspace(self, uri: str) -> Path:
        """Resolve URI to Path and enforce workspace containment."""
        path = self._uri_to_path(uri).resolve()
        try:
            path.relative_to(self._workspace_root)
        except ValueError:
            raise BackendError(
                f"path outside workspace: {path}",
                code="path_traversal",
                details={"path": str(path), "workspace": str(self._workspace_root)},
            ) from None
        return path

    @staticmethod
    def _uri_to_path(uri: str) -> Path:
        """Resolve a file:// URI to a local pathlib.Path."""
        parsed = urllib.parse.urlparse(uri)
        return Path(urllib.request.url2pathname(parsed.path))

    @staticmethod
    def _line_col_to_offset(text: str, line: int, character: int) -> int:
        """Convert 0-based (line, character) to string offset."""
        offset = 0
        current_line = 0
        while current_line < line:
            nl_idx = text.find("\n", offset)
            if nl_idx == -1:
                raise IndexError(f"Line {line} is out of range (file has {current_line + 1} lines)")
            offset = nl_idx + 1
            current_line += 1

        line_end_idx = text.find("\n", offset)
        line_length = (line_end_idx - offset) if line_end_idx != -1 else (len(text) - offset)

        if character > line_length:
            raise IndexError(
                f"Character {character} is out of range on line {line} (length {line_length})"
            )
        return offset + character
