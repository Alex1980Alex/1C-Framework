"""Unit tests for the skill-learning revival (roadmap 260611).

Covers:
  - P0.1 atomic ``_write_jsonl`` (tmp + os.replace, no leftovers)
  - P0.2 rejected as negative dedup → ``action=dup_rejected``
  - P0.3 stats derive-on-read (poisoned cache overridden by actual files)
  - P0.4 ``route_and_save`` skill-learning target → pending quarantine
  - P1.2 ``quarantine_items`` / ``harvest`` confidence split
  - P2.2 memory-first-hook ``_search_skill_learning`` arm (pending damp + метка)
  - P2.3 ``_sl_tokenize`` RU-morphoform normalization
  - P3.1 ``run_review_pending`` TTL auto-reject (dry-run + apply)

All paths are monkeypatched to tmp; conftest isolates CLAUDE_CACHE_DIR sinks.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def sl_server(tmp_path, monkeypatch):
    """skill-learning server module with silos redirected to tmp."""
    import src.memory.skill_learning.server as srv

    monkeypatch.setattr(srv, "PENDING_FILE", tmp_path / "pending_patterns.jsonl")
    monkeypatch.setattr(srv, "SAVED_FILE", tmp_path / "patterns.jsonl")
    monkeypatch.setattr(srv, "REJECTED_FILE", tmp_path / "rejected_patterns.jsonl")
    monkeypatch.setattr(srv, "STATS_FILE", tmp_path / "learning_stats.json")
    return srv


async def _capture(srv, content: str, **kw) -> dict:
    args = {"pattern_type": "workflow-pattern", "name": kw.pop("name", "t"), "content": content}
    args.update(kw)
    return json.loads((await srv.handle_capture_pattern(args))[0].text)


# ---------------------------------------------------------------------------
# P0.1 — atomic rewrite
# ---------------------------------------------------------------------------
def test_write_jsonl_atomic(sl_server, tmp_path):
    path = tmp_path / "x.jsonl"
    sl_server._write_jsonl(path, [{"a": 1}, {"b": "кириллица"}])
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"b": "кириллица"}]
    assert not list(tmp_path.glob("*.tmp"))  # no temp leftovers


# ---------------------------------------------------------------------------
# P0.2 — rejected as negative dedup
# ---------------------------------------------------------------------------
async def test_recapture_rejected_is_dup_rejected(sl_server):
    r1 = await _capture(sl_server, "уникальный контент для отклонения")
    assert r1["status"] == "pending"
    await sl_server.handle_reject({"pattern_id": r1["pattern_id"]})
    assert sl_server._read_jsonl(sl_server.PENDING_FILE) == []

    r2 = await _capture(sl_server, "уникальный контент для отклонения")
    assert r2["action"] == "dup_rejected"
    assert r2["silo"] == "rejected"
    # quarantine NOT re-entered
    assert sl_server._read_jsonl(sl_server.PENDING_FILE) == []


async def test_recapture_pending_is_plain_dup(sl_server):
    r1 = await _capture(sl_server, "контент остающийся в pending")
    r2 = await _capture(sl_server, "контент остающийся в pending")
    assert r2["action"] == "dup"
    assert r2["pattern_id"] == r1["pattern_id"]


# ---------------------------------------------------------------------------
# P0.3 — stats derive-on-read
# ---------------------------------------------------------------------------
async def test_stats_derive_overrides_poisoned_cache(sl_server):
    r = await _capture(sl_server, "паттерн для подтверждения и статистики", confidence=0.9)
    await sl_server.handle_confirm({"pattern_id": r["pattern_id"]})
    # poison the cache: derive-on-read must ignore it
    sl_server._save_stats({"total_patterns": 99, "by_type": {}, "by_confidence": {}})
    stats = json.loads((await sl_server.handle_stats({}))[0].text)
    assert stats["total_patterns"] == 1
    assert stats["by_confidence"]["high"] == 1
    assert stats["pending_count"] == 0
    assert stats["rejected_count"] == 0


# ---------------------------------------------------------------------------
# P0.4 — route_and_save → pending quarantine
# ---------------------------------------------------------------------------
@pytest.fixture
def orchestrator(tmp_path, monkeypatch):
    import src.memory.orchestrator.memory_orchestrator as mo

    monkeypatch.setattr(mo, "_PROJECT_ROOT", tmp_path)
    return mo.MemoryOrchestrator(), tmp_path


async def test_route_and_save_skill_learning_goes_to_pending(orchestrator):
    orch, root = orchestrator
    eid = await orch._save_to_target("skill-learning", "routed контент в карантин", {"name": "r"})
    pend = root / "data" / "skill_learning" / "pending_patterns.jsonl"
    saved = root / "data" / "skill_learning" / "patterns.jsonl"
    recs = [json.loads(line) for line in pend.read_text(encoding="utf-8").splitlines()]
    assert len(recs) == 1 and recs[0]["pattern_id"] == eid
    assert recs[0]["metadata"] == {"routed": True}
    assert not saved.exists()
    # idempotent: same content → same id, no second line
    eid2 = await orch._save_to_target("skill-learning", "routed контент в карантин", {"name": "r"})
    assert eid2 == eid
    assert len(pend.read_text(encoding="utf-8").splitlines()) == 1


async def test_route_and_save_skill_learning_auto_confirm(orchestrator, monkeypatch):
    orch, root = orchestrator
    # B1 pin: auto_confirm эмитит saved БЕЗ reason="pending" (мусор в fact-trace)
    import src.memory.orchestrator.ingest_metrics as im

    events: list[dict] = []
    monkeypatch.setattr(
        im, "record_ingest", lambda store, action, **kw: events.append({"action": action, **kw})
    )
    await orch._save_to_target(
        "skill-learning", "явно подтверждённый контент", {"name": "a", "auto_confirm": True}
    )
    saved = root / "data" / "skill_learning" / "patterns.jsonl"
    assert len(saved.read_text(encoding="utf-8").splitlines()) == 1
    saved_events = [e for e in events if e["action"] == "saved"]
    assert saved_events and saved_events[0].get("reason") is None


async def test_route_and_save_skill_learning_rejected_blocks(orchestrator):
    orch, root = orchestrator
    sl_dir = root / "data" / "skill_learning"
    sl_dir.mkdir(parents=True, exist_ok=True)
    from src.memory.orchestrator.content_hash import hash_content

    ch = hash_content("ранее отклонённый контент маршрута")
    (sl_dir / "rejected_patterns.jsonl").write_text(
        json.dumps({"pattern_id": "rj", "content_hash": ch}) + "\n", encoding="utf-8"
    )
    eid = await orch._save_to_target("skill-learning", "ранее отклонённый контент маршрута", None)
    assert eid == "rj"  # dup against rejected silo, nothing written
    assert not (sl_dir / "pending_patterns.jsonl").exists()


# ---------------------------------------------------------------------------
# P1.2 — quarantine_items / harvest split
# ---------------------------------------------------------------------------
@pytest.fixture
def pattern_harvest():
    # importlib file-load, НЕ `from shared import ...`: src/shared (real package)
    # затеняет .claude/hooks/shared при полном прогоне ([[feedback-hook-src-shared-collision]])
    name = "_ph_test_revival"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, PROJECT_ROOT / ".claude" / "hooks" / "shared" / "pattern_harvest.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # до exec_module: @dataclass резолвит sys.modules[__module__]
    spec.loader.exec_module(mod)
    return mod


class _StubClient:
    def __init__(self, known=()):
        self.known = set(known)

    def retrieve(self, collection_name, ids):
        return [1] if any(i in self.known for i in ids) else []


def _item(ph, content: str, confidence: float = 0.7):
    return ph.HarvestItem(
        content=content,
        name=content[:20],
        description="",
        pattern_type="workflow-pattern",
        source="session-lesson:test.md",
        confidence=confidence,
    )


def test_quarantine_items_writes_pending_and_dedups(pattern_harvest, tmp_path):
    ph = pattern_harvest
    pend, saved, rej = tmp_path / "p.jsonl", tmp_path / "s.jsonl", tmp_path / "r.jsonl"
    items = [_item(ph, "урок номер один в карантин"), _item(ph, "урок номер один в карантин")]
    st = ph.quarantine_items(
        items, client=_StubClient(), pending_file=pend, saved_file=saved, rejected_file=rej
    )
    assert st["quarantined"] == 1
    recs = [json.loads(line) for line in pend.read_text(encoding="utf-8").splitlines()]
    assert recs[0]["metadata"]["auto_captured"] is True
    # re-run → dup against pending silo
    st2 = ph.quarantine_items(
        items[:1], client=_StubClient(), pending_file=pend, saved_file=saved, rejected_file=rej
    )
    assert st2["quarantined"] == 0 and st2["skipped_dup"] == 1


def test_quarantine_skips_learned_patterns_existing(pattern_harvest, tmp_path):
    ph = pattern_harvest
    it = _item(ph, "урок уже собранный старым маршрутом")
    client = _StubClient(known=[ph._point_id(it.content_hash)])
    st = ph.quarantine_items(
        [it],
        client=client,
        pending_file=tmp_path / "p.jsonl",
        saved_file=tmp_path / "s.jsonl",
        rejected_file=tmp_path / "r.jsonl",
    )
    assert st["quarantined"] == 0 and st["skipped_dup"] == 1


def test_harvest_splits_by_confidence(pattern_harvest, tmp_path, monkeypatch):
    ph = pattern_harvest
    lc = tmp_path / "lifecycle"
    lc.mkdir()
    (lc / "s.md").write_text(
        "## Lessons\n- содержательный авто-урок сессии длиной больше минимума\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ph, "QUARANTINE_ENABLED", True)
    stats = ph.harvest(
        drafts_dir=tmp_path / "drafts",
        lifecycle_dir=lc,
        skill_learning_file=tmp_path / "none.jsonl",
        dry_run=True,
    )
    # auto-lesson (conf 0.7 < 0.8) → quarantine, not direct ingest
    assert stats["created"] == 0
    assert stats["quarantined"] == 1
    # opt-out → old direct behaviour
    monkeypatch.setattr(ph, "QUARANTINE_ENABLED", False)
    stats2 = ph.harvest(
        drafts_dir=tmp_path / "drafts",
        lifecycle_dir=lc,
        skill_learning_file=tmp_path / "none.jsonl",
        dry_run=True,
    )
    assert stats2["created"] == 1 and "quarantined" not in stats2


# ---------------------------------------------------------------------------
# P2.2 — memory-first-hook skill-learning arm
# ---------------------------------------------------------------------------
@pytest.fixture
def mf_hook():
    spec = importlib.util.spec_from_file_location(
        "_mfh_test", PROJECT_ROOT / ".claude" / "hooks" / "memory-first-hook.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_mfh_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_hook_arm_surfaces_pending_with_damp(mf_hook, tmp_path, monkeypatch):
    monkeypatch.setattr(mf_hook, "SKILL_LEARNING_DIR", tmp_path)
    (tmp_path / "patterns.jsonl").write_text(
        json.dumps(
            {"pattern_id": "s1", "name": "атомарная запись", "content": "атомарная перезапись JSONL"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "pending_patterns.jsonl").write_text(
        json.dumps(
            {"pattern_id": "p1", "name": "кандидат", "content": "кандидат про атомарную перезапись JSONL"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    qt = set(mf_hook.tokenize("атомарная перезапись JSONL"))
    hits = mf_hook._search_skill_learning(qt, limit=10)
    assert len(hits) == 2
    pend = next(h for h in hits if h["status"] == "pending")
    saved = next(h for h in hits if h["status"] == "saved")
    assert pend["content"].startswith("[pending] ")
    assert pend["category"] == "sl/pending" and saved["category"] == "sl/saved"
    assert saved["score"] > pend["score"]  # damp applied


def test_hook_arm_opt_out(mf_hook, tmp_path, monkeypatch):
    monkeypatch.setattr(mf_hook, "SKILL_LEARNING_ARM_ENABLED", False)
    assert mf_hook._search_skill_learning({"токен"}, limit=5) == []


# ---------------------------------------------------------------------------
# P2.3 — adapter RU normalization
# ---------------------------------------------------------------------------
def test_sl_tokenize_matches_morphoforms():
    from src.memory.orchestrator.memory_orchestrator import _sl_tokenize

    q = _sl_tokenize("атомарной перезаписью файлов")
    c = _sl_tokenize("атомарная перезапись файла")
    assert q & c  # stems collide where exact word-overlap would not


async def test_adapter_search_normalized(tmp_path):
    from src.memory.orchestrator.memory_orchestrator import SkillLearningSearchAdapter

    (tmp_path / "patterns.jsonl").write_text(
        json.dumps(
            {
                "pattern_id": "a1",
                "name": "атомарная запись JSONL",
                "content": "атомарная перезапись JSONL через tmp",
                "created_at": datetime.now().isoformat(),
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    ad = SkillLearningSearchAdapter(tmp_path)
    results = await ad.search("атомарной перезаписью JSONL файла")
    assert results and results[0].unified_id.startswith("learning:skill-learning:")


# ---------------------------------------------------------------------------
# P3.1 — review_pending TTL auto-reject
# ---------------------------------------------------------------------------
@pytest.fixture
def maintenance(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "_mm_test", PROJECT_ROOT / "scripts" / "memory_maintenance.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_mm_test"] = mod
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "SL_PENDING", tmp_path / "pending_patterns.jsonl")
    monkeypatch.setattr(mod, "SL_REJECTED", tmp_path / "rejected_patterns.jsonl")
    return mod


def test_review_pending_dry_run_then_apply(maintenance):
    mm = maintenance
    now = datetime.now()
    old = (now - timedelta(days=45)).isoformat()
    fresh = (now - timedelta(days=5)).isoformat()
    mm.SL_PENDING.write_text(
        json.dumps({"pattern_id": "old1", "content_hash": "h1", "created_at": old}) + "\n"
        + json.dumps({"pattern_id": "new1", "content_hash": "h2", "created_at": fresh}) + "\n"
        + json.dumps({"pattern_id": "nodate", "content_hash": "h3"}) + "\n",
        encoding="utf-8",
    )
    s1 = mm.run_review_pending(False, now)
    assert s1 == {"pending": 3, "expired": 1, "ttl_days": mm.PENDING_TTL_DAYS, "applied": False}
    assert len(mm.SL_PENDING.read_text(encoding="utf-8").splitlines()) == 3  # untouched

    s2 = mm.run_review_pending(True, now)
    assert s2["applied"] is True
    rej = [json.loads(line) for line in mm.SL_REJECTED.read_text(encoding="utf-8").splitlines()]
    assert rej[0]["pattern_id"] == "old1" and rej[0]["reject_reason"] == "ttl_expired"
    left = {
        json.loads(line)["pattern_id"]
        for line in mm.SL_PENDING.read_text(encoding="utf-8").splitlines()
    }
    assert left == {"new1", "nodate"}  # no created_at → честный skip, не auto-reject


def test_review_pending_null_created_at_is_fail_soft(maintenance):
    # B2 pin: "created_at": null давал неперехваченный TypeError (ловился только
    # ValueError) и ронял весь maintenance-ран
    mm = maintenance
    now = datetime.now()
    mm.SL_PENDING.write_text(
        json.dumps({"pattern_id": "nullts", "content_hash": "h", "created_at": None}) + "\n",
        encoding="utf-8",
    )
    s = mm.run_review_pending(True, now)
    assert s["expired"] == 0 and s["pending"] == 1  # skip, не crash и не reject
