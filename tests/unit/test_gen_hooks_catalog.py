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


def test_render_markdown_escapes_pipes_in_matcher(tmp_path):
    """Голый `|` в matcher-ячейке рвёт markdown-таблицу на лишние колонки."""
    settings = _write_settings(
        tmp_path,
        {
            "PostToolUse": [
                {"matcher": "Write|Edit|Bash", "hooks": [{"command": "hooks/a.py", "timeout": 3}]}
            ]
        },
    )
    md = MOD.render_markdown(MOD.load_catalog(settings))
    row = next(line for line in md.splitlines() if "`a.py`" in line)
    assert "`Write\\|Edit\\|Bash`" in row
    assert row.count("|") - row.count("\\|") == 4  # ровно 4 неэкранированных разделителя


def test_render_markdown_escapes_backslash_before_pipe(tmp_path):
    """Бэкслеш экранируется первым — иначе литеральный `\\|` во входе даст `\\\\|` и разрыв ячейки."""
    settings = _write_settings(
        tmp_path,
        {"PreToolUse": [{"matcher": "a\\|b", "hooks": [{"command": "hooks/b.py", "timeout": 3}]}]},
    )
    md = MOD.render_markdown(MOD.load_catalog(settings))
    row = next(line for line in md.splitlines() if "`b.py`" in line)
    assert "`a\\\\\\|b`" in row
    assert row.count("|") - row.count("\\|") == 4


def test_ordered_events_puts_known_first(tmp_path):
    settings = _write_settings(
        tmp_path,
        {"CustomEvent": [{"hooks": [{"command": "hooks/z.py"}]}], "Stop": [{"hooks": []}]},
    )
    order = MOD._ordered_events(MOD.load_catalog(settings))
    assert order.index("Stop") < order.index("CustomEvent")  # known lifecycle events first


# --- router_counts (audit 260706: класс «дрейф счётчика бандлов» триады) ---


def _write_router_config(tmp_path, cfg):
    p = tmp_path / "skill-router-config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


def _make_skills_dir(tmp_path, names_with_skillmd):
    d = tmp_path / "skills"
    d.mkdir()
    for name, has_md in names_with_skillmd:
        sk = d / name
        sk.mkdir()
        if has_md:
            (sk / "SKILL.md").write_text("# skill", encoding="utf-8")
    return d


def test_router_counts_bundles_version_domains(tmp_path):
    cfg = _write_router_config(
        tmp_path,
        {
            "version": 9,
            "bundles": {f"b{i}": {} for i in range(66)},
            "domains": {"1c": ["b0", "b1"], "framework": ["b2"]},
        },
    )
    skills = _make_skills_dir(
        tmp_path, [("a", True), ("b", True), ("c", False), ("references", False)]
    )
    rc = MOD.router_counts(cfg, skills)
    assert rc["bundles"] == 66
    assert rc["version"] == 9
    assert rc["grouped"] == 3  # 2 + 1
    assert rc["ungrouped"] == 63  # 66 - 3
    assert rc["domains"] == {"1c": 2, "framework": 1}
    # только директории с SKILL.md считаются скиллами
    assert rc["skills"] == 2


def test_router_counts_empty_domains(tmp_path):
    cfg = _write_router_config(tmp_path, {"version": 9, "bundles": {"x": {}}, "domains": {}})
    skills = _make_skills_dir(tmp_path, [])
    rc = MOD.router_counts(cfg, skills)
    assert rc["bundles"] == 1
    assert rc["grouped"] == 0
    assert rc["ungrouped"] == 1
    assert rc["skills"] == 0


# --- verify_doc (self-updating guard против дрейфа счётчиков реестра триады) ---


def _write_doc(tmp_path, text):
    p = tmp_path / "SKILL.md"
    p.write_text(text, encoding="utf-8")
    return p


def test_verify_doc_passes_when_synced(tmp_path):
    cfg = _write_router_config(
        tmp_path, {"version": 9, "bundles": {f"b{i}": {} for i in range(66)}, "domains": {}}
    )
    skills = _make_skills_dir(tmp_path, [("a", True), ("b", True)])
    doc = _write_doc(tmp_path, "Роутинг по 66 bundles (config v9).\nКаталог (2 скиллов).")
    assert MOD.verify_doc(doc, cfg, skills) == []


def test_verify_doc_detects_bundle_drift(tmp_path):
    cfg = _write_router_config(
        tmp_path, {"version": 9, "bundles": {f"b{i}": {} for i in range(66)}, "domains": {}}
    )
    skills = _make_skills_dir(tmp_path, [("a", True)])
    doc = _write_doc(tmp_path, "Старый текст: 53 bundles и ещё раз 52 бандла.")
    problems = MOD.verify_doc(doc, cfg, skills)
    # два разных заявленных значения (53, 52) — оба дрейф; дедуп не схлопывает разные
    assert len(problems) == 2
    assert any("53" in p for p in problems) and any("52" in p for p in problems)


def test_verify_doc_dedups_repeated_same_value(tmp_path):
    cfg = _write_router_config(
        tmp_path, {"version": 9, "bundles": {f"b{i}": {} for i in range(66)}, "domains": {}}
    )
    skills = _make_skills_dir(tmp_path, [("a", True)])
    # «53 bundles» упомянуто 3 раза — одно расхождение после дедупа
    doc = _write_doc(tmp_path, "53 bundles ... 53 bundles ... (53 bundles)")
    assert len(MOD.verify_doc(doc, cfg, skills)) == 1


def test_verify_doc_graceful_on_missing_file(tmp_path):
    # недостижимый конфиг → чистое сообщение (не трейсбек), fail-closed (непустой список)
    missing_cfg = tmp_path / "nope.json"
    skills = _make_skills_dir(tmp_path, [])
    doc = _write_doc(tmp_path, "66 bundles")
    problems = MOD.verify_doc(doc, missing_cfg, skills)
    assert len(problems) == 1
    assert "недоступен" in problems[0]
