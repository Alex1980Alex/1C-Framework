from __future__ import annotations

from pathlib import Path

import pytest

from src.bsl.semantic_search.refactor.backends.ast_grep_backend import (
    AstGrepBackend,
    AstGrepMatch,
)
from src.bsl.semantic_search.refactor.backends.base import RenameBackend
from src.bsl.semantic_search.refactor.types import BackendError, WorkspaceEdit


class _FakeRunner:
    def __init__(
        self,
        matches: list[AstGrepMatch] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._matches = list(matches) if matches else []
        self._raise = raise_exc
        self.received: tuple[Path, str, str] | None = None

    def run_rename(self, workspace_root: Path, old_name: str, new_name: str) -> list[AstGrepMatch]:
        self.received = (workspace_root, old_name, new_name)
        if self._raise is not None:
            raise self._raise
        return list(self._matches)


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    return tmp_path


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_protocol_conformance(workspace: Path) -> None:
    backend = AstGrepBackend(_FakeRunner(), workspace)
    assert isinstance(backend, RenameBackend)


def test_can_handle_extensions(workspace: Path) -> None:
    backend = AstGrepBackend(_FakeRunner(), workspace)
    assert backend.can_handle("file:///a.bsl") is True
    assert backend.can_handle("file:///a.BSL") is True
    assert backend.can_handle("file:///a.os") is True
    assert backend.can_handle("file:///a.py") is False


def test_confidence_known_kinds(workspace: Path) -> None:
    backend = AstGrepBackend(_FakeRunner(), workspace)
    assert backend.confidence_for("form_handler") == 0.60
    assert backend.confidence_for("unknown") == 0.30
    assert backend.confidence_for("module_export_proc") == 0.80
    assert backend.confidence_for("nonexistent") == 0.0


def test_word_at_extracts_cyrillic_identifier() -> None:
    assert AstGrepBackend._word_at("Процедура ОбработатьДанные()", 11) == "ОбработатьДанные"
    assert AstGrepBackend._word_at("Процедура ОбработатьДанные()", 10) == "ОбработатьДанные"
    assert AstGrepBackend._word_at("Процедура X()", 13) == ""


def test_word_at_edge_cases() -> None:
    assert AstGrepBackend._word_at("", 0) == ""
    assert AstGrepBackend._word_at("foo", -1) == ""
    assert AstGrepBackend._word_at("foo", 100) == ""
    assert AstGrepBackend._word_at("foo bar", 3) == "foo"


def test_plan_rename_builds_workspace_edit(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура СтараяФункция() Экспорт\nКонецПроцедуры\n")
    file_b = workspace / "b.bsl"
    _write(file_b, "СтараяФункция();\n")
    matches = [
        AstGrepMatch(
            file=file_a,
            start_line=0,
            start_character=10,
            end_line=0,
            end_character=23,
        ),
        AstGrepMatch(
            file=file_b,
            start_line=0,
            start_character=0,
            end_line=0,
            end_character=13,
        ),
    ]
    runner = _FakeRunner(matches=matches)
    backend = AstGrepBackend(runner, workspace)
    result = backend.plan_rename(file_a.resolve().as_uri(), 0, 10, "НоваяФункция")
    assert isinstance(result, WorkspaceEdit)
    assert len(result.file_edits) == 2
    assert runner.received is not None
    assert runner.received[1] == "СтараяФункция"
    assert runner.received[2] == "НоваяФункция"
    all_edits = [e for fe in result.file_edits for e in fe.edits]
    assert all(e.new_text == "НоваяФункция" for e in all_edits)


def test_relative_match_paths_resolved_against_workspace(workspace: Path) -> None:
    """ast-grep emits paths relative to CWD — backend must resolve against workspace_root."""
    file_a = workspace / "sub" / "a.bsl"
    file_a.parent.mkdir(parents=True)
    _write(file_a, "СтараяФункция();\n")

    matches = [
        AstGrepMatch(
            file=Path("sub/a.bsl"),
            start_line=0,
            start_character=0,
            end_line=0,
            end_character=13,
        )
    ]
    backend = AstGrepBackend(_FakeRunner(matches=matches), workspace)
    file_b = workspace / "b.bsl"
    _write(file_b, "СтараяФункция();\n")
    result = backend.plan_rename(file_b.resolve().as_uri(), 0, 0, "НоваяФункция")

    assert len(result.file_edits) == 1
    expected_uri = file_a.resolve().as_uri()
    assert result.file_edits[0].uri == expected_uri


def test_plan_rename_empty_matches_returns_empty_edit(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура X()\nКонецПроцедуры\n")
    backend = AstGrepBackend(_FakeRunner(matches=[]), workspace)
    result = backend.plan_rename(file_a.resolve().as_uri(), 0, 10, "Y")
    assert result.file_edits == []


def test_plan_rename_file_not_found(workspace: Path) -> None:
    backend = AstGrepBackend(_FakeRunner(), workspace)
    with pytest.raises(BackendError) as exc:
        backend.plan_rename((workspace / "nope.bsl").resolve().as_uri(), 0, 0, "X")
    assert exc.value.code == "file_not_found"


def test_plan_rename_position_out_of_range(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура X()\n")
    backend = AstGrepBackend(_FakeRunner(), workspace)
    with pytest.raises(BackendError) as exc:
        backend.plan_rename(file_a.resolve().as_uri(), 99, 0, "Y")
    assert exc.value.code == "position_out_of_range"


def test_plan_rename_no_identifier_at_position(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "   \n")
    backend = AstGrepBackend(_FakeRunner(), workspace)
    with pytest.raises(BackendError) as exc:
        backend.plan_rename(file_a.resolve().as_uri(), 0, 1, "Y")
    assert exc.value.code == "no_identifier"


def test_plan_rename_runner_generic_exception_wrapped(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура X()\n")
    backend = AstGrepBackend(_FakeRunner(raise_exc=RuntimeError("boom")), workspace)
    with pytest.raises(BackendError) as exc:
        backend.plan_rename(file_a.resolve().as_uri(), 0, 10, "Y")
    assert exc.value.code == "runner_error"


def test_plan_rename_runner_backend_error_propagates(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура X()\n")
    runner_err = BackendError("subprocess died", code="subprocess_failed")
    backend = AstGrepBackend(_FakeRunner(raise_exc=runner_err), workspace)
    with pytest.raises(BackendError) as exc:
        backend.plan_rename(file_a.resolve().as_uri(), 0, 10, "Y")
    assert exc.value.code == "subprocess_failed"
