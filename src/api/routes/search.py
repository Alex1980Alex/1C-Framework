"""Search and QA endpoints."""

import json
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.api.dependencies.components import Components, get_components
from src.api.dependencies.auth import get_current_user  # F3.2.4: Get user from JWT
from src.pdf_framework.chains.qa.retrieval_qa import RetrievalQAChain

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    strategy: str = "vector"
    k: int = 5
    filter: dict[str, Any] | None = None
    rerank: bool = True
    expand_query: bool = False
    section: str | None = None  # Filter by section prefix, e.g. "5.14"
    collection_id: str | None = None  # Phase 32: Search within a collection


class SearchResultItem(BaseModel):
    chunk_id: str
    content: str
    score: float
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponseModel(BaseModel):
    query: str
    results: list[SearchResultItem]
    total_found: int
    search_type: str
    elapsed_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AskRequest(BaseModel):
    question: str
    strategy: str = "hybrid"
    k: int = 5
    filter: dict[str, Any] | None = None
    rerank: bool = True
    stream: bool = False


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)
    search_type: str
    elapsed_ms: float
    model_used: str = ""  # Phase 54: Which LLM model was used


@router.post("/", response_model=SearchResponseModel)
async def search_documents(
    request: SearchRequest,
    components: Components = Depends(get_components),
    current_user: str | None = Depends(get_current_user),  # F3.2.4: User attribution for tracing
):
    """Search indexed documents."""
    # F3.2.4: Extract user_id for trace attribution
    user_id = current_user or "anonymous"

    # Phase 32: Resolve collection_id to document_id filter
    search_filter = dict(request.filter) if request.filter else {}
    if request.collection_id:
        coll_store = getattr(components, "collection_store", None)
        if coll_store is not None:
            doc_ids = await coll_store.get_document_ids(request.collection_id)
            if doc_ids:
                search_filter["document_id"] = doc_ids  # list = any of these
            else:
                # Empty collection — return no results
                return SearchResponseModel(
                    query=request.query, results=[], total_found=0,
                    search_type="collection_empty", elapsed_ms=0, metadata={"user_id": user_id},
                )

    effective_filter = search_filter or None

    # Phase 30: Section-first pipeline
    t0 = time.perf_counter()
    if request.strategy == "section_first":
        response = await components.search_manager.search_section_first(
            query=request.query,
            k=request.k,
            filter=effective_filter,
        )
    else:
        response = await components.search_manager.search(
            query=request.query,
            strategy=request.strategy,
            k=request.k,
            filter=effective_filter,
            rerank=request.rerank,
            expand_query=request.expand_query,
            section_prefix=request.section,
        )
    latency = (time.perf_counter() - t0) * 1000

    # Phase 40: Track query
    components.query_tracker.track(
        query=request.query,
        strategy=request.strategy,
        agent="search",
        results_count=response.total_found,
        latency_ms=latency,
    )
    components.audit_logger.log(
        event_type="search",
        query=request.query,
        strategy=request.strategy,
        results_count=response.total_found,
    )

    # F3.2.4: Add user_id to response metadata for trace attribution
    response_metadata = dict(response.metadata)
    response_metadata["user_id"] = user_id

    return SearchResponseModel(
        query=response.query,
        results=[
            SearchResultItem(
                chunk_id=r.chunk.id,
                content=r.chunk.content,
                score=r.score,
                source=r.source,
                metadata=r.chunk.metadata,
            )
            for r in response.results
        ],
        total_found=response.total_found,
        search_type=response.search_type,
        elapsed_ms=response.elapsed_ms,
        metadata=response_metadata,
    )


def _sse_event(event_type: str, data: Any, metadata: dict | None = None) -> str:
    """Format a single SSE event line."""
    payload = {"type": event_type, "data": data, "metadata": metadata or {}}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/ask")
