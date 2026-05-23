from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..types import (
    BackendError,
    FileEdit,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
)

LspClient = Any
LspClientFactory = Callable[[], LspClient]


class MultilspyBackend:
    """Concrete RenameBackend backed by a multilspy-style LSP client."""

    SUPPORTED_EXTENSIONS = (".bsl", ".os")

    _CONFIDENCE = {
        "module_export_proc": 0.95,
        "module_export_func": 0.95,
        "module_local_proc": 0.85,
        "module_local_func": 0.85,
        "local_variable": 0.70,
        "form_handler": 0.60,
    }

    def __init__(self, client_factory: LspClientFactory) -> None:
        self._factory = client_factory

    def can_handle(self, uri: str) -> bool:
        """Return True if URI targets a BSL/OneScript file."""
        return uri.lower().endswith(self.SUPPORTED_EXTENSIONS)

    def confidence_for(self, symbol_kind: str) -> float:
        """Return confidence for renaming a symbol of the given kind."""
        return self._CONFIDENCE.get(symbol_kind, 0.0)

    def plan_rename(self, uri: str, line: int, character: int, new_name: str) -> WorkspaceEdit:
        """Request a rename from the LSP and return it as a domain WorkspaceEdit."""
        try:
            client = self._factory()
        except Exception as exc:
            raise BackendError(f"lsp client factory failed: {exc!r}", code="client_init") from exc

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line, "character": character},
            "newName": new_name,
        }

        try:
            raw = client.rename(params)
        except Exception as exc:
            raise BackendError(f"lsp rename failed: {exc!r}", code="lsp_error") from exc

        if not raw:
            return WorkspaceEdit(file_edits=[])

        return self._lsp_to_workspace_edit(raw)

    @staticmethod
    def _parse_text_edit(d: dict) -> TextEdit:
        try:
            r = d["range"]
            s = r["start"]
            e = r["end"]
            return TextEdit(
                range=Range(
                    Position(s["line"], s["character"]),
                    Position(e["line"], e["character"]),
                ),
                new_text=d.get("newText", d.get("new_text", "")),
            )
        except (KeyError, TypeError) as exc:
            raise BackendError(f"malformed lsp response: {exc!r}", code="malformed") from exc

    @staticmethod
    def _lsp_to_workspace_edit(raw: dict) -> WorkspaceEdit:
        file_edits: list[FileEdit] = []
        parse = MultilspyBackend._parse_text_edit

        try:
            if raw.get("documentChanges"):
                for doc_change in raw["documentChanges"]:
                    if "textDocument" not in doc_change:
                        continue
                    uri = doc_change["textDocument"]["uri"]
                    edits = [parse(e) for e in doc_change["edits"]]
                    file_edits.append(FileEdit(uri=uri, edits=edits))
            elif raw.get("changes"):
                for uri, edits_list in raw["changes"].items():
                    edits = [parse(e) for e in edits_list]
                    file_edits.append(FileEdit(uri=uri, edits=edits))
        except (KeyError, TypeError) as exc:
            raise BackendError(f"malformed lsp response: {exc!r}", code="malformed") from exc

        return WorkspaceEdit(file_edits=file_edits)
