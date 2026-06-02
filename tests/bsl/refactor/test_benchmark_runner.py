import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "docs" / "roadmap"))

import pytest  # noqa: I001

from benchmark.runner import (
    BenchmarkRunner,
    ReportBuilder,
    TaskExecutor,
    TaskResult,
    WorktreeManager,
)

# Namespace collision: tests/bsl/__init__.py shadows src/bsl/.
# Force-load src/bsl/ into sys.modules as 'bsl' before importing types.
import importlib

_bsl_pkg = importlib.import_module("src.bsl")
sys.modules["bsl"] = _bsl_pkg

from bsl.semantic_search.refactor.types import (
    BackendError,
    FileEdit,
    Position,
    Range,
    TextEdit,
    WorkspaceEdit,
)


class MockBackend:
    def __init__(self, edit=None, error=None):
        self._edit = edit or WorkspaceEdit()
        self._error = error

    def can_handle(self, uri):
        return True

    def plan_rename(self, uri, line, char, new_name):
        if self._error:
            raise self._error
        return self._edit


def _task(task_id="T01", **kw):
    defaults = dict(
        id=task_id,
        file_uri="test.bsl",
        line=0,
        character=0,
        new_name="Foo",
        expected_files=[],
        parent_sha="synthetic",
        category="CAT-1-local-variable",
        commit_sha="synthetic",
        old_name="Bar",
        expected_files_affected=0,
        expected_edits=0,
        notes="test",
    )
    defaults.update(kw)
    return defaults


def _edit_single(uri="test.bsl"):
    return WorkspaceEdit(
        file_edits=[
            FileEdit(
                uri=uri,
                edits=[
                    TextEdit(
                        range=Range(
                            start=Position(line=0, character=0), end=Position(line=0, character=3)
                        ),
                        new_text="Foo",
                    )
                ],
            )
        ]
    )


def _result(**kw):
    defaults = dict(
        task_id="T01",
        backend="mock",
        applied=False,
        rolled_back=False,
        files_affected=0,
        files_match_expected=False,
        edits_match_expected=False,
        duration_ms_plan=0,
        duration_ms_apply=0,
        error_code=None,
        fallback_used=False,
        manual_required=False,
        classifier_confidence=0.0,
        matrix_confidence=0.0,
        actual_files=[],
        expected_files=[],
    )
    defaults.update(kw)
    return TaskResult(**defaults)


class TestTaskExecutor:
    def test_processes_single_task(self, tmp_path):
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "test.bsl").write_text("Процедура Тест()\nКонецПроцедуры", encoding="utf-8")

        backend = MockBackend(edit=_edit_single())
        executor = TaskExecutor(repo_root=tmp_path)
        result = executor.run(_task(), backend, worktree)

        assert result.applied is True
        assert result.files_affected == 1
        assert result.error_code is None

    def test_handles_backend_error(self, tmp_path):
        worktree = tmp_path / "wt"
        worktree.mkdir()
        (worktree / "test.bsl").write_text("content", encoding="utf-8")

        backend = MockBackend(error=BackendError("fail", code="test_err"))
        executor = TaskExecutor(repo_root=tmp_path)
        result = executor.run(_task(), backend, worktree)

        assert result.applied is False
        assert result.error_code == "test_err"


class TestWorktreeManager:
    def test_worktree_isolation(self, tmp_path):
        try:
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                capture_output=True,
                check=True,
                cwd=REPO_ROOT,
            )
        except Exception:
            pytest.skip("Not in a git repo")

        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            encoding="utf-8",
        ).strip()

        mgr = WorktreeManager(repo_root=REPO_ROOT, base_tmp=tmp_path)
        wt1 = mgr.create(sha, "T01", "mock")
        wt2 = mgr.create(sha, "T02", "mock")

        assert wt1 != wt2
        assert wt1.is_dir()
        assert wt2.is_dir()

        mgr.cleanup(wt1)
        mgr.cleanup(wt2)
        assert not wt1.exists()
        assert not wt2.exists()


class TestReportBuilder:
    def test_markdown_contains_backends(self):
        builder = ReportBuilder()
        results = [
            _result(task_id="T01", backend="ast-grep", applied=True),
            _result(task_id="T02", backend="multilspy", applied=False, error_code="fail"),
        ]
        md = builder.render_markdown(results, [_task(task_id="T01"), _task(task_id="T02")], "run-1")

        assert "ast-grep" in md
        assert "multilspy" in md
        assert "run-1" in md
        assert "Per-Backend" in md

    def test_csv_has_header_and_rows(self):
        builder = ReportBuilder()
        results = [
            _result(task_id="T01", backend="ast-grep", applied=True),
            _result(task_id="T02", backend="multilspy", applied=False),
        ]
        csv_text = builder.render_csv(results, [_task(task_id="T01"), _task(task_id="T02")])
        lines = csv_text.strip().split("\n")

        assert len(lines) == 3  # header + 2 data rows
        assert "task_id" in lines[0]
        assert "backend" in lines[0]
        assert "ast-grep" in lines[1]
        assert "multilspy" in lines[2]


class TestBenchmarkRunner:
    def test_synthetic_sha_uses_repo_root(self, tmp_path):
        (tmp_path / "test.bsl").write_text("content", encoding="utf-8")
        tasks_file = tmp_path / "tasks.json"
        tasks_file.write_text(json.dumps({"version": 1, "tasks": [_task()]}))
        output_dir = tmp_path / "out"

        runner = BenchmarkRunner(tmp_path, tasks_file, output_dir)
        results = runner.run(
            backends={"mock": MockBackend(edit=_edit_single())},
            run_id="test-synthetic",
        )
        assert len(results) == 1
        assert results[0].task_id == "T01"
