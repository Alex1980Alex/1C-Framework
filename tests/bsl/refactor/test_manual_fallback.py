from __future__ import annotations

from pathlib import Path

import pytest

from src.bsl.semantic_search.refactor import (
    AstGrepBackend,
    HeuristicClassifier,
    ManualFallbackInstruction,
    MultilspyBackend,
    RefactorOrchestrator,
    RenameVerifier,
    SymbolKind,
    WorkspaceEditApplier,
)
from src.bsl.semantic_search.refactor.types import BackendError


class _StubLspClient:
    def __init__(self, response=None, raise_exc=None):
        self._response = response
        self._raise = raise_exc

    def rename(self, params):
        if self._raise:
            raise self._raise
        return self._response


class _FakeRunner:
    def __init__(self, matches=None, raise_exc=None):
        self._matches = list(matches) if matches else []
        self._raise = raise_exc

    def run_rename(self, workspace_root, old_name, new_name):
        if self._raise:
            raise self._raise
        return list(self._matches)


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _make_orchestrator(tmp_path, lsp_client=None, runner=None):
    multilspy = MultilspyBackend(lambda: lsp_client or _StubLspClient())
    astgrep = AstGrepBackend(runner or _FakeRunner(), tmp_path)
    applier = WorkspaceEditApplier(tmp_path)
    verifier = RenameVerifier(applier, lambda: [])
    return RefactorOrchestrator(
        backends={"multilspy": multilspy, "ast-grep": astgrep},
        classifier=HeuristicClassifier(),
        verifier=verifier,
    )


def test_manual_fallback_returned_when_both_backends_fail(tmp_path):
    file_a = tmp_path / "forms" / "form_module.bsl"
    file_a.parent.mkdir(parents=True)
    file_a.write_text("Процедура ПриОткрытии() Экспорт\nКонецПроцедуры\n", encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(raise_exc=RuntimeError("lsp dead"))
    runner = _FakeRunner(raise_exc=RuntimeError("ast dead"))
    orch = _make_orchestrator(tmp_path, lsp, runner)

    result = orch.rename(uri, 0, 10, "ПриЗагрузке", dry_run=True)
    assert result.reason == "manual_required"
    assert result.manual_instruction is not None
    assert isinstance(result.manual_instruction, ManualFallbackInstruction)
    assert result.manual_instruction.symbol_kind == SymbolKind.FORM_HANDLER
    assert result.manual_instruction.new_name == "ПриЗагрузке"


def test_manual_fallback_disabled_still_raises_backend_error(tmp_path):
    file_a = tmp_path / "module.bsl"
    content = "Перем СтарыйВар;\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(response=None)
    runner = _FakeRunner()
    orch = _make_orchestrator(tmp_path, lsp, runner)

    with pytest.raises(BackendError) as exc_info:
        orch.rename(uri, 0, 5, "НовыйВар", dry_run=True, content=content)
    assert exc_info.value.code == "all_backends_failed"


def test_manual_instruction_includes_suggested_approach_per_kind(tmp_path):
    file_a = tmp_path / "forms" / "form.bsl"
    file_a.parent.mkdir(parents=True)
    file_a.write_text("Процедура ПриОткрытии() Экспорт\nКонецПроцедуры\n", encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(raise_exc=RuntimeError("dead"))
    runner = _FakeRunner(matches=[])
    orch = _make_orchestrator(tmp_path, lsp, runner)

    result = orch.rename(uri, 0, 10, "ПриЗагрузке", dry_run=True)
    assert result.manual_instruction is not None
    assert (
        "Grep" in result.manual_instruction.suggested_approach
        or "EDT" in result.manual_instruction.suggested_approach
    )
    assert len(result.manual_instruction.warnings) > 0


def test_mcp_rename_surfaces_manual_instruction(tmp_path):
    """Real MCP handler must serialize manual_instruction + status='manual_required'."""
    from src.bsl.semantic_search.mcp import (
        bsl_rename_symbol,
        register_rename_driver_factory,
    )

    file_a = tmp_path / "forms" / "form.bsl"
    file_a.parent.mkdir(parents=True)
    file_a.write_text("Процедура ПриОткрытии() Экспорт\nКонецПроцедуры\n", encoding="utf-8")
    uri = _file_uri(file_a)

    def factory():
        return _make_orchestrator(
            tmp_path,
            lsp_client=_StubLspClient(raise_exc=RuntimeError("dead")),
            runner=_FakeRunner(matches=[]),
        )

    register_rename_driver_factory(factory)
    try:
        result = bsl_rename_symbol(
            uri=uri, line=0, character=10, new_name="ПриЗагрузке", dry_run=True
        )
    finally:
        register_rename_driver_factory(None)

    assert result["status"] == "manual_required"
    assert result["reason"] == "manual_required"
    mi = result["manual_instruction"]
    assert mi["uri"] == uri
    assert mi["new_name"] == "ПриЗагрузке"
    assert mi["symbol_kind"] == SymbolKind.FORM_HANDLER.value
    assert mi["rationale"]
    assert isinstance(mi["warnings"], list)
    assert isinstance(mi["suggested_approach"], str)
