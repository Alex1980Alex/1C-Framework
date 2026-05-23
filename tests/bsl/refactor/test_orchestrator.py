from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.bsl.semantic_search.refactor import (
    AstGrepBackend,
    AstGrepMatch,
    HeuristicClassifier,
    MultilspyBackend,
    OrchestratorResult,
    RefactorOrchestrator,
    RenameVerifier,
    RoutingMatrix,
    SymbolKind,
    WorkspaceEditApplier,
)
from src.bsl.semantic_search.refactor.types import BackendError


class _StubLspClient:
    def __init__(self, response: Any = None, raise_exc: Exception | None = None) -> None:
        self._response = response
        self._raise = raise_exc
        self.calls = 0

    def rename(self, params: dict) -> Any:
        self.calls += 1
        self.last_params = params
        if self._raise is not None:
            raise self._raise
        return self._response


class _FakeRunner:
    def __init__(
        self,
        matches: list[AstGrepMatch] | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._matches = list(matches) if matches else []
        self._raise = raise_exc
        self.calls = 0

    def run_rename(self, workspace_root: Path, old_name: str, new_name: str) -> list[AstGrepMatch]:
        self.calls += 1
        self.last_call = (workspace_root, old_name, new_name)
        if self._raise is not None:
            raise self._raise
        return list(self._matches)


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _lsp_edit(uri: str, line: int, start_col: int, end_col: int, new_name: str) -> dict:
    return {
        "documentChanges": [
            {
                "textDocument": {"uri": uri, "version": 1},
                "edits": [
                    {
                        "range": {
                            "start": {"line": line, "character": start_col},
                            "end": {"line": line, "character": end_col},
                        },
                        "newText": new_name,
                    }
                ],
            }
        ]
    }


def _make_orchestrator(
    workspace: Path,
    lsp_client: _StubLspClient | None = None,
    runner: _FakeRunner | None = None,
    error_provider=lambda: [],
) -> tuple[RefactorOrchestrator, WorkspaceEditApplier]:
    multilspy = MultilspyBackend(lambda: lsp_client or _StubLspClient())
    astgrep = AstGrepBackend(runner or _FakeRunner(), workspace)
    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, error_provider)
    orch = RefactorOrchestrator(
        backends={"multilspy": multilspy, "ast-grep": astgrep},
        classifier=HeuristicClassifier(),
        verifier=verifier,
    )
    return orch, applier


def test_primary_multilspy_used_for_module_export_proc(tmp_path: Path) -> None:
    """MODULE_EXPORT_PROC routes to multilspy; fallback not invoked."""
    file_a = tmp_path / "module.bsl"
    file_a.write_text("Процедура Старая() Экспорт\nКонецПроцедуры\n", encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    runner = _FakeRunner()
    orch, _ = _make_orchestrator(tmp_path, lsp, runner)

    content = file_a.read_text(encoding="utf-8")
    result = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)

    assert isinstance(result, OrchestratorResult)
    assert result.symbol_kind == SymbolKind.MODULE_EXPORT_PROC
    assert result.primary_backend == "multilspy"
    assert result.fallback_used is False
    assert result.confidence == 0.95
    assert result.files_affected == 1
    assert result.total_edits == 1
    assert result.confirm_token is not None
    assert lsp.calls == 1
    assert runner.calls == 0


def test_multilspy_raises_triggers_ast_grep_fallback(tmp_path: Path) -> None:
    """DoD R2.5: primary backend unavailable → automatic switch to B."""
    file_a = tmp_path / "module.bsl"
    file_a.write_text("Процедура Старая() Экспорт\nКонецПроцедуры\n", encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(raise_exc=RuntimeError("lsp unreachable"))
    runner = _FakeRunner(
        matches=[
            AstGrepMatch(
                file=file_a,
                start_line=0,
                start_character=10,
                end_line=0,
                end_character=16,
            )
        ]
    )
    orch, _ = _make_orchestrator(tmp_path, lsp, runner)

    content = file_a.read_text(encoding="utf-8")
    result = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)

    assert result.fallback_used is True
    assert result.primary_backend == "ast-grep"
    assert result.symbol_kind == SymbolKind.MODULE_EXPORT_PROC
    assert result.files_affected == 1
    assert result.total_edits == 1
    assert lsp.calls == 1
    assert runner.calls == 1


def test_multilspy_empty_edit_triggers_fallback(tmp_path: Path) -> None:
    """Empty WorkspaceEdit from primary is treated as failure → fallback used."""
    file_a = tmp_path / "module.bsl"
    file_a.write_text("Процедура Старая() Экспорт\nКонецПроцедуры\n", encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(response=None)
    runner = _FakeRunner(
        matches=[
            AstGrepMatch(
                file=file_a,
                start_line=0,
                start_character=10,
                end_line=0,
                end_character=16,
            )
        ]
    )
    orch, _ = _make_orchestrator(tmp_path, lsp, runner)

    content = file_a.read_text(encoding="utf-8")
    result = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)

    assert result.fallback_used is True
    assert result.primary_backend == "ast-grep"


