from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_ROOT = _REPO_ROOT / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))


def _lazy_import_types():  # noqa: ANN202
    from bsl.semantic_search.refactor.types import BackendError, WorkspaceEdit

    return BackendError, WorkspaceEdit


class RenameBackendProto(Protocol):
    def plan_rename(self, uri: str, line: int, character: int, new_name: str) -> Any: ...
    def can_handle(self, uri: str) -> bool: ...


@dataclass(slots=True)
class TaskResult:
    task_id: str
    backend: str
    applied: bool
    rolled_back: bool
    files_affected: int
    files_match_expected: bool
    edits_match_expected: bool
    duration_ms_plan: int
    duration_ms_apply: int
    error_code: str | None
    fallback_used: bool
    manual_required: bool
    classifier_confidence: float
    matrix_confidence: float
    actual_files: list[str]
    expected_files: list[str]


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


class WorktreeManager:
    """Manages isolated git worktrees for benchmark tasks."""

    def __init__(self, repo_root: Path, base_tmp: Path | None = None) -> None:
        self._repo_root = repo_root.resolve()
        self._base_tmp = (base_tmp or Path(tempfile.gettempdir())).resolve()
        self._active_worktrees: list[Path] = []
        import atexit

        atexit.register(self._cleanup_all)

    def _run_git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self._repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_git_env(),
        )

    def create(self, parent_sha: str, task_id: str, backend: str) -> Path:
        if not re.fullmatch(r"[0-9a-fA-F]{4,40}", parent_sha):
            raise ValueError(f"Invalid git SHA: {parent_sha!r}")
        worktree_path = self._base_tmp / f"wt_{task_id}_{backend}"
        res = self._run_git("worktree", "add", "--detach", str(worktree_path), parent_sha)
        if res.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {res.stderr.strip()}")
        self._active_worktrees.append(worktree_path)
        return worktree_path

    def cleanup(self, worktree_path: Path) -> None:
        for attempt in range(3):
            res = self._run_git("worktree", "remove", "--force", str(worktree_path))
            if res.returncode == 0 or not worktree_path.exists():
                break
            time.sleep(0.5 * (2**attempt))

        if worktree_path.exists():
            for attempt in range(3):
                try:
                    shutil.rmtree(worktree_path)
                    break
                except PermissionError:
                    if attempt == 2:
                        raise
                    time.sleep(0.5 * (2**attempt))

        if worktree_path in self._active_worktrees:
            self._active_worktrees.remove(worktree_path)
        if not self._active_worktrees:
            self._run_git("worktree", "prune")

    def _cleanup_all(self) -> None:
        for wt in list(self._active_worktrees):
            try:
                self.cleanup(wt)
            except Exception:  # noqa: BLE001
                pass


class TaskExecutor:
    """Executes a single benchmark task inside a worktree."""

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root.resolve()

    def run(self, task: dict, backend: RenameBackendProto, worktree_path: Path) -> TaskResult:
        BackendError, _ = _lazy_import_types()
        task_id = task["id"]
        file_uri = task["file_uri"]
        line = task["line"]
        char = task["character"]
        new_name = task["new_name"]
        expected_files = sorted(task.get("expected_files", []))

        abs_file = worktree_path / file_uri
        resolved_uri = f"file:///{abs_file.as_posix()}"

        error_code: str | None = None
        applied = False
        files_affected = 0
        actual_files: list[str] = []
        duration_ms_plan = 0
        files_match_expected = False
        edits_match_expected = False

        try:
            t0 = time.perf_counter()
            edit = backend.plan_rename(resolved_uri, line, char, new_name)
            t1 = time.perf_counter()
            duration_ms_plan = int((t1 - t0) * 1000)

            applied = bool(edit.file_edits)
            files_affected = len(edit.file_edits)

            for fe in edit.file_edits:
                uri_norm = fe.uri.replace("\\", "/")
                wt_prefix = worktree_path.as_posix()
                if uri_norm.startswith(wt_prefix):
                    uri_norm = uri_norm[len(wt_prefix) :].lstrip("/")
                if uri_norm.startswith("file:///"):
                    uri_norm = uri_norm[8:]
                actual_files.append(uri_norm)

            actual_files = sorted(set(actual_files))
            files_match_expected = actual_files == expected_files

            if not expected_files and not edit.file_edits:
                edits_match_expected = True
            elif files_match_expected and edit.file_edits:
                edits_match_expected = True

        except BackendError as exc:
            error_code = exc.code or "UNKNOWN"
        except Exception:  # noqa: BLE001
            error_code = "UNHANDLED"

        return TaskResult(
            task_id=task_id,
            backend=type(backend).__name__,
            applied=applied,
            rolled_back=False,
            files_affected=files_affected,
            files_match_expected=files_match_expected,
            edits_match_expected=edits_match_expected,
            duration_ms_plan=duration_ms_plan,
            duration_ms_apply=0,
            error_code=error_code,
            fallback_used=False,
            manual_required=not applied and bool(error_code),
            classifier_confidence=0.0,
            matrix_confidence=0.0,
            actual_files=actual_files,
            expected_files=expected_files,
        )


