"""
Integration tests for Memory System P2 — Search + Services.

Tests:
- BM25Index: tokenization, indexing, search, remove
- HybridSearchService: sparse, dense, RRF/weighted fusion
- BSLScorer: object type detection, symbol extraction, scoring, reranking
- VersioningService: create, history, rollback, diff, cleanup
- TTLService: register, expiry, cleanup, extend, policy
- ForgetGateService: decay, access-based, surprise, composite, apply
- GraphAlgorithms: shortest path, pagerank, centrality, components, communities
- LRUCache: get/put, TTL, eviction, stats
- MetricsCollector: counters, gauges, timers, export
"""

import asyncio
import time
from datetime import datetime, timedelta

import pytest

from src.memory.ai_memory.services.ttl_service import (
    TTLPolicy,
    TTLService,
)

# --- Services ---
from src.memory.ai_memory.services.versioning_service import (
    ChangeType,
    VersioningService,
)

# --- Infrastructure ---
from src.memory.infrastructure.cache import LRUCache
from src.memory.infrastructure.metrics import MetricsCollector, get_metrics_collector, reset_metrics
from src.memory.orchestrator.search.bsl_scorer import (
    BSLObjectType,
    BSLScorer,
    BSLSymbolType,
)

# --- Search ---
from src.memory.orchestrator.search.config import (
    SearchConfig,
    VectorType,
)
from src.memory.orchestrator.search.hybrid_search import (
    BM25Index,
    HybridSearchService,
)
from src.memory.vector_memory.graph.algorithms import GraphAlgorithms

# --- Graph ---
from src.memory.vector_memory.graph.relation_types import (
    Relation,
    RelationDirection,
    RelationRegistry,
    RelationType,
)
from src.memory.vector_memory.services.forgetgate_service import (
    ForgetAction,
    ForgetCandidate,
    ForgetGateConfig,
    ForgetGateService,
    ForgetStrategy,
    SurpriseCalculator,
)

# ========== BM25Index Tests ==========


class TestBM25Index:
    def test_add_and_search(self):
        idx = BM25Index()
        idx.add_document("d1", "Процедура ОбработкаПроведения документ")
        idx.add_document("d2", "Функция ПолучитьДанные запрос")
        idx.add_document("d3", "Процедура ОбработкаЗаполнения форма")

        results = idx.search("ОбработкаПроведения документ")
        assert len(results) > 0
        assert results[0][0] == "d1"

    def test_empty_query_returns_empty(self):
        idx = BM25Index()
        idx.add_document("d1", "hello world")
        assert idx.search("") == []

    def test_bsl_stopwords_excluded(self):
        idx = BM25Index()
        idx.add_document("d1", "Если Тогда КонецЕсли unique_token")
        # Stopwords are stored as-is but tokenizer lowercases tokens
        # Search for stopword-only query should score lower than unique token
        stopword_results = idx.search("Если")
        unique_results = idx.search("unique_token")
        assert len(unique_results) > 0
        if stopword_results:
            assert unique_results[0][1] >= stopword_results[0][1]

    def test_remove_document(self):
        idx = BM25Index()
        idx.add_document("d1", "unique content here")
        assert idx.total_docs == 1
        assert idx.remove_document("d1")
        assert idx.total_docs == 0
        assert idx.search("unique") == []

    def test_batch_add(self):
        idx = BM25Index()
        idx.add_documents_batch(
            [
                ("d1", "first document"),
                ("d2", "second document"),
                ("d3", "third document"),
            ]
        )
        assert idx.total_docs == 3

    def test_stats(self):
        idx = BM25Index()
        idx.add_document("d1", "test content")
        stats = idx.stats
        assert stats["total_documents"] == 1
        assert stats["unique_terms"] > 0


# ========== HybridSearchService Tests ==========


