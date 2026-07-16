"""Payload-contract regression (roadmap 260716 P0.5).

The 2026-07-16 incident: ONE point stored with `pattern_type: 'requirements'` made
`PatternType(...)` raise inside a read loop, which took down the whole
`search_patterns` response and put the `unified_search` vector arm into
`sources_failed`. Two independent defects — a strict reader and unvalidated writers —
so both sides are pinned here:

  * coercion   — the single alias table maps every observed drift value;
  * read-path  — a drifted/None/garbage payload degrades a FIELD, never raises;
  * isolation  — one unreadable point costs that point, not the response;
  * write-path — the three automated writers cannot store a non-canonical type.

Fixture payloads deliberately mirror the real drift found in the live collection.
"""

from __future__ import annotations

import json
from datetime import datetime

import pytest

pytestmark = pytest.mark.unit


# Values actually found in `learned_patterns` / the skill-learning silos (audit §2).
OBSERVED_DRIFT = {
    "requirements": "workflow-pattern",
    "error-fix": "debugging-heuristic",
    "1c-bsl": "bsl-pattern",
    "1c-query-optimization": "bsl-pattern",
    "1c-metadata-pattern": "bsl-pattern",
    "workflow": "workflow-pattern",
    "testing-workflow": "workflow-pattern",
    "refactor-pattern": "code-convention",
    "architecture-lesson": "architectural-principle",
    "debugging": "debugging-heuristic",
}


# ---------------------------------------------------------------------------
# P0.1 — coercion
# ---------------------------------------------------------------------------
class TestCoerce:
    def test_observed_drift_maps_to_canonical(self):
        from src.memory.vector_memory.models import PatternType

        for raw, expected in OBSERVED_DRIFT.items():
            assert PatternType.coerce(raw).value == expected, raw

    def test_canonical_values_pass_through(self):
        from src.memory.vector_memory.models import PatternType

        for pt in PatternType:
            assert PatternType.coerce(pt.value) is pt
            assert PatternType.coerce(pt) is pt  # enum instance

    @pytest.mark.parametrize("value", [None, "", "   ", "totally-unknown", 123, {"a": 1}])
    def test_unknown_and_junk_fall_back_to_default(self, value):
        from src.memory.vector_memory.models import DEFAULT_PATTERN_TYPE, PatternType

        assert PatternType.coerce(value) is DEFAULT_PATTERN_TYPE

    def test_default_is_not_invariant(self):
        # Junk must stay archivable by staleness — otherwise unknown types would be
        # immortal in the ForgetGate.
        from src.memory.vector_memory.confidence import is_invariant
        from src.memory.vector_memory.models import DEFAULT_PATTERN_TYPE

        assert is_invariant(DEFAULT_PATTERN_TYPE.value) is False

    def test_key_normalization(self):
        from src.memory.vector_memory.models import PatternType

        assert PatternType.coerce("  Error_Fix  ").value == "debugging-heuristic"
        assert PatternType.coerce("CODE-CONVENTION").value == "code-convention"

    def test_normalize_reports_original_only_when_coerced(self):
        from src.memory.vector_memory.models import normalize_pattern_type

        assert normalize_pattern_type("requirements") == ("workflow-pattern", "requirements")
        # No coercion happened → nothing to preserve.
        assert normalize_pattern_type("bsl-pattern") == ("bsl-pattern", None)
        assert normalize_pattern_type(None) == ("workflow-pattern", None)

    def test_is_invariant_uses_canonical_type(self):
        # `1c-bsl` coerces to bsl-pattern, so it must be invariant exactly like the
        # canonical spelling (design Д4) — search and ForgetGate must not disagree.
        from src.memory.vector_memory.confidence import is_invariant

        assert is_invariant("1c-bsl") is True
        assert is_invariant("bsl-pattern") is True
        assert is_invariant("") is False


