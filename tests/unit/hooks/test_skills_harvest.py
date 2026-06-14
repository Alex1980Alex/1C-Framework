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


# ---------------------------------------------------------------------------
# mirror_skill_library (roadmap 260612 P0.1/P0.2, acceptance A1/A2)
# ---------------------------------------------------------------------------
class FakeMirrorClient:
    """Scroll/upsert/delete/snapshot fake reconciling against in-memory payloads."""

    def __init__(self, initial: dict[str, dict] | None = None) -> None:
        # point_id -> payload
        self.payloads: dict[str, dict] = dict(initial or {})
        self.snapshots = 0

    def scroll(self, collection_name: str, limit: int, offset=None, **_kw):
        import types

        items = [types.SimpleNamespace(id=pid, payload=pl) for pid, pl in self.payloads.items()]
        return items, None

    def upsert(self, collection_name: str, points: list) -> None:
        for p in points:
            self.payloads[p.id] = p.payload

    def delete(self, collection_name: str, points_selector: list) -> None:
        for pid in points_selector:
            self.payloads.pop(pid, None)

    def create_snapshot(self, collection_name: str):
        import types

        self.snapshots += 1
        return types.SimpleNamespace(name="snap-test")


def _disk_hash(skills_dir: Path, name: str) -> str:
    return sh._skill_hash((skills_dir / name / "SKILL.md").read_text(encoding="utf-8"))


def test_mirror_dry_run_plans_without_writes(env: tuple[Path, Path]) -> None:
    sdir, state = env
    _mk(sdir, "alpha", "first")
    ghost_pid = sh._point_id("dead-skill")
    client = FakeMirrorClient({ghost_pid: {"skill_name": "dead-skill"}})
    stats = sh.mirror_skill_library(
        skills_dir=sdir, state_file=state, client=client, embed=_embed, apply=False
    )
    assert stats["ghosts"] == ["dead-skill"]
    assert stats["to_upsert"] == ["alpha"]
    assert ghost_pid in client.payloads  # dry-run: nothing pruned
    assert client.snapshots == 0
    assert not state.exists()


def test_mirror_apply_prunes_ghost_and_upserts_with_content_hash(
    env: tuple[Path, Path],
) -> None:
    """A1 (create->index with content_hash) + A2 (delete->prune, S1 regression)."""
    sdir, state = env
    _mk(sdir, "alpha", "first")
    _mk(sdir, "beta", "second")
    ghost_pid = sh._point_id("1c-mcp-toolkit")
    client = FakeMirrorClient({ghost_pid: {"skill_name": "1c-mcp-toolkit"}})
    stats = sh.mirror_skill_library(
        skills_dir=sdir, state_file=state, client=client, embed=_embed, apply=True
    )
    assert stats["pruned"] == 1
    assert ghost_pid not in client.payloads
    assert client.snapshots == 1  # prune is irreversible -> snapshot first
    assert stats["upserted"] == 2
    for name in ("alpha", "beta"):
        payload = client.payloads[sh._point_id(name)]
        assert payload["content_hash"] == _disk_hash(sdir, name)  # §26 write-contract
    assert state.exists()  # incremental harvester resynced


def test_mirror_unchanged_content_hash_skips_embed(env: tuple[Path, Path]) -> None:
    sdir, state = env
    _mk(sdir, "alpha", "first")
    pid = sh._point_id("alpha")
    client = FakeMirrorClient(
        {pid: {"skill_name": "alpha", "content_hash": _disk_hash(sdir, "alpha")}}
    )
    calls: list[str] = []

    def counting_embed(text: str) -> list[float]:
        calls.append(text)
        return [0.2] * 8

    stats = sh.mirror_skill_library(
        skills_dir=sdir, state_file=state, client=client, embed=counting_embed, apply=True
    )
    assert stats["upserted"] == 0
    assert stats["unchanged"] == 1
    assert calls == []


def test_mirror_records_ingest_events(
    env: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P0.2: every write attempt lands in memory-ingestion.log (saved + pruned)."""
    import json

    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(cache_dir))
    sdir, state = env
    _mk(sdir, "alpha", "first")
    client = FakeMirrorClient({sh._point_id("dead"): {"skill_name": "dead"}})
    sh.mirror_skill_library(
        skills_dir=sdir, state_file=state, client=client, embed=_embed, apply=True
    )
    log = cache_dir / "memory-ingestion.log"
    assert log.exists()
    events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    actions = {(e["store"], e["action"], e.get("skill")) for e in events}
    assert ("skill_library", "saved", "alpha") in actions
    assert ("skill_library", "pruned", "dead") in actions