class TestHybridSearchService:
    @pytest.fixture
    def svc(self):
        config = SearchConfig(default_vector_type=VectorType.SPARSE)
        return HybridSearchService(config=config)

    def test_index_and_search_sparse(self, svc):
        svc.index_document("d1", "Процедура ОбработкаПроведения")
        svc.index_document("d2", "Функция ПолучитьДанные")

        result = asyncio.get_event_loop().run_until_complete(svc.search("ОбработкаПроведения"))
        assert result.sparse_count > 0
        assert len(result.results) > 0
        assert result.results[0].id == "d1"

    def test_search_returns_timing(self, svc):
        svc.index_document("d1", "test content")
        result = asyncio.get_event_loop().run_until_complete(svc.search("test"))
        assert result.search_time_ms >= 0

    def test_stats(self, svc):
        svc.index_document("d1", "test")
        stats = svc.get_stats()
        assert "bm25" in stats
        assert stats["dense_available"] is False

    @pytest.mark.asyncio
    async def test_hybrid_with_dense_fn(self):
        """Test hybrid mode with injected dense search."""

        async def mock_dense(query: str, top_k: int):
            return [("d1", 0.9), ("d2", 0.5)]

        config = SearchConfig(default_vector_type=VectorType.HYBRID)
        svc = HybridSearchService(config=config, dense_search_fn=mock_dense)
        svc.index_document("d1", "matching content query")
        svc.index_document("d2", "other content")

        result = await svc.search("matching query")
        assert result.dense_count > 0
        assert result.sparse_count >= 0


# ========== BSLScorer Tests ==========


class TestBSLScorer:
    @pytest.fixture
    def scorer(self):
        return BSLScorer()

    def test_detect_common_module(self, scorer):
        assert (
            scorer.detect_object_type("CommonModules/MyModule/Ext/Module.bsl")
            == BSLObjectType.COMMON_MODULE
        )

    def test_detect_document(self, scorer):
        assert (
            scorer.detect_object_type("Documents/Invoice/Ext/ObjectModule.bsl")
            == BSLObjectType.DOCUMENT
        )

    def test_detect_catalog_russian(self, scorer):
        assert (
            scorer.detect_object_type("Справочники/Номенклатура/Ext/Module.bsl")
            == BSLObjectType.CATALOG
        )

    def test_detect_unknown(self, scorer):
        assert scorer.detect_object_type("some/random/path.bsl") == BSLObjectType.UNKNOWN

    def test_extract_symbols(self, scorer):
        code = """
Процедура ОбработкаПроведения(Отказ, РежимПроведения) Экспорт
    // code
КонецПроцедуры

Функция ПолучитьДанные(Параметр1, Параметр2)
    // code
КонецФункции
"""
        symbols = scorer.extract_symbols(code)
        assert len(symbols) == 2

        by_name = {s.name: s for s in symbols}
        assert "ОбработкаПроведения" in by_name
        assert by_name["ОбработкаПроведения"].symbol_type == BSLSymbolType.EVENT_HANDLER
        assert by_name["ОбработкаПроведения"].is_export is True
        assert "ПолучитьДанные" in by_name
        assert by_name["ПолучитьДанные"].symbol_type == BSLSymbolType.FUNCTION

    def test_analyze_content_with_queries(self, scorer):
        code = 'Запрос = Новый Запрос; Запрос.Текст = "ВЫБРАТЬ";'
        result = scorer.analyze_content(code)
        assert result.has_queries is True

    def test_score_match_boosts(self, scorer):
        code = """
Функция ПолучитьДанные() Экспорт
КонецФункции
"""
        result = scorer.score_match("ПолучитьДанные", code, "CommonModules/Test/Module.bsl")
        assert result.final_score > result.base_score  # should be boosted

    def test_rerank(self, scorer):
        results = [
            ("d1", "Процедура Обычная()\nКонецПроцедуры", 0.5),
            ("d2", "Функция ПолучитьДанные() Экспорт\nКонецФункции", 0.5),
        ]
        reranked = scorer.rerank("ПолучитьДанные", results)
        assert reranked[0][0] == "d2"  # exact match should rank higher


