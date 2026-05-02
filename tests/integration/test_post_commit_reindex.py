"""Unit tests for scripts/git_post_commit_reindex.py.

Covers: _bsl_project_root, _split_bsl_and_framework, _changed_files, main().
Uses importlib.util to load the script since scripts/ has no __init__.py.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "git_post_commit_reindex",
    str(SCRIPTS_DIR / "git_post_commit_reindex.py"),
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_file(root: Path, rel: str, size: int = 100) -> None:
    p = root / Path(rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """Patch REPO_ROOT to tmp_path so path checks use temp files."""
    monkeypatch.setattr(mod, "REPO_ROOT", tmp_path, raising=False)
    return tmp_path


# ---------------------------------------------------------------------------
# _bsl_project_root
# ---------------------------------------------------------------------------


class TestBslProjectRoot:
    def test_valid_path_returns_project_root(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path, raising=False)
        result = mod._bsl_project_root(
            "configuration/MyProject/Documents/Doc.bsl"
        )
        assert result is not None
        assert result.name == "MyProject"

    def test_nested_file_still_returns_project_root(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path, raising=False)
        result = mod._bsl_project_root(
            "configuration/ProjX/Sub/Deep/Module.bsl"
        )
        assert result is not None
        assert result.name == "ProjX"

    def test_no_configuration_segment_returns_none(self):
        assert mod._bsl_project_root("src/bsl/CommonModule.bsl") is None

    def test_configuration_is_last_part_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "REPO_ROOT", tmp_path, raising=False)
        # No project name after configuration
        assert mod._bsl_project_root("configuration") is None

    def test_configuration_not_preceded_by_projects_returns_none(self):
        # "other" instead of "projects"
        assert (
            mod._bsl_project_root(
                "src/other/configuration/MyProject/File.bsl"
            )
            is None
        )

    def test_framework_path_returns_none(self):
        assert mod._bsl_project_root("src/framework_search/config.py") is None


# ---------------------------------------------------------------------------
# _split_bsl_and_framework
# ---------------------------------------------------------------------------


class TestSplitBslAndFramework:
    def test_py_file_goes_to_framework(self, repo):
        _make_file(repo, "src/framework_search/utils.py")
        fw, bsl = mod._split_bsl_and_framework(["src/framework_search/utils.py"])
        assert "src/framework_search/utils.py" in fw
        assert bsl == []

    def test_bsl_under_config_goes_to_bsl_groups(self, repo):
        rel = "configuration/MyProj/Documents/Doc.bsl"
        _make_file(repo, rel)
        fw, bsl = mod._split_bsl_and_framework([rel])
        assert fw == []
        assert len(bsl) == 1
        assert bsl[0]["project"].endswith("MyProj")
        assert len(bsl[0]["files"]) == 1

    def test_bsl_outside_config_prefix_ignored(self, repo):
        rel = "src/bsl/CommonModule.bsl"
        _make_file(repo, rel)
        fw, bsl = mod._split_bsl_and_framework([rel])
        assert fw == []
        assert bsl == []

    def test_nonexistent_file_skipped(self, repo):
        fw, bsl = mod._split_bsl_and_framework(["src/ghost_file.py"])
        assert fw == []
        assert bsl == []

    def test_oversized_bsl_file_skipped(self, repo):
        rel = "configuration/MyProj/Huge.bsl"
        _make_file(repo, rel, size=mod.BSL_MAX_FILE_BYTES + 1)
        fw, bsl = mod._split_bsl_and_framework([rel])
        assert bsl == []

    def test_oversized_framework_file_skipped(self, repo):
        _make_file(repo, "src/framework_search/big.py", size=mod.MAX_FILE_BYTES + 1)
        fw, bsl = mod._split_bsl_and_framework(["src/framework_search/big.py"])
        assert fw == []

    def test_multiple_bsl_same_project_grouped(self, repo):
        rels = [
            "configuration/MyProj/Doc1.bsl",
            "configuration/MyProj/Doc2.bsl",
        ]
        for rel in rels:
            _make_file(repo, rel)
        fw, bsl = mod._split_bsl_and_framework(rels)
        assert len(bsl) == 1
        assert len(bsl[0]["files"]) == 2

    def test_bsl_multiple_projects_separate_groups(self, repo):
        rel_a = "configuration/ProjA/File.bsl"
        rel_b = "configuration/ProjB/File.bsl"
        _make_file(repo, rel_a)
        _make_file(repo, rel_b)
        fw, bsl = mod._split_bsl_and_framework([rel_a, rel_b])
        assert len(bsl) == 2

    def test_unknown_extension_ignored(self, repo):
        _make_file(repo, "tools/runner.exe")
        fw, bsl = mod._split_bsl_and_framework(["tools/runner.exe"])
        assert fw == []
        assert bsl == []

    def test_empty_input_returns_empty(self, repo):
        fw, bsl = mod._split_bsl_and_framework([])
        assert fw == []
        assert bsl == []

    # Note: the OSError branches inside the stat() try/except in _split_bsl_and_framework
    # are defensive TOCTOU guards (file deleted between exists() and stat()). Testing them
    # via Path.stat monkeypatching is fragile on Python 3.13+ due to pathlib._abc._ignore_error
    # re-raising synthetic OSErrors without a recognised errno. These branches are intentionally
    # not covered here — they are pure OS-edge-case guards, not business logic.


# ---------------------------------------------------------------------------
# _changed_files
# ---------------------------------------------------------------------------


class TestChangedFiles:
    def test_normal_output_parsed(self, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess, "check_output",
            lambda *a, **kw: "src/foo.py\nsrc/bar.md\n",
        )
        assert mod._changed_files("HEAD~1") == ["src/foo.py", "src/bar.md"]

    def test_windows_backslash_normalised_to_posix(self, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess, "check_output",
            lambda *a, **kw: "src\\framework_search\\config.py\n",
        )
        assert mod._changed_files("HEAD~1") == ["src/framework_search/config.py"]

    def test_called_process_error_returns_empty(self, monkeypatch):
        def raise_cpe(*a, **kw):
            raise subprocess.CalledProcessError(128, "git")

        monkeypatch.setattr(mod.subprocess, "check_output", raise_cpe)
        assert mod._changed_files("HEAD~1") == []

    def test_empty_git_output_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess, "check_output",
            lambda *a, **kw: "",
        )
        assert mod._changed_files("HEAD~1") == []

    def test_blank_lines_stripped(self, monkeypatch):
        monkeypatch.setattr(
            mod.subprocess, "check_output",
            lambda *a, **kw: "\nsrc/foo.py\n\nsrc/bar.py\n",
        )
        assert mod._changed_files("HEAD~1") == ["src/foo.py", "src/bar.py"]


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


class TestMain:
    def _patch_argv(self, monkeypatch, extra: list[str] | None = None) -> None:
        monkeypatch.setattr(sys, "argv", ["git_post_commit_reindex"] + (extra or []))

    def test_first_commit_returns_0(self, monkeypatch):
        self._patch_argv(monkeypatch)

        def raise_cpe(*a, **kw):
            raise subprocess.CalledProcessError(128, "git")

        monkeypatch.setattr(mod.subprocess, "check_output", raise_cpe)
        assert mod.main() == 0

    def test_no_changed_files_returns_0(self, monkeypatch):
        self._patch_argv(monkeypatch)
        monkeypatch.setattr(mod.subprocess, "check_output", lambda *a, **kw: "abc123\n")
        monkeypatch.setattr(mod, "_changed_files", lambda *a, **kw: [])
        assert mod.main() == 0

    def test_max_files_exceeded_returns_0(self, monkeypatch, tmp_path):
        self._patch_argv(monkeypatch, ["--max-files", "5"])
        monkeypatch.setattr(mod, "LOG_PATH", tmp_path / "test.log", raising=False)
        monkeypatch.setattr(mod.subprocess, "check_output", lambda *a, **kw: "abc123\n")
        monkeypatch.setattr(
            mod, "_changed_files",
            lambda *a, **kw: [f"file{i}.py" for i in range(10)],
        )
        assert mod.main() == 0

    def test_framework_files_call_spawn_framework(self, monkeypatch):
        self._patch_argv(monkeypatch)
        monkeypatch.setattr(mod.subprocess, "check_output", lambda *a, **kw: "abc123\n")
        monkeypatch.setattr(
            mod, "_changed_files",
            lambda *a, **kw: ["src/framework_search/utils.py"],
        )
        monkeypatch.setattr(
            mod, "_split_bsl_and_framework",
            lambda paths: (["src/framework_search/utils.py"], []),
        )
        spawned: list[list[str]] = []
        monkeypatch.setattr(mod, "_spawn_framework_reindex", lambda p: spawned.append(p))
        monkeypatch.setattr(mod, "_spawn_bsl_reindex", lambda p, f: None)
        assert mod.main() == 0
        assert spawned == [["src/framework_search/utils.py"]]

    def test_bsl_files_call_spawn_bsl(self, monkeypatch):
        self._patch_argv(monkeypatch)
        monkeypatch.setattr(mod.subprocess, "check_output", lambda *a, **kw: "abc123\n")
        rel = "configuration/X/F.bsl"
        bsl_group = {"project": "/repo/configuration/X", "files": ["/repo/F.bsl"]}
        monkeypatch.setattr(mod, "_changed_files", lambda *a, **kw: [rel])
        monkeypatch.setattr(
            mod, "_split_bsl_and_framework",
            lambda paths: ([], [bsl_group]),
        )
        monkeypatch.setattr(mod, "_spawn_framework_reindex", lambda p: None)
        spawned: list[tuple[str, list[str]]] = []
        monkeypatch.setattr(mod, "_spawn_bsl_reindex", lambda p, f: spawned.append((p, f)))
        assert mod.main() == 0
        assert len(spawned) == 1
        assert spawned[0][0] == bsl_group["project"]
        assert spawned[0][1] == bsl_group["files"]

    def test_no_indexed_files_returns_0_without_spawning(self, monkeypatch):
        self._patch_argv(monkeypatch)
        monkeypatch.setattr(mod.subprocess, "check_output", lambda *a, **kw: "abc123\n")
        monkeypatch.setattr(mod, "_changed_files", lambda *a, **kw: ["tools/runner.exe"])
        monkeypatch.setattr(mod, "_split_bsl_and_framework", lambda paths: ([], []))
        spawned: list = []
        monkeypatch.setattr(mod, "_spawn_framework_reindex", lambda p: spawned.append(p))
        monkeypatch.setattr(mod, "_spawn_bsl_reindex", lambda p, f: spawned.append(p))
        assert mod.main() == 0
        assert spawned == []

    def test_main_returns_0_even_if_spawn_raises(self, monkeypatch):
        """main() must not block git commits even when spawn fails (missing venv etc.)."""
        self._patch_argv(monkeypatch)
        monkeypatch.setattr(mod.subprocess, "check_output", lambda *a, **kw: "abc123\n")
        monkeypatch.setattr(
            mod, "_changed_files",
            lambda *a, **kw: ["src/framework_search/utils.py"],
        )
        monkeypatch.setattr(
            mod, "_split_bsl_and_framework",
            lambda paths: (["src/framework_search/utils.py"], []),
        )
        monkeypatch.setattr(
            mod, "_spawn_framework_reindex",
            lambda p: (_ for _ in ()).throw(OSError("spawn failed")),
        )
        monkeypatch.setattr(mod, "_spawn_bsl_reindex", lambda p, f: None)
        assert mod.main() == 0
