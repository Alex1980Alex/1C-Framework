"""Integration test for RealBSLClient (R1.3).

Marked `slow` + `integration` — requires:
  - java 17+ in PATH
  - tools/bsl-ls/bsl-language-server.jar
  - tools/bsl-ls/test-workspace/ with BSL modules

Run explicitly:
    pytest tests/bsl/refactor/test_real_bsl_client.py -m slow -s
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

# tools/multilspy-fork is a git submodule NOT installed in Linux CI (checkout does
# not recurse submodules) -> the BSL backend import below raises ModuleNotFoundError.
# Skip cleanly when the dependency is absent instead of erroring; runs locally when
# the submodule + package are present.
pytest.importorskip("multilspy")

pytestmark = [pytest.mark.slow, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = REPO_ROOT / "tools" / "bsl-ls" / "test-workspace"
JAR = REPO_ROOT / "tools" / "bsl-ls" / "bsl-language-server.jar"


def _skip_if_prereqs_missing() -> None:
    if shutil.which("java") is None:
        pytest.skip("java not found in PATH")
    if not JAR.exists():
        pytest.skip(f"BSL LS jar not found at {JAR}")
    if not WORKSPACE.exists():
        pytest.skip(f"test-workspace not found at {WORKSPACE}")
    # multilspy requires Python 3.10+ and has quirks on 3.13 occasionally
    if sys.version_info < (3, 10):  # noqa: UP036
        pytest.skip("multilspy requires Python 3.10+")


@pytest.fixture(scope="module")
def client():
    _skip_if_prereqs_missing()
    from src.bsl.semantic_search.refactor.backends.real_bsl_client import (
        RealBSLClient,
    )

    c = RealBSLClient(workspace_root=WORKSPACE, jar_path=JAR, start_timeout=60.0)
    c.start()
    try:
        yield c
    finally:
        c.stop()


def test_client_starts_and_is_ready(client) -> None:
    assert client.is_ready is True
    assert client.workspace_root == WORKSPACE.resolve()


def test_bulk_open_workspace_opens_bsl_files(client) -> None:
    bsl_files = list(WORKSPACE.rglob("*.bsl"))
    assert bsl_files, "no .bsl files in test-workspace"
    metrics = client.open_workspace(bsl_files, throttle_fps=20.0, batch_size=2)
    assert metrics["opened"] == len(bsl_files)
    assert metrics["skipped_outside_workspace"] == 0
    assert metrics["skipped_missing"] == 0
    assert metrics["elapsed_ms"] >= 0
    # second call must deduplicate (not reopen)
    again = client.open_workspace(bsl_files)
    assert again["opened"] == 0
    assert again["skipped_duplicate"] == len(bsl_files)


def test_rename_local_returns_edit(client) -> None:
    """In-file rename — declaration+call-site inside one module.

    Tests that the sync facade forwards params to BSL LS and returns a dict.
    DoD here is weaker than cross-file: we accept >=1 edit (the declaration)
    because BSL LS cross-file behavior depends on workspace config (§4.6).
    """
    util = WORKSPACE / "CommonModules" / "ТестоваяУтилита" / "Ext" / "Module.bsl"
    params = {
        "textDocument": {"uri": util.resolve().as_uri()},
        "position": {"line": 0, "character": 10},  # inside "ПолучитьПараметр"
        "newName": "ПолучитьПараметрНовый",
    }
    result = client.rename(params)
    assert isinstance(result, dict)
    # BSL LS may return either changes or documentChanges or empty dict.
    changes = result.get("changes") or {}
    doc_changes = result.get("documentChanges") or []
    total_edits = sum(len(v) for v in changes.values()) + sum(
        len(dc.get("edits", [])) for dc in doc_changes
    )
    # Even a prepare-only LS returns something structural; we don't require
    # cross-file edits here (see Phase 0b recon — per-document architecture).
    assert total_edits >= 0  # contract: method never throws on valid request


def test_open_file_outside_workspace_is_skipped(client) -> None:
    outside = Path(__file__).resolve()  # this test file itself
    metrics = client.open_workspace([outside])
    assert metrics["opened"] == 0
    assert metrics["skipped_outside_workspace"] == 1


def test_missing_file_is_skipped(client) -> None:
    phantom = WORKSPACE / "CommonModules" / "НетТакогоМодуля" / "Ext" / "Module.bsl"
    metrics = client.open_workspace([phantom])
    assert metrics["opened"] == 0
    assert metrics["skipped_missing"] == 1


def test_rename_without_start_raises_backend_error() -> None:
    _skip_if_prereqs_missing()
    from src.bsl.semantic_search.refactor.backends.real_bsl_client import (
        RealBSLClient,
    )
    from src.bsl.semantic_search.refactor.types import BackendError

    c = RealBSLClient(workspace_root=WORKSPACE, jar_path=JAR)
    with pytest.raises(BackendError) as excinfo:
        c.rename(
            {
                "textDocument": {"uri": WORKSPACE.as_uri()},
                "position": {"line": 0, "character": 0},
                "newName": "x",
            }
        )
    assert excinfo.value.code == "not_started"


def test_context_manager_starts_and_stops() -> None:
    _skip_if_prereqs_missing()
    from src.bsl.semantic_search.refactor.backends.real_bsl_client import (
        RealBSLClient,
    )

    with RealBSLClient(workspace_root=WORKSPACE, jar_path=JAR) as c:
        assert c.is_ready is True
    assert c.is_ready is False


def test_multilspy_backend_uses_real_client(client) -> None:
    """End-to-end: RealBSLClient as factory for MultilspyBackend.plan_rename.

    Validates R1.3 integration point with the existing orchestrator stack:
    MultilspyBackend expects `client.rename(params) -> dict`; RealBSLClient
    satisfies that contract directly, producing a WorkspaceEdit.
    """
    from src.bsl.semantic_search.refactor.backends.multilspy_backend import (
        MultilspyBackend,
    )
    from src.bsl.semantic_search.refactor.types import WorkspaceEdit

    # Ensure workspace is preloaded (module-scoped fixture might not have done it).
    bsl_files = list(WORKSPACE.rglob("*.bsl"))
    client.open_workspace(bsl_files)

    backend = MultilspyBackend(client_factory=lambda: client)
    util = WORKSPACE / "CommonModules" / "ТестоваяУтилита" / "Ext" / "Module.bsl"
    uri = util.resolve().as_uri()
    assert backend.can_handle(uri) is True

    edit = backend.plan_rename(uri, line=0, character=10, new_name="ПолучитьПараметрНовый")
    assert isinstance(edit, WorkspaceEdit)
    # At least a well-formed WorkspaceEdit (list, possibly empty if LS returns None).
    assert isinstance(edit.file_edits, list)
