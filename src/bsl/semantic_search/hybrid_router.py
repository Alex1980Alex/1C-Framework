"""Hybrid retrieval router for BSL queries (Phase 5 GraphRAG roadmap 260502)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

QueryType = Literal["semantic", "multi_hop_callers", "impact_analysis", "architectural",
                    "dead_code", "cross_cutting", "topology", "mixed"]
Strategy = Literal["vector", "graph", "community", "hybrid"]


@dataclass
class RouterResult:
    query: str
    detected_type: QueryType
    strategy_used: Strategy
    results: list[dict[str, Any]] = field(default_factory=list)
    layers_consulted: list[str] = field(default_factory=list)
    latency_ms: float = 0.0


def classify_query(query: str) -> QueryType:
    """Rule-based classifier — recognizes Russian + English query patterns."""
    q = query.lower()
    callers_kw = ["кто вызывает", "кто использует", "callers of", "callers"]
    impact_kw = ["что сломается", "сломается", "если переименую", "если изменю",
                 "if i rename", "impact", "влияние", "повлия", "пострадают"]
    arch_kw = ["overview", "обзор", "устройство", "архитектура",
               "опиши подсистему", "опиши арм", "опиши устройство",
               "describe subsystem", "арм оператора",
               "взаимосвязи", "связи через", "взаимодействие подсистем"]
    dead_kw = ["dead code", "не вызывается", "не вызываются",
               "никем не используется", "никем не вызывается", "никем не вызываются",
               "unused", "мертвый"]
    cross_kw = ["функциональн", "fo и регистр", "фо и регистр",
                "регистр и функцион", "cross-cutting",
                "пишут в регистр", "пишут регистр",
                "читают регистр", "читают из регистра",
                "одновременно", "вместе используются", "общие функции"]
    topology_kw = ["самые часто", "часто вызываемые", "топ функций",
                   "узкие места", "больше всего вызовов",
                   "больше всего исходящих", "ранжируй по", "топ-",
                   "статистика графа"]
    if any(k in q for k in topology_kw): return "topology"
    if any(k in q for k in callers_kw): return "multi_hop_callers"
    if any(k in q for k in impact_kw): return "impact_analysis"
    if any(k in q for k in arch_kw): return "architectural"
    if any(k in q for k in dead_kw): return "dead_code"
    if any(k in q for k in cross_kw): return "cross_cutting"
    return "semantic"


def strategy_for(query_type: QueryType) -> Strategy:
    """Map query type to retrieval strategy."""
    return {
        "semantic": "vector",
        "multi_hop_callers": "graph",
        "impact_analysis": "graph",
        "architectural": "community",
        "dead_code": "graph",
        "cross_cutting": "hybrid",
        "topology": "graph",
        "mixed": "hybrid",
    }.get(query_type, "hybrid")


def route(query: str, *, force_strategy: Strategy | None = None) -> tuple[QueryType, Strategy]:
    qt = classify_query(query)
    st = force_strategy or strategy_for(qt)
    logger.debug("Router: %r -> type=%s, strategy=%s", query, qt, st)
    return qt, st


def hybrid_search(query: str, *,
                  vector_fn=None, graph_fn=None, community_fn=None,
                  k: int = 10, force_strategy: Strategy | None = None) -> RouterResult:
    """Run query through router + appropriate backend(s).
    
    Backends are pluggable callables:
      vector_fn(query, k) -> list[dict] — Qdrant bsl_code_v4_late lookup
      graph_fn(query, k, query_type) -> list[dict] — Neo4j Cypher (depends on type)
      community_fn(query, k) -> list[dict] — Qdrant graph_embeddings filter Community
    """
    import time
    t0 = time.time()
    qt, st = route(query, force_strategy=force_strategy)
    res = RouterResult(query=query, detected_type=qt, strategy_used=st)
    if st == "vector" and vector_fn:
        res.results = vector_fn(query, k=k); res.layers_consulted.append("Layer 1: bsl_code_v4_late")
    elif st == "graph" and graph_fn:
        res.results = graph_fn(query, k=k, query_type=qt); res.layers_consulted.append("Layer 3: Neo4j")
        if not res.results and vector_fn:
            res.results = vector_fn(query, k=k); res.layers_consulted.append("Layer 1 (graph empty fallback)")
    elif st == "community" and community_fn:
        res.results = community_fn(query, k=k); res.layers_consulted.append("Layer 4: communities")
    elif st == "hybrid":
        merged = []
        if vector_fn:
            merged.extend(vector_fn(query, k=max(3, k//2)))
            res.layers_consulted.append("Layer 1")
        if graph_fn:
            merged.extend(graph_fn(query, k=max(3, k//2), query_type=qt))
            res.layers_consulted.append("Layer 3")
        if community_fn:
            merged.extend(community_fn(query, k=3))
            res.layers_consulted.append("Layer 4")
        seen, uniq = set(), []
        for r in merged:
            key = r.get("id") or r.get("name") or repr(r)[:50]
            if key in seen: continue
            seen.add(key); uniq.append(r)
        res.results = uniq[:k]
    else:
        if vector_fn:
            res.results = vector_fn(query, k=k); res.layers_consulted.append("Layer 1 (fallback)")
    res.latency_ms = (time.time() - t0) * 1000
    return res
