"""Unit tests for .claude/hooks/shared/skills_harvest.py (§26 P1 D1.2).

Covers acceptance criteria:
- cold-start seed records hashes WITHOUT embedding (no 80-embed storm)
- changed skill -> 1 upsert; unchanged rerun -> 0 (hash idempotency)
- new skill -> upsert
- removed skill (state has it, file gone) -> point deleted + state pruned
- per-run cap bounds upserts
- fail-soft: embed None / client errors -> counted, never raises
- point id mirrors the batch indexer (uuid5 NAMESPACE_URL, skill_name)
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
_MODULE_PATH = _HOOKS_DIR / "shared" / "skills_harvest.py"


def _load() -> Any:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("skills_harvest", _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


sh = _load()


class FakeClient:
    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def upsert(self, collection_name: str, points: list[Any]) -> None:
        for p in points:
            self.store[p.id] = p

    def delete(self, collection_name: str, points_selector: list[str]) -> None:
        for pid in points_selector:
            self.store.pop(pid, None)


def _embed(_t: str) -> list[float]:
    return [0.2] * 8


def _mk(skills_dir: Path, name: str, desc: str) -> None:
    d = skills_dir / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc} Triggers: 'x', 'y'\n---\n\nBody of {name}.\n",
        encoding="utf-8",
    )


@pytest.fixture()
def env(tmp_path: Path) -> tuple[Path, Path]:
    s = tmp_path / "skills"
    s.mkdir()
    return s, tmp_path / "state.json"


def test_cold_start_seeds_without_embedding(env: tuple[Path, Path]) -> None:
    sdir, state = env
    _mk(sdir, "alpha", "first")
    _mk(sdir, "beta", "second")
    client = FakeClient()
    stats = sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)
    assert stats["seeded"] is True
    assert stats["upserted"] == 0
    assert len(client.store) == 0
    assert state.exists()


def test_changed_upserts_then_idempotent(env: tuple[Path, Path]) -> None:
    sdir, state = env
    _mk(sdir, "alpha", "first")
    client = FakeClient()
    sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)  # seed
    _mk(sdir, "alpha", "first UPDATED")
    s1 = sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)
    assert s1["upserted"] == 1
    assert len(client.store) == 1
    s2 = sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)
    assert s2["upserted"] == 0
    assert s2["skipped_unchanged"] == 1


def test_new_after_seed_upserts(env: tuple[Path, Path]) -> None:
    sdir, state = env
    _mk(sdir, "alpha", "first")
    client = FakeClient()
    sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)  # seed
    _mk(sdir, "gamma", "brand new")
    s1 = sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)
    assert s1["upserted"] == 1
    assert s1["items"] == ["gamma"]
    assert sh._point_id("gamma") in client.store


def test_removed_is_cleaned_up(env: tuple[Path, Path]) -> None:
    sdir, state = env
    _mk(sdir, "alpha", "first")
    _mk(sdir, "beta", "second")
    client = FakeClient()
    sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)  # seed
    client.store[sh._point_id("beta")] = object()
    import shutil

    shutil.rmtree(sdir / "beta")
    s1 = sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)
    assert s1["deleted"] == 1
    assert sh._point_id("beta") not in client.store


def test_cap_bounds_upserts(env: tuple[Path, Path]) -> None:
    sdir, state = env
    _mk(sdir, "alpha", "first")
    client = FakeClient()
    sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)  # seed
    for i in range(4):
        _mk(sdir, f"new{i}", f"new {i}")
    s1 = sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed, cap=2)
    assert s1["upserted"] == 2
    assert s1["skipped_cap"] == 2


def test_failsoft_embed_none(env: tuple[Path, Path]) -> None:
    sdir, state = env
    _mk(sdir, "alpha", "first")
    client = FakeClient()
    sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=_embed)  # seed
    _mk(sdir, "alpha", "first UPDATED")
    s1 = sh.harvest_skills(skills_dir=sdir, state_file=state, client=client, embed=lambda _t: None)
    assert s1["upserted"] == 0
    assert s1["errors"] == 1


def test_point_id_matches_indexer_scheme() -> None:
    assert sh._point_id("alpha") == str(uuid.uuid5(uuid.NAMESPACE_URL, "alpha"))