async def ask_question(
    request: AskRequest,
    components: Components = Depends(get_components),
    current_user: str | None = Depends(get_current_user),  # F3.2.4: User attribution
):
    """Ask a question and get an LLM-generated answer with context.

    With stream=true, returns Server-Sent Events (SSE) stream.
    With stream=false (default), returns JSON response.
    """
    t0 = time.perf_counter()

    # F3.2.4: Extract user_id for trace attribution
    user_id = current_user or "anonymous"

    search_response = await components.search_manager.search(
        query=request.question,
        strategy=request.strategy,
        k=request.k,
        filter=request.filter,
        rerank=request.rerank,
    )

    chain = RetrievalQAChain(
        settings=components.settings.agent,
        api_key=components.settings.anthropic_api_key,
    )

    sources: list[str] = []
    for r in search_response.results:
        src = r.chunk.metadata.get("source", "")
        if src and src not in sources:
            sources.append(src)

    # Phase 42: Create fast LLM for enrichment if enabled
    fast_llm = None
    if components.settings.self_rag.enrichment_enabled:
        from langchain_anthropic import ChatAnthropic as _ChatAnthropic
        _llm_kwargs: dict[str, Any] = {
            "model": components.settings.self_rag.grading_model,
            "temperature": 0.0,
            "max_tokens": 1024,
            "api_key": components.settings.anthropic_api_key or None,
        }
        if components.settings.agent.base_url:
            _llm_kwargs["base_url"] = components.settings.agent.base_url
        fast_llm = _ChatAnthropic(**_llm_kwargs)

    # --- Non-streaming path (default) ---
    if not request.stream:
        answer = await chain.answer(
            request.question,
            search_response,
            search_manager=components.search_manager if fast_llm else None,
            fast_llm=fast_llm,
        )
        elapsed = (time.perf_counter() - t0) * 1000
        return AskResponse(
            answer=answer,
            sources=sources,
            search_type=search_response.search_type,
            elapsed_ms=elapsed,
        )

    # --- Streaming path (SSE) ---
    async def event_generator():
        search_ms = (time.perf_counter() - t0) * 1000
        yield _sse_event("status", "searching_done", {"elapsed_ms": round(search_ms)})

        # Early source delivery — client gets sources before generation starts
        yield _sse_event("sources", sources, {
            "total_found": search_response.total_found,
            "search_type": search_response.search_type,
        })

        yield _sse_event("status", "generating")

        collected: list[str] = []
        gen_start = time.perf_counter()
        ttft_sent = False
        async for token in chain.stream_answer(request.question, search_response):
            collected.append(token)
            # Phase 49: TTFT (Time To First Token) metric
            if not ttft_sent:
                ttft_ms = (time.perf_counter() - gen_start) * 1000
                yield _sse_event("ttft", "", {"ttft_ms": round(ttft_ms)})
                ttft_sent = True
            yield _sse_event("token", token)

        # Post-processing: append section refs if LLM didn't include them
        full_answer = "".join(collected)
        from src.pdf_framework.utils.section_refs import append_section_refs
        final_answer = append_section_refs(full_answer, search_response.results)
        extra = final_answer[len(full_answer):]
        if extra:
            yield _sse_event("token", extra)

        elapsed = (time.perf_counter() - t0) * 1000
        yield _sse_event("done", "", {
            "elapsed_ms": round(elapsed),
            "ttft_ms": round(ttft_ms) if ttft_sent else None,
            "search_ms": round(search_ms),
            "search_type": search_response.search_type,
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Phase 33: Analytical RAG Agent


class AnalyzeRequest(BaseModel):
    question: str
    max_rounds: int = 3
    collection_id: str | None = None  # Phase 32: Scope to collection


class AnalyzeResponse(BaseModel):
    answer: str
    summary: str = ""
    comparison_table: dict[str, Any] | None = None
    evidence_count: int = 0
    rounds_used: int = 0
    coverage: float = 0.0
    sources: list[str] = Field(default_factory=list)
    structured: dict[str, Any] = Field(default_factory=dict)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_question(
    request: AnalyzeRequest,
    components: Components = Depends(get_components),
):
    """Analytical RAG: multi-round evidence gathering with structured output.

    Phase 33: For comparative, analytical, and overview questions.
    Uses Think -> Act -> Observe -> Re-Think cycle.
    """
    from src.pdf_framework.agents.analytical.agent import create_analytical_agent

    agent = create_analytical_agent(
        search_manager=components.search_manager,
        settings=components.settings.agent,
        api_key=components.settings.anthropic_api_key,
        fast_model=components.settings.self_rag.grading_model,
    )

    initial_state = {
        "question": request.question,
        "max_rounds": request.max_rounds,
    }

    t0 = time.perf_counter()
    result = await agent.ainvoke(initial_state)
    latency = (time.perf_counter() - t0) * 1000

    structured = result.get("structured_answer", {})

    # Phase 40: Track
    components.query_tracker.track(
        query=request.question,
        agent="analytical",
        results_count=len(result.get("evidence", [])),
        latency_ms=latency,
    )
    components.audit_logger.log(
        event_type="analyze",
        query=request.question,
        agent="analytical",
        results_count=len(result.get("evidence", [])),
        answer_preview=result.get("answer", ""),
    )

    return AnalyzeResponse(
        answer=result.get("answer", ""),
        summary=structured.get("summary", ""),
        comparison_table=structured.get("comparison_table"),
        evidence_count=len(result.get("evidence", [])),
        rounds_used=result.get("round", 0),
        coverage=result.get("coverage", 0.0),
        sources=result.get("sources", []),
        structured=structured,
    )


# Phase 36: Research Agent v2


class ResearchRequest(BaseModel):
    question: str
    max_rounds: int = 5
    session_id: str | None = None  # Resume previous session


class ResearchResponse(BaseModel):
    answer: str
    executive_summary: str = ""
    sections: list[dict[str, Any]] = Field(default_factory=list)
    evidence_count: int = 0
    rounds_used: int = 0
    coverage: float = 0.0
    contradictions: int = 0
    total_queries: int = 0
    sources: list[str] = Field(default_factory=list)
    session_id: str = ""


@router.post("/research", response_model=ResearchResponse)
async def research_question(
    request: ResearchRequest,
    components: Components = Depends(get_components),
):
    """Deep research v2: plan-execute-verify with evidence graph.

    Phase 36: Autonomous multi-round research with:
    - Dependency-tree planning
    - Evidence graph with contradiction detection
    - Quality gates (coverage >=80%, groundedness >=90%)
    - Structured report generation
    """
    from src.pdf_framework.agents.research_v2.agent import create_research_agent_v2

    agent = create_research_agent_v2(
        search_manager=components.search_manager,
        settings=components.settings.agent,
        api_key=components.settings.anthropic_api_key,
        fast_model=components.settings.self_rag.grading_model,
    )

    initial_state = {
        "question": request.question,
        "max_rounds": request.max_rounds,
    }
    if request.session_id:
        initial_state["session_id"] = request.session_id

    t0 = time.perf_counter()
    result = await agent.ainvoke(initial_state)
    latency = (time.perf_counter() - t0) * 1000

    report = result.get("report", {})
    eg = result.get("evidence_graph", {})

    # Phase 40: Track
    components.query_tracker.track(
        query=request.question,
        agent="research_v2",
        results_count=report.get("evidence_count", 0),
        latency_ms=latency,
    )
    components.audit_logger.log(
        event_type="research",
        query=request.question,
        agent="research_v2",
        results_count=report.get("evidence_count", 0),
        answer_preview=result.get("answer", ""),
        sources=report.get("sources", []),
    )

    return ResearchResponse(
        answer=result.get("answer", ""),
        executive_summary=report.get("executive_summary", ""),
        sections=[s for s in report.get("sections", [])],
        evidence_count=report.get("evidence_count", 0),
        rounds_used=report.get("rounds_used", 0),
        coverage=report.get("coverage", 0.0),
        contradictions=len(eg.get("relations", [])),
        total_queries=report.get("total_search_queries", 0),
        sources=report.get("sources", []),
        session_id=result.get("session_id", ""),
    )


# Phase 39: Multi-Agent Orchestration


class MultiAgentRequest(BaseModel):
    question: str
    max_iterations: int = 2


class MultiAgentResponse(BaseModel):
    answer: str
    groundedness: float = 0.0
    completeness: float = 0.0
    findings_count: int = 0
    chunks_used: int = 0
    iterations: int = 0
    agents_used: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/multi-agent", response_model=MultiAgentResponse)
async def multi_agent_question(
    request: MultiAgentRequest,
    components: Components = Depends(get_components),
):
    """Multi-agent orchestration: retrieval → analysis → writing → verification.

    Phase 39: Specialized agents collaborate for comprehensive analysis.
    """
    from src.pdf_framework.agents.multi.orchestrator import create_multi_agent

    agent = create_multi_agent(
        search_manager=components.search_manager,
        settings=components.settings.agent,
        api_key=components.settings.anthropic_api_key,
        fast_model=components.settings.self_rag.grading_model,
    )

    t0 = time.perf_counter()
    result = await agent.ainvoke({
        "question": request.question,
        "max_iterations": request.max_iterations,
    })
    latency = (time.perf_counter() - t0) * 1000

    report = result.get("report", {})

    # Phase 40: Track
    components.query_tracker.track(
        query=request.question,
        agent="multi_agent",
        results_count=report.get("chunks_used", 0),
        latency_ms=latency,
    )
    components.audit_logger.log(
        event_type="multi_agent",
        query=request.question,
        agent="multi_agent",
        results_count=report.get("chunks_used", 0),
        answer_preview=result.get("answer", ""),
        sources=report.get("sources", []),
    )

    return MultiAgentResponse(
        answer=result.get("answer", ""),
        groundedness=report.get("groundedness", 0),
        completeness=report.get("completeness", 0),
        findings_count=report.get("findings_count", 0),
        chunks_used=report.get("chunks_used", 0),
        iterations=report.get("iterations", 0),
        agents_used=report.get("agents_used", []),
        sources=report.get("sources", []),
        messages=result.get("messages", []),
    )


# Phase 55: Visual Search (ColPali)


class VisualSearchRequest(BaseModel):
    query: str
    k: int = 5
    document_id: str | None = None
    visual_weight: float = 0.5  # For hybrid visual+text search
    text_weight: float = 0.5


class VisualSearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total_found: int
    visual_results: int
    text_results: int
    elapsed_ms: float
    search_type: str = "visual"


@router.post("/visual", response_model=VisualSearchResponse)
async def visual_search(
    request: VisualSearchRequest,
    components: Components = Depends(get_components),
    current_user: str | None = Depends(get_current_user),
):
    """Visual search using ColPali embeddings for tables/charts/diagrams.

    Phase 55: End-to-end visual retrieval without OCR.
    Searches page images by visual similarity.
    """
    user_id = current_user or "anonymous"
    t0 = time.perf_counter()

    # Try to get visual strategy from search manager
    visual_strategy = components.search_manager._strategies.get("visual")

    if visual_strategy is None:
        # Fallback: return empty results with error info
        return VisualSearchResponse(
            query=request.query,
            results=[],
            total_found=0,
            visual_results=0,
            text_results=0,
            elapsed_ms=0,
            search_type="visual_not_configured",
        )

    # Get text embedding for hybrid search
    text_embedding = await components.embedding_engine.embed_text(request.query)

    # Perform hybrid visual+text search
    response = await visual_strategy.hybrid_visual_text_search(
        query=request.query,
        text_embedding=text_embedding,
        k=request.k,
        visual_weight=request.visual_weight,
        text_weight=request.text_weight,
        document_id=request.document_id,
    )

    latency = (time.perf_counter() - t0) * 1000

    # Phase 40: Track query
    components.query_tracker.track(
        query=request.query,
        strategy="visual",
        agent="visual_search",
        results_count=response.total_found,
        latency_ms=latency,
    )

    metadata = response.metadata or {}
    visual_count = metadata.get("visual_count", 0)
    text_count = metadata.get("text_count", 0)

    return VisualSearchResponse(
        query=response.query,
        results=[
            SearchResultItem(
                chunk_id=r.chunk.id,
                content=r.chunk.content,
                score=r.score,
                source=r.source,
                metadata=r.chunk.metadata,
            )
            for r in response.results
        ],
        total_found=response.total_found,
        visual_results=visual_count,
        text_results=text_count,
        elapsed_ms=response.elapsed_ms,
        search_type=response.search_type,
    )


# Phase 57: Plan-Execute Agent


class PlanExecuteRequest(BaseModel):
    query: str
    max_iterations: int = 5
    stream: bool = False


class PlanExecuteStep(BaseModel):
    step_id: str
    description: str
    tool: str
    query: str
    status: str  # pending/in_progress/completed/failed
    result: str | None = None


class PlanExecuteResponse(BaseModel):
    query: str
    answer: str
    steps: list[PlanExecuteStep] = Field(default_factory=list)
    iterations: int = 0
    elapsed_ms: float
    model_used: str = ""


@router.post("/plan-execute", response_model=PlanExecuteResponse)
async def plan_execute_query(
    request: PlanExecuteRequest,
    components: Components = Depends(get_components),
    current_user: str | None = Depends(get_current_user),
):
    """Plan-Execute agent for complex queries (Phase 57).

    Breaks down complex queries into 2-5 steps, executes each with appropriate tool,
    and synthesizes a final answer.
    """
    from src.pdf_framework.agents.plan_execute.agent import create_plan_execute_agent
    from langchain_anthropic import ChatAnthropic

    user_id = current_user or "anonymous"
    t0 = time.perf_counter()

    # Create LLM for planning and synthesis
    llm_kwargs: dict[str, Any] = {
        "model": components.settings.agent.model,
        "temperature": 0.0,
        "max_tokens": 4096,
    }
    if components.settings.agent.base_url:
        llm_kwargs["base_url"] = components.settings.agent.base_url

    llm = ChatAnthropic(
        **llm_kwargs,
        api_key=components.settings.anthropic_api_key or None,
    )

    # Create tools
    tools = {
        "search": lambda q, **kw: components.search_manager.search(q, "hybrid", **kw),
        "graph_query": lambda q, **kw: components.search_manager.search(q, "graph", **kw),
        "calculate": lambda expr: eval(expr, {"__builtins__": {}}, {}),
        "web_search": lambda q, **kw: components.search_manager.search(q, "hybrid", **kw),
    }

    # Create agent
    agent = create_plan_execute_agent(
        llm=llm,
        search_manager=components.search_manager,
        tools=tools,
        max_iterations=request.max_iterations,
    )

    # Run agent
    result = await agent.ainvoke({
        "query": request.query,
        "max_iterations": request.max_iterations,
    })

    latency = (time.perf_counter() - t0) * 1000

    # Track query
    components.query_tracker.track(
        query=request.query,
        strategy="plan_execute",
        agent="plan_execute",
        results_count=len(result.plan),
        latency_ms=latency,
    )

    # Convert steps to response format
    steps = [
        PlanExecuteStep(
            step_id=step.step_id,
            description=step.description,
            tool=step.tool,
            query=step.query,
            status=step.status,
            result=str(step.result) if step.result else None,
        )
        for step in result.plan
    ]

    return PlanExecuteResponse(
        query=request.query,
        answer=result.final_answer,
        steps=steps,
        iterations=result.iterations,
        elapsed_ms=latency,
        model_used=components.settings.agent.model,
    )
