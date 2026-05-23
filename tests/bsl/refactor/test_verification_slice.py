from __future__ import annotations

from pathlib import Path

import pytest

from src.bsl.semantic_search.refactor.types import (
    FileEdit,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
)
from src.bsl.semantic_search.refactor.verification import RenameVerifier
from src.bsl.semantic_search.refactor.workspace_edit import WorkspaceEditApplier


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _simple_edit(
    path: Path, line: int, start_char: int, end_char: int, new_text: str
) -> WorkspaceEdit:
    return WorkspaceEdit(
        file_edits=[
            FileEdit(
                uri=_file_uri(path),
                edits=[
                    TextEdit(
                        range=Range(Position(line, start_char), Position(line, end_char)),
                        new_text=new_text,
                    )
                ],
            )
        ]
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def test_happy_path_no_new_errors(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    file_a.write_text("Процедура Старая()\nКонецПроцедуры\n", encoding="utf-8")

    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, lambda: [])

    edit = _simple_edit(file_a, 0, 10, 16, "Новая")
    result = verifier.verify_and_apply(edit)

    assert result.ok is True
    assert result.applied is True
    assert result.rolled_back is False

    text = file_a.read_text(encoding="utf-8")
    assert "Новая" in text
    assert "Старая" not in text


def test_rollback_on_error_regression(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    file_b = workspace / "b.bsl"
    original_a = "Процедура A()\nКонецПроцедуры\n"
    original_b = "Процедура B()\nКонецПроцедуры\n"
    file_a.write_text(original_a, encoding="utf-8")
    file_b.write_text(original_b, encoding="utf-8")

    calls = {"n": 0}

    def provider() -> list[str]:
        calls["n"] += 1
        return [] if calls["n"] == 1 else ["err1", "err2"]

    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, provider)

    edit = WorkspaceEdit(
        file_edits=[
            FileEdit(
                uri=_file_uri(file_a),
                edits=[
                    TextEdit(
                        range=Range(Position(0, 10), Position(0, 11)),
                        new_text="X",
                    )
                ],
            ),
            FileEdit(
                uri=_file_uri(file_b),
                edits=[
                    TextEdit(
                        range=Range(Position(0, 10), Position(0, 11)),
                        new_text="Y",
                    )
                ],
            ),
        ]
    )

    result = verifier.verify_and_apply(edit)

    assert result.applied is True
    assert result.rolled_back is True
    assert result.ok is False
    assert file_a.read_text(encoding="utf-8") == original_a
    assert file_b.read_text(encoding="utf-8") == original_b
    assert result.reason is not None
    assert "error count rose" in result.reason


def test_apply_exception_reports_not_applied(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    file_a.write_text("short\n", encoding="utf-8")

    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, lambda: [])

    edit = _simple_edit(file_a, 0, 100, 101, "X")
    result = verifier.verify_and_apply(edit)

    assert result.applied is False
    assert result.rolled_back is False
    assert result.reason is not None
    assert "raised" in result.reason
    assert file_a.read_text(encoding="utf-8") == "short\n"


def test_path_traversal_rejected(workspace: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    outside = tmp_path_factory.mktemp("outside")
    victim = outside / "victim.bsl"
    victim.write_text("original\n", encoding="utf-8")

    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, lambda: [])

    edit = _simple_edit(victim, 0, 0, 8, "HIJACKED")
    result = verifier.verify_and_apply(edit)

    assert result.applied is False
    assert result.reason is not None
    assert "path outside workspace" in result.reason or "path_traversal" in result.reason
    assert victim.read_text(encoding="utf-8") == "original\n"
