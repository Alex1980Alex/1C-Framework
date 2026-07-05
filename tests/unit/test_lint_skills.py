"""Unit tests for the skill catalog linter (audit 260705 §БП G1).

Includes the regression for the unquote bug (found 2026-07-06): links with %20
(space in "framework documentation") were false-positive DEADLINK because the
linter resolved the raw url-encoded target instead of decoding it first.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "lint_skills", str(_ROOT / "scripts" / "lint_skills.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load()


def _skill(tmp_path, name, body):
    d = tmp_path / name
    d.mkdir()
    (d / "SKILL.md").write_text(body, encoding="utf-8")
    return d


def test_clean_skill_no_findings(tmp_path):
    d = _skill(
        tmp_path, "good", "---\nname: good\ndescription: валидное описание триггеры\n---\n\nbody\n"
    )
    assert MOD.lint_one(d) == []


def test_encoded_space_link_is_not_deadlink(tmp_path):
    """Regression: a %20-encoded link to an existing file must NOT be DEADLINK."""
    # реальный файл-цель с пробелом в имени каталога
    target_dir = tmp_path / "docs" / "framework documentation"
    target_dir.mkdir(parents=True)
    (target_dir / "page.md").write_text("x", encoding="utf-8")
    d = _skill(
        tmp_path,
        "linker",
        "---\nname: linker\ndescription: d\n---\n\n"
        "[ссылка](../docs/framework%20documentation/page.md)\n",
    )
    rules = {f["rule"] for f in MOD.lint_one(d)}
    assert "DEADLINK" not in rules  # %20 decoded -> resolves


def test_genuinely_broken_link_is_deadlink(tmp_path):
    d = _skill(tmp_path, "broken", "---\nname: broken\ndescription: d\n---\n\n[x](./nope.md)\n")
    assert any(f["rule"] == "DEADLINK" for f in MOD.lint_one(d))


def test_placeholder_link_exempt(tmp_path):
    d = _skill(
        tmp_path,
        "tmpl",
        "---\nname: tmpl\ndescription: d\n---\n\n[пример](docs/path/to/file.md) и [p](path.md)\n",
    )
    assert not any(f["rule"] == "DEADLINK" for f in MOD.lint_one(d))


def test_nodesc_and_namedir(tmp_path):
    d = _skill(tmp_path, "wrong-dir", "---\nname: other-name\n---\n\nbody\n")
    rules = {f["rule"] for f in MOD.lint_one(d)}
    assert "NODESC" in rules and "NAMEDIR" in rules


def test_desc1024_over_budget(tmp_path):
    d = _skill(tmp_path, "verbose", f"---\nname: verbose\ndescription: {'д' * 1100}\n---\n\nbody\n")
    assert any(f["rule"] == "DESC1024" for f in MOD.lint_one(d))