# ========== VersioningService Tests ==========


class TestVersioningService:
    @pytest.fixture
    def svc(self, tmp_path):
        return VersioningService(storage_path=tmp_path / "versions.jsonl")

    @pytest.mark.asyncio
    async def test_create_version(self, svc):
        v = await svc.create_version("e1", {"key": "val"}, ChangeType.CREATE)
        assert v.version == 1
        assert v.entity_id == "e1"

    @pytest.mark.asyncio
    async def test_version_history(self, svc):
        await svc.create_version("e1", {"v": 1}, ChangeType.CREATE)
        await svc.create_version("e1", {"v": 2}, ChangeType.UPDATE)
        await svc.create_version("e1", {"v": 3}, ChangeType.UPDATE)

        history = await svc.get_version_history("e1")
        assert len(history) == 3
        assert history[0].version == 3  # newest first

    @pytest.mark.asyncio
    async def test_rollback(self, svc):
        await svc.create_version("e1", {"v": 1}, ChangeType.CREATE)
        await svc.create_version("e1", {"v": 2}, ChangeType.UPDATE)

        rolled = await svc.rollback_to_version("e1", 1)
        assert rolled is not None
        assert rolled.content == {"v": 1}
        assert rolled.change_type == ChangeType.ROLLBACK

    @pytest.mark.asyncio
    async def test_compare_versions(self, svc):
        await svc.create_version("e1", {"a": 1, "b": 2}, ChangeType.CREATE)
        await svc.create_version("e1", {"a": 1, "b": 3, "c": 4}, ChangeType.UPDATE)

        diff = await svc.compare_versions("e1", 1, 2)
        assert "changes" in diff
        changes_by_key = {c["key"]: c for c in diff["changes"]}
        assert changes_by_key["b"]["type"] == "modified"
        assert changes_by_key["c"]["type"] == "added"

    @pytest.mark.asyncio
    async def test_stats(self, svc):
        await svc.create_version("e1", {}, ChangeType.CREATE)
        stats = await svc.get_stats()
        assert stats["total_entities"] == 1
        assert stats["total_versions"] == 1

    @pytest.mark.asyncio
    async def test_persistence(self, tmp_path):
        path = tmp_path / "versions.jsonl"
        svc1 = VersioningService(storage_path=path)
        await svc1.create_version("e1", {"data": "test"}, ChangeType.CREATE)

        # New instance should load from disk
        svc2 = VersioningService(storage_path=path)
        loaded = await svc2.load_all_from_storage()
        assert loaded == 1


# ========== TTLService Tests ==========


class TestTTLService:
    @pytest.fixture
    def svc(self, tmp_path):
        return TTLService(
            storage_path=tmp_path / "ttl.jsonl",
            enable_auto_cleanup=False,
        )

    @pytest.mark.asyncio
    async def test_register_and_check(self, svc):
        entry = await svc.register("e1", TTLPolicy.LONG)
        assert entry.entity_id == "e1"
        assert not await svc.is_expired("e1")

    @pytest.mark.asyncio
    async def test_never_expires(self, svc):
        await svc.register("e1", TTLPolicy.NEVER)
        assert not await svc.is_expired("e1")

    @pytest.mark.asyncio
    async def test_unknown_is_expired(self, svc):
        assert await svc.is_expired("nonexistent")

    @pytest.mark.asyncio
    async def test_expired_entry(self, svc):
        entry = await svc.register("e1", TTLPolicy.CUSTOM, ttl_seconds=0)
        # Immediately expired (ttl=0 becomes default, so set manually)
        entry.expires_at = datetime.now() - timedelta(seconds=1)
        assert await svc.is_expired("e1")

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, svc):
        entry = await svc.register("e1", TTLPolicy.SHORT)
        entry.expires_at = datetime.now() - timedelta(hours=2)

        removed = await svc.cleanup_expired()
        assert "e1" in removed

    @pytest.mark.asyncio
    async def test_extend_ttl(self, svc):
        entry = await svc.register("e1", TTLPolicy.SHORT)
        old_expires = entry.expires_at

        updated = await svc.extend_ttl("e1", 7200)
        assert updated is not None
        assert updated.expires_at > old_expires
        assert updated.extended_count == 1

    @pytest.mark.asyncio
    async def test_record_access(self, svc):
        await svc.register("e1", TTLPolicy.LONG)
        updated = await svc.record_access("e1")
        assert updated is not None
        assert updated.access_count == 1

    @pytest.mark.asyncio
    async def test_stats(self, svc):
        await svc.register("e1", TTLPolicy.LONG)
        await svc.register("e2", TTLPolicy.NEVER)
        stats = await svc.get_stats()
        assert stats["total_entries"] == 2
        assert stats["never_expire"] == 1


