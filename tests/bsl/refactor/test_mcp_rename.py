from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.bsl.semantic_search.mcp import (
    bsl_rename_symbol,
    register_rename_driver_factory,
)
from src.bsl.semantic_search.refactor.backends.multilspy_backend import (
    MultilspyBackend,
)
from src.bsl.semantic_search.refactor.driver import RenameDriver
from src.bsl.semantic_search.refactor.verification import RenameVerifier
from src.bsl.semantic_search.refactor.workspace_edit import WorkspaceEditApplier


class _StubLspClient:
    def __init__(self, response: dict) -> None:
        self._response = response

    def rename(self, params: dict) -> dict:
        return self._response


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _lsp_rename_response(uri: str, line: int, start: int, end: int, new_text: str) -> dict:
    return {
        "documentChanges": [
            {
                "textDocument": {"uri": uri, "version": 1},
                "edits": [
                    {
                        "range": {
                            "start": {"line": line, "character": start},
                            "end": {"line": line, "character": end},
                        },
                        "newText": new_text,
                    }
                ],
            }
        ]
    }


@pytest.fixture(autouse=True)
def _clear_factory() -> Any:
    register_rename_driver_factory(None)
    yield
    register_rename_driver_factory(None)


def _install_driver(workspace: Path, lsp_response: dict) -> None:
    def factory() -> RenameDriver:
        backend = MultilspyBackend(lambda: _StubLspClient(lsp_response))
        applier = WorkspaceEditApplier(workspace)
        verifier = RenameVerifier(applier, lambda: [])
        return RenameDriver(backend, verifier)

    register_rename_driver_factory(factory)


def test_tool_returns_not_initialized_without_factory() -> None:
    result = bsl_rename_symbol(uri="file:///x.bsl", line=0, character=0, new_name="Y", dry_run=True)
    assert result["error"] == "rename pipeline not initialized"
    assert result["code"] == "not_initialized"


def test_tool_dry_run_returns_plan(tmp_path: Path) -> None:
    file_a = tmp_path / "a.bsl"
    file_a.write_text("Процедура Старая() Экспорт\nКонецПроцедуры\n", encoding="utf-8")

    uri = _file_uri(file_a)
    _install_driver(tmp_path, _lsp_rename_response(uri, 0, 10, 16, "Новая"))

    result = bsl_rename_symbol(uri=uri, line=0, character=10, new_name="Новая", dry_run=True)

    assert result["ok"] is False
    assert result["applied"] is False
    assert result["rolled_back"] is False
    assert result["confirm_token"] is not None
    assert len(result["confirm_token"]) == 64
    assert result["files_affected"] == 1
    assert result["total_edits"] == 1


def test_tool_confirm_applies_file(tmp_path: Path) -> None:
    file_a = tmp_path / "a.bsl"
    file_a.write_text("Процедура Старая() Экспорт\nКонецПроцедуры\n", encoding="utf-8")

    uri = _file_uri(file_a)
    _install_driver(tmp_path, _lsp_rename_response(uri, 0, 10, 16, "Новая"))

    plan = bsl_rename_symbol(uri=uri, line=0, character=10, new_name="Новая", dry_run=True)
    applied = bsl_rename_symbol(
        uri=uri,
        line=0,
        character=10,
        new_name="Новая",
        dry_run=False,
        confirm_token=plan["confirm_token"],
    )

    assert applied["ok"] is True
    assert applied["applied"] is True
    assert applied["rolled_back"] is False
    assert "Новая" in file_a.read_text(encoding="utf-8")


def test_tool_token_mismatch_returns_error_dict(tmp_path: Path) -> None:
    file_a = tmp_path / "a.bsl"
    file_a.write_text("Процедура X()\nКонецПроцедуры\n", encoding="utf-8")

    uri = _file_uri(file_a)
    _install_driver(tmp_path, _lsp_rename_response(uri, 0, 10, 11, "Y"))

    result = bsl_rename_symbol(
        uri=uri,
        line=0,
        character=10,
        new_name="Y",
        dry_run=False,
        confirm_token="wrong",
    )

    assert "error" in result
    assert result["code"] == "token_mismatch"
    assert file_a.read_text(encoding="utf-8") == "Процедура X()\nКонецПроцедуры\n"


def test_tool_unsupported_uri_returns_error_dict(tmp_path: Path) -> None:
    file_py = tmp_path / "a.py"
    file_py.write_text("x = 1\n", encoding="utf-8")

    uri = _file_uri(file_py)
    _install_driver(tmp_path, _lsp_rename_response(uri, 0, 0, 1, "Y"))

    result = bsl_rename_symbol(uri=uri, line=0, character=0, new_name="Y", dry_run=True)

    assert "error" in result
    assert result["code"] == "unsupported_uri"


def test_tool_backend_error_returns_error_dict(tmp_path: Path) -> None:
    class _ExplodingClient:
        def rename(self, params: dict) -> dict:
            raise RuntimeError("lsp down")

    def factory() -> RenameDriver:
        backend = MultilspyBackend(lambda: _ExplodingClient())
        applier = WorkspaceEditApplier(tmp_path)
        verifier = RenameVerifier(applier, lambda: [])
        return RenameDriver(backend, verifier)

    register_rename_driver_factory(factory)

    result = bsl_rename_symbol(uri="file:///x.bsl", line=0, character=0, new_name="Y", dry_run=True)

    assert "error" in result
    assert result["code"] == "lsp_error"