class TestSafeParsers:
    def test_coerce_float_rejects_none_garbage_and_nonfinite(self):
        from src.memory.vector_memory.models import coerce_float

        assert coerce_float(None, 0.5) == 0.5
        assert coerce_float("abc", 0.5) == 0.5
        assert coerce_float("nan", 0.5) == 0.5  # survives float(), poisons sorting
        assert coerce_float(float("inf"), 0.5) == 0.5
        assert coerce_float("0.9", 0.5) == 0.9

    def test_coerce_dt_never_raises(self):
        from src.memory.vector_memory.models import coerce_dt

        assert coerce_dt(None) is None
        assert coerce_dt("garbage") is None
        assert coerce_dt(12345) is None
        assert coerce_dt("2026-07-16T10:00:00") == datetime(2026, 7, 16, 10, 0, 0)


# ---------------------------------------------------------------------------
# P0.2 — tolerant read
# ---------------------------------------------------------------------------
def _poisoned_payload() -> dict:
    """Every defect the audit found, in one payload.

    Keep this exhaustive — it is the fixture the tolerant-read tests share, and an
    omission here is a live hole: the first cut lacked `expired_at`/`version`, and a
    strict `fromisoformat(payload["expired_at"])` survived review inside a function
    whose own docstring promised "Never raises".
    """
    return {
        "pattern_id": "p-bad",
        "pattern_type": "requirements",  # out of enum → the incident
        "name": "bad",
        "content": "poisoned",
        "confidence": None,  # explicit null: .get(k, default) does NOT cover it
        "created_at": "not-a-date",
        "last_decay_at": "also-not-a-date",
        "expired_at": "not-a-date-either",
        # succ/fail BOTH absent → consumers take the legacy-seed branch.
        "application_count": None,
        "decay_rate": "x",
        "version": None,
        "evidence_sources": [{"source_type": "x", "reference": "y", "timestamp": "bad"}],
    }


def _garbage_counts_payload() -> dict:
    """Counts PRESENT but garbage — the branch _poisoned_payload cannot reach.

    Every consumer short-circuits to the legacy-seed branch when succ OR fail is
    missing, so a fixture carrying `succ: "abc"` next to `fail: None` never
    exercises `coerce_float(raw_succ, ...)`. That inert poison is exactly why two
    strict `float(succ)` sites survived review.
    """
    return {
        "pattern_id": "p-counts",
        "pattern_type": "bsl-pattern",
        "name": "garbage counts",
        "content": "counts present but unusable",
        "confidence": "high",  # legacy TEXT importance
        "succ": "abc",
        "fail": [],
        "created_at": datetime.now().isoformat(),
        "last_decay_at": datetime.now().isoformat(),
    }