# ========== ForgetGateService Tests ==========


class TestForgetGateService:
    def _make_candidate(
        self, entity_id="e1", confidence=0.8, days_old=10, access_count=5, tags=None
    ):
        now = datetime.now()
        return ForgetCandidate(
            entity_id=entity_id,
            current_confidence=confidence,
            last_accessed=now - timedelta(days=2),
            access_count=access_count,
            created_at=now - timedelta(days=days_old),
            tags=tags or [],
        )

    def test_confidence_decay(self):
        gate = ForgetGateService(ForgetGateConfig(strategy=ForgetStrategy.CONFIDENCE_DECAY))
        candidates = [self._make_candidate(days_old=100, confidence=0.5)]
        decisions = gate.evaluate(candidates)
        assert len(decisions) == 1
        assert decisions[0].new_confidence < 0.5  # should decay

    def test_high_confidence_kept(self):
        gate = ForgetGateService(ForgetGateConfig(strategy=ForgetStrategy.CONFIDENCE_DECAY))
        candidates = [self._make_candidate(days_old=1, confidence=0.95)]
        decisions = gate.evaluate(candidates)
        assert decisions[0].action == ForgetAction.KEEP

    def test_access_based_penalty(self):
        gate = ForgetGateService(
            ForgetGateConfig(
                strategy=ForgetStrategy.ACCESS_BASED,
                access_decay_days=7,
            )
        )
        c = self._make_candidate(days_old=60, access_count=0)
        c.last_accessed = datetime.now() - timedelta(days=60)
        decisions = gate.evaluate([c])
        assert decisions[0].new_confidence < c.current_confidence

    def test_surprise_keeps_novel(self):
        gate = ForgetGateService(ForgetGateConfig(strategy=ForgetStrategy.SURPRISE_BASED))
        candidates = [
            self._make_candidate("common", tags=["tag1"]),
            self._make_candidate("common2", tags=["tag1"]),
            self._make_candidate("rare", tags=["unique_rare_tag"]),
        ]
        decisions = gate.evaluate(candidates)
        # rare entry should have higher confidence preserved
        rare_decision = [d for d in decisions if d.entity_id == "rare"][0]
        common_decision = [d for d in decisions if d.entity_id == "common"][0]
        assert rare_decision.new_confidence >= common_decision.new_confidence

    def test_composite_strategy(self):
        gate = ForgetGateService(ForgetGateConfig(strategy=ForgetStrategy.COMPOSITE))
        candidates = [self._make_candidate()]
        decisions = gate.evaluate(candidates)
        assert len(decisions) == 1
        assert "composite" in decisions[0].reason

    def test_apply_dry_run(self):
        gate = ForgetGateService(ForgetGateConfig(dry_run=True))
        candidates = [self._make_candidate(confidence=0.01, days_old=365)]
        decisions = gate.evaluate(candidates)
        stats = gate.apply(decisions)
        assert stats.total_evaluated == 1
        # dry_run = no actual side effects but stats are counted

    def test_apply_with_callback(self):
        applied = []

        def apply_fn(decision):
            applied.append(decision.entity_id)
            return True

        gate = ForgetGateService(
            ForgetGateConfig(
                strategy=ForgetStrategy.CONFIDENCE_DECAY,
                min_confidence=0.9,  # high threshold
            )
        )
        candidates = [self._make_candidate(confidence=0.5, days_old=30)]
        decisions = gate.evaluate(candidates)
        stats = gate.apply(decisions, apply_fn=apply_fn)
        assert stats.total_evaluated == 1

    def test_stats(self):
        gate = ForgetGateService()
        stats = gate.get_stats()
        assert "strategy" in stats
        assert stats["last_run"] is None


