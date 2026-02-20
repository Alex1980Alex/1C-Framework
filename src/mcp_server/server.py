"""MCP Server v2 for PDF Vector & Graph Framework (Phase 37).

12 tools: PDF indexing, search, QA, graph, analysis, research,
collections, ToC, web search, source fusion, documents, stats.

Transport: stdio (default) or SSE.
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from src.api.dependencies.components import Components

server = Server("pdf-vector-graph")
_components: Components | None = None


async def _get_components() -> Components:
    global _components
    if _components is None:
        _components = Components()
        await _components.initialize()
    return _components


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ---- Core Tools ----
        Tool(
            name="index_pdf",
            description="Index a PDF document: load, split into chunks, compute embeddings, and store.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to the PDF file"},
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="search_documents",
            description="Search indexed documents. Strategies: vector, graph, hybrid, bm25, section_first, graphrag_local, graphrag_light.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "strategy": {
                        "type": "string",
                        "enum": ["vector", "graph", "hybrid", "bm25", "section_first", "graphrag_local", "graphrag_light"],
                        "default": "hybrid",
                    },
                    "k": {"type": "integer", "default": 5, "description": "Number of results"},
                    "section": {"type": "string", "description": "Filter by section prefix (e.g. '5.14')"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="ask_question",
            description="Ask a question and get an LLM-generated answer using RAG.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The question to answer"},
                    "strategy": {
                        "type": "string",
                        "enum": ["vector", "graph", "hybrid", "bm25"],
                        "default": "hybrid",
                    },
                },
                "required": ["question"],
            },
        ),
        Tool(
            name="graph_query",
            description="Query the knowledge graph for entities and relations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Entity name or search term"},
                    "entity_type": {"type": "string", "default": ""},
                    "depth": {"type": "integer", "default": 1},
                },
                "required": ["query"],
            },
        ),
        # ---- Phase 33: Analytical ----
        Tool(
            name="analyze",
            description="Analytical RAG: multi-round evidence gathering with comparison tables. For complex comparative/analytical questions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Analytical question"},
                    "max_rounds": {"type": "integer", "default": 3},
                },
                "required": ["question"],
            },
        ),
        # ---- Phase 36: Research ----
        Tool(
            name="research",
            description="Deep research v2: plan-execute-verify with evidence graph and structured reports.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Research question"},
                    "max_rounds": {"type": "integer", "default": 5},
                },
                "required": ["question"],
            },
        ),
        # ---- Phase 37: Web Search ----
        Tool(
            name="web_search",
            description="Search the web via Tavily/SerpAPI/DuckDuckGo. Used as fallback when local docs lack information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Web search query"},
                    "k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="search_with_fallback",
            description="Search local docs first; if low confidence, also search the web and fuse results.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "strategy": {"type": "string", "default": "hybrid"},
                    "k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
        # ---- Phase 32: Collections ----
        Tool(
            name="list_collections",
            description="List all document collections.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="list_documents",
            description="List indexed documents with metadata.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ---- Phase 30: ToC ----
        Tool(
            name="get_toc",
            description="Get table of contents for an indexed document.",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Document ID"},
                },
                "required": ["document_id"],
            },
        ),
        # ---- Stats ----
        Tool(
            name="get_stats",
            description="Get statistics about indexed documents and knowledge graph.",
            inputSchema={"type": "object", "properties": {}},
        ),
        # ---- Phase 55: Visual Search ----
        Tool(
            name="visual_search",
            description="Search visual pages (tables, charts, diagrams) by text description.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text description of visual content"},
                    "k": {"type": "integer", "default": 5},
                    "document_id": {"type": "string", "description": "Filter by document"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="visual_hybrid_search",
            description="Hybrid visual + text search with RRF fusion.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "k": {"type": "integer", "default": 5},
                    "visual_weight": {"type": "number", "default": 0.5},
                    "text_weight": {"type": "number", "default": 0.5},
                },
                "required": ["query"],
            },
        ),
        # ---- Phase 57: Plan-Execute ----
        Tool(
            name="plan_execute",
            description="Plan-Execute agent: breaks complex queries into steps and executes with appropriate tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Complex query to analyze"},
                    "max_iterations": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    components = await _get_components()

    if name == "index_pdf":
        file_path = arguments["file_path"]
        document = await components.loader.load(file_path)
        chunks = components.pipeline.process(document)
        result = await components.indexer.index_chunks(
            chunks, document_id=document.id, source_path=document.source_path,
        )
        return [TextContent(
            type="text",
            text=json.dumps({
                "document_id": result.document_id,
                "chunks_stored": result.chunks_stored,
                "embeddings_computed": result.embeddings_computed,
            }),
        )]

    elif name == "search_documents":
        section = arguments.get("section")
        if arguments.get("strategy") == "section_first":
            response = await components.search_manager.search_section_first(
                query=arguments["query"],
                k=arguments.get("k", 5),
            )
        else:
            response = await components.search_manager.search(
                query=arguments["query"],
                strategy=arguments.get("strategy", "hybrid"),
                k=arguments.get("k", 5),
                section_prefix=section,
            )
        results = [
            {
                "chunk_id": r.chunk.id,
                "content": r.chunk.content[:500],
                "score": round(r.score, 3),
                "source": r.source,
                "section": r.chunk.metadata.get("section_title", ""),
                "page": r.chunk.metadata.get("page_number"),
            }
            for r in response.results
        ]
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False))]

    elif name == "ask_question":
        from src.pdf_framework.chains.qa.retrieval_qa import RetrievalQAChain

        search_response = await components.search_manager.search(
            query=arguments["question"],
            strategy=arguments.get("strategy", "hybrid"),
            k=5,
        )
        chain = RetrievalQAChain(
            settings=components.settings.agent,
            api_key=components.settings.anthropic_api_key,
        )
        answer = await chain.answer(arguments["question"], search_response)
        return [TextContent(type="text", text=answer)]

    elif name == "graph_query":
        entities = await components.graph_store.find_entities(
            name=arguments["query"],
            entity_type=arguments.get("entity_type") or None,
            limit=10,
        )
        results = []
        for entity in entities:
            subgraph = await components.graph_store.get_neighbors(
                entity.id, depth=arguments.get("depth", 1),
            )
            results.append({
                "entity": {"id": entity.id, "name": entity.name, "type": entity.entity_type},
                "relations": [
                    {"type": r.relation_type, "target": r.target_entity_id}
                    for r in subgraph.relations[:10]
                ],
            })
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False))]

    elif name == "analyze":
        from src.pdf_framework.agents.analytical.agent import create_analytical_agent

        agent = create_analytical_agent(
            search_manager=components.search_manager,
            settings=components.settings.agent,
            api_key=components.settings.anthropic_api_key,
        )
        result = await agent.ainvoke({
            "question": arguments["question"],
            "max_rounds": arguments.get("max_rounds", 3),
        })
        return [TextContent(type="text", text=result.get("answer", ""))]

    elif name == "research":
        from src.pdf_framework.agents.research_v2.agent import create_research_agent_v2

        agent = create_research_agent_v2(
            search_manager=components.search_manager,
            settings=components.settings.agent,
            api_key=components.settings.anthropic_api_key,
        )
        result = await agent.ainvoke({
            "question": arguments["question"],
            "max_rounds": arguments.get("max_rounds", 5),
        })
        return [TextContent(type="text", text=result.get("answer", ""))]

    elif name == "web_search":
        web = getattr(components, "web_search_strategy", None)
        if web is None:
            return [TextContent(type="text", text="Web search not configured. Set EXTERNAL__TAVILY_API_KEY.")]
        response = await web.search(
            query=arguments["query"],
            k=arguments.get("k", 5),
        )
        results = [
            {
                "content": r.chunk.content[:500],
                "url": r.chunk.metadata.get("url", ""),
                "title": r.chunk.metadata.get("title", ""),
                "score": round(r.score, 3),
            }
            for r in response.results
        ]
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False))]

    elif name == "search_with_fallback":
        fusion = getattr(components, "source_fusion", None)
        if fusion is None:
            # No fusion configured, just do local search
            response = await components.search_manager.search(
                query=arguments["query"],
                strategy=arguments.get("strategy", "hybrid"),
                k=arguments.get("k", 5),
            )
        else:
            response = await fusion.search_with_fallback(
                query=arguments["query"],
                strategy=arguments.get("strategy", "hybrid"),
                k=arguments.get("k", 5),
            )
        results = [
            {
                "content": r.chunk.content[:500],
                "score": round(r.score, 3),
                "source": r.source,
                "trust": r.chunk.metadata.get("trust", "documentation"),
            }
            for r in response.results
        ]
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False))]

    elif name == "list_collections":
        coll_store = getattr(components, "collection_store", None)
        if coll_store is None:
            return [TextContent(type="text", text="[]")]
        collections = await coll_store.list_all()
        return [TextContent(
            type="text",
            text=json.dumps([c.model_dump() for c in collections], ensure_ascii=False),
        )]

    elif name == "list_documents":
        registry = getattr(components, "document_registry", None)
        if registry is None:
            return [TextContent(type="text", text="[]")]
        docs = await registry.list_all()
        return [TextContent(
            type="text",
            text=json.dumps([d.model_dump() for d in docs], ensure_ascii=False, default=str),
        )]

    elif name == "get_toc":
        from src.pdf_framework.processing.toc_parser import DocumentToC

        doc_id = arguments["document_id"]
        # Get chunks for this document from vector store
        chunks_data = await components.vector_store.scroll(
            filter={"document_id": doc_id},
            limit=2000,
            fields=["section_number", "section_title", "breadcrumb", "page_number"],
        )
        toc = DocumentToC.build_from_chunks(chunks_data)
        return [TextContent(
            type="text",
            text=json.dumps(toc.to_dict(), ensure_ascii=False),
        )]

    elif name == "get_stats":
        vector_count = await components.vector_store.count()
        graph_stats = await components.graph_store.get_statistics()
        return [TextContent(type="text", text=json.dumps({
            "vector_store": {"document_count": vector_count},
            "graph_store": graph_stats,
        }))]

    elif name == "visual_search":
        response = await components.search_manager.search_visual(
            query=arguments["query"],
            k=arguments.get("k", 5),
            document_id=arguments.get("document_id"),
        )
        results = [
            {
                "chunk_id": r.chunk.id,
                "content": r.chunk.content[:500],
                "page": r.chunk.metadata.get("page_number"),
                "score": round(r.score, 3),
                "source": r.source,
            }
            for r in response.results
        ]
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False))]

    elif name == "visual_hybrid_search":
        response = await components.search_manager.search_hybrid_visual_text(
            query=arguments["query"],
            k=arguments.get("k", 5),
            visual_weight=arguments.get("visual_weight", 0.5),
            text_weight=arguments.get("text_weight", 0.5),
        )
        results = [
            {
                "chunk_id": r.chunk.id,
                "content": r.chunk.content[:500],
                "page": r.chunk.metadata.get("page_number"),
                "score": round(r.score, 3),
                "source": r.source,
            }
            for r in response.results
        ]
        metadata = response.metadata or {}
        return [TextContent(type="text", text=json.dumps({
            "results": results,
            "visual_count": metadata.get("visual_count", 0),
            "text_count": metadata.get("text_count", 0),
        }, ensure_ascii=False))]

    elif name == "plan_execute":
        from src.pdf_framework.agents.plan_execute.agent import create_plan_execute_agent
        from langchain_anthropic import ChatAnthropic

        llm_kwargs = {
            "model": components.settings.agent.model,
            "temperature": 0.0,
            "max_tokens": 4096,
        }
        if components.settings.agent.base_url:
            llm_kwargs["base_url"] = components.settings.agent.base_url

        llm = ChatAnthropic(
            **llm_kwargs,
            api_key=components.settings.anthropic_api_key.get_secret_value(),
        )

        tools = {
            "search": lambda q, **kw: components.search_manager.search(q, "hybrid", **kw),
            "graph_query": lambda q, **kw: components.search_manager.search(q, "graph", **kw),
            "calculate": lambda expr: str(eval(expr, {"__builtins__": {}}, {})),
            "web_search": lambda q, **kw: components.search_manager.search(q, "hybrid", **kw),
        }

        agent = create_plan_execute_agent(
            llm=llm,
            search_manager=components.search_manager,
            tools=tools,
            max_iterations=arguments.get("max_iterations", 5),
        )

        result = await agent.ainvoke({
            "query": arguments["query"],
            "max_iterations": arguments.get("max_iterations", 5),
        })

        steps = [
            {
                "step_id": s.step_id,
                "description": s.description,
                "tool": s.tool,
                "status": s.status,
                "result": str(s.result) if s.result else None,
            }
            for s in result.plan
        ]

        return [TextContent(type="text", text=json.dumps({
            "query": arguments["query"],
            "answer": result.final_answer,
            "steps": steps,
            "iterations": result.iterations,
        }, ensure_ascii=False))]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
