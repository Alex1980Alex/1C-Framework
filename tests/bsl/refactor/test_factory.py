from __future__ import annotations

from pathlib import Path

import pytest

from src.bsl.semantic_search.refactor.backends.ast_grep_backend import (
    AstGrepBackend,
    AstGrepMatch,
)
from src.bsl.semantic_search.refactor.backends.factory import (
    PREFILTER_DISABLE_ENV,
    build_ast_grep_backend,
)


class _FakeRunner:
    def run_rename(
        self, workspace_root: Path, old_name: str, new_name: str
    ) -> list[AstGrepMatch]:
        return []


def test_factory_no_prefilter_when_flag_off(tmp_path: Path) -> None:
    backend = build_ast_grep_backend(
        runner=_FakeRunner(),
        workspace_root=tmp_path,
        config={"use_call_graph_prefilter": False},
        env={},
    )
    assert isinstance(backend, AstGrepBackend)
    assert backend._prefilter is None


def test_factory_env_disables_prefilter(tmp_path: Path) -> None:
    # cache file exists, flag ON, but env kill-switch should win
    cg_db = tmp_path / "cg.db"
    cg_db.write_bytes(b"")
    backend = build_ast_grep_backend(
        runner=_FakeRunner(),
        workspace_root=tmp_path,
        project_root=tmp_path,
        config={
            "use_call_graph_prefilter": True,
            "call_graph_db": "cg.db",
        },
        env={PREFILTER_DISABLE_ENV: "1"},
    )
    assert backend._prefilter is None


def test_factory_missing_db_falls_back_no_prefilter(tmp_path: Path) -> None:
    backend = build_ast_grep_backend(
        runner=_FakeRunner(),
        workspace_root=tmp_path,
        project_root=tmp_path,
        config={
            "use_call_graph_prefilter": True,
            "call_graph_db": "does-not-exist.db",
        },
        env={},
    )
    assert backend._prefilter is None


def test_factory_builds_prefilter_when_db_exists(tmp_path: Path) -> None:
    # Build a real CallGraphStore DB to satisfy schema init
    from src.bsl.call_graph.store import CallGraphStore

    cg_db = tmp_path / "cg.db"
    CallGraphStore(str(cg_db))  # initializes schema

    backend = build_ast_grep_backend(
        runner=_FakeRunner(),
        workspace_root=tmp_path,
        project_root=tmp_path,
        config={
            "use_call_graph_prefilter": True,
            "call_graph_db": "cg.db",
        },
        env={},
    )
    assert backend._prefilter is not None


def test_factory_uses_routing_matrix_when_config_none(tmp_path: Path) -> None:
    from src.bsl.semantic_search.refactor.classifier import RoutingMatrix

    RoutingMatrix.reset()
    try:
        # default _AST_GREP_GLOBAL has use_call_graph_prefilter=False → no prefilter
        backend = build_ast_grep_backend(
            runner=_FakeRunner(),
            workspace_root=tmp_path,
            project_root=tmp_path,
            env={},
        )
        assert backend._prefilter is None
    finally:
        RoutingMatrix.reset()