# ========== SurpriseCalculator Tests ==========


class TestSurpriseCalculator:
    def test_rare_tags_high_surprise(self):
        calc = SurpriseCalculator()
        candidates = [
            ForgetCandidate("c1", 0.5, None, 0, datetime.now(), tags=["common"]),
            ForgetCandidate("c2", 0.5, None, 0, datetime.now(), tags=["common"]),
            ForgetCandidate("c3", 0.5, None, 0, datetime.now(), tags=["rare_unique"]),
        ]
        calc.update_frequencies(candidates)

        common_score = calc.surprise_score(candidates[0])
        rare_score = calc.surprise_score(candidates[2])
        assert rare_score > common_score

    def test_no_tags_neutral(self):
        calc = SurpriseCalculator()
        c = ForgetCandidate("c1", 0.5, None, 0, datetime.now(), tags=[])
        calc.update_frequencies([c])
        assert calc.surprise_score(c) == 0.5


# ========== GraphAlgorithms Tests ==========


class TestGraphAlgorithms:
    def _make_graph(self):
        """Create a simple test graph: A -> B -> C, A -> C."""
        registry = RelationRegistry()
        registry.add(
            Relation("A", "B", RelationType.CALLS, weight=1.0, direction=RelationDirection.OUTGOING)
        )
        registry.add(
            Relation("B", "C", RelationType.CALLS, weight=2.0, direction=RelationDirection.OUTGOING)
        )
        registry.add(
            Relation(
                "A", "C", RelationType.REFERENCES, weight=5.0, direction=RelationDirection.OUTGOING
            )
        )
        return GraphAlgorithms(registry)

    def test_shortest_path(self):
        ga = self._make_graph()
        path = ga.shortest_path("A", "C")
        assert path is not None
        assert path.source == "A"
        assert path.target == "C"
        assert len(path.path) >= 2

    def test_shortest_path_self(self):
        ga = self._make_graph()
        path = ga.shortest_path("A", "A")
        assert path is not None
        assert path.hop_count == 0

    def test_shortest_path_no_connection(self):
        registry = RelationRegistry()
        registry.add(
            Relation("A", "B", RelationType.CALLS, weight=1.0, direction=RelationDirection.OUTGOING)
        )
        # D is isolated
        ga = GraphAlgorithms(registry)
        path = ga.shortest_path("A", "D")
        assert path is None

    def test_pagerank(self):
        ga = self._make_graph()
        ranks = ga.pagerank()
        assert len(ranks) > 0
        # All ranks should sum to ~1.0
        total = sum(ranks.values())
        assert abs(total - 1.0) < 0.01

    def test_degree_centrality(self):
        ga = self._make_graph()
        centrality = ga.degree_centrality()
        assert "A" in centrality
        assert centrality["A"] > 0

    def test_connected_components(self):
        ga = self._make_graph()
        components = ga.connected_components()
        assert len(components) >= 1

    def test_detect_communities(self):
        ga = self._make_graph()
        communities = ga.detect_communities()
        # With a small graph, may or may not detect communities > 1 member
        assert isinstance(communities, list)

    def test_get_neighbors(self):
        ga = self._make_graph()
        neighbors = ga.get_neighbors("A")
        assert len(neighbors) > 0

    def test_stats(self):
        ga = self._make_graph()
        stats = ga.get_stats()
        assert stats["total_nodes"] > 0
        assert stats["total_edges"] > 0


# ========== RelationRegistry Tests ==========


