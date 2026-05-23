from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.bsl.semantic_search.refactor import (
    AstGrepBackend,
    AstGrepMatch,
    HeuristicClassifier,
    MultilspyBackend,
    RefactorOrchestrator,
    RenameVerifier,
    SymbolKind,
    WorkspaceEditApplier,
)
from src.bsl.semantic_search.refactor.telemetry import JsonlTelemetryWriter
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


def _lsp_edit(uri, line, start_col, end_col, new_name):
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
    workspace, lsp_client=None, runner=None, error_provider=lambda: [], telemetry=None
):
    multilspy = MultilspyBackend(lambda: lsp_client or _StubLspClient())
    astgrep = AstGrepBackend(runner or _FakeRunner(), workspace)
    applier = WorkspaceEditApplier(workspace)
    verifier = RenameVerifier(applier, error_provider)
    return RefactorOrchestrator(
        backends={"multilspy": multilspy, "ast-grep": astgrep},
        classifier=HeuristicClassifier(),
        verifier=verifier,
        telemetry=telemetry,
    )


def _read_events(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines]


def test_telemetry_emits_on_primary_success(tmp_path):
    log_file = tmp_path / "tel.jsonl"
    tw = JsonlTelemetryWriter(log_file, rotate_daily=False)
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch = _make_orchestrator(tmp_path, lsp_client=lsp, telemetry=tw)
    orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)

    events = _read_events(log_file)
    assert len(events) == 1
    e = events[0]
    assert e["primary_backend"] == "multilspy"
    assert e["fallback_used"] is False
    assert e["applied"] is False
    assert e["error_code"] is None
    assert e["symbol_kind"] == "module_export_proc"
    assert e["duration_ms"] >= 0


def test_telemetry_emits_on_fallback_success(tmp_path):
    log_file = tmp_path / "tel.jsonl"
    tw = JsonlTelemetryWriter(log_file, rotate_daily=False)
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(raise_exc=RuntimeError("lsp dead"))
    runner = _FakeRunner(
        matches=[
            AstGrepMatch(
                file=file_a, start_line=0, start_character=10, end_line=0, end_character=16
            )
        ]
    )
    orch = _make_orchestrator(tmp_path, lsp_client=lsp, runner=runner, telemetry=tw)
    orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)

    events = _read_events(log_file)
    assert len(events) == 1
    assert events[0]["fallback_used"] is True
    assert events[0]["primary_backend"] == "ast-grep"


def test_telemetry_emits_on_all_failed(tmp_path):
    log_file = tmp_path / "tel.jsonl"
    tw = JsonlTelemetryWriter(log_file, rotate_daily=False)
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(raise_exc=RuntimeError("dead"))
    runner = _FakeRunner(raise_exc=RuntimeError("dead"))
    orch = _make_orchestrator(tmp_path, lsp_client=lsp, runner=runner, telemetry=tw)

    with pytest.raises(BackendError):
        orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)

    events = _read_events(log_file)
    assert len(events) == 1
    assert events[0]["error_code"] == "all_backends_failed"


def test_telemetry_emits_on_applied(tmp_path):
    log_file = tmp_path / "tel.jsonl"
    tw = JsonlTelemetryWriter(log_file, rotate_daily=False)
    file_a = tmp_path / "module.bsl"
    original = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(original, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch = _make_orchestrator(tmp_path, lsp_client=lsp, telemetry=tw)

    plan = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=original)
    lsp._response = _lsp_edit(uri, 0, 10, 16, "Новая")
    orch.rename(
        uri, 0, 10, "Новая", dry_run=False, confirm_token=plan.confirm_token, content=original
    )

    events = _read_events(log_file)
    apply_event = events[1]
    assert apply_event["applied"] is True
    assert apply_event["rolled_back"] is False
    assert apply_event["token_matched"] is True


def test_telemetry_emits_on_rolled_back(tmp_path):
    log_file = tmp_path / "tel.jsonl"
    tw = JsonlTelemetryWriter(log_file, rotate_daily=False)
    file_a = tmp_path / "module.bsl"
    original = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(original, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    call_count = [0]

    def growing_errors():
        call_count[0] += 1
        return ["err"] * call_count[0]

    orch = _make_orchestrator(tmp_path, lsp_client=lsp, error_provider=growing_errors, telemetry=tw)

    plan = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=original)
    lsp._response = _lsp_edit(uri, 0, 10, 16, "Новая")
    orch.rename(
        uri, 0, 10, "Новая", dry_run=False, confirm_token=plan.confirm_token, content=original
    )

    events = _read_events(log_file)
    apply_event = events[1]
    assert apply_event["rolled_back"] is True


def test_telemetry_emits_on_token_mismatch(tmp_path):
    log_file = tmp_path / "tel.jsonl"
    tw = JsonlTelemetryWriter(log_file, rotate_daily=False)
    file_a = tmp_path / "module.bsl"
    original = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(original, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch = _make_orchestrator(tmp_path, lsp_client=lsp, telemetry=tw)

    with pytest.raises(BackendError):
        orch.rename(uri, 0, 10, "Новая", dry_run=False, confirm_token="bad", content=original)

    events = _read_events(log_file)
    assert len(events) == 1
    assert events[0]["error_code"] == "token_mismatch"


def test_telemetry_event_includes_version_field(tmp_path):
    log_file = tmp_path / "tel.jsonl"
    tw = JsonlTelemetryWriter(log_file, rotate_daily=False)
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch = _make_orchestrator(tmp_path, lsp_client=lsp, telemetry=tw)
    orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)

    events = _read_events(log_file)
    assert events[0]["version"] == 1
    # old_name extracted from content at the cursor
    assert events[0]["old_name"] == "Старая"
    # matrix_confidence from RoutingMatrix (0.95 for export proc)
    # classifier_confidence = 1.0 (content-based, kind != UNKNOWN)
    assert events[0]["matrix_confidence"] == pytest.approx(0.95)
    assert events[0]["classifier_confidence"] == pytest.approx(1.0)


def test_telemetry_gzips_old_rotated_files(tmp_path):
    import gzip

    base = tmp_path / "tel.jsonl"
    old_file = tmp_path / "tel-2025-01-01.jsonl"
    old_file.write_text('{"stale":1}\n', encoding="utf-8")
    recent_file = tmp_path / f"tel-{_today_utc()}.jsonl"
    recent_file.write_text('{"fresh":1}\n', encoding="utf-8")

    JsonlTelemetryWriter(base, compress_after_days=30)

    assert not old_file.exists(), "stale file should have been compressed away"
    gz = tmp_path / "tel-2025-01-01.jsonl.gz"
    assert gz.exists()
    with gzip.open(gz, "rt", encoding="utf-8") as fh:
        assert fh.read() == '{"stale":1}\n'
    # recent file untouched
    assert recent_file.exists()


def _today_utc() -> str:
    from datetime import datetime, timezone

    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")  # noqa: UP017


def test_telemetry_none_noop(tmp_path):
    file_a = tmp_path / "module.bsl"
    content = "Процедура Старая() Экспорт\nКонецПроцедуры\n"
    file_a.write_text(content, encoding="utf-8")
    uri = _file_uri(file_a)

    lsp = _StubLspClient(_lsp_edit(uri, 0, 10, 16, "Новая"))
    orch = _make_orchestrator(tmp_path, lsp_client=lsp, telemetry=None)
    result = orch.rename(uri, 0, 10, "Новая", dry_run=True, content=content)
    assert result.ok is False
    assert result.symbol_kind == SymbolKind.MODULE_EXPORT_PROC