class TestTolerantRead:
    def test_pattern_from_payload_survives_every_defect(self):
        from src.memory.vector_memory.server import _pattern_from_payload

        p = _pattern_from_payload("pid", _poisoned_payload())
        assert p.pattern_type.value == "workflow-pattern"
        assert isinstance(p.created_at, datetime)
        assert p.confidence == 0.5

    def test_pattern_from_payload_handles_none_payload(self):
        from src.memory.vector_memory.server import _pattern_from_payload

        assert _pattern_from_payload("pid", None).content == ""

    def test_garbage_counts_branch_is_tolerant(self):
        # The `succ`/`fail` PRESENT-but-garbage branch (see fixture docstring).
        from src.memory.vector_memory.confidence import payload_effective_confidence
        from src.memory.vector_memory.server import _pattern_from_payload

        payload = _garbage_counts_payload()
        assert 0.0 < payload_effective_confidence(payload) < 1.0
        p = _pattern_from_payload("pid", payload)
        assert p.succ == 0.0 and p.fail == 0.0

    def test_resolve_state_tolerates_null_confidence(self):
        # `confidence: null` reached seed_counts_from_legacy as None → `None * n`
        # TypeError, killing search/list/decay for the whole collection.
        from src.memory.vector_memory.confidence import payload_effective_confidence

        eff = payload_effective_confidence(_poisoned_payload())
        assert 0.0 < eff < 1.0

    def test_should_archive_tolerates_garbage_dates(self):
        from src.memory.vector_memory.confidence import should_archive

        assert should_archive(_poisoned_payload(), datetime.now()) in (True, False)

    def test_model_from_dict_is_tolerant(self):
        from src.memory.vector_memory.models import LearnedPattern

        p = LearnedPattern.from_dict({"pattern_type": "error-fix"})  # missing keys too
        assert p.pattern_type.value == "debugging-heuristic"
        assert p.content == ""

    def test_evidence_source_tolerates_garbage_timestamp(self):
        from src.memory.vector_memory.models import EvidenceSource

        e = EvidenceSource.from_dict({"source": "harvester", "timestamp": "bad", "weight": "x"})
        assert e.timestamp is None
        assert e.weight == 1.0

    def test_apply_to_payload_survives_poisoned_payload(self):
        # Regression: `int(payload.get("application_count", 0))` raised on an explicit
        # null AFTER set_payload had already written — the write landed, the caller
        # got an error, the lifecycle record was lost.
        from src.memory.vector_memory.confidence import apply_to_payload

        updates = apply_to_payload(_poisoned_payload(), True, datetime.now())
        assert updates["application_count"] == 1
        assert 0.0 < updates["confidence"] < 1.0

    async def test_get_pattern_survives_poisoned_point(self, monkeypatch):
        # handle_get_pattern is the one _pattern_from_payload caller with no per-item
        # backstop: a strict parse here surfaces as "Error: ..." to the client.
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm

        point = type("P", (), {"id": "p-bad", "payload": _poisoned_payload()})()
        monkeypatch.setattr(
            vm, "_get_qdrant", lambda: type("C", (), {"retrieve": lambda *a, **k: [point]})()
        )

        out = json.loads((await vm.handle_get_pattern({"pattern_id": "p-bad"}))[0].text)
        assert out["success"] is True
        assert out["pattern"]["pattern_type"] == "workflow-pattern"

    def test_reinforce_survives_poisoned_payload(self):
        # The pattern-reinforce-stop production path: the mutation must not be
        # followed by a raise — set_payload has already landed by then.
        import src.memory.vector_memory.reinforce as rf

        point = type("P", (), {"id": "p-bad", "payload": _poisoned_payload()})()

        class _C:
            def __init__(self):
                self.written = []

            def retrieve(self, *a, **k):
                return [point]

            def set_payload(self, *a, **k):
                self.written.append(k)

        client = _C()
        result = rf.reinforce_pattern("p-bad", success=True, client=client)
        assert result["success"] is True, result
        assert client.written, "the point must actually be updated"