class TestRelationRegistry:
    def test_add_and_get_by_source(self):
        reg = RelationRegistry()
        reg.add(Relation("A", "B", RelationType.CALLS, weight=1.0))
        rels = reg.get_by_source("A")
        assert len(rels) >= 1

    def test_get_between(self):
        reg = RelationRegistry()
        reg.add(Relation("A", "B", RelationType.CALLS))
        reg.add(Relation("A", "C", RelationType.REFERENCES))
        between = reg.get_between("A", "B")
        assert len(between) == 1

    def test_remove(self):
        reg = RelationRegistry()
        reg.add(Relation("A", "B", RelationType.REFERENCES))
        assert reg.remove("A", "B", RelationType.REFERENCES)
        assert len(reg.get_by_source("A")) == 0

    def test_stats(self):
        reg = RelationRegistry()
        reg.add(Relation("A", "B", RelationType.CALLS))
        stats = reg.stats
        assert stats["total_relations"] >= 1


# ========== LRUCache Tests ==========


class TestLRUCache:
    def test_put_and_get(self):
        cache = LRUCache(max_size=10)
        cache.put("k1", "v1")
        assert cache.get("k1") == "v1"

    def test_miss_returns_none(self):
        cache = LRUCache()
        assert cache.get("nonexistent") is None

    def test_eviction(self):
        cache = LRUCache(max_size=2)
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        cache.put("k3", "v3")  # evicts k1
        assert cache.get("k1") is None
        assert cache.get("k2") == "v2"
        assert cache.get("k3") == "v3"

    def test_ttl_expiry(self):
        cache = LRUCache(default_ttl=0.1)
        cache.put("k1", "v1")
        time.sleep(0.15)
        assert cache.get("k1") is None

    def test_cleanup_expired(self):
        cache = LRUCache(default_ttl=0.05)
        cache.put("k1", "v1")
        cache.put("k2", "v2", ttl=3600)  # long TTL
        time.sleep(0.1)
        removed = cache.cleanup_expired()
        assert removed == 1
        assert "k2" in cache

    def test_delete(self):
        cache = LRUCache()
        cache.put("k1", "v1")
        assert cache.delete("k1")
        assert cache.get("k1") is None

    def test_stats(self):
        cache = LRUCache()
        cache.put("k1", "v1")
        cache.get("k1")  # hit
        cache.get("k2")  # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["size"] == 1

    def test_contains(self):
        cache = LRUCache()
        cache.put("k1", "v1")
        assert "k1" in cache
        assert "k2" not in cache

    def test_clear(self):
        cache = LRUCache()
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        cleared = cache.clear()
        assert cleared == 2
        assert len(cache) == 0


# ========== MetricsCollector Tests ==========


class TestMetricsCollector:
    def test_counter(self):
        m = MetricsCollector()
        assert m.counter("req") == 1
        assert m.counter("req") == 2
        assert m.counter("req", delta=5) == 7

    def test_gauge(self):
        m = MetricsCollector()
        m.gauge("cache_size", 42)
        metrics = m.get_all()
        assert metrics["gauges"]["cache_size"] == 42

    def test_timer_context_manager(self):
        m = MetricsCollector()
        with m.timer("op"):
            time.sleep(0.01)
        metrics = m.get_all()
        assert "op" in metrics["durations"]
        assert metrics["durations"]["op"]["count"] == 1
        assert metrics["durations"]["op"]["total"] > 0

    def test_export_json(self):
        m = MetricsCollector()
        m.counter("test")
        json_str = m.export_json()
        assert '"test"' in json_str

    def test_reset(self):
        m = MetricsCollector()
        m.counter("req")
        m.reset()
        metrics = m.get_all()
        assert len(metrics["counters"]) == 0

    def test_global_singleton(self):
        reset_metrics()
        c = get_metrics_collector()
        c.counter("global_test")
        c2 = get_metrics_collector()
        assert c2.get_all()["counters"]["global_test"] == 1
        reset_metrics()
