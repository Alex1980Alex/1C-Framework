"""Unit tests for framework_search.file_walker."""

from __future__ import annotations

from pathlib import Path

import pytest

from framework_search.file_walker import _matches_skip, iter_indexable_files

pytestmark = pytest.mark.unit


class TestMatchesSkip:
    def test_pycache_substring(self) -> None:
        assert _matches_skip("src/foo/__pycache__/mod.cpython-311.pyc")

    def test_normal_python_file_not_skipped(self) -> None:
        assert not _matches_skip("src/framework_search/chunker_base.py")

    def test_venv_skipped(self) -> None:
        assert _matches_skip("src/.venv/lib/python3.11/site-packages/x.py")

    def test_node_modules_skipped(self) -> None:
        assert _matches_skip("tools/ui/node_modules/react/index.js")

    def test_bsl_projects_prefix_match(self) -> None:
        # "/src/projects/configuration/" → prefix without leading slash
        assert _matches_skip("src/projects/configuration/Module1.bsl")

    def test_tools_serena_skipped(self) -> None:
        assert _matches_skip("tools/serena/agent.py")

    def test_docs_normal_not_skipped(self) -> None:
        assert not _matches_skip("docs/framework documentation/01_ОБЗОР/01.1_Введение.md")

    def test_case_insensitive(self) -> None:
        assert _matches_skip("SRC/__PYCACHE__/x.py")

    def test_data_dir_skipped(self) -> None:
        assert _matches_skip("src/data/something.json")

    def test_package_lock_skipped(self) -> None:
        assert _matches_skip("package-lock.json")


class TestIterIndexableFiles:
    def test_py_file_yielded(self, tmp_path: Path) -> None:
        f = tmp_path / "hello.py"
        f.write_text("x = 1")
        results = list(iter_indexable_files(roots=[], extra_files=[], repo_root=tmp_path))
        # no roots, no extras → empty
        assert results == []

    def test_py_file_in_root(self, tmp_path: Path) -> None:
        root = tmp_path / "src"
        root.mkdir()
        (root / "module.py").write_text("def f(): pass")
        results = list(iter_indexable_files(roots=["src"], extra_files=[], repo_root=tmp_path))
        assert len(results) == 1
        _, rel, lang = results[0]
        assert rel == "src/module.py"
        assert lang == "python"

    def test_md_file_in_root(self, tmp_path: Path) -> None:
        root = tmp_path / "docs"
        root.mkdir()
        (root / "readme.md").write_text("# Title")
        results = list(iter_indexable_files(roots=["docs"], extra_files=[], repo_root=tmp_path))
        assert len(results) == 1
        _, _, lang = results[0]
        assert lang == "markdown"

    def test_unknown_extension_not_yielded(self, tmp_path: Path) -> None:
        root = tmp_path / "src"
        root.mkdir()
        (root / "binary.exe").write_bytes(b"\x00\x01\x02")
        results = list(iter_indexable_files(roots=["src"], extra_files=[], repo_root=tmp_path))
        assert results == []

    def test_pycache_dir_skipped(self, tmp_path: Path) -> None:
        root = tmp_path / "src"
        pycache = root / "__pycache__"
        pycache.mkdir(parents=True)
        (pycache / "mod.cpython-311.pyc").write_text("bytecode")
        results = list(iter_indexable_files(roots=["src"], extra_files=[], repo_root=tmp_path))
        assert results == []

    def test_large_file_skipped(self, tmp_path: Path) -> None:
        root = tmp_path / "src"
        root.mkdir()
        big = root / "huge.py"
        big.write_bytes(b"x" * (512 * 1024 + 1))
        results = list(iter_indexable_files(roots=["src"], extra_files=[], repo_root=tmp_path))
        assert results == []

    def test_dedup_same_file_two_roots(self, tmp_path: Path) -> None:
        # Create overlapping roots that both walk the same file.
        root_a = tmp_path / "src"
        root_a.mkdir()
        (root_a / "shared.py").write_text("pass")
        # root_b points to same dir via alias (use the same path twice)
        results = list(iter_indexable_files(roots=["src", "src"], extra_files=[], repo_root=tmp_path))
        assert len(results) == 1


class TestIterIndexableFilesExtras:
    def test_extra_file_yielded(self, tmp_path: Path) -> None:
        (tmp_path / "CLAUDE.md").write_text("# instructions")
        results = list(iter_indexable_files(roots=[], extra_files=["CLAUDE.md"], repo_root=tmp_path))
        assert len(results) == 1
        _, rel, lang = results[0]
        assert rel == "CLAUDE.md"
        assert lang == "markdown"

    def test_missing_extra_not_yielded(self, tmp_path: Path) -> None:
        results = list(iter_indexable_files(roots=[], extra_files=["nonexistent.md"], repo_root=tmp_path))
        assert results == []
