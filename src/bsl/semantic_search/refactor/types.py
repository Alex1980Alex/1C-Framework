from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Position:
    line: int
    character: int


@dataclass(frozen=True, slots=True)
class Range:
    start: Position
    end: Position


@dataclass(frozen=True, slots=True)
class TextEdit:
    range: Range
    new_text: str


@dataclass(slots=True)
class FileEdit:
    uri: str
    edits: list[TextEdit] = field(default_factory=list)


@dataclass(slots=True)
class WorkspaceEdit:
    file_edits: list[FileEdit] = field(default_factory=list)


class BackendError(Exception):
    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details
