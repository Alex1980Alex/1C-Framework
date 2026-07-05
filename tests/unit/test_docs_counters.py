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
