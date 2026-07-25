"""Регрессия validate_toc: директорная ссылка TOC = покрытие поддерева.

Корень (CI 2026-07-25): TOC ссылается на КАТАЛОГИ глав (перенумерация по слоям
Harness 2026-07-04), а парсер брал только `.md`-ссылки и объявлял все файлы под
каталогами «орфанами» — 315 ложных орфанов роняли `test_docs_invariants`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "_validate_toc", _ROOT / "scripts" / "validate_toc.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _mk_docs(tmp_path: Path) -> Path:
    docs = tmp_path / "docs"
    (docs / "chapter" / "nested").mkdir(parents=True)
    (docs / "chapter" / "a.md").write_text("a", encoding="utf-8")
    (docs / "chapter" / "nested" / "b.md").write_text("b", encoding="utf-8")
    (docs / "solo.md").write_text("solo", encoding="utf-8")
    (docs / "orphan.md").write_text("orphan", encoding="utf-8")
    return docs


def test_directory_link_covers_subtree(tmp_path: Path):
    docs = _mk_docs(tmp_path)
    toc = docs / "TOC.md"
    toc.write_text("- [Глава](chapter/)\n- [Соло](solo.md)\n", encoding="utf-8")

    declared = _load().parse_toc_links(toc, docs)

    assert Path("chapter/a.md") in declared  # прямой файл главы
    assert Path("chapter/nested/b.md") in declared  # вложенный — тоже покрыт
    assert Path("solo.md") in declared  # обычная файловая ссылка не сломана
    assert Path("orphan.md") not in declared  # непокрытый файл остаётся орфаном


def test_external_and_anchor_links_ignored(tmp_path: Path):
    docs = _mk_docs(tmp_path)
    toc = docs / "TOC.md"
    toc.write_text(
        "[web](https://example.com/x.md)\n[вне](../outside.md)\n[якорь](solo.md#section)\n",
        encoding="utf-8",
    )

    declared = _load().parse_toc_links(toc, docs)

    assert declared == {Path("solo.md")}  # якорь отрезан, внешние отброшены


def test_parse_toc_dirs_reports_declared_directories(tmp_path: Path):
    """Каталог, объявленный в TOC, но отсутствующий на диске, должен быть видим:
    в `parse_toc_links` он раскрывается в пустоту и молча исчезает."""
    docs = _mk_docs(tmp_path)
    toc = docs / "TOC.md"
    toc.write_text(
        "- [Глава](chapter/)\n- [Нет такой](ghost/)\n- [Соло](solo.md)\n", encoding="utf-8"
    )

    dirs = _load().parse_toc_dirs(toc, docs)

    assert dirs == {Path("chapter"), Path("ghost")}
    assert not (docs / "ghost").is_dir()  # именно эту пропажу и ловит main()
