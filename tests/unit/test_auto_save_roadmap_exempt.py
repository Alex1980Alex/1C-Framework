"""Регрессия E12 (ретро 260725): roadmap исключён во ВСЕХ трёх авто-коммит хуках.

Исключение `docs/roadmap/` было проведено только в двух хуках трио
(`auto-git-save.py::IGNORE_PATH_PREFIXES` и `posttooluse-auto-git-save.py::SKIP_PATTERNS`),
а третий - `auto-git-save-prompt.py` (UserPromptSubmit, префикс `chore: auto-commit`) -
остался без него и уносил roadmap-правки безымянным авто-коммитом.

Тест пинит инвариант для всех трёх, чтобы «починили в двух из трёх» не повторилось.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_HOOKS = _ROOT / ".claude" / "hooks"

ROADMAP_FILE = "docs/roadmap/260725_ROADMAP_SESSION_RETRO.md"
NORMAL_FILE = "scripts/analyze_tool_health.py"


def _load(name: str):
    path = _HOOKS / name
    spec = importlib.util.spec_from_file_location(f"_hk_{name.replace('-', '_')[:-3]}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize(
    ("hook", "func"),
    [
        ("auto-git-save.py", "should_track_file"),
        ("auto-git-save-prompt.py", "_should_track"),
        ("posttooluse-auto-git-save.py", "_should_track"),
    ],
)
def test_roadmap_not_auto_committed(hook, func):
    """САБОТАЖ-ИНВАРИАНТ: ни один из трёх хуков не забирает docs/roadmap/*."""
    mod = _load(hook)
    assert getattr(mod, func)(ROADMAP_FILE) is False, (
        f"{hook} унесёт roadmap в безымянный авто-коммит"
    )


@pytest.mark.parametrize(
    ("hook", "func"),
    [
        ("auto-git-save.py", "should_track_file"),
        ("auto-git-save-prompt.py", "_should_track"),
        ("posttooluse-auto-git-save.py", "_should_track"),
    ],
)
def test_normal_code_still_tracked(hook, func):
    """Обратная сторона: обычный код по-прежнему автосейвится (не переисключили)."""
    mod = _load(hook)
    assert getattr(mod, func)(NORMAL_FILE) is True, f"{hook} перестал отслеживать обычный код"


def test_prompt_hook_declares_prefix_list():
    """У третьего хука появился именно список префиксов (а не разовая заплатка)."""
    mod = _load("auto-git-save-prompt.py")
    assert "docs/roadmap/" in mod.IGNORE_PATH_PREFIXES
