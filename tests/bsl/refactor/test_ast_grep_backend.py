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
    assert backend.confidence_for("form_handler") == 0.95  # calibrated pilot-B
    assert backend.confidence_for("unknown") == 0.30
    assert backend.confidence_for("module_export_proc") == 0.95  # calibrated pilot-B
    assert backend.confidence_for("nonexistent") == 0.0


def test_word_at_extracts_cyrillic_identifier() -> None:
    assert AstGrepBackend._word_at("Процедура ОбработатьДанные()", 11) == "ОбработатьДанные"
    assert AstGrepBackend._word_at("Процедура ОбработатьДанные()", 10) == "ОбработатьДанные"
    assert AstGrepBackend._word_at("Процедура X()", 13) == ""


def test_word_at_edge_cases() -> None:
    assert AstGrepBackend._word_at("", 0) == ""
    assert AstGrepBackend._word_at("foo", -1) == ""
    assert AstGrepBackend._word_at("foo", 100) == ""
    assert AstGrepBackend._word_at("foo bar", 3) == "bar"  # pos 3 = space, scans forward


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


class _AllowFilesPrefilter:
    """Stub prefilter that whitelists a fixed set of resolved paths."""

    def __init__(self, allow: set[Path] | None) -> None:
        self._allow = allow

    def allowed_files(self, old_name, module_hint=None):  # noqa: ARG002
        return self._allow


def test_prefilter_drops_matches_outside_allowlist(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура F() Экспорт\nКонецПроцедуры\n")
    file_b = workspace / "b.bsl"
    _write(file_b, "F();\n")
    file_c = workspace / "c.bsl"
    _write(file_c, "F();\n")

    matches = [
        AstGrepMatch(file=file_a, start_line=0, start_character=10, end_line=0, end_character=11),
        AstGrepMatch(file=file_b, start_line=0, start_character=0, end_line=0, end_character=1),
        AstGrepMatch(file=file_c, start_line=0, start_character=0, end_line=0, end_character=1),
    ]
    runner = _FakeRunner(matches=matches)
    prefilter = _AllowFilesPrefilter({file_a.resolve(), file_b.resolve()})
    backend = AstGrepBackend(runner, workspace, prefilter=prefilter)

    result = backend.plan_rename(file_a.resolve().as_uri(), 0, 10, "G")

    assert backend.last_prefilter_used is True
    assert backend.last_prefilter_dropped == 1
    edited_uris = {fe.uri for fe in result.file_edits}
    assert file_c.resolve().as_uri() not in edited_uris
    assert file_a.resolve().as_uri() in edited_uris
    assert file_b.resolve().as_uri() in edited_uris


def test_prefilter_unknown_symbol_no_drop(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура F() Экспорт\nКонецПроцедуры\n")
    file_b = workspace / "b.bsl"
    _write(file_b, "F();\n")

    matches = [
        AstGrepMatch(file=file_a, start_line=0, start_character=10, end_line=0, end_character=11),
        AstGrepMatch(file=file_b, start_line=0, start_character=0, end_line=0, end_character=1),
    ]
    backend = AstGrepBackend(
        _FakeRunner(matches=matches),
        workspace,
        prefilter=_AllowFilesPrefilter(None),  # unknown symbol → fallback
    )
    result = backend.plan_rename(file_a.resolve().as_uri(), 0, 10, "G")

    assert backend.last_prefilter_used is False
    assert backend.last_prefilter_dropped == 0
    assert len(result.file_edits) == 2


def test_prefilter_counters_reset_per_call(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура F() Экспорт\nКонецПроцедуры\n")
    file_b = workspace / "b.bsl"
    _write(file_b, "F();\n")

    runner = _FakeRunner(matches=[
        AstGrepMatch(file=file_a, start_line=0, start_character=10, end_line=0, end_character=11),
        AstGrepMatch(file=file_b, start_line=0, start_character=0, end_line=0, end_character=1),
    ])
    backend = AstGrepBackend(
        runner, workspace, prefilter=_AllowFilesPrefilter({file_a.resolve()})
    )
    backend.plan_rename(file_a.resolve().as_uri(), 0, 10, "G")
    assert backend.last_prefilter_dropped == 1

    # Second call: switch to no-filter prefilter (returns None)
    backend2 = AstGrepBackend(
        runner, workspace, prefilter=_AllowFilesPrefilter(None)
    )
    backend2.plan_rename(file_a.resolve().as_uri(), 0, 10, "H")
    assert backend2.last_prefilter_used is False
    assert backend2.last_prefilter_dropped == 0


def test_plan_rename_runner_backend_error_propagates(workspace: Path) -> None:
    file_a = workspace / "a.bsl"
    _write(file_a, "Процедура X()\n")
    runner_err = BackendError("subprocess died", code="subprocess_failed")
    backend = AstGrepBackend(_FakeRunner(raise_exc=runner_err), workspace)
    with pytest.raises(BackendError) as exc:
        backend.plan_rename(file_a.resolve().as_uri(), 0, 10, "Y")
    assert exc.value.code == "subprocess_failed"
