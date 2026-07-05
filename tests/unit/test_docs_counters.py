"""Unit tests for scripts/docs_counters.py (roadmap 260704 P3.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.docs_counters import (
    count_bundles,
    count_hooks,
    count_lazy_mcp,
    count_mcp_servers,
    count_skills,
    probe_qdrant_collections,
    scan_drift,
)

pytestmark = pytest.mark.unit


def test_count_skills_counts_dirs_with_skill_md(tmp_path: Path) -> None:
    skills_dir = tmp_path / ".claude" / "skills"
    (skills_dir / "alpha").mkdir(parents=True)
    (skills_dir / "alpha" / "SKILL.md").write_text("# Alpha", encoding="utf-8")
    (skills_dir / "beta").mkdir(parents=True)
    (skills_dir / "beta" / "SKILL.md").write_text("# Beta", encoding="utf-8")
    (skills_dir / "no_skill_md").mkdir(parents=True)

    assert count_skills(tmp_path) == 2


def test_count_skills_missing_dir_returns_zero(tmp_path: Path) -> None:
    assert count_skills(tmp_path) == 0


def test_count_bundles_reads_bundles_and_version(tmp_path: Path) -> None:
    config_dir = tmp_path / ".claude" / "skills"
    config_dir.mkdir(parents=True)
    config = {
        "version": 9,
        "bundles": {
            "bundle-a": {"skills": ["a"]},
            "bundle-b": {"skills": ["b"]},
        },
    }
    (config_dir / "skill-router-config.json").write_text(json.dumps(config), encoding="utf-8")

    bundles_total, version = count_bundles(tmp_path)
    assert bundles_total == 2
    assert version == 9


def test_count_mcp_servers_counts_keys(tmp_path: Path) -> None:
    mcp_config = {
        "mcpServers": {
            "server-a": {},
            "server-b": {},
            "server-c": {},
        }
    }
    (tmp_path / ".mcp.json").write_text(json.dumps(mcp_config), encoding="utf-8")

    assert count_mcp_servers(tmp_path) == 3


def test_count_lazy_mcp_sums_servers_and_categories(tmp_path: Path) -> None:
    registry_dir = tmp_path / "infra" / "lazy-mcp" / "config"
    registry_dir.mkdir(parents=True)
    registry_yaml = """
categories:
  cat-one:
    description: "Category one"
    servers:
      server-a:
        command: "python"
      server-b:
        command: "node"
  cat-two:
    description: "Category two"
    servers:
      server-c:
        command: "python"
"""
    (registry_dir / "registry.yaml").write_text(registry_yaml, encoding="utf-8")

    servers_total, categories_total = count_lazy_mcp(tmp_path)
    assert servers_total == 3
    assert categories_total == 2


def test_count_hooks_excludes_subdirs(tmp_path: Path) -> None:
    hooks_dir = tmp_path / ".claude" / "hooks"
    (hooks_dir / "shared").mkdir(parents=True)
    (hooks_dir / "hook_a.py").write_text("", encoding="utf-8")
    (hooks_dir / "hook_b.py").write_text("", encoding="utf-8")
    (hooks_dir / "shared" / "helper.py").write_text("", encoding="utf-8")

    assert count_hooks(tmp_path) == 2


def test_probe_qdrant_collections_graceful_on_unavailable(monkeypatch) -> None:
    def _raise(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("scripts.docs_counters.urllib.request.urlopen", _raise)

    assert probe_qdrant_collections() is None


def _make_doc(tmp_path: Path, name: str, text: str) -> None:
    docs_dir = tmp_path / "docs" / "framework documentation" / "9_НАВЫКИ"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / name).write_text(text, encoding="utf-8")


def test_scan_drift_flags_stale_counter(tmp_path: Path) -> None:
    _make_doc(tmp_path, "11.6_Каталог.md", "В каталоге 57 скиллов на выбор.\n")

    mismatches = scan_drift(tmp_path, {"skills_total": 97})

    assert len(mismatches) == 1
    assert mismatches[0]["found"] == 57
    assert mismatches[0]["live"] == 97
    assert mismatches[0]["counter"] == "skills_total"


def test_scan_drift_silent_when_counter_matches(tmp_path: Path) -> None:
    _make_doc(tmp_path, "11.6_Каталог.md", "В каталоге 97 скиллов на выбор.\n")

    assert scan_drift(tmp_path, {"skills_total": 97}) == []


def test_scan_drift_excludes_changelog_and_roadmap_files(tmp_path: Path) -> None:
    _make_doc(tmp_path, "27.13_Memory_Changelog.md", "Тогда было 44 скилла.\n")
    _make_doc(tmp_path, "28_1.6_Дорожная_карта.md", "План: 12 скиллов.\n")

    assert scan_drift(tmp_path, {"skills_total": 97}) == []


def test_scan_drift_ignores_parenthesised_chapter_refs(tmp_path: Path) -> None:
    # "скиллов (см. гл. 11" is a cross-reference, not a counter mention.
    _make_doc(tmp_path, "11.2_Архитектура.md", "Список скиллов (гл. 11) ведётся отдельно.\n")

    assert scan_drift(tmp_path, {"skills_total": 97}) == []
