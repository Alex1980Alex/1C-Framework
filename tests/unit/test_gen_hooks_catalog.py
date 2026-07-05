"""Unit tests for the hook-catalog generator (audit 260705 P2.1).

Pure logic (load_catalog / counts / render_markdown) against a synthetic
settings dict — no dependency on the live settings.json.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "gen_hooks_catalog", str(_ROOT / "scripts" / "gen_hooks_catalog.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = _load_module()


def _write_settings(tmp_path, hooks):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"hooks": hooks}), encoding="utf-8")
    return p


def test_script_name_extracts_last_py():
    assert MOD._script_name("C:/x/.venv/python.exe C:/x/.claude/hooks/foo-bar.py") == "foo-bar.py"
    assert MOD._script_name("python a.py then b.py") == "b.py"
    assert MOD._script_name("no-script-here") == "no-script-here"


def test_load_catalog_flattens_groups(tmp_path):
    settings = _write_settings(
        tmp_path,
        {
            "PreToolUse": [
                {"matcher": "Write|Edit", "hooks": [{"command": "py hooks/a.py", "timeout": 3}]},
                {"matcher": "Bash", "hooks": [{"command": "py hooks/b.py", "timeout": 5}]},
            ],
            "Stop": [{"hooks": [{"command": "py hooks/c.py"}]}],  # no matcher, no timeout
        },
    )
    cat = MOD.load_catalog(settings)
    assert [r["script"] for r in cat["PreToolUse"]] == ["a.py", "b.py"]
    assert cat["PreToolUse"][0]["matcher"] == "Write|Edit"
    # missing matcher -> "(all)"; missing timeout -> None
    assert cat["Stop"][0]["matcher"] == "(all)"
    assert cat["Stop"][0]["timeout"] is None


def test_counts_totals(tmp_path):
    settings = _write_settings(
        tmp_path,
        {
            "PreToolUse": [{"hooks": [{"command": "hooks/a.py"}, {"command": "hooks/b.py"}]}],
            "Stop": [{"hooks": [{"command": "hooks/c.py"}]}],
        },
    )
    c = MOD.counts(MOD.load_catalog(settings))
    assert c["PreToolUse"] == 2
    assert c["Stop"] == 1
    assert c["TOTAL"] == 3


def test_render_markdown_has_autogen_marker_and_counts(tmp_path):
    settings = _write_settings(
        tmp_path,
        {"PreToolUse": [{"matcher": "Write", "hooks": [{"command": "hooks/a.py", "timeout": 3}]}]},
    )
    md = MOD.render_markdown(MOD.load_catalog(settings))
    assert "АВТО-ГЕНЕРАЦИЯ" in md  # doc must not be hand-edited
    assert "Всего регистраций: 1" in md
    assert "`a.py`" in md and "`Write`" in md and "3s" in md


def test_ordered_events_puts_known_first(tmp_path):
    settings = _write_settings(
        tmp_path,
        {"CustomEvent": [{"hooks": [{"command": "hooks/z.py"}]}], "Stop": [{"hooks": []}]},
    )
    order = MOD._ordered_events(MOD.load_catalog(settings))
    assert order.index("Stop") < order.index("CustomEvent")  # known lifecycle events first
