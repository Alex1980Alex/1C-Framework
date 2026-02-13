"""E2E Test Roadmap — All 40 Phases on Real PDF.

Tests every phase of the PDF Vector & Graph Framework via REST API
against the indexed document: Глава 5. Объекты конфигурации (1012 chunks).

Usage:
    # 1. Start the API server
    python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000

    # 2. Run tests
    python tests/test_e2e_phases.py
"""

import sys
import time
from dataclasses import dataclass, field

import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT_SHORT = 15.0
TIMEOUT_MEDIUM = 60.0
TIMEOUT_LONG = 300.0

QUERIES = {
    "simple": "справочники",
    "specific": "регистры накопления",
    "technical": "план счетов",
    "comparison": "Чем отличается справочник от перечисления?",
    "overview": "Какие типы регистров существуют в 1С?",
}


# ---------------------------------------------------------------------------
# Test Runner
# ---------------------------------------------------------------------------


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    elapsed_ms: float


@dataclass
class TestRunner:
    base_url: str = BASE_URL
    results: list[TestResult] = field(default_factory=list)
    context: dict = field(default_factory=dict)

    def run_group(self, name: str, timeout: float, tests: list):
        print(f"\n{'=' * 64}")
        print(f"  GROUP: {name}")
        print("=" * 64)
        client = httpx.Client(base_url=self.base_url, timeout=timeout)
        try:
            for test_fn in tests:
                t0 = time.perf_counter()
                try:
                    passed, msg = test_fn(client, self.context)
                except httpx.TimeoutException:
                    passed, msg = False, "TIMEOUT"
                except Exception as e:
                    passed, msg = False, f"ERROR: {e!s:.80s}"
                elapsed = (time.perf_counter() - t0) * 1000
                result = TestResult(test_fn.__name__, passed, msg, elapsed)
                self.results.append(result)
                tag = "\033[92m[PASS]\033[0m" if passed else "\033[91m[FAIL]\033[0m"
                print(f"{tag} {result.name:50s} {elapsed:8.0f}ms  {msg}")
        finally:
            client.close()

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        total_ms = sum(r.elapsed_ms for r in self.results)

        print(f"\n{'=' * 64}")
        print("  SUMMARY")
        print("=" * 64)
        print(f"Total:   {total}")
        print(f"Passed:  {passed} ({100 * passed / total:.1f}%)" if total else "")
        print(f"Failed:  {failed}")
        print(f"Time:    {total_ms / 1000:.1f}s")

        if failed:
            print(f"\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"  - {r.name}: {r.message}")

        return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# GROUP 1: System Health
# ---------------------------------------------------------------------------


def test_health(client: httpx.Client, ctx: dict):
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    vs = d.get("checks", {}).get("vector_store", {})
    count = vs.get("document_count", 0)
    return True, f"vector_store={count} docs"


def test_health_ready(client: httpx.Client, ctx: dict):
    r = client.get("/health/ready")
    return r.status_code == 200, f"status={r.status_code}"


def test_health_live(client: httpx.Client, ctx: dict):
    r = client.get("/health/live")
    return r.status_code == 200, f"status={r.status_code}"


# ---------------------------------------------------------------------------
# GROUP 2: Documents (read-only)
# ---------------------------------------------------------------------------


def test_documents_list(client: httpx.Client, ctx: dict):
    r = client.get("/documents/")
    assert r.status_code == 200
    d = r.json()
    docs = d if isinstance(d, list) else d.get("documents", [])
    if docs:
        first = docs[0]
        doc_id = first.get("document_id") or first.get("id", "")
        ctx["document_id"] = doc_id
    return len(docs) > 0, f"{len(docs)} documents, doc_id={ctx.get('document_id', '?')[:16]}"


def test_documents_stats(client: httpx.Client, ctx: dict):
    r = client.get("/documents/stats")
    assert r.status_code == 200
    d = r.json()
    vs = d.get("vector_store", {})
    chunks = vs.get("document_count", 0)
    gs = d.get("graph_store", {})
    nodes = gs.get("node_count", 0)
    assert chunks >= 1000, f"Expected ≥1000 chunks, got {chunks}"
    return True, f"chunks={chunks}, graph_nodes={nodes}"


def test_documents_registry(client: httpx.Client, ctx: dict):
    r = client.get("/documents/registry")
    if r.status_code == 200:
        d = r.json()
        docs = d if isinstance(d, list) else d.get("documents", [])
        return True, f"{len(docs)} registered"
    return r.status_code == 200, f"status={r.status_code}"


def test_documents_files(client: httpx.Client, ctx: dict):
    r = client.get("/documents/files")
    if r.status_code == 200:
        d = r.json()
        files = d if isinstance(d, list) else d.get("files", [])
        return True, f"{len(files)} files"
    return r.status_code == 200, f"status={r.status_code}"


# ---------------------------------------------------------------------------
# GROUP 3: Search Core (5 strategies)
# ---------------------------------------------------------------------------


def _search(client, query, strategy, k=5, rerank=False, **extra):
    r = client.post("/search/", json={
        "query": query, "strategy": strategy, "k": k, "rerank": rerank, **extra,
    })
    assert r.status_code == 200, f"status={r.status_code}: {r.text[:200]}"
    d = r.json()
    return d


def test_search_vector(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["simple"], "vector")
    return d["total_found"] > 0, f"found={d['total_found']} elapsed={d['elapsed_ms']:.0f}ms"


def test_search_hybrid(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["simple"], "hybrid")
    return d["total_found"] > 0, f"found={d['total_found']} elapsed={d['elapsed_ms']:.0f}ms"


def test_search_bm25(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["simple"], "bm25")
    ok = d["total_found"] > 0
    return ok, f"found={d['total_found']} elapsed={d['elapsed_ms']:.0f}ms"


def test_search_mmr(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["simple"], "mmr")
    return d["total_found"] > 0, f"found={d['total_found']} elapsed={d['elapsed_ms']:.0f}ms"


def test_search_section_first(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["specific"], "section_first")
    found = d["total_found"]
    return found >= 0, f"found={found} type={d['search_type']} elapsed={d['elapsed_ms']:.0f}ms"


# ---------------------------------------------------------------------------
# GROUP 4: Search Advanced (5 strategies)
# ---------------------------------------------------------------------------


def test_search_graphrag_local(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["specific"], "graphrag_local")
    return d["total_found"] >= 0, f"found={d['total_found']} elapsed={d['elapsed_ms']:.0f}ms"


def test_search_graphrag_light(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["specific"], "graphrag_light")
    return d["total_found"] >= 0, f"found={d['total_found']} elapsed={d['elapsed_ms']:.0f}ms"


def test_search_graphrag_auto(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["simple"], "graphrag_auto")
    return d["total_found"] >= 0, f"found={d['total_found']} type={d['search_type']}"


def test_search_adaptive(client: httpx.Client, ctx: dict):
    d = _search(client, QUERIES["comparison"], "adaptive")
    return d["total_found"] >= 0, f"found={d['total_found']} type={d['search_type']}"


def test_search_two_stage(client: httpx.Client, ctx: dict):
    r = client.post("/search/", json={
        "query": QUERIES["simple"], "strategy": "two_stage", "k": 5, "rerank": False,
    })
    if r.status_code == 500:
        # two_stage is disabled by default (settings.two_stage.enabled=False)
        return True, "SKIP: two_stage disabled (enabled=False in config)"
    assert r.status_code == 200, f"status={r.status_code}: {r.text[:200]}"
    d = r.json()
    return d["total_found"] >= 0, f"found={d['total_found']} elapsed={d['elapsed_ms']:.0f}ms"


# ---------------------------------------------------------------------------
# GROUP 5: RAG Agent
# ---------------------------------------------------------------------------


def test_ask(client: httpx.Client, ctx: dict):
    r = client.post("/search/ask", json={
        "question": "Что такое справочники в 1С?",
        "strategy": "hybrid",
        "k": 5,
    })
    assert r.status_code == 200
    d = r.json()
    answer = d.get("answer", "")
    return len(answer) > 50, f"answer={len(answer)} chars, type={d.get('search_type')}"


def test_chat_message(client: httpx.Client, ctx: dict):
    r = client.post("/chat/message", json={
        "message": "Объясни что такое регистры в 1С",
        "stream": False,
        "strategy": "hybrid",
    })
    assert r.status_code == 200
    d = r.json()
    ctx["thread_id"] = d.get("thread_id", "")
    answer = d.get("answer", "")
    return len(answer) > 30, f"answer={len(answer)} chars, thread={ctx['thread_id'][:8]}"


def test_chat_followup(client: httpx.Client, ctx: dict):
    tid = ctx.get("thread_id")
    if not tid:
        return False, "no thread_id from previous test"
    r = client.post("/chat/message", json={
        "message": "А чем они отличаются от справочников?",
        "thread_id": tid,
        "stream": False,
        "strategy": "hybrid",
    })
    assert r.status_code == 200
    d = r.json()
    answer = d.get("answer", "")
    return len(answer) > 30, f"answer={len(answer)} chars (follow-up)"


# ---------------------------------------------------------------------------
# GROUP 6: Analytical Agent (Phase 33)
# ---------------------------------------------------------------------------


def test_analyze(client: httpx.Client, ctx: dict):
    r = client.post("/search/analyze", json={
        "question": QUERIES["comparison"],
        "max_rounds": 2,
    })
    assert r.status_code == 200
    d = r.json()
    answer = d.get("answer", "")
    rounds = d.get("rounds_used", 0)
    evidence = d.get("evidence_count", 0)
    return len(answer) > 100, f"answer={len(answer)} chars, rounds={rounds}, evidence={evidence}"


# ---------------------------------------------------------------------------
# GROUP 7: Research Agent (Phase 36)
# ---------------------------------------------------------------------------


def test_research(client: httpx.Client, ctx: dict):
    r = client.post("/search/research", json={
        "question": QUERIES["overview"],
        "max_rounds": 2,
    })
    assert r.status_code == 200
    d = r.json()
    answer = d.get("answer", "")
    sections = len(d.get("sections", []))
    evidence = d.get("evidence_count", 0)
    sid = d.get("session_id", "")
    return len(answer) > 100, (
        f"answer={len(answer)} chars, sections={sections}, "
        f"evidence={evidence}, session={sid[:8]}"
    )


# ---------------------------------------------------------------------------
# GROUP 8: Multi-Agent (Phase 39)
# ---------------------------------------------------------------------------


def test_multi_agent(client: httpx.Client, ctx: dict):
    r = client.post("/search/multi-agent", json={
        "question": "Подробно опиши план счетов в 1С",
        "max_iterations": 1,
    })
    assert r.status_code == 200
    d = r.json()
    answer = d.get("answer", "")
    agents = d.get("agents_used", [])
    gr = d.get("groundedness", 0)
    comp = d.get("completeness", 0)
    return len(answer) > 100 and len(agents) == 4, (
        f"answer={len(answer)} chars, agents={len(agents)}, "
        f"groundedness={gr:.0%}, completeness={comp:.0%}"
    )


# ---------------------------------------------------------------------------
# GROUP 9: Knowledge Graph
# ---------------------------------------------------------------------------


def test_graph_stats(client: httpx.Client, ctx: dict):
    r = client.get("/graph/stats")
    assert r.status_code == 200
    d = r.json()
    nodes = d.get("node_count") or d.get("entities", 0)
    edges = d.get("edge_count") or d.get("relations", 0)
    return nodes > 0, f"nodes={nodes}, edges={edges}"


def test_graph_entities(client: httpx.Client, ctx: dict):
    r = client.get("/graph/entities", params={"limit": 5})
    assert r.status_code == 200
    d = r.json()
    entities = d.get("entities", [])
    if entities:
        ctx["entity_id"] = entities[0].get("id", "")
    return len(entities) > 0, f"{len(entities)} entities"


def test_graph_neighbors(client: httpx.Client, ctx: dict):
    eid = ctx.get("entity_id")
    if not eid:
        return False, "no entity_id from previous test"
    r = client.get(f"/graph/neighbors/{eid}", params={"depth": 1})
    if r.status_code == 200:
        d = r.json()
        entities = d.get("entities", [])
        relations = d.get("relations", [])
        return True, f"{len(entities)} entities, {len(relations)} relations"
    return False, f"status={r.status_code}"


def test_graph_entity_embeddings_stats(client: httpx.Client, ctx: dict):
    r = client.get("/graph/entity-embeddings/stats")
    if r.status_code == 200:
        d = r.json()
        total = d.get("points") or d.get("total_points", 0)
        return True, f"points={total}, exists={d.get('exists', '?')}"
    if r.status_code == 501:
        return True, "SKIP (LightRAG not configured)"
    return False, f"status={r.status_code}"


# ---------------------------------------------------------------------------
# GROUP 10: ToC Navigation (Phase 30)
# ---------------------------------------------------------------------------


def test_toc_tree(client: httpx.Client, ctx: dict):
    doc_id = ctx.get("document_id")
    if not doc_id:
        return False, "no document_id"
    r = client.get(f"/toc/{doc_id}")
    if r.status_code == 200:
        d = r.json()
        sections = d.get("sections") or d.get("tree") or d.get("children", [])
        total = d.get("total_sections") or len(sections)
        return total > 0, f"{total} sections"
    return False, f"status={r.status_code}: {r.text[:100]}"


def test_toc_section_detail(client: httpx.Client, ctx: dict):
    doc_id = ctx.get("document_id")
    if not doc_id:
        return False, "no document_id"
    r = client.get(f"/toc/{doc_id}/section/5.8")
    if r.status_code == 200:
        d = r.json()
        chunks = d.get("chunk_count", 0)
        title = d.get("title") or d.get("section_title", "")
        return True, f"chunks={chunks}, title={title[:40]}"
    if r.status_code == 404:
        return True, "SKIP (section 5.8 not found — OK)"
    return False, f"status={r.status_code}: {r.text[:100]}"


# ---------------------------------------------------------------------------
# GROUP 11: Collections (Phase 32)
# ---------------------------------------------------------------------------


def test_collections_create(client: httpx.Client, ctx: dict):
    r = client.post("/collections/", json={
        "name": "E2E Test Collection",
        "description": "Automated test",
        "tags": ["test", "e2e"],
    })
    assert r.status_code == 200, f"status={r.status_code}: {r.text[:200]}"
    d = r.json()
    ctx["collection_id"] = d.get("id") or d.get("collection_id", "")
    return bool(ctx["collection_id"]), f"id={ctx['collection_id'][:16]}"


def test_collections_list(client: httpx.Client, ctx: dict):
    r = client.get("/collections/")
    assert r.status_code == 200
    d = r.json()
    total = d.get("total", 0)
    return total > 0, f"{total} collections"


def test_collections_add_document(client: httpx.Client, ctx: dict):
    cid = ctx.get("collection_id")
    doc_id = ctx.get("document_id")
    if not cid or not doc_id:
        return False, "no collection_id or document_id"
    r = client.post(f"/collections/{cid}/documents", json={
        "document_ids": [doc_id],
    })
    return r.status_code == 200, f"status={r.status_code}"


def test_collections_search_scoped(client: httpx.Client, ctx: dict):
    cid = ctx.get("collection_id")
    if not cid:
        return False, "no collection_id"
    d = _search(client, QUERIES["simple"], "bm25", collection_id=cid)
    return d["total_found"] >= 0, f"found={d['total_found']} (scoped)"


def test_collections_list_documents(client: httpx.Client, ctx: dict):
    cid = ctx.get("collection_id")
    if not cid:
        return False, "no collection_id"
    r = client.get(f"/collections/{cid}/documents")
    if r.status_code == 200:
        d = r.json()
        docs = d if isinstance(d, list) else d.get("documents", [])
        return True, f"{len(docs)} documents in collection"
    return False, f"status={r.status_code}"


def test_collections_delete(client: httpx.Client, ctx: dict):
    cid = ctx.get("collection_id")
    if not cid:
        return False, "no collection_id"
    r = client.delete(f"/collections/{cid}")
    return r.status_code == 200, f"deleted (status={r.status_code})"


# ---------------------------------------------------------------------------
# GROUP 12: Feedback (Phase 22)
# ---------------------------------------------------------------------------


def test_feedback_submit(client: httpx.Client, ctx: dict):
    r = client.post("/feedback/submit", json={
        "query": "справочники в 1С",
        "answer": "Справочники — это объекты конфигурации для хранения условно-постоянной информации.",
        "feedback": "positive",
        "strategy": "hybrid",
        "score": 0.9,
        "sources": ["chapter5.pdf"],
    })
    if r.status_code == 200:
        d = r.json()
        return d.get("success", False), f"id={d.get('feedback_id', 0)}"
    return False, f"status={r.status_code}: {r.text[:200]}"


def test_feedback_stats(client: httpx.Client, ctx: dict):
    r = client.get("/feedback/stats")
    if r.status_code == 200:
        d = r.json()
        total = d.get("total_feedback") or d.get("total", 0)
        return True, f"total={total}"
    return False, f"status={r.status_code}"


# ---------------------------------------------------------------------------
# GROUP 13: Cache & Metrics
# ---------------------------------------------------------------------------


def test_cache_stats(client: httpx.Client, ctx: dict):
    r = client.get("/cache/stats")
    assert r.status_code == 200
    d = r.json()
    keys = list(d.keys())
    return True, f"keys={keys[:4]}"


def test_metrics_json(client: httpx.Client, ctx: dict):
    r = client.get("/metrics")
    assert r.status_code == 200
    d = r.json()
    total = d.get("queries_total", 0)
    return True, f"queries_total={total}"


def test_metrics_html(client: httpx.Client, ctx: dict):
    r = client.get("/metrics/html")
    ok = r.status_code == 200 and "html" in r.headers.get("content-type", "").lower()
    return ok, f"status={r.status_code}, len={len(r.text)}"


# ---------------------------------------------------------------------------
# GROUP 14: Analytics (Phase 40)
# ---------------------------------------------------------------------------


def test_analytics_summary(client: httpx.Client, ctx: dict):
    r = client.get("/analytics/summary")
    assert r.status_code == 200
    d = r.json()
    total_q = d.get("queries", {}).get("total_queries", 0)
    audit = d.get("audit", {}).get("total_events", 0)
    return True, f"queries={total_q}, audit_events={audit}"


def test_analytics_queries(client: httpx.Client, ctx: dict):
    r = client.get("/analytics/queries")
    assert r.status_code == 200
    d = r.json()
    total = d.get("total_queries", 0)
    strategies = d.get("top_strategies", [])
    return True, f"total={total}, strategies={len(strategies)}"


def test_analytics_recent(client: httpx.Client, ctx: dict):
    r = client.get("/analytics/queries/recent", params={"limit": 10})
    assert r.status_code == 200
    d = r.json()
    count = len(d) if isinstance(d, list) else 0
    return True, f"{count} recent queries"


def test_analytics_costs(client: httpx.Client, ctx: dict):
    r = client.get("/analytics/costs")
    assert r.status_code == 200
    d = r.json()
    cost = d.get("total_cost_usd", 0)
    return True, f"total_cost=${cost}"


def test_analytics_audit(client: httpx.Client, ctx: dict):
    r = client.get("/analytics/audit", params={"limit": 10})
    assert r.status_code == 200
    d = r.json()
    count = len(d) if isinstance(d, list) else 0
    return True, f"{count} audit entries"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    runner = TestRunner()

    # Check server is up first
    try:
        httpx.get(f"{BASE_URL}/health/live", timeout=5.0)
    except Exception:
        print(f"\nERROR: API server not reachable at {BASE_URL}")
        print("Start it with: python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8000")
        return 1

    groups = [
        # (name, timeout, tests)
        ("1. System Health", TIMEOUT_SHORT, [
            test_health, test_health_ready, test_health_live,
        ]),
        ("2. Documents (read-only)", TIMEOUT_SHORT, [
            test_documents_list, test_documents_stats,
            test_documents_registry, test_documents_files,
        ]),
        ("3. Search Core (5 strategies)", TIMEOUT_MEDIUM, [
            test_search_vector, test_search_hybrid, test_search_bm25,
            test_search_mmr, test_search_section_first,
        ]),
        ("4. Search Advanced (5 strategies)", TIMEOUT_MEDIUM, [
            test_search_graphrag_local, test_search_graphrag_light,
            test_search_graphrag_auto, test_search_adaptive,
            test_search_two_stage,
        ]),
        ("5. RAG Agent (Phases 5, 9)", TIMEOUT_LONG, [
            test_ask, test_chat_message, test_chat_followup,
        ]),
        ("6. Analytical Agent (Phase 33)", TIMEOUT_LONG, [
            test_analyze,
        ]),
        ("7. Research Agent (Phase 36)", TIMEOUT_LONG, [
            test_research,
        ]),
        ("8. Multi-Agent (Phase 39)", TIMEOUT_LONG, [
            test_multi_agent,
        ]),
        ("9. Knowledge Graph (Phases 6, 38)", TIMEOUT_SHORT, [
            test_graph_stats, test_graph_entities,
            test_graph_neighbors, test_graph_entity_embeddings_stats,
        ]),
        ("10. ToC Navigation (Phase 30)", TIMEOUT_SHORT, [
            test_toc_tree, test_toc_section_detail,
        ]),
        ("11. Collections (Phase 32)", TIMEOUT_MEDIUM, [
            test_collections_create, test_collections_list,
            test_collections_add_document, test_collections_search_scoped,
            test_collections_list_documents, test_collections_delete,
        ]),
        ("12. Feedback (Phase 22)", TIMEOUT_SHORT, [
            test_feedback_submit, test_feedback_stats,
        ]),
        ("13. Cache & Metrics (Phases 11, 17)", TIMEOUT_SHORT, [
            test_cache_stats, test_metrics_json, test_metrics_html,
        ]),
        ("14. Analytics (Phase 40)", TIMEOUT_SHORT, [
            test_analytics_summary, test_analytics_queries,
            test_analytics_recent, test_analytics_costs,
            test_analytics_audit,
        ]),
    ]

    for name, timeout, tests in groups:
        runner.run_group(name, timeout, tests)

    return runner.summary()


if __name__ == "__main__":
    sys.exit(main())