def test_form_handler_routes_ast_grep_primary(tmp_path: Path) -> None:
    """FORM_HANDLER → ast-grep primary; multilspy not invoked."""
    form_dir = tmp_path / "src" / "forms"
    form_dir.mkdir(parents=True)
    file_a = form_dir / "form_module.bsl"
    file_a.write_text("Процедура ПриОткрытии() Экспорт\nКонецПроцедуры\n", encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient()
    runner = _FakeRunner(
        matches=[
            AstGrepMatch(
                file=file_a,
                start_line=0,
                start_character=10,
                end_line=0,
                end_character=21,
            )
        ]
    )
    orch, _ = _make_orchestrator(tmp_path, lsp, runner)

    result = orch.rename(uri, 0, 10, "ПриЗагрузке", dry_run=True)

    assert result.symbol_kind == SymbolKind.FORM_HANDLER
    assert result.primary_backend == "ast-grep"
    assert result.fallback_used is False
    assert runner.calls == 1
    assert lsp.calls == 0


def test_local_variable_no_fallback_fails_hard(tmp_path: Path) -> None:
    """LOCAL_VARIABLE has no fallback in routing matrix; empty edit → all_backends_failed."""
    file_a = tmp_path / "module.bsl"
    content = "Перем СтарыйВар;\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(response=None)
    runner = _FakeRunner()
    orch, _ = _make_orchestrator(tmp_path, lsp, runner)

    with pytest.raises(BackendError) as exc_info:
        orch.rename(uri, 0, 5, "НовыйВар", dry_run=True, content=content)

    assert exc_info.value.code == "all_backends_failed"
    assert runner.calls == 0


def test_unknown_kind_routes_ast_grep_returns_manual(tmp_path: Path) -> None:
    """UNKNOWN → ast-grep primary, no fallback, manual_fallback=True → manual instruction."""
    file_a = tmp_path / "module.bsl"
    file_a.write_text("// просто комментарий\n", encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient()
    runner = _FakeRunner()
    orch, _ = _make_orchestrator(tmp_path, lsp, runner)

    result = orch.rename(uri, 0, 3, "X", dry_run=True, content=None)
    assert result.symbol_kind == SymbolKind.UNKNOWN
    assert result.reason == "manual_required"
    assert result.manual_instruction is not None
    assert result.manual_instruction.suggested_approach != ""
    assert runner.calls == 1
    assert lsp.calls == 0


def test_dry_run_returns_summary_and_token(tmp_path: Path) -> None:
    """Dry run returns confirm_token and leaves the file untouched."""
    file_a = tmp_path / "module.bsl"
    original = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(original, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch, _ = _make_orchestrator(tmp_path, lsp)

    result = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=original)

    assert result.applied is False
    assert result.rolled_back is False
    assert result.confirm_token is not None
    assert file_a.read_text(encoding="utf-8") == original


def test_apply_with_token_writes_file(tmp_path: Path) -> None:
    """Two-phase contract: dry_run produces token, apply with matching token writes."""
    file_a = tmp_path / "module.bsl"
    original = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(original, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch, _ = _make_orchestrator(tmp_path, lsp)

    plan = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=original)
    assert plan.confirm_token is not None

    lsp._response = _lsp_edit(uri, 0, 10, 16, "Новая")

    applied = orch.rename(
        uri,
        0,
        10,
        "Новая",
        dry_run=False,
        confirm_token=plan.confirm_token,
        content=original,
    )

    assert applied.applied is True
    assert applied.rolled_back is False
    text = file_a.read_text(encoding="utf-8")
    assert "Новая" in text
    assert "Старая" not in text


def test_apply_with_wrong_token_raises(tmp_path: Path) -> None:
    file_a = tmp_path / "module.bsl"
    original = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(original, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch, _ = _make_orchestrator(tmp_path, lsp)

    with pytest.raises(BackendError) as exc_info:
        orch.rename(
            uri,
            0,
            10,
            "Новая",
            dry_run=False,
            confirm_token="deadbeef",
            content=original,
        )
    assert exc_info.value.code == "token_mismatch"


def test_missing_primary_backend_raises(tmp_path: Path) -> None:
    """Routing points to unregistered backend → backend_missing."""
    applier = WorkspaceEditApplier(tmp_path)
    verifier = RenameVerifier(applier, lambda: [])
    orch = RefactorOrchestrator(
        backends={"ast-grep": AstGrepBackend(_FakeRunner(), tmp_path)},
        classifier=HeuristicClassifier(),
        verifier=verifier,
    )
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    with pytest.raises(BackendError) as exc_info:
        orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)
    assert exc_info.value.code == "backend_missing"


def test_both_backends_fail_raises(tmp_path: Path) -> None:
    """Primary raises, fallback raises → all_backends_failed."""
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(raise_exc=RuntimeError("lsp dead"))
    runner = _FakeRunner(raise_exc=RuntimeError("ast-grep dead"))
    orch, _ = _make_orchestrator(tmp_path, lsp, runner)

    with pytest.raises(BackendError) as exc_info:
        orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)
    assert exc_info.value.code == "all_backends_failed"


def test_fallback_empty_also_fails(tmp_path: Path) -> None:
    """Primary empty and fallback empty → all_backends_failed."""
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(response=None)
    runner = _FakeRunner(matches=[])
    orch, _ = _make_orchestrator(tmp_path, lsp, runner)

    with pytest.raises(BackendError) as exc_info:
        orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)
    assert exc_info.value.code == "all_backends_failed"


def test_confidence_matches_routing_matrix(tmp_path: Path) -> None:
    """Orchestrator result.confidence mirrors RoutingMatrix.route_for(kind).confidence."""
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch, _ = _make_orchestrator(tmp_path, lsp)

    result = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)
    expected = RoutingMatrix.route_for(SymbolKind.MODULE_EXPORT_PROC).confidence
    assert result.confidence == expected
