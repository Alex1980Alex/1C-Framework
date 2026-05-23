from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.bsl.semantic_search.refactor import (
    MultilspyBackend,
    RenameVerifier,
    WorkspaceEditApplier,
)


class _StubLspClient:
    """Returns a canned LSP WorkspaceEdit for a known rename."""

    def __init__(self, response: Any) -> None:
        self._response = response

    def rename(self, params: dict) -> Any:
        return self._response


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def test_end_to_end_rename_via_backend_applier_verifier(workspace: Path) -> None:
    file_a = workspace / "module.bsl"
    file_a.write_text("Процедура Старая() Экспорт\nКонецПроцедуры\n", encoding="utf-8")

    uri = _file_uri(file_a)
    lsp_response = {
        "documentChanges": [
            {
                "textDocument": {"uri": uri, "version": 1},
                "edits": [
                    {
                        "range": {
                            "start": {"line": 0, "character": 10},
                            "end": {"line": 0, "character": 16},
                        },
                        "newText": "Новая",
                    }
                ],
            }
        ]
    }

    backend = MultilspyBackend(lambda: _StubLspClient(lsp_response))
    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, lambda: [])

    edit = backend.plan_rename(uri, 0, 10, "Новая")
    assert len(edit.file_edits) == 1

    result = verifier.verify_and_apply(edit)

    assert result.ok is True
    text = file_a.read_text(encoding="utf-8")
    assert "Новая" in text
    assert "Старая" not in text
