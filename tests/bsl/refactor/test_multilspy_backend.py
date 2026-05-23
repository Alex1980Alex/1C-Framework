from __future__ import annotations

from typing import Any

import pytest

from src.bsl.semantic_search.refactor.backends.base import RenameBackend
from src.bsl.semantic_search.refactor.backends.multilspy_backend import (
    MultilspyBackend,
)
from src.bsl.semantic_search.refactor.types import BackendError, WorkspaceEdit


class _FakeClient:
    def __init__(self, response: Any = None, raise_exc: Exception | None = None) -> None:
        self._response = response
        self._raise = raise_exc
        self.received_params: dict | None = None

    def rename(self, params: dict) -> Any:
        self.received_params = params
        if self._raise is not None:
            raise self._raise
        return self._response


def test_protocol_conformance() -> None:
    backend = MultilspyBackend(lambda: _FakeClient())
    assert isinstance(backend, RenameBackend)


def test_can_handle_extensions() -> None:
    backend = MultilspyBackend(lambda: _FakeClient())
    assert backend.can_handle("file:///x/y.bsl") is True
    assert backend.can_handle("file:///x/y.BSL") is True
    assert backend.can_handle("file:///x/y.os") is True
    assert backend.can_handle("file:///x/y.py") is False


def test_confidence_known_and_unknown() -> None:
    backend = MultilspyBackend(lambda: _FakeClient())
    assert backend.confidence_for("module_export_proc") == 0.95
    assert backend.confidence_for("local_variable") == 0.70
    assert backend.confidence_for("nonexistent_kind") == 0.0


def test_plan_rename_parses_document_changes() -> None:
    raw = {
        "documentChanges": [
            {
                "textDocument": {"uri": "file:///a.bsl", "version": 1},
                "edits": [
                    {
                        "range": {
                            "start": {"line": 0, "character": 10},
                            "end": {"line": 0, "character": 16},
                        },
                        "newText": "Новая",
                    },
                    {
                        "range": {
                            "start": {"line": 5, "character": 0},
                            "end": {"line": 5, "character": 5},
                        },
                        "newText": "foo",
                    },
                ],
            },
            {
                "textDocument": {"uri": "file:///b.bsl", "version": 1},
                "edits": [
                    {
                        "range": {
                            "start": {"line": 2, "character": 3},
                            "end": {"line": 2, "character": 8},
                        },
                        "newText": "bar",
                    },
                ],
            },
        ]
    }
    client = _FakeClient(response=raw)
    backend = MultilspyBackend(lambda: client)
    result = backend.plan_rename("file:///a.bsl", 0, 10, "Новая")

    assert isinstance(result, WorkspaceEdit)
    assert len(result.file_edits) == 2
    assert result.file_edits[0].uri == "file:///a.bsl"
    assert len(result.file_edits[0].edits) == 2
    assert result.file_edits[0].edits[0].new_text == "Новая"
    assert result.file_edits[0].edits[0].range.start.line == 0
    assert result.file_edits[0].edits[0].range.end.character == 16
    assert client.received_params is not None
    assert client.received_params["textDocument"]["uri"] == "file:///a.bsl"
    assert client.received_params["position"] == {"line": 0, "character": 10}
    assert client.received_params["newName"] == "Новая"


def test_plan_rename_parses_changes_fallback() -> None:
    raw = {
        "changes": {
            "file:///a.bsl": [
                {
                    "range": {
                        "start": {"line": 0, "character": 0},
                        "end": {"line": 0, "character": 3},
                    },
                    "newText": "New",
                },
            ],
        }
    }
    backend = MultilspyBackend(lambda: _FakeClient(response=raw))
    result = backend.plan_rename("file:///a.bsl", 0, 0, "New")

    assert len(result.file_edits) == 1
    assert result.file_edits[0].uri == "file:///a.bsl"
    assert result.file_edits[0].edits[0].new_text == "New"


def test_plan_rename_skips_document_changes_without_textdocument() -> None:
    raw = {
        "documentChanges": [
            {"kind": "create", "uri": "file:///new.bsl"},
            {
                "textDocument": {"uri": "file:///a.bsl"},
                "edits": [
                    {
                        "range": {
                            "start": {"line": 0, "character": 0},
                            "end": {"line": 0, "character": 1},
                        },
                        "newText": "X",
                    }
                ],
            },
        ]
    }
    backend = MultilspyBackend(lambda: _FakeClient(response=raw))
    result = backend.plan_rename("file:///a.bsl", 0, 0, "X")

    assert len(result.file_edits) == 1
    assert result.file_edits[0].uri == "file:///a.bsl"


def test_plan_rename_empty_response_returns_empty_edit() -> None:
    backend = MultilspyBackend(lambda: _FakeClient(response=None))
    result = backend.plan_rename("file:///a.bsl", 0, 0, "X")
    assert result.file_edits == []


def test_plan_rename_lsp_error_wrapped_in_backend_error() -> None:
    backend = MultilspyBackend(lambda: _FakeClient(raise_exc=RuntimeError("boom")))
    with pytest.raises(BackendError) as excinfo:
        backend.plan_rename("file:///a.bsl", 0, 0, "X")
    assert excinfo.value.code == "lsp_error"
    assert "boom" in str(excinfo.value)


def test_plan_rename_factory_error_wrapped() -> None:
    def bad_factory() -> Any:
        raise ConnectionError("lsp dead")

    backend = MultilspyBackend(bad_factory)
    with pytest.raises(BackendError) as excinfo:
        backend.plan_rename("file:///a.bsl", 0, 0, "X")
    assert excinfo.value.code == "client_init"
    assert "lsp dead" in str(excinfo.value)


def test_plan_rename_malformed_response_wrapped() -> None:
    raw = {"changes": {"file:///a.bsl": [{"newText": "X"}]}}
    backend = MultilspyBackend(lambda: _FakeClient(response=raw))
    with pytest.raises(BackendError) as excinfo:
        backend.plan_rename("file:///a.bsl", 0, 0, "X")
    assert excinfo.value.code == "malformed"
