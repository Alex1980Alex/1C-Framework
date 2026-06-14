"""Wikilink-резолюция по слагам (наблюдение §18 roadmap 260612 LinkRegistry).

Память живёт в трёх формах имени: файл с подчёркиваниями, kebab-слаг в
frontmatter `name:`, kebab-ссылка `[[...]]` в роадмапах. Валидатор обязан
резолвить ссылку по канону (слагу), а не по буквальному имени файла.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "roadmap_progress_log.py"
_spec = importlib.util.spec_from_file_location("roadmap_progress_log", _SCRIPT)
rpl = importlib.util.module_from_spec(_spec)
sys.modules["roadmap_progress_log"] = rpl
_spec.loader.exec_module(rpl)


@pytest.fixture
def mem_dir(tmp_path: Path) -> Path:
    d = tmp_path / "memory"
    d.mkdir()
    # классика: underscore-файл + kebab-слаг в frontmatter
    (d / "feedback_bsl_sparse_bm25_dominance.md").write_text(
        "---\nname: feedback-bsl-sparse-bm25-dominance\ndescription: x\n---\nbody\n",
        encoding="utf-8",
    )
    # файл без frontmatter name (только stem)
    (d / "project_roadmap_audit_pattern.md").write_text("no frontmatter\n", encoding="utf-8")
    # frontmatter name, отличающийся от stem (канон — слаг)
    (d / "feedback_auto_git_save_preempt.md").write_text(
        "---\nname: auto-git-save-preempts-parent-commit\n---\nbody\n", encoding="utf-8"
    )
    return d


def test_kebab_link_resolves_underscore_file(mem_dir: Path) -> None:
    slugs = rpl.memory_slug_index(mem_dir)
    assert rpl._canon("feedback-bsl-sparse-bm25-dominance") in slugs


def test_stem_resolves_without_frontmatter(mem_dir: Path) -> None:
    slugs = rpl.memory_slug_index(mem_dir)
    # обе формы ссылки на файл без frontmatter резолвятся
    assert rpl._canon("project-roadmap-audit-pattern") in slugs
    assert rpl._canon("project_roadmap_audit_pattern") in slugs


def test_frontmatter_slug_differs_from_stem(mem_dir: Path) -> None:
    slugs = rpl.memory_slug_index(mem_dir)
    # канонический слаг (≠ stem) резолвится, как велит контракт памяти
    assert rpl._canon("auto-git-save-preempts-parent-commit") in slugs
    # и stem-форма тоже (обратная совместимость старых ссылок)
    assert rpl._canon("feedback-auto-git-save-preempt") in slugs


def test_genuinely_missing_link_is_broken(mem_dir: Path) -> None:
    slugs = rpl.memory_slug_index(mem_dir)
    assert rpl._canon("feedback-nonexistent-entry") not in slugs
