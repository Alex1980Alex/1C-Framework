from __future__ import annotations

from pathlib import Path

import pytest

from src.bsl.semantic_search.refactor.backends.multilspy_backend import (
    MultilspyBackend,
)
from src.bsl.semantic_search.refactor.driver import RenameDriver, RenameResult
from src.bsl.semantic_search.refactor.types import (
    BackendError,
    FileEdit,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
)
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


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def _make_driver(
    workspace: Path, lsp_response: dict, errors: list[str] | None = None
) -> RenameDriver:
    backend = MultilspyBackend(lambda: _StubLspClient(lsp_response))
    applier = WorkspaceEditApplier(workspace)
    errs = errors or []
    verifier = RenameVerifier(applier, lambda: list(errs))
    return RenameDriver(backend, verifier)


def test_dry_run_returns_plan_without_applying(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    original = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(original, encoding="utf-8")

    uri = _file_uri(file_a)
    driver = _make_driver(workspace, _lsp_rename_response(uri, 0, 10, 16, "Новая"))

    result = driver.rename(uri, 0, 10, "Новая", dry_run=True)

    assert isinstance(result, RenameResult)
    assert result.applied is False
    assert result.rolled_back is False
    assert result.confirm_token is not None
    assert len(result.confirm_token) == 64
    assert result.files_affected == 1
    assert result.total_edits == 1
    assert file_a.read_text(encoding="utf-8") == original


def test_confirm_with_matching_token_applies(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    file_a.write_text("Процедура Старая() Экспорт\nКонецПроцедуры\n", encoding="utf-8")

    uri = _file_uri(file_a)
    driver = _make_driver(workspace, _lsp_rename_response(uri, 0, 10, 16, "Новая"))

    plan = driver.rename(uri, 0, 10, "Новая", dry_run=True)
    assert plan.confirm_token is not None

    result = driver.rename(uri, 0, 10, "Новая", dry_run=False, confirm_token=plan.confirm_token)

    assert result.ok is True
    assert result.applied is True
    assert result.rolled_back is False
    text = file_a.read_text(encoding="utf-8")
    assert "Новая" in text
    assert "Старая" not in text


def test_confirm_with_mismatched_token_raises(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    file_a.write_text("Процедура X()\nКонецПроцедуры\n", encoding="utf-8")

    uri = _file_uri(file_a)
    driver = _make_driver(workspace, _lsp_rename_response(uri, 0, 10, 11, "Y"))

    with pytest.raises(BackendError) as exc:
        driver.rename(uri, 0, 10, "Y", dry_run=False, confirm_token="nope")
    assert exc.value.code == "token_mismatch"
    assert file_a.read_text(encoding="utf-8") == "Процедура X()\nКонецПроцедуры\n"


def test_confirm_with_none_token_raises(workspace: Path) -> None:
    uri = _file_uri(workspace / "a.bsl")
    driver = _make_driver(workspace, _lsp_rename_response(uri, 0, 0, 1, "Y"))

    with pytest.raises(BackendError) as exc:
        driver.rename(uri, 0, 0, "Y", dry_run=False, confirm_token=None)
    assert exc.value.code == "token_mismatch"


def test_unsupported_uri_raises(workspace: Path) -> None:
    file_py = workspace / "a.py"
    file_py.write_text("x = 1\n", encoding="utf-8")

    driver = _make_driver(workspace, _lsp_rename_response(_file_uri(file_py), 0, 0, 1, "Y"))

    with pytest.raises(BackendError) as exc:
        driver.rename(_file_uri(file_py), 0, 0, "Y", dry_run=True)
    assert exc.value.code == "unsupported_uri"


def test_verifier_rollback_propagates(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    original = "Процедура A()\nКонецПроцедуры\n"
    file_a.write_text(original, encoding="utf-8")

    uri = _file_uri(file_a)

    calls = {"n": 0}

    def regress_on_second_call() -> list[str]:
        calls["n"] += 1
        return [] if calls["n"] == 1 else ["err1", "err2"]

    backend = MultilspyBackend(lambda: _StubLspClient(_lsp_rename_response(uri, 0, 10, 11, "Z")))
    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, regress_on_second_call)
    driver = RenameDriver(backend, verifier)

    plan = driver.rename(uri, 0, 10, "Z", dry_run=True)
    result = driver.rename(uri, 0, 10, "Z", dry_run=False, confirm_token=plan.confirm_token)

    assert result.applied is True
    assert result.rolled_back is True
    assert result.ok is False
    assert file_a.read_text(encoding="utf-8") == original


def test_token_is_stable_for_same_edit() -> None:
    edit = WorkspaceEdit(
        file_edits=[
            FileEdit(
                uri="file:///a.bsl",
                edits=[
                    TextEdit(
                        range=Range(Position(0, 0), Position(0, 5)),
                        new_text="Hello",
                    )
                ],
            )
        ]
    )
    t1 = RenameDriver._compute_token(edit)
    t2 = RenameDriver._compute_token(edit)
    assert t1 == t2


def test_token_differs_for_different_edits() -> None:
    def make(new_text: str) -> WorkspaceEdit:
        return WorkspaceEdit(
            file_edits=[
                FileEdit(
                    uri="file:///a.bsl",
                    edits=[
                        TextEdit(
                            range=Range(Position(0, 0), Position(0, 5)),
                            new_text=new_text,
                        )
                    ],
                )
            ]
        )

    assert RenameDriver._compute_token(make("A")) != RenameDriver._compute_token(make("B"))


def test_backend_error_propagates_without_wrapping(workspace: Path) -> None:
    class _ExplodingClient:
        def rename(self, params: dict) -> dict:
            raise RuntimeError("lsp down")

    backend = MultilspyBackend(lambda: _ExplodingClient())
    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, lambda: [])
    driver = RenameDriver(backend, verifier)

    with pytest.raises(BackendError) as exc:
        driver.rename("file:///x.bsl", 0, 0, "Y", dry_run=True)
    assert exc.value.code == "lsp_error"
