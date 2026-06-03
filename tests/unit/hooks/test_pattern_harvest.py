"""Unit tests for .claude/hooks/shared/pattern_harvest.py (§26 P1 D1.1).

Covers acceptance criteria:
- synthetic confirmed drafts + lessons → K cubes
- rerun against a populated store → 0 new (content_hash dedup)
- per-run cap fires at >N
- content-quality floor: pending / placeholder / noise filtered
- fail-soft: embed None and client errors → counted, never raises
- dry_run counts without upsert
- payload mirrors save_pattern (+ content_hash, confidence 0.70)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
_MODULE_PATH = _HOOKS_DIR / "shared" / "pattern_harvest.py"


def _load() -> Any:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("pattern_harvest", _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # @dataclass needs the module registered first
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


ph = _load()


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeClient:
    """In-memory stand-in for QdrantClient (retrieve/upsert by point id)."""

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    def retrieve(self, collection_name: str, ids: list[str]) -> list[Any]:
        return [self.store[i] for i in ids if i in self.store]

    def upsert(self, collection_name: str, points: list[Any]) -> None:
        for p in points:
            self.store[p.id] = p


def _fake_embed(_text: str) -> list[float]:
    return [0.1] * 8


# --------------------------------------------------------------------------- #
# Fixtures: synthetic sources
# --------------------------------------------------------------------------- #
def _write_draft(d: Path, key: str, status: str, rule: str, *, placeholder: bool = False) -> None:
    rule_line = rule if not placeholder else "<что делать / чего НЕ делать>"
    (d / f"draft_{key}.md").write_text(
        "---\n"
        f"name: feedback-draft-{key}\n"
        'description: "use OurHelper not raw call"\n'
        "metadata:\n"
        "  type: feedback\n"
        f"  status: {status}\n"
        "---\n\n"
        "**Исходное замечание пользователя:**\nsome review note\n\n"
        f"**Правило (заполнить при подтверждении):** {rule_line}\n"
        "**Why:** грузит весь объект из БД\n"
        "**How to apply:** в циклах\n",
        encoding="utf-8",
    )


def _write_lifecycle(d: Path, name: str, lessons: list[str], noise: list[str]) -> None:
    body = ["---", "session_id: s1", "---", "", "## §6 Lessons", ""]
    for ln in lessons + noise:
        body.append(f"- {ln}")
    (d / f"{name}.md").write_text("\n".join(body), encoding="utf-8")


@pytest.fixture()
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    drafts = tmp_path / "drafts"
    life = tmp_path / "lifecycle"
    drafts.mkdir()
    life.mkdir()
    return drafts, life


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_confirmed_drafts_and_lessons_create_cubes(dirs: tuple[Path, Path]) -> None:
    drafts, life = dirs
    _write_draft(drafts, "a", "confirmed", "Читать реквизит через ОбщегоНазначения, не Ссылка.Реквизит")
    _write_lifecycle(
        life,
        "2099-01-01_sess",
        lessons=["Always run post-merge importlib sweep after -X theirs merges to catch regressions"],
        noise=["Обновить доки/скиллы (изменён x.py)", "Запустить code-verify для изменённого кода"],
    )
    client = FakeClient()
    stats = ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=client, embed=_fake_embed,
                       sources=("drafts", "lessons"), lesson_max_age_hours=0)
    assert stats["created"] == 2  # 1 draft + 1 real lesson (noise filtered)
    assert stats["errors"] == 0
    assert len(client.store) == 2


def test_pending_and_placeholder_drafts_skipped(dirs: tuple[Path, Path]) -> None:
    drafts, life = dirs
    _write_draft(drafts, "pending", "pending", "this rule is long enough to pass the floor")
    _write_draft(drafts, "ph", "confirmed", "ignored", placeholder=True)
    client = FakeClient()
    stats = ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=client, embed=_fake_embed,
                       sources=("drafts",))
    assert stats["created"] == 0
    assert len(client.store) == 0


def test_rerun_is_idempotent_zero_new(dirs: tuple[Path, Path]) -> None:
    drafts, life = dirs
    _write_draft(drafts, "a", "confirmed", "Читать реквизит через ОбщегоНазначения, не Ссылка.Реквизит")
    client = FakeClient()
    first = ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=client, embed=_fake_embed,
                       sources=("drafts",))
    assert first["created"] == 1
    second = ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=client, embed=_fake_embed,
                        sources=("drafts",))
    assert second["created"] == 0
    assert second["skipped_dup"] == 1
    assert len(client.store) == 1  # no duplicate point


def test_cap_fires_above_n(dirs: tuple[Path, Path]) -> None:
    drafts, life = dirs
    for i in range(5):
        _write_draft(drafts, f"d{i}", "confirmed", f"distinct confirmed rule number {i} long enough to pass floor")
    client = FakeClient()
    stats = ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=client, embed=_fake_embed,
                       sources=("drafts",), cap=2)
    assert stats["created"] == 2
    assert stats["skipped_cap"] == 3


def test_failsoft_embed_none(dirs: tuple[Path, Path]) -> None:
    drafts, life = dirs
    _write_draft(drafts, "a", "confirmed", "a confirmed rule that is definitely long enough here")
    client = FakeClient()
    stats = ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=client,
                       embed=lambda _t: None, sources=("drafts",))
    assert stats["created"] == 0
    assert stats["errors"] == 1
    assert len(client.store) == 0


def test_failsoft_client_raises(dirs: tuple[Path, Path]) -> None:
    drafts, life = dirs
    _write_draft(drafts, "a", "confirmed", "a confirmed rule that is definitely long enough here")

    class Boom:
        def retrieve(self, *a: Any, **k: Any) -> Any:
            raise RuntimeError("qdrant down")

    stats = ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=Boom(), embed=_fake_embed,
                       sources=("drafts",))
    assert stats["created"] == 0
    assert stats["errors"] == 1


def test_dry_run_counts_without_upsert(dirs: tuple[Path, Path]) -> None:
    drafts, life = dirs
    _write_draft(drafts, "a", "confirmed", "a confirmed rule that is definitely long enough here")
    client = FakeClient()
    stats = ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=client, embed=_fake_embed,
                       sources=("drafts",), dry_run=True)
    assert stats["created"] == 1
    assert len(client.store) == 0  # nothing persisted


def _write_skill_jsonl(path: Path, records: list[dict]) -> None:
    import json as _json

    path.write_text("\n".join(_json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")


def test_skill_learning_source_ingests_confirmed(tmp_path: Path) -> None:
    """§26 P2 D2.2: confirmed (non-archived) skill-learning patterns → learned_patterns."""
    jf = tmp_path / "patterns.jsonl"
    _write_skill_jsonl(
        jf,
        [
            {"pattern_id": "p1", "name": "use httpx", "content": "Always use httpx.AsyncClient for async HTTP calls in this framework", "pattern_type": "code-convention", "tags": ["http"]},
            {"pattern_id": "p2", "name": "archived one", "content": "this is archived and must be skipped entirely here", "archived": True},
            {"pattern_id": "p3", "name": "too short", "content": "tiny"},
        ],
    )
    client = FakeClient()
    stats = ph.harvest(skill_learning_file=jf, client=client, embed=_fake_embed,
                       sources=("skill_learning",))
    assert stats["created"] == 1  # archived + too-short skipped
    assert len(client.store) == 1
    pl = next(iter(client.store.values())).payload
    assert pl["pattern_type"] == "code-convention"
    assert "skill-learning" in pl["tags"]
    assert pl["metadata"]["harvest_source"].startswith("skill-learning:")


def test_skill_learning_rerun_is_idempotent(tmp_path: Path) -> None:
    jf = tmp_path / "patterns.jsonl"
    _write_skill_jsonl(jf, [{"pattern_id": "p1", "name": "x", "content": "a confirmed skill pattern long enough to pass the floor"}])
    client = FakeClient()
    s1 = ph.harvest(skill_learning_file=jf, client=client, embed=_fake_embed, sources=("skill_learning",))
    s2 = ph.harvest(skill_learning_file=jf, client=client, embed=_fake_embed, sources=("skill_learning",))
    assert s1["created"] == 1 and s2["created"] == 0 and s2["skipped_dup"] == 1


def test_ingest_items_on_created_callback() -> None:
    """ingest_items fires on_created(item, pid) per successful upsert (P2 D2.3 links)."""
    client = FakeClient()
    seen: list[tuple[str, str]] = []
    items = [ph.HarvestItem(content="a brand new consolidated semantic pattern here",
                            name="n", description="d", pattern_type="workflow-pattern", source="reflection:x")]
    stats = ph.ingest_items(items, client=client, embed=_fake_embed,
                            on_created=lambda it, pid: seen.append((it.name, pid)))
    assert stats["created"] == 1
    assert len(seen) == 1 and seen[0][0] == "n"


def test_payload_mirrors_save_pattern(dirs: tuple[Path, Path]) -> None:
    drafts, life = dirs
    _write_draft(drafts, "a", "confirmed", "Читать реквизит через ОбщегоНазначения, не Ссылка.Реквизит")
    client = FakeClient()
    ph.harvest(drafts_dir=drafts, lifecycle_dir=life, client=client, embed=_fake_embed,
               sources=("drafts",))
    point = next(iter(client.store.values()))
    pl = point.payload
    # §22 confidence seed + §26 content_hash + save_pattern-shaped fields
    assert pl["confidence"] == pytest.approx(0.70, abs=1e-9)
    assert pl["succ"] == 0.0 and pl["fail"] == 0.0
    assert len(pl["content_hash"]) == 16
    assert pl["pattern_type"] == "code-convention"
    for key in ("pattern_id", "name", "content", "evidence_sources", "decay_rate",
                "application_count", "version", "last_decay_at"):
        assert key in pl
    assert pl["metadata"]["harvested"] is True