def _percentile(sorted_vals: list[int], pct: float) -> int:
    if not sorted_vals:
        return 0
    idx = (pct / 100.0) * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return int(sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo]))


class ReportBuilder:
    """Aggregates results and renders Markdown / CSV reports."""

    def aggregate(self, results: list[TaskResult], tasks: list[dict] | None = None) -> dict:
        tasks = tasks or []
        task_cat_map = {t["id"]: t.get("category", "uncategorized") for t in tasks}

        backend_stats: dict[str, dict[str, Any]] = {}
        per_category: dict[str, dict[str, list[bool]]] = {}
        failure_taxonomy: dict[str, list[str]] = {}

        for r in results:
            b = r.backend
            if b not in backend_stats:
                backend_stats[b] = {"total": 0, "applied": 0, "rolled_back": 0, "durations": []}
            bs = backend_stats[b]
            bs["total"] += 1
            if r.applied:
                bs["applied"] += 1
            if r.rolled_back:
                bs["rolled_back"] += 1
            bs["durations"].append(r.duration_ms_plan)

            cat = task_cat_map.get(r.task_id, "uncategorized")
            per_category.setdefault(cat, {}).setdefault(b, []).append(r.applied)

            if not r.applied or r.error_code is not None:
                failure_taxonomy.setdefault(b, []).append(r.task_id)

        per_backend: dict[str, dict[str, Any]] = {}
        for b, bs in backend_stats.items():
            total = max(bs["total"], 1)
            durations = sorted(bs["durations"])
            per_backend[b] = {
                "success_rate": bs["applied"] / total,
                "rollback_rate": bs["rolled_back"] / total,
                "avg_duration_ms": sum(bs["durations"]) / total if durations else 0,
                "p50": _percentile(durations, 50),
                "p95": _percentile(durations, 95),
                "p99": _percentile(durations, 99),
            }

        per_category_summary: dict[str, dict[str, float]] = {}
        for cat, backends in per_category.items():
            per_category_summary[cat] = {}
            for b, outcomes in backends.items():
                per_category_summary[cat][b] = sum(outcomes) / len(outcomes) if outcomes else 0.0

        return {
            "per_backend": per_backend,
            "per_category": per_category_summary,
            "failure_taxonomy": failure_taxonomy,
        }

    def render_markdown(self, results: list[TaskResult], tasks: list[dict], run_id: str) -> str:
        agg = self.aggregate(results, tasks)
        lines: list[str] = [
            f"# Benchmark Report - {run_id}",
            "",
            f"**Tasks:** {len(tasks)} | **Results:** {len(results)}",
            "",
            "## Per-Backend Summary",
            "",
            "| Backend | Success | Rollback | p50 ms | p95 ms | p99 ms |",
            "|---------|---------|----------|--------|--------|--------|",
        ]
        for b, s in agg["per_backend"].items():
            lines.append(
                f"| {b} | {s['success_rate']:.1%} | {s['rollback_rate']:.1%} "
                f"| {s['p50']} | {s['p95']} | {s['p99']} |"
            )
        lines.append("")

        if agg["per_category"]:
            lines += ["## Per-Category Success Rate", ""]
            all_b = sorted({b for c in agg["per_category"].values() for b in c})
            lines.append("| Category | " + " | ".join(all_b) + " |")
            lines.append("|----------|" + "|".join(["--------"] * len(all_b)) + "|")
            for cat in sorted(agg["per_category"]):
                row = f"| {cat} "
                for b in all_b:
                    row += f"| {agg['per_category'][cat].get(b, 0.0):.1%} "
                lines.append(row + "|")
            lines.append("")

        if agg["failure_taxonomy"]:
            lines += ["## Failure Taxonomy", ""]
            for b, tids in agg["failure_taxonomy"].items():
                lines.append(f"### {b}")
                for tid in tids:
                    lines.append(f"- {tid}")
                lines.append("")

        return "\n".join(lines)

    def render_csv(self, results: list[TaskResult], tasks: list[dict] | None = None) -> str:
        tasks = tasks or []
        cat_map = {t["id"]: t.get("category", "") for t in tasks}
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "task_id",
                "category",
                "backend",
                "applied",
                "rolled_back",
                "duration_ms_plan",
                "duration_ms_apply",
                "files_match_expected",
                "error_code",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.task_id,
                    cat_map.get(r.task_id, ""),
                    r.backend,
                    r.applied,
                    r.rolled_back,
                    r.duration_ms_plan,
                    r.duration_ms_apply,
                    r.files_match_expected,
                    r.error_code or "",
                ]
            )
        return buf.getvalue()


