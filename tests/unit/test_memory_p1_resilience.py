"""P1 regression (roadmap 260716) — the memory paths that do not crash, they lie.

P0 hardened the INPUT (a drifted payload must not kill a reader). P1 hardens the
OUTPUT: a job that silently drops fields it does not know, a fusion that dilutes a
score with arms that said nothing, an error relabelled as a timeout, two readers of one
collection disagreeing about what is visible, a dedupe that would orphan the graph.

Each test below pins one such lie. They are written to go RED if the fix is reverted —
the P0 review cost four iterations to learn that a test which cannot fail pins nothing.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# P1.1 — merge must not lose fields
# ---------------------------------------------------------------------------
class TestMergeKeepsEverything:
    def _silo(self, tmp_path, lines: list[str]):
        (tmp_path / "patterns.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return tmp_path

    def _rows(self, d):
        return [
            json.loads(x)
            for x in (d / "patterns.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]

    async def test_unknown_fields_survive_a_merge(self, tmp_path):
        """`content_hash` / `evidence_sources` are written by producers with a WIDER schema.

        The cadence job rewrites the whole silo, so a field this dataclass does not
        declare used to be DELETED from disk — and the content_hash quarantine dedup
        went blind as a result.
        """
        from src.memory.skill_learning.merge_patterns import PatternMerger

        d = self._silo(
            tmp_path,
            [
                json.dumps(
                    {
                        "pattern_id": "a",
                        "content": "same text",
                        "confidence": 0.9,
                        "content_hash": "deadbeef",
                        "evidence_sources": [{"reference": "r"}],
                    }
                ),
                json.dumps({"pattern_id": "b", "content": "same text", "confidence": 0.4}),
            ],
        )
        result = await PatternMerger(d).merge_duplicates()
        assert result.patterns_merged == 1

        rows = self._rows(d)
        assert len(rows) == 1
        kept = rows[0]
        assert kept["pattern_id"] == "a"  # higher confidence wins
        assert kept["content_hash"] == "deadbeef"
        assert kept["evidence_sources"] == [{"reference": "r"}]

    async def test_a_live_duplicate_un_archives_the_merged_record(self, tmp_path):
        """Making `archived` durable without teaching the merge about it INVERTS the bug.

        The winner is picked by confidence, so an archived record at 0.9 beats a live
        one at 0.4 and the group used to collapse to an ARCHIVED record — deleting the
        live copy from the silo, after which pattern_harvest skips the fact entirely.
        (Before P1.1 the same input resurrected the archived record. Both are wrong.)

        §22 revive-on-recurrence decides it: a live duplicate means the fact came back.
        Archival is a claim about the FACT, not about one copy of it.
        """
        from src.memory.skill_learning.merge_patterns import PatternMerger

        d = self._silo(
            tmp_path,
            [
                json.dumps(
                    {"pattern_id": "a", "content": "x", "confidence": 0.9, "archived": True}
                ),
                json.dumps({"pattern_id": "b", "content": "x", "confidence": 0.4}),
            ],
        )
        await PatternMerger(d).merge_duplicates()

        rows = self._rows(d)
        assert len(rows) == 1
        assert not rows[0].get("archived"), "a live duplicate must revive the fact"

    async def test_all_archived_stays_archived(self, tmp_path):
        """The other half of the same rule: nothing came back, so nothing revives."""
        from src.memory.skill_learning.merge_patterns import PatternMerger

        d = self._silo(
            tmp_path,
            [
                json.dumps(
                    {"pattern_id": "a", "content": "x", "confidence": 0.9, "archived": True}
                ),
                json.dumps(
                    {"pattern_id": "b", "content": "x", "confidence": 0.4, "archived": True}
                ),
            ],
        )
        await PatternMerger(d).merge_duplicates()

        rows = self._rows(d)
        assert len(rows) == 1
        assert rows[0]["archived"] is True

    async def test_unreadable_line_is_preserved_not_dropped(self, tmp_path):
        """This job REWRITES the file, so "skip on read" means "delete from disk".

        Same class as the P0 migration defect (F6): a hand-edited or half-flushed line
        is a bug to look at, not data to discard silently.
        """
        from src.memory.skill_learning.merge_patterns import PatternMerger

        d = self._silo(
            tmp_path,
            [
                json.dumps({"pattern_id": "a", "content": "dup", "confidence": 0.9}),
                json.dumps({"pattern_id": "b", "content": "dup", "confidence": 0.5}),
                "{not json at all",
                "12345",  # parses, but is not a dict — used to raise out of the job
            ],
        )
        await PatternMerger(d).merge_duplicates()

        text = (d / "patterns.jsonl").read_text(encoding="utf-8")
        assert "{not json at all" in text
        assert "12345" in text

    def test_extra_bucket_never_shadows_a_known_field(self):
        from src.memory.skill_learning.merge_patterns import PatternRecord

        r = PatternRecord.from_dict({"pattern_id": "a", "confidence": 0.9, "weird": 1})
        r.confidence = 0.1  # a merge changed it
        r.extra["confidence"] = 0.9  # a stale copy must not win
        assert r.to_dict()["confidence"] == 0.1
        assert r.to_dict()["weird"] == 1


# ---------------------------------------------------------------------------
# P1.2 / P1.3 — fusion and honest failures
# ---------------------------------------------------------------------------
def _item(uid: str, score: float, created=None):
    from src.memory.orchestrator.unified_id import MemoryType, SourceServer
    from src.memory.orchestrator.unified_search import SearchResultItem

    return SearchResultItem(
        unified_id=uid,
        source=SourceServer.VECTOR_MEMORY,
        memory_type=MemoryType.SEMANTIC,
        content=uid,
        raw_score=score,
        created_at=created,
    )


class _Adapter:
    """Adapter returning a fixed payload, or raising / hanging on demand."""

    def __init__(self, name, items=None, raises=None, hang=False):
        self._name = name
        self._items = items or []
        self._raises = raises
        self._hang = hang
        self.calls = 0

    def source_name(self):
        return self._name

    async def search(self, query, limit=10, **kw):
        self.calls += 1
        if self._raises:
            raise self._raises
        if self._hang:
            await asyncio.sleep(10)
        return self._items


class TestRRFEmptyArms:
    async def test_single_arm_hit_does_not_sink_under_min_score(self):
        """An arm that says nothing is not evidence AGAINST a result.

        Failed arms never reach the fusion dict (they are in sources_failed), so empty
        ones must be excluded from the denominator too. With 3 arms registered and one
        hit, the old max_rrf gave that hit a base of 1/3 ≈ 0.33 — grazing the default
        min_score=0.3 — purely because two arms were silent.
        """
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        engine = UnifiedSearchEngine()
        engine.register_adapter(_Adapter("vector-memory", [_item("semantic:vector-memory:x", 0.2)]))
        engine.register_adapter(_Adapter("memory-ai", []))
        engine.register_adapter(_Adapter("skill-learning", []))

        out = await engine.search("q", min_score=0.3, include_links=False)
        # Old denominator: 0.6·0.33 + 0.4·0.2 = 0.28 -> filtered out entirely.
        assert out.total_results == 1, "a lone hit was diluted out of existence"
        assert out.results[0].normalized_score == pytest.approx(1.0)

    async def test_agreement_still_outranks_a_single_source(self):
        """Guard against over-correcting: RRF must still reward multi-arm agreement."""
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        engine = UnifiedSearchEngine()
        both = "semantic:vector-memory:both"
        engine.register_adapter(
            _Adapter("a", [_item(both, 0.5), _item("semantic:vector-memory:solo", 0.5)])
        )
        engine.register_adapter(_Adapter("b", [_item(both, 0.5)]))

        out = await engine.search("q", min_score=0.0, include_links=False)
        scores = {r.unified_id: r.final_score for r in out.results}
        assert scores[both] > scores["semantic:vector-memory:solo"]


class TestHonestFailures:
    """The hard-timeout reaper is pinned through `resolve_after_hard_timeout`, not
    through the timing that reaches it.

    The first cut of this test drove the whole engine with a failing + a hanging
    adapter and PASSED with the fix reverted: the failing arm is caught by the normal
    loop, so the salvage branch never saw it. Measuring the branch properly turned up
    why it is nearly unreachable — a coroutine that swallows CancelledError defeats the
    outer `asyncio.timeout` exactly as it defeats `wait_for` (probe: 1.03 s elapsed
    against a 0.15 s ceiling, no TimeoutError). Rather than fake loop starvation, the
    decision is a pure function and gets tested as one.
    """

    async def _done_task(self, coro):
        t = asyncio.create_task(coro)
        try:
            await t
        except Exception:
            pass
        return t

    async def test_real_error_is_not_relabelled_hard_timeout(self):
        """A task that already finished with a REAL error (TEI refused, Qdrant 400, a
        bad payload) must report THAT error, not `hard_timeout` — otherwise the true
        cause dies at the boundary and the operator goes hunting latency."""
        from src.memory.orchestrator.unified_search import resolve_after_hard_timeout

        async def _boom():
            raise ConnectionError("qdrant down")

        task = await self._done_task(_boom())
        results, err = resolve_after_hard_timeout("vector-memory", task, 7.5)
        assert results is None
        assert err.error_type == "ConnectionError"
        assert "qdrant down" in err.error

    async def test_finished_task_is_salvaged_not_discarded(self):
        from src.memory.orchestrator.unified_search import resolve_after_hard_timeout

        async def _ok():
            return [_item("semantic:vector-memory:x", 0.9)]

        task = await self._done_task(_ok())
        results, err = resolve_after_hard_timeout("vector-memory", task, 7.5)
        assert err is None
        assert [r.unified_id for r in results] == ["semantic:vector-memory:x"]

    async def test_still_running_task_is_cancelled_and_reported(self):
        from src.memory.orchestrator.unified_search import resolve_after_hard_timeout

        async def _hang():
            await asyncio.sleep(10)

        task = asyncio.create_task(_hang())
        await asyncio.sleep(0)  # let it start
        results, err = resolve_after_hard_timeout("slow", task, 7.5)
        assert results is None
        assert err.error_type == "hard_timeout"
        assert task.cancelled() or task.cancelling()

    async def test_normal_loop_still_reports_real_errors(self):
        """The everyday path (no hard timeout) must stay honest too."""
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        engine = UnifiedSearchEngine()
        engine.register_adapter(_Adapter("boom", raises=ConnectionError("qdrant down")))
        out = await engine.search("q", include_links=False)
        assert [(e.source, e.error_type) for e in out.sources_failed] == [
            ("boom", "ConnectionError")
        ]

    async def test_reaper_is_wired_into_the_hard_timeout_branch(self, monkeypatch):
        """Drive the real branch, not just its helper.

        The ceiling normally sits ABOVE every per-adapter timeout, so the branch never
        wins the race in a healthy engine — which is why a plain slow/failing pair of
        adapters could not reach it and the first version of this test was vacuous.
        Inverting HARD_TIMEOUT_FACTOR makes the backstop fire deterministically, so the
        call site (not only resolve_after_hard_timeout) is pinned.
        """
        from src.memory.orchestrator import unified_search as us

        monkeypatch.setattr(us, "HARD_TIMEOUT_FACTOR", 0.05)  # ceiling beats wait_for
        engine = us.UnifiedSearchEngine()
        engine.register_adapter(_Adapter("stuck", hang=True))  # awaited when the ceiling fires
        engine.register_adapter(_Adapter("boom", raises=ConnectionError("qdrant down")))

        out = await engine.search(
            "q", include_links=False, options=us.SearchOptions(timeout_ms=2000)
        )
        errs = {e.source: e.error_type for e in out.sources_failed}
        # `boom` finished with a real error while the loop was stuck on `stuck`; the
        # reaper must report ConnectionError, not the ceiling that happened to expire.
        assert errs == {"stuck": "hard_timeout", "boom": "ConnectionError"}

    async def test_open_breaker_fails_fast_and_honestly(self):
        """A tripped arm is a REPORTED failure, never a silent empty arm.

        Silence would read as "nothing matched" — the exact dishonesty P1 is about.
        And it must not be called at all: fail-fast is the whole point of the breaker.
        """
        from src.memory.infrastructure.circuit_breaker import CircuitBreakerRegistry
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        registry = CircuitBreakerRegistry()
        engine = UnifiedSearchEngine(breaker_registry=registry)
        arm = _Adapter("vector-memory", [_item("semantic:vector-memory:x", 0.9)])
        engine.register_adapter(arm)

        breaker = engine._breaker("vector-memory")
        for _ in range(5):  # failure_threshold
            breaker.record_failure("tei down")

        out = await engine.search("q", include_links=False)
        assert arm.calls == 0, "OPEN circuit must not pay the adapter timeout"
        assert [e.error_type for e in out.sources_failed] == ["circuit_open"]
        assert out.sources_searched == []

    async def test_breaker_registry_is_shared_with_propagation(self):
        """One registry, so memory_circuit_status/-reset control search too."""
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        class _Reg:
            def __init__(self):
                self.names = []

            def get_or_create(self, name, config=None):
                self.names.append(name)
                return None

        reg = _Reg()
        UnifiedSearchEngine(breaker_registry=reg)._breaker("vector-memory")
        assert reg.names == ["search:vector-memory"]  # mirrors "propagation:<source>"

    async def test_orchestrator_actually_wires_its_registry_into_search(self, monkeypatch):
        """Pin the WIRING, not just the engine's willingness to accept a registry.

        The test above builds the engine by hand, so reverting
        `UnifiedSearchEngine(link_registry, breaker_registry=...)` back to
        `UnifiedSearchEngine(link_registry)` in the orchestrator would leave search arms
        silently breaker-less and still green — the P0 "helper tested, call-site
        uncovered" trap.
        """
        from src.memory.orchestrator.memory_orchestrator import MemoryOrchestrator

        orch = MemoryOrchestrator()
        # start() pre-warms Qdrant/TEI; only the construction order matters here.
        monkeypatch.setattr(MemoryOrchestrator, "_build_propagation_handlers", lambda self: {})
        await orch.start()
        try:
            assert orch._search_engine._breaker_registry is orch._circuit_registry
            assert orch._search_engine._breaker("vector-memory") is not None
        finally:
            await orch.stop()

    async def test_engine_feeds_arm_outcomes_back_to_the_breaker(self):
        """The breaker must trip from REAL traffic, not only from a hand-cranked one.

        `test_open_breaker_fails_fast_and_honestly` arms the circuit itself, so deleting
        every `_record(...)` call left it green while a dead TEI never tripped anything
        and kept costing the full timeout per search — i.e. exactly what P1.3 claims to
        have fixed.
        """
        from src.memory.infrastructure.circuit_breaker import CircuitBreakerRegistry, CircuitState
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        registry = CircuitBreakerRegistry()
        engine = UnifiedSearchEngine(breaker_registry=registry)
        engine.register_adapter(_Adapter("vector-memory", raises=ConnectionError("tei down")))

        for _ in range(5):  # failure_threshold
            await engine.search("q", include_links=False)

        assert engine._breaker("vector-memory").state is CircuitState.OPEN

    async def test_success_keeps_the_circuit_closed(self):
        from src.memory.infrastructure.circuit_breaker import CircuitBreakerRegistry, CircuitState
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        registry = CircuitBreakerRegistry()
        engine = UnifiedSearchEngine(breaker_registry=registry)
        engine.register_adapter(_Adapter("vector-memory", [_item("semantic:vector-memory:x", 0.9)]))

        for _ in range(5):
            await engine.search("q", include_links=False)

        assert engine._breaker("vector-memory").state is CircuitState.CLOSED

    async def test_tripped_arm_recovers_after_reset_timeout(self):
        """A transient outage must not kill the arm for the life of the process.

        This is the regression P1.3 nearly shipped. `allow_request()` — the obvious API
        here — returns `success_count < half_open_max_probes` in HALF_OPEN, where
        success_count is a LIFETIME counter nothing resets. So an arm with any
        successful history was rejected forever once tripped, and a TEI restart became a
        permanent outage requiring /mcp reconnect: strictly worse than the slow arm the
        breaker was added to avoid.
        """
        from src.memory.infrastructure.circuit_breaker import (
            CircuitBreakerConfig,
            CircuitBreakerRegistry,
        )
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        registry = CircuitBreakerRegistry()
        engine = UnifiedSearchEngine(breaker_registry=registry)
        arm = _Adapter("vector-memory", [_item("semantic:vector-memory:x", 0.9)])
        engine.register_adapter(arm)

        breaker = registry.get_or_create(
            "search:vector-memory",
            CircuitBreakerConfig(failure_threshold=2, reset_timeout=60.0),
        )
        # Healthy history first — this is what makes the monotonic counter bite.
        breaker.record_success()
        breaker.record_success()
        breaker.record_failure("tei down")
        breaker.record_failure("tei down")

        out = await engine.search("q", include_links=False)
        assert [e.error_type for e in out.sources_failed] == ["circuit_open"]
        assert arm.calls == 0

        # ...outage over, reset_timeout elapsed (rewind the clock rather than sleep 60s).
        breaker._stats.last_failure_time -= 61.0

        out = await engine.search("q", include_links=False)
        assert arm.calls == 1, "the arm must be probed again once the circuit half-opens"
        assert out.sources_failed == []
        assert out.total_results == 1

    async def test_arm_failures_are_typed_in_the_trace(self, tmp_path, monkeypatch):
        """`sources_failed=[name]` could not tell TEI-down from a 400 from a breaker."""
        monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
        from src.memory.orchestrator.unified_search import UnifiedSearchEngine

        engine = UnifiedSearchEngine()
        engine.register_adapter(_Adapter("boom", raises=ValueError("bad payload")))
        await engine.search("q", include_links=False)

        log = tmp_path / "memory-read.log"
        assert log.exists()
        rec = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
        assert rec["sources_failed_detail"] == {"boom": "ValueError"}


class TestScoreNormalizerTz:
    def test_aware_created_at_does_not_kill_the_whole_search(self):
        """M9: this runs AFTER the arms are collected, outside per-adapter isolation —
        one aware datetime from any adapter would take down the entire federated search
        with `can't subtract offset-naive and offset-aware datetimes`."""
        from src.memory.orchestrator.unified_search import ScoreNormalizer, SearchOptions

        aware = datetime.now(UTC) - timedelta(hours=1)
        score = ScoreNormalizer().normalize(_item("x", 0.5, created=aware), SearchOptions())
        assert score == pytest.approx(0.5 * ScoreNormalizer.BOOST_RECENT_24H)


# ---------------------------------------------------------------------------
# P1.4 — one retrieval policy for one collection
# ---------------------------------------------------------------------------
class _Pt:
    def __init__(self, pid, payload, score=0.9):
        self.id = pid
        self.payload = payload
        self.score = score


def _live(pid, **over):
    payload = {
        "pattern_id": pid,
        "pattern_type": "workflow-pattern",
        "content": pid,
        "succ": 5.0,
        "fail": 0.0,
        "created_at": datetime.now().isoformat(),
        "last_decay_at": datetime.now().isoformat(),
    }
    payload.update(over)
    return _Pt(pid, payload)


class TestVectorArmSharesServerPolicy:
    async def _arm(self, monkeypatch, points):
        import src.memory.vector_memory.server as vm
        from src.memory.orchestrator.memory_orchestrator import VectorMemorySearchAdapter

        monkeypatch.setattr(
            vm,
            "_get_qdrant",
            lambda: type(
                "C", (), {"query_points": lambda *a, **k: type("R", (), {"points": points})()}
            )(),
        )

        async def _embed(_q):
            return [0.0] * 8

        monkeypatch.setattr(vm, "_get_embedding", _embed)
        return await VectorMemorySearchAdapter().search("q", limit=5)

    async def test_arm_hides_archived_like_search_patterns_does(self, monkeypatch):
        """M4: the arm never excluded `expired_at`, so unified_search surfaced patterns
        that a direct search_patterns deliberately hid — §24.2.4 held on one path only."""
        pytest.importorskip("qdrant_client")
        items = await self._arm(
            monkeypatch,
            [_live("alive"), _live("archived", expired_at=datetime.now().isoformat())],
        )
        assert [i.content for i in items] == ["alive"]

    async def test_arm_ranks_by_effective_confidence(self, monkeypatch):
        """The arm prefiltered/scored on the STORED denorm. Under count decay the
        effective value can differ from it, so the arm ranked by a number no other
        reader believed. Here the stored denorm is a lie in both directions."""
        pytest.importorskip("qdrant_client")
        items = await self._arm(monkeypatch, [_live("p", confidence=0.01)])
        assert items, "a stale stored denorm must not filter the point out"
        # score = similarity(0.9) x EFFECTIVE (~0.8 from succ=5), not x stored 0.01.
        assert items[0].raw_score > 0.5
        assert items[0].metadata["confidence"] > 0.5

    async def test_arm_and_tool_return_the_same_points(self, monkeypatch):
        """The actual invariant: two readers, one policy."""
        pytest.importorskip("qdrant_client")
        import src.memory.vector_memory.server as vm

        points = [_live("a"), _live("b", expired_at=datetime.now().isoformat()), _live("c")]
        items = await self._arm(monkeypatch, points)
        tool = json.loads(
            (await vm.handle_search_patterns({"query": "q", "min_confidence": 0.3}))[0].text
        )
        assert [i.content for i in items] == [r["pattern"]["content"] for r in tool["results"]]


# ---------------------------------------------------------------------------
# P1.5 — M6 (memory-ai importance)
# ---------------------------------------------------------------------------
class TestImportanceOrdering:
    def _db(self, tmp_path, rows):
        db = tmp_path / "m.db"
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE important_messages (id TEXT PRIMARY KEY, content TEXT, "
            "importance REAL DEFAULT 0.5, category TEXT, tags TEXT, created_at TEXT, "
            "updated_at TEXT, metadata TEXT)"
        )
        for i, (rid, imp) in enumerate(rows):
            conn.execute(
                "INSERT INTO important_messages VALUES (?,?,?,?,?,?,?,?)",
                (rid, rid, imp, "general", "[]", f"2026-01-0{i + 1}", None, None),
            )
        conn.commit()
        conn.close()
        return db

    async def test_text_importance_does_not_outrank_numbers(self, tmp_path, monkeypatch):
        """M6, in the direction the defect actually exists.

        The audit said legacy TEXT importance silently DROPS OUT of the filter
        (`TEXT >= 0.5` = false). Measured on sqlite3: the opposite. TEXT sorts above
        every REAL, so such a row always passes the filter and takes the top of
        `ORDER BY importance DESC` — 'low' outranked 0.99.
        """
        import src.memory.ai_memory.server as ai

        db = self._db(tmp_path, [("low-label", "low"), ("high-num", 0.99)])
        monkeypatch.setattr(ai, "DB_PATH", db)

        out = json.loads((await ai.get_important_messages({"min_importance": 0.5}))[0].text)
        ids = [m["id"] for m in out["messages"]]
        assert ids[0] == "high-num", "a TEXT label hijacked the top of the ranking"
        assert "low-label" not in ids, "'low' (0.3) must not pass min_importance=0.5"

    async def test_search_messages_window_is_not_hijacked_by_a_text_row(
        self, tmp_path, monkeypatch
    ):
        """M6 applies to EVERY reader of the column, not just get_important_messages.

        `search_messages` picks its candidate window with `ORDER BY importance` and has
        NO filter to save it, so a TEXT importance takes the top of the window and
        crowds real matches out before scoring even runs. Shrink the window to 1 and one
        junk row is enough to prove it — an assertion on the RETURNED order would not,
        since sorting the output in Python is a tautology.
        """
        import src.memory.ai_memory.server as ai

        db = self._db(tmp_path, [("junk", "low"), ("wanted", 0.99)])
        monkeypatch.setattr(ai, "DB_PATH", db)
        monkeypatch.setattr(ai, "SEARCH_WINDOW", 1)

        out = json.loads((await ai.search_messages({"query": "wanted"}))[0].text)
        assert [m["id"] for m in out["messages"]] == ["wanted"], (
            "a TEXT importance took the candidate window and hid the real match"
        )

    async def test_search_messages_coerces_importance_on_output(self, tmp_path, monkeypatch):
        import src.memory.ai_memory.server as ai

        db = self._db(tmp_path, [("junk", "low")])
        monkeypatch.setattr(ai, "DB_PATH", db)

        out = json.loads((await ai.search_messages({"query": "junk"}))[0].text)
        assert out["messages"][0]["importance"] == 0.3  # not the raw string "low"

    async def test_unknown_label_is_worthless_to_both_sql_and_python(self, tmp_path, monkeypatch):
        """A value nobody can interpret must not outrank ones that can — and the filter
        and the reported number must agree. SQL casts an unknown label to 0.0; reporting
        the writer's 0.7 default would filter the row out by one number and hand the
        caller another."""
        import src.memory.ai_memory.server as ai

        assert ai._coerce_importance("urgent", ai.READ_UNKNOWN_IMPORTANCE) == 0.0
        db = self._db(tmp_path, [("weird", "urgent"), ("real", 0.6)])
        monkeypatch.setattr(ai, "DB_PATH", db)

        out = json.loads((await ai.get_important_messages({"min_importance": 0.5}))[0].text)
        assert [m["id"] for m in out["messages"]] == ["real"]

    async def test_known_labels_keep_their_meaning(self, tmp_path, monkeypatch):
        """The label->number map is the writer's; SQL derives it from the same table,
        so a legacy 'high' still means 0.9 rather than being cast to 0.0 and dropped."""
        import src.memory.ai_memory.server as ai

        db = self._db(tmp_path, [("high-label", "high"), ("mid-num", 0.6)])
        monkeypatch.setattr(ai, "DB_PATH", db)

        out = json.loads((await ai.get_important_messages({"min_importance": 0.5}))[0].text)
        by_id = {m["id"]: m for m in out["messages"]}
        assert set(by_id) == {"high-label", "mid-num"}
        assert by_id["high-label"]["importance"] == 0.9  # coerced on the way out
        assert out["messages"][0]["id"] == "high-label"  # 0.9 > 0.6


# ---------------------------------------------------------------------------
# P1.6 — one Qdrant client per process
# ---------------------------------------------------------------------------
class TestReinforceClientReuse:
    def test_default_client_is_built_once(self, monkeypatch):
        """M11: reinforce_session walks up to 10 surfaced patterns per Stop hook, and
        each call used to open its own client — 10 unclosed TCP connections per
        session. On 2026-07-01 that produced 10 live reinforce_error entries with
        WinError 10048 (ephemeral port exhaustion)."""
        import src.memory.vector_memory.reinforce as r

        built = []

        class _FakeClient:
            def __init__(self, **kw):
                built.append(kw)

            def retrieve(self, **kw):
                return []

        monkeypatch.setitem(
            __import__("sys").modules,
            "qdrant_client",
            type("m", (), {"QdrantClient": _FakeClient}),
        )
        r.reset_default_client()
        try:
            for _ in range(10):
                r.reinforce_pattern("p", True)
            assert len(built) == 1, f"one client per process, got {len(built)}"
        finally:
            r.reset_default_client()


# ---------------------------------------------------------------------------
# P1.7 — dedupe that respects the graph
# ---------------------------------------------------------------------------
def _dedupe_mod():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / "dedupe_learned_patterns.py"
    spec = importlib.util.spec_from_file_location("dedupe_learned_patterns_p1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


D = _dedupe_mod()


def _pt(pid, content="same", created="2026-01-01"):
    return {"id": pid, "payload": {"pattern_id": pid, "content": content, "created_at": created}}


def _link(lid, src, ltype, tgt):
    return {
        "link_id": lid,
        "source_id": src,
        "target_id": tgt,
        "link_type": ltype,
        "strength": 1.0,
        "metadata": {},
        "created_by": "test",
    }


class TestLinkAwareDedupe:
    # Live shape of group 084cbde3 (probe 2026-07-17): the mirror is the OLDER point,
    # so the heuristic picked it and would have deleted the canonical.
    OLD, NEW = "5e88c5a9", "1e3e91c8"

    def _links(self):
        return [
            _link("l1", D.uid(self.OLD), "mirrors", D.uid(self.NEW)),
            _link("l2", D.uid(self.NEW), "derives_from", "episodic:memory-ai:src1"),
            _link("l3", "episodic:memory-ai:src1", "mirrors", D.uid(self.NEW)),
            _link("l4", "episodic:memory-ai:src1", "mirrors", D.uid(self.OLD)),
        ]

    def _group(self):
        return [_pt(self.NEW, created="2026-06-11"), _pt(self.OLD, created="2026-04-04")]

    def test_canonical_designation_beats_the_heuristic(self):
        """`mirrors: A -> B` means B is canonical (cross_store_sync, §26 P3). The
        heuristic (richest schema, earliest created_at) picked A — so two subsystems
        named two different survivors and this tool would have deleted the canonical.
        Live: 2 of 3 duplicate groups."""
        links = self._links()
        assert D.pick_survivor(self._group(), None)["id"] == self.OLD  # heuristic alone
        assert D.pick_survivor(self._group(), links)["id"] == self.NEW  # designation wins

    def test_mirror_chain_resolves_to_the_end(self):
        links = [
            _link("x", D.uid("A"), "mirrors", D.uid("B")),
            _link("y", D.uid("B"), "mirrors", D.uid("C")),
        ]
        assert D.canonical_from_links({"A", "B", "C"}, links) == "C"

    def test_contradictory_mirrors_fall_back_to_the_heuristic(self):
        links = [
            _link("x", D.uid("A"), "mirrors", D.uid("B")),
            _link("y", D.uid("B"), "mirrors", D.uid("A")),
        ]
        assert D.canonical_from_links({"A", "B"}, links) is None

    def test_loser_edges_move_and_nothing_dangles(self):
        plan = D.build_plan(self._group(), drop_test=False, links=self._links())
        assert plan["dup_delete_ids"] == [self.OLD]
        assert plan["dangling_links"] == []
        # l1 (intra-group mirrors) and l4 (episodic already mirrors the survivor via l3)
        # both lose their referent; nothing needs re-pointing in this shape.
        assert {lk["link_id"] for lk in plan["link_deletes"]} == {"l1", "l4"}
        assert plan["link_repoints"] == []
        assert plan["canonical_conflicts"][0]["canonical"] == self.NEW

    def test_provenance_is_repointed_not_dropped(self):
        """Live group 84645b24: the ONLY derives_from edge to the episodic source hung
        off the loser. "Also delete the links" would have dropped that provenance."""
        surv, loser = "56b46f85", "aed98df7"
        links = [
            _link("m", D.uid(loser), "mirrors", D.uid(surv)),
            _link("d", D.uid(loser), "derives_from", "episodic:memory-ai:ec260b89"),
        ]
        group = [_pt(surv, created="2026-04-04"), _pt(loser, created="2026-06-11")]
        plan = D.build_plan(group, drop_test=False, links=links)

        assert plan["dup_delete_ids"] == [loser]
        assert plan["dangling_links"] == []
        moved = plan["link_repoints"]
        assert len(moved) == 1
        assert moved[0]["link_id"] == "d"
        assert moved[0]["new_source_id"] == D.uid(surv)
        assert moved[0]["new_target_id"] == "episodic:memory-ai:ec260b89"

    def test_repoint_collapses_into_an_existing_edge(self):
        """Never plan a duplicate the registry would refuse to create."""
        surv, loser = "S", "L"
        links = [
            _link("m", D.uid(loser), "mirrors", D.uid(surv)),
            _link("a", D.uid(loser), "supports", "episodic:memory-ai:z"),
            _link("b", D.uid(surv), "supports", "episodic:memory-ai:z"),  # already there
        ]
        plan = D.build_plan(
            [_pt(surv, created="2026-01-01"), _pt(loser, created="2026-02-01")],
            drop_test=False,
            links=links,
        )
        assert plan["link_repoints"] == []
        assert {lk["link_id"] for lk in plan["link_deletes"]} == {"m", "a"}
        assert plan["dangling_links"] == []

    def test_purged_test_records_take_their_edges_with_them(self):
        """A purged record has no survivor to inherit edges — they go with it."""
        points = [_pt("t", content="Entity lookup test content")]
        links = [_link("e", "episodic:memory-ai:x", "mirrors", D.uid("t"))]
        plan = D.build_plan(points, drop_test=True, links=links)
        assert plan["test_delete_ids"] == ["t"]
        assert {lk["link_id"] for lk in plan["link_deletes"]} == {"e"}
        assert plan["dangling_links"] == []

    def test_unlinked_groups_behave_exactly_as_before(self):
        """No edges -> the heuristic is unchanged (the old contract still holds)."""
        plan = D.build_plan(
            [_pt("a", created="2026-01-01"), _pt("b", created="2026-02-01")],
            drop_test=False,
            links=[],
        )
        assert plan["dup_delete_ids"] == ["b"]
        assert plan["link_deletes"] == [] and plan["link_repoints"] == []

    def test_edge_between_two_duplicate_groups_is_remapped_once(self):
        """An edge whose BOTH ends are losers, in DIFFERENT groups.

        Planned per-group, this edge is visited twice and re-pointed twice with
        contradictory ends (`x1→y2` and `x2→y1`) — neither is the answer (`x1→y1`) and
        both dangle. The dangling guard could not see it either: it asked "was this
        link_id planned?", and a wrongly-planned edge counts as planned.
        """
        points = [
            _pt("x1", content="X", created="2026-01-01"),
            _pt("x2", content="X", created="2026-02-01"),
            _pt("y1", content="Y", created="2026-01-01"),
            _pt("y2", content="Y", created="2026-02-01"),
        ]
        links = [_link("L", D.uid("x2"), "supports", D.uid("y2"))]
        plan = D.build_plan(points, drop_test=False, links=links)

        assert sorted(plan["dup_delete_ids"]) == ["x2", "y2"]
        assert len(plan["link_repoints"]) == 1, "one edge must not be planned twice"
        moved = plan["link_repoints"][0]
        assert (moved["new_source_id"], moved["new_target_id"]) == (D.uid("x1"), D.uid("y1"))
        assert plan["dangling_links"] == []

    def test_test_purge_of_a_duplicated_record_leaves_nothing_dangling(self):
        """dedupe × drop_test: the survivor of a group can itself be a purge target.

        Computing test_ids AFTER the link plan let a point inherit re-pointed edges and
        then be deleted, while the guard reported all clear. Every member of a content
        group is the same content, so a marker match purges the whole group.
        """
        points = [
            _pt("t1", content="Entity lookup test content", created="2026-01-01"),
            _pt("t2", content="Entity lookup test content", created="2026-02-01"),
        ]
        links = [_link("d", D.uid("t2"), "derives_from", "episodic:memory-ai:ep")]
        plan = D.build_plan(points, drop_test=True, links=links)

        assert sorted(plan["test_delete_ids"]) == ["t1", "t2"]
        assert plan["dup_delete_ids"] == []  # no dedupe inside a fully purged group
        assert plan["link_repoints"] == [], "nothing survives to inherit the edge"
        assert {lk["link_id"] for lk in plan["link_deletes"]} == {"d"}
        assert plan["dangling_links"] == []

    def test_dangling_guard_inspects_final_endpoints(self):
        """The guard must fail on a BAD PLAN, not merely on an unplanned edge.

        Sabotage the remap so a re-point lands on a deleted point: the old
        bookkeeping-based guard ("link_id was planned") could not fail here by
        construction.
        """
        remap = {D.uid("loser"): D.uid("ghost")}  # ghost is itself deleted
        links = [_link("e", D.uid("loser"), "supports", "episodic:memory-ai:z")]
        deletes, repoints = D.plan_link_moves(remap, set(), links)
        assert repoints[0]["new_source_id"] == D.uid("ghost")
        assert deletes == []
        # Emulate build_plan's invariant on this plan.
        final = [(r["new_source_id"], r["new_target_id"]) for r in repoints]
        assert any(s == D.uid("ghost") for s, _ in final)


class TestDedupeApplyLayer:
    """The destructive half of P1.7 — the planner was pinned, the applier was not."""

    class _FakeRegistry:
        def __init__(self, existing=None, refuse=None):
            self.created: list[tuple] = []
            self.deleted: list[str] = []
            self._existing = existing or set()
            self._refuse = refuse

        def find_link(self, source_id, target_id, link_type):
            return object() if (source_id, target_id) in self._existing else None

        def create_link(self, **kw):
            if self._refuse:
                raise self._refuse
            self.created.append((kw["source_id"], kw["target_id"]))
            return object()

        def delete_link(self, link_id, deleted_by="system"):
            self.deleted.append(link_id)
            return True

    def _plan(self, **over):
        plan = {
            "link_repoints": [
                {
                    **_link("e", D.uid("L"), "derives_from", "episodic:memory-ai:z"),
                    "new_source_id": D.uid("S"),
                    "new_target_id": "episodic:memory-ai:z",
                }
            ],
            "link_deletes": [],
        }
        plan.update(over)
        return plan

    def test_repoint_creates_then_deletes(self):
        reg = self._FakeRegistry()
        repointed, deleted, failed = D.apply_link_plan(reg, self._plan())
        assert reg.created == [(D.uid("S"), "episodic:memory-ai:z")]
        assert reg.deleted == ["e"] and (repointed, deleted, failed) == (1, 0, [])

    def test_refused_repoint_keeps_the_origin(self):
        """`except ValueError: pass` + an unconditional delete destroyed the edge.

        create_link raises ValueError for a NON-unified entity id, an unknown link type,
        a self-link and an out-of-range strength — not only for "already exists". A
        legacy bare-uuid edge would have been refused, deleted anyway, and counted as
        "1 repointed": provenance loss reported as success.
        """
        reg = self._FakeRegistry(refuse=ValueError("Invalid entity_id: bare uuid"))
        repointed, _deleted, failed = D.apply_link_plan(reg, self._plan())
        assert repointed == 0
        assert reg.deleted == [], "a refused re-point must NOT delete the evidence"
        assert len(failed) == 1 and "Invalid entity_id" in failed[0]["error"]

    def test_existing_target_edge_collapses_without_creating(self):
        reg = self._FakeRegistry(existing={(D.uid("S"), "episodic:memory-ai:z")})
        repointed, _deleted, failed = D.apply_link_plan(reg, self._plan())
        assert reg.created == [] and reg.deleted == ["e"]
        assert (repointed, failed) == (1, [])

    def test_load_links_normalizes_bare_ids(self):
        """The bare-uuid lookup was decoration: every downstream set is keyed on uid(),
        so a loaded bare-id edge matched nothing and dangled anyway."""

        class _Lk:
            def __init__(self, s, t):
                self.link_id, self.source_id, self.target_id = "b1", s, t
                self.link_type = type("T", (), {"value": "mirrors"})()
                self.strength, self.metadata, self.created_by = 1.0, {}, "x"

        class _Reg:
            def get_all_links(self, eid):
                return {"outgoing": [_Lk("p1", "episodic:memory-ai:z")], "incoming": []}

        out = D.load_links_for(_Reg(), ["p1"])
        assert out[0]["source_id"] == D.uid("p1"), "bare end must be normalized"
        assert out[0]["target_id"] == "episodic:memory-ai:z"  # foreign id left alone


# ---------------------------------------------------------------------------
# M7 — surfacing hook must not mislabel a payload defect as an outage
# ---------------------------------------------------------------------------
def _hook():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "memory-first-hook.py"
    spec = importlib.util.spec_from_file_location("memory_first_hook_p1", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestSurfacingHookPayloadTolerance:
    def test_null_confidence_does_not_raise(self):
        """`float(payload.get("confidence", 0.5))` raised on an explicit null: .get's
        default does not cover a PRESENT null. In the lexical arm that truncated the
        results; in the dense arm it escaped to the arm-wide handler and was reported as
        `tei: down` — a healthy embedder blamed for a payload defect."""
        h = _hook()
        assert h._pattern_effective_confidence({"confidence": None}) == h._PRIOR_CONFIDENCE

    def test_degraded_fallback_uses_the_prior_not_a_half(self):
        """The gate multiplies the score by this value, so 0.5 vs the 0.70 every other
        reader seeds with is a ~40% swing in what surfaces (roadmap 260716 P1.9)."""
        h = _hook()
        assert h._PRIOR_CONFIDENCE == 0.7
        assert h._safe_float(None, h._PRIOR_CONFIDENCE) == 0.7
        assert h._safe_float("abc", h._PRIOR_CONFIDENCE) == 0.7
        assert h._safe_float(float("inf"), h._PRIOR_CONFIDENCE) == 0.7
        assert h._safe_float("0.9", 0.5) == 0.9


# ---------------------------------------------------------------------------
# M10 — normalize must not drop content_hash
# ---------------------------------------------------------------------------
class TestNormalizeKeepsContentHash:
    def _mod(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[2] / "scripts" / "normalize_light_patterns.py"
        spec = importlib.util.spec_from_file_location("normalize_light_patterns_p1", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_content_hash_is_written_and_derived(self):
        """overwrite_payload REPLACES the payload, and the built dict carried no
        content_hash — so normalizing dropped the field that read-time consumers
        (cross-store sync, the curation banner) key on."""
        from src.memory.orchestrator.content_hash import hash_content

        m = self._mod()
        out = m.normalize_payload("pid", {"category": "decision", "content": "X"}, "2026-01-01")
        assert out["content_hash"] == str(hash_content("X"))

    def test_a_stored_hash_is_not_trusted(self):
        """P0 in reverse: a payload field is untrusted input, and a stale hash copied
        into the canonical schema would point readers at the wrong fact."""
        from src.memory.orchestrator.content_hash import hash_content

        m = self._mod()
        out = m.normalize_payload(
            "pid",
            {"category": "decision", "content": "X", "content_hash": "stale-wrong"},
            "2026-01-01",
        )
        assert out["content_hash"] == str(hash_content("X"))
