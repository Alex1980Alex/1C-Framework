from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..types import (
    BackendError,
    FileEdit,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
)


@dataclass(frozen=True, slots=True)
class AstGrepMatch:
    """A single occurrence found by ast-grep that should be rewritten."""

    file: Path
    start_line: int
    start_character: int
    end_line: int
    end_character: int


@runtime_checkable
class AstGrepRunner(Protocol):
    """Runs ast-grep against a workspace, returning occurrences of the target identifier."""

    def run_rename(
        self, workspace_root: Path, old_name: str, new_name: str
    ) -> list[AstGrepMatch]: ...


class AstGrepBackend:
    """RenameBackend implemented via ast-grep + tree-sitter-bsl patterns."""

    SUPPORTED_EXTENSIONS = (".bsl", ".os")

    _CONFIDENCE = {
        "module_export_proc": 0.80,
        "module_export_func": 0.80,
        "module_local_proc": 0.75,
        "module_local_func": 0.75,
        "local_variable": 0.40,
        "form_handler": 0.60,
        "unknown": 0.30,
    }

    def __init__(self, runner: AstGrepRunner, workspace_root: Path) -> None:
        self._runner = runner
        self._workspace_root = workspace_root.resolve()

    def can_handle(self, uri: str) -> bool:
        """True for .bsl and .os file URIs."""
        return uri.lower().endswith(self.SUPPORTED_EXTENSIONS)

    def confidence_for(self, symbol_kind: str) -> float:
        """Return confidence for renaming a symbol of the given kind."""
        return self._CONFIDENCE.get(symbol_kind, 0.0)

    def plan_rename(self, uri: str, line: int, character: int, new_name: str) -> WorkspaceEdit:
        """Extract identifier at (line, character), run ast-grep, build WorkspaceEdit."""
        path = self._uri_to_path(uri)
        if not path.exists():
            raise BackendError(f"file not found: {path}", code="file_not_found")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BackendError(f"cannot read file: {exc!r}", code="read_failed") from exc

        lines = text.splitlines()
        if line < 0 or line >= len(lines):
            raise BackendError(
                f"line {line} out of range (file has {len(lines)} lines)",
                code="position_out_of_range",
            )
        old_name = self._word_at(lines[line], character)
        if not old_name:
            raise BackendError(
                f"no identifier at line {line}, character {character}",
                code="no_identifier",
            )

        try:
            matches = self._runner.run_rename(self._workspace_root, old_name, new_name)
        except BackendError:
            raise
        except Exception as exc:
            raise BackendError(f"ast-grep runner failed: {exc!r}", code="runner_error") from exc

        return self._matches_to_edit(matches, new_name, self._workspace_root)

    @staticmethod
    def _uri_to_path(uri: str) -> Path:
        """Convert file:// URI to local Path."""
        parsed = urllib.parse.urlparse(uri)
        return Path(urllib.request.url2pathname(parsed.path))

    @staticmethod
    def _word_at(line_text: str, character: int) -> str:
        """Extract the identifier (Unicode word chars) at the given position."""
        if character < 0 or character > len(line_text):
            return ""

        def _is_id(ch: str) -> bool:
            return ch.isalnum() or ch == "_"

        start = character
        while start > 0 and _is_id(line_text[start - 1]):
            start -= 1
        end = character
        while end < len(line_text) and _is_id(line_text[end]):
            end += 1
        return line_text[start:end]

    @staticmethod
    def _matches_to_edit(
        matches: list[AstGrepMatch], new_name: str, workspace_root: Path
    ) -> WorkspaceEdit:
        """Group matches by file and emit one FileEdit per file.

        Relative match paths are resolved against `workspace_root` so that the
        resulting URIs are absolute regardless of the current process CWD.
        """
        by_file: dict[Path, list[TextEdit]] = {}
        for m in matches:
            path = m.file if m.file.is_absolute() else workspace_root / m.file
            edit = TextEdit(
                range=Range(
                    Position(m.start_line, m.start_character),
                    Position(m.end_line, m.end_character),
                ),
                new_text=new_name,
            )
            by_file.setdefault(path, []).append(edit)
        file_edits = [
            FileEdit(uri=p.resolve().as_uri(), edits=edits) for p, edits in by_file.items()
        ]
        return WorkspaceEdit(file_edits=file_edits)