class BenchmarkRunner:
    """End-to-end benchmark: worktrees + execution + reporting."""

    def __init__(self, repo_root: Path, tasks_path: Path, output_dir: Path) -> None:
        self._repo_root = repo_root.resolve()
        self._tasks_path = tasks_path.resolve()
        self._output_dir = output_dir.resolve()
        self._wt_mgr = WorktreeManager(self._repo_root)
        self._executor = TaskExecutor(self._repo_root)
        self._reporter = ReportBuilder()

    def run(
        self,
        backends: dict[str, RenameBackendProto],
        run_id: str,
        categories: list[str] | None = None,
        task_ids: list[str] | None = None,
    ) -> list[TaskResult]:
        self._output_dir.mkdir(parents=True, exist_ok=True)

        with open(self._tasks_path, encoding="utf-8") as fh:
            dataset = json.load(fh)
        tasks: list[dict] = dataset.get("tasks", [])

        if categories is not None:
            cat_set = set(categories)
            tasks = [t for t in tasks if t.get("category") in cat_set]
        if task_ids is not None:
            tid_set = set(task_ids)
            tasks = [t for t in tasks if t["id"] in tid_set]

        results: list[TaskResult] = []
        jsonl_path = self._output_dir / f"{run_id}.jsonl"

        with open(jsonl_path, "a", encoding="utf-8") as jsonl_fh:
            for backend_name, backend_instance in backends.items():
                for task in tasks:
                    tid = task["id"]
                    parent_sha = task.get("parent_sha", "HEAD")

                    worktree_path: Path | None = None
                    try:
                        if parent_sha == "synthetic":
                            worktree_path = self._repo_root
                        else:
                            worktree_path = self._wt_mgr.create(parent_sha, tid, backend_name)

                        tr = self._executor.run(task, backend_instance, worktree_path)

                        event = {
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "uri": task["file_uri"],
                            "symbol_kind": task.get("category", "unknown"),
                            "old_name": task.get("old_name"),
                            "new_name": task["new_name"],
                            "primary_backend": backend_name,
                            "fallback_used": tr.fallback_used,
                            "applied": tr.applied,
                            "rolled_back": tr.rolled_back,
                            "duration_ms": tr.duration_ms_plan,
                            "error_code": tr.error_code,
                            "classifier_confidence": tr.classifier_confidence,
                            "matrix_confidence": tr.matrix_confidence,
                            "version": 1,
                        }
                        jsonl_fh.write(json.dumps(event, ensure_ascii=False) + "\n")
                        jsonl_fh.flush()

                    except Exception as exc:  # noqa: BLE001
                        tr = TaskResult(
                            task_id=tid,
                            backend=backend_name,
                            applied=False,
                            rolled_back=False,
                            files_affected=0,
                            files_match_expected=False,
                            edits_match_expected=False,
                            duration_ms_plan=0,
                            duration_ms_apply=0,
                            error_code=f"RUNNER_ERROR:{exc}",
                            fallback_used=False,
                            manual_required=True,
                            classifier_confidence=0.0,
                            matrix_confidence=0.0,
                            actual_files=[],
                            expected_files=task.get("expected_files", []),
                        )
                    finally:
                        if worktree_path is not None and parent_sha != "synthetic":
                            try:
                                self._wt_mgr.cleanup(worktree_path)
                            except Exception:  # noqa: BLE001
                                pass

                    results.append(tr)

        md = self._reporter.render_markdown(results, tasks, run_id)
        (self._output_dir / f"{run_id}_report.md").write_text(md, encoding="utf-8")
        csv_text = self._reporter.render_csv(results, tasks)
        (self._output_dir / f"{run_id}_report.csv").write_text(csv_text, encoding="utf-8")

        return results