class TestPerItemIsolation:
    """One unreadable point must not cost the whole response."""

    class _Point:
        def __init__(self, pid, payload, score=0.9):
            self.id = pid
            self.payload = payload
            self.score = score

    def _healthy(self, pid="p-ok"):
        return self._Point(
            pid,
            {
                "pattern_id": pid,
                "pattern_type": "code-convention",
                "name": "ok",
                "content": "healthy",
                "confidence": 0.8,
                "succ": 5.0,
                "fail": 0.0,
                "created_at": datetime.now().isoformat(),
            },
        )

    async def test_search_skips_only_the_bad_point(self, monkeypatch):
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm

        # A payload that defeats even the tolerant parse: coercion cannot rescue a
        # non-dict payload, so this exercises the try/except backstop itself.
        bad = self._Point("p-bad", ["not", "a", "dict"])
        results = type("R", (), {"points": [self._healthy("a"), bad, self._healthy("b")]})()

        monkeypatch.setattr(
            vm, "_get_qdrant", lambda: type("C", (), {"query_points": lambda *a, **k: results})()
        )
        monkeypatch.setattr(vm, "_get_embedding", _fake_embed)

        out = json.loads(
            (await vm.handle_search_patterns({"query": "q", "min_confidence": 0.0}))[0].text
        )
        assert out["count"] == 2  # both healthy points survived
        assert out["items_skipped"] == 1

    async def test_list_skips_only_the_bad_point(self, monkeypatch):
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm

        points = [self._healthy("a"), self._Point("p-bad", ["nope"]), self._healthy("b")]
        monkeypatch.setattr(
            vm, "_get_qdrant", lambda: type("C", (), {"scroll": lambda *a, **k: (points, None)})()
        )

        out = json.loads((await vm.handle_list_patterns({}))[0].text)
        assert out["count"] == 2
        assert out["items_skipped"] == 1

    async def test_unified_search_vector_arm_survives_bad_point(self, monkeypatch):
        """The literal incident surface: this arm landed in `sources_failed`.

        The no-blanket-except rule for the arm (honest infra failure) must not be
        conflated with per-point tolerance.
        """
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm
        from src.memory.orchestrator.memory_orchestrator import VectorMemorySearchAdapter

        points = [self._healthy("a"), self._Point("p-bad", ["not-a-dict"]), self._healthy("b")]
        monkeypatch.setattr(
            vm,
            "_get_qdrant",
            lambda: type(
                "C", (), {"query_points": lambda *a, **k: type("R", (), {"points": points})()}
            )(),
        )
        monkeypatch.setattr(vm, "_get_embedding", _fake_embed)

        items = await VectorMemorySearchAdapter().search("q", limit=5)
        assert len(items) == 2  # arm alive, only the bad point dropped

    async def test_vector_arm_still_propagates_infra_failure(self, monkeypatch):
        # Guard against over-catching: TEI/Qdrant down must still reach
        # sources_failed (honest-failure contract, roadmap 260611 F12).
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm
        from src.memory.orchestrator.memory_orchestrator import VectorMemorySearchAdapter

        def _boom():
            raise ConnectionError("qdrant down")

        monkeypatch.setattr(vm, "_get_qdrant", _boom)
        with pytest.raises(ConnectionError):
            await VectorMemorySearchAdapter().search("q", limit=5)

    async def test_cascade_survives_bad_neighbour(self, monkeypatch):
        """One bad neighbour must not abort the cascade for the healthy ones.

        Before P0 the failure escaped to the function-level `except: pass`, which
        also skipped _bump_epoch() — already-written neighbours sat behind a stale
        surfacing cache.
        """
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm

        store = {
            # Garbage counts are COERCED, not skipped — the neighbour still gets its
            # nudge (degraded fields), which is the point of the coercion layer.
            "n-garbage": {"succ": "abc", "fail": []},
            # A non-dict payload defeats coercion itself → exercises the try/except.
            "n-bad": ["not-a-dict"],
            "n-good": {"succ": 1.0, "fail": 0.0, "confidence": 0.7},
        }

        class _C:
            def __init__(self):
                self.written = []

            def retrieve(self, collection_name, ids, with_payload=True):
                pid = ids[0]
                return [self._Pt(pid, store[pid])] if pid in store else []

            def set_payload(self, collection_name, payload, points):
                self.written.append(points[0])

            class _Pt:
                def __init__(self, pid, payload):
                    self.id = pid
                    self.payload = payload

        class _Link:
            def __init__(self, tid):
                self.target_id = tid
                self.strength = 0.8
                self.created_at = datetime.now().isoformat()

        class _Reg:
            def get_links_from(self, pid, link_types=None):
                if ":" in pid:  # the unified-ID lookup — same edges, dedup by `seen`
                    return []
                return [_Link("n-garbage"), _Link("n-bad"), _Link("n-good")]

        # _cascade_confidence imports `memory.orchestrator.link_registry` (NOT
        # `src.memory...`), which only resolves once <repo>/src is on sys.path — the
        # running server puts it there lazily inside _get_embedding. Reproduce that
        # state, otherwise the import fails, the function no-ops via its outer
        # `except: pass`, and this test would pass vacuously against a dead cascade.
        import sys
        from pathlib import Path

        src_dir = str(Path(__file__).resolve().parents[2] / "src")
        if src_dir not in sys.path:
            sys.path.append(src_dir)
        import memory.orchestrator.link_registry as lr

        monkeypatch.setattr(lr, "LinkRegistry", lambda *a, **k: _Reg())
        bumped: list = []
        monkeypatch.setattr(vm, "_bump_epoch", lambda: bumped.append(1))

        client = _C()
        stats = vm._cascade_confidence(client, "p-src", True, datetime.now())
        # The unreadable neighbour costs exactly itself: the healthy one AND the
        # coercible-garbage one are still nudged.
        assert set(client.written) == {"n-good", "n-garbage"}, client.written
        assert stats["entities_updated"] == 2
        assert stats["errors"] == 1  # surfaced, not just logged
        # ...and the epoch is still bumped, so surfacing sees the partial result.
        assert bumped, "a partial cascade must still invalidate the surfacing cache"

    async def test_propagation_handler_survives_garbage_counts(self, monkeypatch, tmp_path):
        """The vector propagation handler runs behind a circuit breaker: a raise on
        one point ticks `propagation:vector-memory` toward OPEN, and then the breaker
        fails the WHOLE arm as failed:circuit_open. So one point with garbage counts
        must degrade, never raise.
        """
        pytest.importorskip("qdrant_client")
        from types import SimpleNamespace

        from src.memory.orchestrator.memory_orchestrator import MemoryOrchestrator
        from src.memory.orchestrator.unified_id import SourceServer
        from src.memory.vector_memory import server as vm_server

        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path / "cache"))
        written: list = []

        class _FakeQdrant:
            def retrieve(self, collection_name, ids, with_payload):
                # Counts PRESENT but unusable — the branch that stayed strict.
                return [SimpleNamespace(payload={"succ": "abc", "fail": [], "confidence": None})]

            def set_payload(self, collection_name, payload, points):
                written.append(payload)

        monkeypatch.setattr(vm_server, "_get_qdrant", lambda: _FakeQdrant())

        handler = MemoryOrchestrator()._build_propagation_handlers()[SourceServer.VECTOR_MEMORY]
        assert await handler("semantic:vector-memory:p1", 1.0) is True
        assert written and 0.0 < written[0]["confidence"] < 1.0

    async def test_handler_seeds_legacy_points_at_the_prior(self, monkeypatch, tmp_path):
        """Pin the CALL SITE, not just the helper (delegation must stay behaviour-preserving).

        The payload here has NO succ/fail and NO confidence → the legacy-seed branch,
        the only place `default_confidence` is read. The earlier version of this test
        asserted on `_resolve_state` directly while the handler test used a
        counts-present payload — so `default_confidence=0.70` could be deleted with
        the whole suite still green. That is the same inert-poison trap documented on
        `_garbage_counts_payload` one floor up.

        Seeding at the Beta prior (0.70) leaves derive_confidence AT the prior; the
        read-path default (0.5) would drag a legacy point below it (n=4 → 0.643).
        """
        pytest.importorskip("qdrant_client")
        from types import SimpleNamespace

        from src.memory.orchestrator.memory_orchestrator import MemoryOrchestrator
        from src.memory.orchestrator.unified_id import SourceServer
        from src.memory.vector_memory import server as vm_server

        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path / "cache"))
        written: list = []

        class _FakeQdrant:
            def retrieve(self, collection_name, ids, with_payload):
                return [SimpleNamespace(payload={"application_count": 4})]

            def set_payload(self, collection_name, payload, points):
                written.append(payload)

        monkeypatch.setattr(vm_server, "_get_qdrant", lambda: _FakeQdrant())

        handler = MemoryOrchestrator()._build_propagation_handlers()[SourceServer.VECTOR_MEMORY]
        assert await handler("semantic:vector-memory:p1", 1.0) is True
        # prior-seed 0.70·4 = (2.8, 1.2), then +1.0 on succ for a positive delta.
        assert written[0]["succ"] == round(2.8 + 1.0, 6), written[0]
        assert written[0]["fail"] == round(1.2, 6)

    def test_read_path_seed_default_is_untouched(self):
        from src.memory.vector_memory.confidence import _resolve_state

        assert _resolve_state({"application_count": 4})[:2] == (2.0, 2.0)

    async def test_skill_learning_arm_survives_bad_record(self, monkeypatch, tmp_path):
        """A garbage `created_at` in the silo used to drop the whole skill-learning
        arm of unified_search into sources_failed — the vector-arm incident, in the
        sibling arm."""
        from src.memory.orchestrator import memory_orchestrator as mo

        silo = tmp_path / "patterns.jsonl"
        silo.write_text(
            json.dumps(
                {
                    "pattern_id": "1",
                    "name": "bad date",
                    "content": "alpha beta",
                    "created_at": "not-a-date",
                }
            )
            + "\n"
            + json.dumps(
                {
                    "pattern_id": "2",
                    "name": "ok",
                    "content": "alpha beta",
                    "created_at": datetime.now().isoformat(),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        items = await mo.SkillLearningSearchAdapter(tmp_path).search("alpha beta", limit=5)
        assert len(items) == 2  # both survive; the bad date degrades to None
        assert any(i.created_at is None for i in items)

    def test_plan_forget_reports_unreadable_instead_of_dying(self):
        from src.memory.maintenance.forget_gate import plan_forget

        points = [
            {
                "id": "ok",
                "payload": {"succ": 10, "fail": 0, "created_at": datetime.now().isoformat()},
            },
            {"id": "bad", "payload": ["not-a-dict"]},
        ]
        plan = plan_forget(points, datetime.now())
        assert plan.unreadable == ["bad"]
        assert "ok" in plan.keep
        # Never archive what could not be evaluated.
        assert plan.archive == []


async def _fake_embed(text):
    return [0.1] * 4096


# ---------------------------------------------------------------------------
# P0.3 — writers cannot store a non-canonical type
# ---------------------------------------------------------------------------
class TestWriteContract:
    def test_harvester_coerces_and_keeps_provenance(self):
        import importlib.util
        import sys
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[2]
            / ".claude"
            / "hooks"
            / "shared"
            / "pattern_harvest.py"
        )
        spec = importlib.util.spec_from_file_location("_ph_test", path)
        ph = importlib.util.module_from_spec(spec)
        sys.modules["_ph_test"] = ph
        spec.loader.exec_module(ph)

        item = ph.HarvestItem(
            content="x" * 40,
            name="n",
            description="d",
            pattern_type="requirements",
            source="skill-learning:1",
            tags=[],
        )
        payload = ph._build_payload(item, "hash", datetime.now())
        assert payload["pattern_type"] == "workflow-pattern"
        assert payload["metadata"]["original_pattern_type"] == "requirements"

    def test_capture_pattern_coerces_before_quarantine(self, monkeypatch, tmp_path):
        pytest.importorskip("mcp")
        import src.memory.skill_learning.server as sl

        written: list = []
        monkeypatch.setattr(sl, "PENDING_FILE", tmp_path / "pending.jsonl")
        monkeypatch.setattr(sl, "_existing_hashes", lambda: {})
        monkeypatch.setattr(sl, "_append_jsonl", lambda path, rec: written.append(rec))
        monkeypatch.setattr(sl, "_record_ingest", lambda *a, **k: None)

        import asyncio

        asyncio.run(
            sl.handle_capture_pattern(
                {"pattern_type": "error-fix", "name": "n", "content": "c" * 30}
            )
        )
        assert written, "capture must persist the pattern"
        assert written[0]["pattern_type"] == "debugging-heuristic"
        assert written[0]["metadata"]["original_pattern_type"] == "error-fix"

    async def test_route_and_save_coerces_both_targets(self, monkeypatch, tmp_path):
        """route_and_save hand-builds payloads, bypassing save_pattern's validation —
        it wrote `metadata={"pattern_type": None}` into Qdrant verbatim."""
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm
        from src.memory.orchestrator import memory_orchestrator as mo

        upserted: list = []

        class _C:
            def retrieve(self, *a, **k):
                return []

            def upsert(self, collection_name, points):
                upserted.extend(points)

        monkeypatch.setattr(vm, "_get_qdrant", lambda: _C())
        monkeypatch.setattr(vm, "_get_embedding", _fake_embed)
        monkeypatch.setattr(mo, "_PROJECT_ROOT", tmp_path)

        orch = mo.MemoryOrchestrator()
        # vector-memory branch
        await orch._save_to_target(
            "vector-memory", "content that is long enough", {"pattern_type": "error-fix"}
        )
        assert upserted[0].payload["pattern_type"] == "debugging-heuristic"
        assert upserted[0].payload["metadata"]["original_pattern_type"] == "error-fix"

        # skill-learning branch → quarantine silo
        await orch._save_to_target(
            "skill-learning", "another long enough content", {"pattern_type": "requirements"}
        )
        pending = (tmp_path / "data" / "skill_learning" / "pending_patterns.jsonl").read_text(
            encoding="utf-8"
        )
        rec = json.loads(pending.splitlines()[0])
        assert rec["pattern_type"] == "workflow-pattern"
        assert rec["metadata"]["original_pattern_type"] == "requirements"

    async def test_route_and_save_rejects_empty_content_honestly(self, monkeypatch, tmp_path):
        """Empty content is rejected, not coerced (design Д5).

        `_save_to_target` swallows its own exceptions by contract and returns None;
        route_and_save turns that None into `failed_targets` + success:false. So the
        rejection is honest — never a crash, never a silent success.
        """
        pytest.importorskip("qdrant_client")
        from src.memory.orchestrator import memory_orchestrator as mo

        monkeypatch.setattr(mo, "_PROJECT_ROOT", tmp_path)
        orch = mo.MemoryOrchestrator()
        assert await orch._save_to_target("vector-memory", "   ", {}) is None
        assert await orch._save_to_target("skill-learning", "", {}) is None

    async def test_save_pattern_stays_strict(self, monkeypatch):
        """Pin design Д3: save_pattern is fail-closed on purpose.

        It is the ONE writer that must reject instead of coerce — an explicit MCP
        call with an enum-documented schema deserves an honest error. Without this
        pin, a "coerce everywhere" refactor would silently remove that.
        """
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm

        monkeypatch.setattr(
            vm,
            "_get_qdrant",
            lambda: type(
                "C", (), {"retrieve": lambda *a, **k: [], "upsert": lambda *a, **k: None}
            )(),
        )
        monkeypatch.setattr(vm, "_get_embedding", _fake_embed)

        with pytest.raises(ValueError):
            await vm.handle_save_pattern(
                {"pattern_type": "requirements", "name": "n", "content": "c" * 30}
            )

    def test_migration_preserves_unparsable_silo_lines(self, tmp_path):
        """The migration must never be a silent line-dropper.

        scan_silo/write_silo do a whole-file read-modify-write, so anything the
        script cannot parse has to be echoed back verbatim — the first cut dropped
        such lines while the docstring claimed the opposite.
        """
        import importlib.util
        import sys
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "scripts" / "migrate_pattern_types.py"
        spec = importlib.util.spec_from_file_location("_mig_test", path)
        mig = importlib.util.module_from_spec(spec)
        sys.modules["_mig_test"] = mig
        spec.loader.exec_module(mig)

        silo = tmp_path / "patterns.jsonl"
        silo.write_text(
            '{"pattern_id": "1", "pattern_type": "error-fix", "content": "x"}\n'
            "not json at all\n"
            '"a bare string, valid json but not an object"\n'
            '{"pattern_id": "2", "pattern_type": "bsl-pattern", "content": "y"}\n',
            encoding="utf-8",
        )
        entries, changes = mig.scan_silo(silo)
        assert len(changes) == 1  # only the drifted record
        mig.write_silo(silo, entries)

        lines = silo.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 4, lines  # nothing dropped
        assert "not json at all" in lines
        assert json.loads(lines[0])["pattern_type"] == "debugging-heuristic"
        assert json.loads(lines[3])["pattern_type"] == "bsl-pattern"  # untouched

    def test_capture_schema_advertises_the_enum(self):
        pytest.importorskip("mcp")
        import asyncio

        import src.memory.skill_learning.server as sl
        from src.memory.vector_memory.models import PatternType

        tools = asyncio.run(sl.list_tools())
        capture = next(t for t in tools if t.name == "capture_pattern")
        assert capture.inputSchema["properties"]["pattern_type"]["enum"] == [
            pt.value for pt in PatternType
        ]
