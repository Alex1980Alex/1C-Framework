"""CLI interface for PDF Vector & Graph Framework.

Commands:
    index    - Index PDF documents into vector and graph stores
    search   - Search indexed documents
    ask      - Ask a question using RAG
    chat     - Interactive chat with conversation memory (Phase 9)
    cache    - Manage caches (stats, clear) - Phase 11
    tenant   - Manage tenants (create, list, delete) - Phase 12
    auth     - Generate JWT tokens - Phase 12
    stats    - Show index statistics
    server   - Start REST API server
    eval     - Run evaluation benchmark
    research - Deep research across documents (Phase 19)
    autorag  - AutoRAG grid search optimization (Phase 20)
    feedback - Manage feedback and self-learning (Phase 22)
"""

import asyncio
import io
import sys
import uuid

import typer
from rich.console import Console
from rich.table import Table

# Fix Cyrillic encoding on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

app = typer.Typer(
    name="pdf-framework",
    help="PDF Vector & Graph Framework CLI",
)
console = Console()


def _get_components():
    """Lazily initialize framework components."""
    from src.api.dependencies.components import Components

    components = Components()
    loop = asyncio.new_event_loop()
    loop.run_until_complete(components.initialize())
    return components


@app.command()
def index(
    file_path: str = typer.Argument(..., help="Path to PDF file to index"),
    build_graph: bool = typer.Option(False, "--graph", help="Also build knowledge graph"),
    communities: bool = typer.Option(False, "--communities", help="Detect communities after graph build (Phase 6)"),
    parent_child: bool = typer.Option(False, "--parent-child", help="Use parent-child two-level splitting (Phase 7)"),
    contextual: bool = typer.Option(False, "--contextual", help="Generate LLM context per chunk (Phase 3.1)"),
    layout_aware: bool = typer.Option(False, "--layout-aware", help="Use layout-aware PDF parsing (Phase 10)"),
    extract_images: bool = typer.Option(False, "--extract-images", help="Extract and describe images (Phase 10)"),
    template: str = typer.Option("auto", "--template", help="Parse template: auto/generic/research_paper/user_manual (Phase 10)"),
    raptor: bool = typer.Option(False, "--raptor", help="Build RAPTOR tree for hierarchical retrieval (Phase 13.1)"),
    summarize: bool = typer.Option(False, "--summarize", help="Generate document summary for pre-routing (Phase 13.4)"),
):
    """Index a PDF document into the vector store.

    Phase 10: Use --layout-aware for structure-aware parsing, --extract-images for Vision API.
    Phase 13: Use --raptor for RAPTOR tree, --summarize for document summary index.
    """
    components = _get_components()

    async def _run():
        # Phase 10: Layout-aware loading
        if layout_aware or components.settings.layout.layout_detection_enabled:
            from src.pdf_framework.loaders.providers.layout_parser import LayoutAwareLoader

            console.print("[yellow]Using layout-aware PDF parsing[/yellow]")

            loader = LayoutAwareLoader(
                strategy=components.settings.layout.layout_strategy,
                infer_table_structure=components.settings.layout.infer_table_structure,
                extract_images=extract_images or components.settings.layout.extract_images,
            )
            document = await loader.load(file_path)
        else:
            document = await components.loader.load(file_path)

        # Phase 10: Table extraction
        if layout_aware and components.settings.layout.extract_tables:
            from src.pdf_framework.processing.table_extractor import TableExtractor

            console.print("[yellow]Extracting tables...[/yellow]")

            extractor = TableExtractor()
            tables = extractor.extract_all(file_path)

            for table in tables:
                console.print(f"  Table p.{table.page_number}: "
                            f"{len(table.headers)} cols × {len(table.rows)} rows")

        # Phase 10: Image description
        if extract_images or components.settings.layout.extract_images:
            from src.pdf_framework.processing.image_extractor import ImageExtractor

            console.print("[yellow]Describing images with Claude Vision...[/yellow]")

            img_extractor = ImageExtractor(
                api_key=components.settings.anthropic_api_key,
                model=components.settings.layout.image_description_model,
            )

            if img_extractor.has_vision_support():
                descriptions = await img_extractor.extract_all(file_path)

                console.print(f"[green]Described {len(descriptions)} images[/green]")

                for desc in descriptions:
                    console.print(f"  p.{desc.page_number}: {desc.description[:60]}...")
            else:
                console.print("[dim]Vision API not available, skipping images[/dim]")

        # Phase 7: Parent-Child two-level splitting
        if parent_child or components.settings.parent_child.enabled:
            from src.pdf_framework.vector_store.parent_store import ParentDocumentStore

            parents, chunks = components.pipeline.process_parent_child(
                document,
                pc_settings=components.settings.parent_child,
            )

            # Store parents in ParentDocumentStore
            parent_store = components.parent_store
            if parent_store is None:
                parent_store = ParentDocumentStore(
                    db_path=components.settings.parent_child.parent_store_path,
                )
                await parent_store.initialize()

            await parent_store.add_parents(parents)
            console.print(
                f"[green]Parent-Child:[/green] {len(parents)} parents, "
                f"{len(chunks)} children"
            )
        elif layout_aware or components.settings.layout.layout_detection_enabled:
            # Phase 10: Structure-aware splitting for layout-parsed documents
            from src.pdf_framework.processing.splitters.structure_aware import StructureAwareSplitter

            splitter = StructureAwareSplitter(
                max_chunk_size=components.settings.layout.structure_aware_chunk_size,
                chunk_overlap=components.settings.layout.structure_aware_overlap,
            )
            chunks = splitter.split(document)
            console.print(f"[green]Structure-aware:[/green] {len(chunks)} chunks")
        else:
            chunks = components.pipeline.process(document)

        # Phase 3.1: Contextual Retrieval
        if contextual or components.settings.contextual_retrieval.enabled:
            from src.pdf_framework.processing.context_generator import ContextGenerator

            generator = ContextGenerator(
                settings=components.settings.agent,
                context_settings=components.settings.contextual_retrieval,
                api_key=components.settings.anthropic_api_key,
            )
            chunks = await generator.enrich_chunks(chunks, document)
            console.print(f"[green]Context:[/green] generated for {len(chunks)} chunks")

        result = await components.indexer.index_chunks(
            chunks,
            document_id=document.id,
            source_path=document.source_path,
        )
        console.print(f"[green]Indexed:[/green] {result.chunks_stored} chunks, "
                       f"{result.embeddings_computed} embeddings")

        if build_graph:
            from src.pdf_framework.graph_store.construction.builder import GraphBuilder
            from src.pdf_framework.processing.extractors.entity_extractor import LLMEntityExtractor

            extractor = LLMEntityExtractor(
                settings=components.settings.agent,
                api_key=components.settings.anthropic_api_key,
            )
            builder = GraphBuilder(
                extractor, components.graph_store,
                concurrency=components.settings.agent.graph_concurrency,
            )
            stats = await builder.build_from_chunks(chunks)
            console.print(f"[green]Graph:[/green] {stats['entities_added']} entities, "
                          f"{stats['relations_added']} relations")

            # Phase 6: Community detection and summarization
            if communities and components.settings.graph_rag.community_detection_enabled:
                from src.pdf_framework.graph_store.community import CommunityDetector
                from src.pdf_framework.graph_store.summarizer import CommunitySummarizer

                detector = CommunityDetector(settings=components.settings.graph_rag)
                graph = components.graph_store._graph  # NetworkX graph

                comm_map = await detector.detect(graph)
                await detector.apply_to_graph(graph, comm_map)

                comm_stats = detector.get_community_stats(graph, comm_map)
                console.print(
                    f"[green]Communities:[/green] {comm_stats['num_communities']} detected "
                    f"(avg size {comm_stats['avg_community_size']:.1f})"
                )

                # Generate summaries
                summarizer = CommunitySummarizer(
                    settings=components.settings.graph_rag,
                    api_key=components.settings.anthropic_api_key,
                    base_url=components.settings.agent.base_url,
                )
                summaries = await summarizer.summarize_all(graph, comm_map)

                # Store summaries as COMMUNITY nodes in graph
                for comm_id, summary in summaries.items():
                    graph.add_node(
                        f"community_{comm_id}",
                        node_type="COMMUNITY",
                        community_id=comm_id,
                        level=0,
                        summary=summary,
                    )

                components.graph_store._save_to_file()
                console.print(f"[green]Summaries:[/green] {len(summaries)} community summaries generated")

        # Phase 13.1: RAPTOR Tree Builder
        if raptor or components.settings.raptor.enabled:
            from src.pdf_framework.processing.raptor import get_raptor_builder

            console.print("[yellow]Building RAPTOR tree...[/yellow]")

            builder = get_raptor_builder(
                max_levels=components.settings.raptor.max_levels,
                summarization_model=components.settings.raptor.summarization_model,
                api_key=components.settings.anthropic_api_key,
                base_url=components.settings.agent.base_url,
            )

            # Get embeddings for chunks
            chunk_texts = [chunk.get("content", "") for chunk in chunks]
            embeddings = await components.embedding_engine.embed_texts_batch(chunk_texts)

            # Build tree
            tree = await builder.build(
                chunks=chunks,
                embeddings=embeddings,
                document_id=document.id,
            )

            # Index RAPTOR nodes into vector store
            for level_nodes in tree.levels:
                for node in level_nodes:
                    from src.pdf_framework.schemas.documents import DocumentChunk

                    chunk = DocumentChunk(
                        id=node.id,
                        content=node.content,
                        document_id=document.id,
                        metadata={
                            "raptor_node": True,
                            "raptor_level": node.level,
                            "document_id": document.id,
                            "node_type": "summary" if node.level > 0 else "leaf",
                            **node.metadata,
                        },
                    )

                    if node.embedding:
                        await components.vector_store.add_documents([chunk], [node.embedding])

            console.print(
                f"[green]RAPTOR:[/green] {tree.total_nodes} nodes, "
                f"{len(tree.levels)} levels, max level {tree.max_level}"
            )

        # Phase 13.4: Document Summary Index
        if summarize or components.settings.summary_index.enabled:
            from src.pdf_framework.processing.summary_index import get_summary_index

            console.print("[yellow]Generating document summary...[/yellow]")

            summary_idx = get_summary_index(
                collection_name=components.settings.summary_index.collection_name,
                persist_dir=components.settings.vector_store.persist_dir,
                summarization_model=components.settings.summary_index.summarization_model,
                api_key=components.settings.anthropic_api_key,
                base_url=components.settings.agent.base_url,
            )

            doc_summary = await summary_idx.add_document(
                document_id=document.id,
                chunks=chunks,
                title=document.metadata.get("title", document.id),
                metadata={"source_path": document.source_path},
            )

            console.print(
                f"[green]Summary:[/green] {len(doc_summary.summary)} chars, "
                f"{doc_summary.chunk_count} chunks indexed"
            )

    asyncio.run(_run())


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    strategy: str = typer.Option("vector", "--strategy", "-s", help="Search strategy (vector/graph/hybrid/mmr/two_stage/graphrag_local/graphrag_global/auto_merge/adaptive/raptor)"),
    k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
    no_rerank: bool = typer.Option(False, "--no-rerank", help="Disable reranking (Phase 1.1)"),
    doc_type: str = typer.Option(None, "--doc-type", help="Filter by document_type (Phase 1.3)"),
    language: str = typer.Option(None, "--language", help="Filter by language (Phase 1.3)"),
    version: str = typer.Option(None, "--version", help="Filter by version (Phase 1.3)"),
    diversity: float = typer.Option(None, "--diversity", help="MMR diversity lambda 0.0-1.0 (Phase 2.1)"),
    expand_query: bool = typer.Option(False, "--expand-query", help="Enable query expansion (Phase 2.3)"),
    force_route: str = typer.Option(None, "--force-route", help="Force adaptive to use specific strategy (Phase 8)"),
):
    """Search indexed documents.

    Phase 1: Reranking, metadata filtering.
    Phase 2: MMR (--strategy mmr --diversity 0.7), query expansion (--expand-query).
    Phase 3: Two-stage pipeline (--strategy two_stage).
    Phase 6: GraphRAG (--strategy graphrag_local / graphrag_global).
    Phase 7: Parent-Child (--strategy auto_merge).
    Phase 8: Adaptive RAG (--strategy adaptive), force route (--force-route vector).
    Phase 13: RAPTOR (--strategy raptor).
    """
    components = _get_components()

    async def _run():
        # Build metadata filter (Phase 1.3)
        filter_dict = {}
        if doc_type:
            filter_dict["document_type"] = doc_type
        if language:
            filter_dict["language"] = language
        if version:
            filter_dict["version"] = version

        # Build extra kwargs for strategy-specific params
        extra_kwargs = {}
        if diversity is not None:
            extra_kwargs["diversity"] = diversity
        if force_route is not None:
            extra_kwargs["force_route"] = force_route

        response = await components.search_manager.search(
            query=query,
            strategy=strategy,
            k=k,
            filter=filter_dict if filter_dict else None,
            rerank=not no_rerank,
            expand_query=expand_query,
            **extra_kwargs,
        )
        table = Table(title=f"Search results ({response.search_type}, {response.elapsed_ms:.0f}ms)")
        table.add_column("#", width=3)
        table.add_column("Score", width=8)
        table.add_column("Content", max_width=80)
        table.add_column("Source", width=20)

        for i, result in enumerate(response.results, 1):
            table.add_row(
                str(i),
                f"{result.score:.3f}",
                result.chunk.content[:200] + "...",
                result.source,
            )
        console.print(table)

    asyncio.run(_run())


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
    strategy: str = typer.Option("hybrid", "--strategy", "-s", help="Search strategy (hybrid/vector/mmr/two_stage/graphrag_local/graphrag_global/auto_merge/adaptive/raptor)"),
    stream: bool = typer.Option(False, "--stream", help="Enable streaming response (Phase 9)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show Self-RAG pipeline details"),
    no_self_rag: bool = typer.Option(False, "--no-self-rag", help="Disable Self-RAG (use legacy chain)"),
):
    """Ask a question using RAG agent (Phase 5: Self-RAG).

    Uses LangGraph agent with document grading, query rewriting,
    and hallucination checking. Use --no-self-rag for legacy chain mode.

    Phase 9: Use --stream for real-time token streaming.
    """
    import logging

    components = _get_components()

    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        for name in ["src.pdf_framework.agents.rag"]:
            logging.getLogger(name).setLevel(logging.DEBUG)

    async def _run():
        if stream:
            # Phase 9: Streaming mode
            from src.pdf_framework.agents.rag.agent import create_rag_agent
            from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

            agent = create_rag_agent(
                search_manager=components.search_manager,
                settings=components.settings.agent,
                self_rag_settings=components.settings.self_rag,
                api_key=components.settings.anthropic_api_key,
            )

            runner = StreamingRAGRunner(agent, show_status=False)

            # Stream and print tokens in real-time
            console.print(f"\n[bold]Answer:[/bold]\n")
            async for event in runner.stream(question, search_strategy=strategy):
                if event.type.value == "token":
                    console.print(event.data, end="", markup=False)
                elif event.type.value == "source":
                    console.print(f"\n\n[dim]Sources:[/dim]")
                    for src in event.data:
                        console.print(f"  - {src.get('id', 'unknown')}")
                elif event.type.value == "error":
                    console.print(f"\n[red]Error:[/red] {event.data}")
            console.print("\n")
            return

        if no_self_rag:
            # Legacy mode: use RetrievalQAChain directly
            from src.pdf_framework.chains.qa.retrieval_qa import RetrievalQAChain

            search_response = await components.search_manager.search(
                query=question, strategy=strategy, k=5,
            )
            chain = RetrievalQAChain(
                settings=components.settings.agent,
                api_key=components.settings.anthropic_api_key,
            )
            answer = await chain.answer(question, search_response)
            console.print(f"\n[bold]Answer:[/bold]\n{answer}\n")

            if search_response.results:
                console.print("[dim]Sources:[/dim]")
                for r in search_response.results:
                    src = r.chunk.metadata.get("source", "unknown")
                    console.print(f"  - {src} (score: {r.score:.3f})")
            return

        # Self-RAG mode: use LangGraph agent
        from src.pdf_framework.agents.rag.agent import create_rag_agent

        agent = create_rag_agent(
            search_manager=components.search_manager,
            settings=components.settings.agent,
            self_rag_settings=components.settings.self_rag,
            api_key=components.settings.anthropic_api_key,
        )

        result = await agent.ainvoke({
            "question": question,
            "search_strategy": strategy,
        })

        answer = result.get("answer", "No answer generated.")
        console.print(f"\n[bold]Answer:[/bold]\n{answer}\n")

        # Show Self-RAG metadata in verbose mode
        if verbose:
            ratio = result.get("relevance_ratio")
            retries = result.get("retry_count", 0)
            hallucinated = result.get("is_hallucinated", False)
            gen_attempts = result.get("generation_attempts", 0)

            console.print("[dim]Self-RAG pipeline:[/dim]")
            if ratio is not None:
                console.print(f"  Relevance ratio: {ratio:.2%}")
            if retries > 0:
                console.print(f"  Query rewrites: {retries}")
            console.print(f"  Hallucinated: {'yes' if hallucinated else 'no'}")
            if gen_attempts > 0:
                console.print(f"  Generation attempts: {gen_attempts}")

        sources = result.get("sources", [])
        if sources:
            console.print("[dim]Sources:[/dim]")
            for src in sources:
                console.print(f"  - {src}")

    asyncio.run(_run())


@app.command()
def chat(
    thread: str = typer.Option(None, "--thread", "-t", help="Thread ID to continue (default: new thread)"),
    strategy: str = typer.Option("adaptive", "--strategy", "-s", help="Search strategy"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show pipeline details"),
):
    """Interactive chat with conversation memory (Phase 9).

    Commands:
        /quit       - Exit chat
        /clear      - Clear current thread history
        /history    - Show conversation history
        /strategy   - Change search strategy
        /stream     - Toggle streaming mode
    """
    from src.pdf_framework.agents.memory.conversation import ConversationMemory
    from src.pdf_framework.agents.rag.agent import create_rag_agent
    from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

    components = _get_components()

    # Setup
    thread_id = thread or str(uuid.uuid4())
    memory = ConversationMemory(
        backend=components.settings.conversation.memory_backend,
        db_path=str(components.settings.conversation.db_path),
        max_history=components.settings.conversation.max_history,
    )

    # Get existing history or start new
    loop = asyncio.new_event_loop()
    history = loop.run_until_complete(
        memory.get_history(thread_id)
    )

    streaming_enabled = True

    console.print(f"\n[bold green]Chat started[/bold green] (thread: {thread_id[:8]}...)")
    console.print("[dim]Type /quit to exit, /help for commands[/dim]\n")

    if history:
        console.print(f"[dim]Continuing conversation ({len(history)} messages)[/dim]")

    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold]You:[/bold] ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.lower() in ("/quit", "/exit", "/q"):
                console.print(f"\n[dim]Chat saved (thread: {thread_id[:8]}...)[/dim]")
                break

            if user_input.lower() == "/clear":
                loop.run_until_complete(memory.clear_thread(thread_id))
                console.print("[yellow]Thread cleared[/yellow]")
                continue

            if user_input.lower() == "/history":
                hist = loop.run_until_complete(memory.get_history(thread_id))
                for i, msg in enumerate(hist, 1):
                    role = "[bold cyan]You[/bold cyan]" if msg.role == "user" else "[bold green]Assistant[/bold green]"
                    content = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    console.print(f"  [{i}] {role}: {content}")
                continue

            if user_input.lower().startswith("/strategy"):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    strategy = parts[1]
                    console.print(f"[yellow]Strategy changed to: {strategy}[/yellow]")
                else:
                    console.print(f"[yellow]Current strategy: {strategy}[/yellow]")
                continue

            if user_input.lower() == "/stream":
                streaming_enabled = not streaming_enabled
                status = "enabled" if streaming_enabled else "disabled"
                console.print(f"[yellow]Streaming {status}[/yellow]")
                continue

            if user_input.lower() == "/help":
                console.print("""
[bold]Available commands:[/bold]
  /quit, /exit, /q    - Exit chat
  /clear             - Clear current thread history
  /history           - Show conversation history
  /strategy <name>   - Change search strategy
  /stream            - Toggle streaming mode
                """)
                continue

            # Process user message
            async def _process():
                # Store user message
                await memory.add_message(thread_id, "user", user_input)

                # Get history
                chat_history = await memory.get_history(thread_id)
                # Exclude just-added message
                chat_history = chat_history[:-1] if len(chat_history) > 1 else []

                # Setup agent and runner
                agent = create_rag_agent(
                    search_manager=components.search_manager,
                    settings=components.settings.agent,
                    self_rag_settings=components.settings.self_rag,
                    api_key=components.settings.anthropic_api_key,
                )
                runner = StreamingRAGRunner(agent, show_status=verbose)

                console.print("\n[bold green]Assistant:[/bold green]")

                if streaming_enabled:
                    # Stream tokens
                    answer_parts = []
                    sources = []

                    async for event in runner.stream(
                        user_input,
                        thread_id=thread_id,
                        chat_history=chat_history,
                        search_strategy=strategy,
                    ):
                        if event.type.value == "token":
                            console.print(event.data, end="", markup=False)
                            answer_parts.append(event.data)
                        elif event.type.value == "source":
                            sources = event.data
                        elif event.type.value == "status" and verbose:
                            console.print(f"\n[dim][{event.data}][/dim]", end="")

                    # Store assistant response
                    full_answer = "".join(answer_parts)
                    if full_answer:
                        await memory.add_message(
                            thread_id,
                            "assistant",
                            full_answer,
                            metadata={"strategy": strategy},
                        )

                    console.print("\n")
                    if sources:
                        console.print(f"[dim]Sources: {len(sources)} documents[/dim]")
                else:
                    # Non-streaming
                    result = await collect_stream(
                        runner.stream(
                            user_input,
                            thread_id=thread_id,
                            chat_history=chat_history,
                            search_strategy=strategy,
                        )
                    )

                    console.print(result.get("answer", ""))
                    console.print()

                    # Store assistant response
                    if result.get("answer"):
                        await memory.add_message(
                            thread_id,
                            "assistant",
                            result["answer"],
                            metadata={"strategy": strategy},
                        )

                    if result.get("sources"):
                        console.print(f"[dim]Sources: {len(result['sources'])} documents[/dim]")

            from src.pdf_framework.agents.rag.streaming import collect_stream
            asyncio.run(_process())

        except KeyboardInterrupt:
            console.print("\n\n[dim]Use /quit to exit[/dim]")
        except EOFError:
            break


@app.command()
def stats():
    """Show index statistics."""
    components = _get_components()

    async def _run():
        vector_count = await components.vector_store.count()
        graph_stats = await components.graph_store.get_statistics()

        console.print(f"\n[bold]Vector Store:[/bold]")
        console.print(f"  Documents: {vector_count}")
        console.print(f"\n[bold]Graph Store:[/bold]")
        for key, value in graph_stats.items():
            console.print(f"  {key}: {value}")

    asyncio.run(_run())


@app.command()
def server(
    host: str = typer.Option("0.0.0.0", help="Server host"),
    port: int = typer.Option(8000, help="Server port"),
):
    """Start the REST API server."""
    import uvicorn

    console.print(f"[green]Starting server on {host}:{port}[/green]")
    uvicorn.run("src.api.app:app", host=host, port=port, reload=False)


@app.command()
def dashboard(
    port: int = typer.Option(8000, help="Server port"),
    host: str = typer.Option("127.0.0.1", help="Server host"),
    page: str = typer.Option("metrics/html", help="Dashboard page to open"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser"),
):
    """Open metrics dashboard, auto-starting server if needed.

    Checks if the API server is already running. If not, starts it
    in the background and opens the dashboard in your default browser.

    Examples:
        pdf-framework dashboard
        pdf-framework dashboard --port 9000
        pdf-framework dashboard --page docs
        pdf-framework dashboard --no-browser
    """
    import socket
    import subprocess
    import sys
    import time
    import webbrowser

    url = f"http://{host}:{port}/{page}"

    def _is_port_open(h: str, p: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((h, p)) == 0

    if _is_port_open(host, port):
        console.print(f"[green]Server already running on {host}:{port}[/green]")
    else:
        console.print(f"[yellow]Server not running. Starting on {host}:{port}...[/yellow]")
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "src.api.app:create_app",
             "--factory", "--host", host, "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        # Wait for server to become ready
        for i in range(30):
            time.sleep(0.5)
            if _is_port_open(host, port):
                console.print(f"[green]Server started successfully[/green]")
                break
        else:
            console.print(f"[red]Server failed to start within 15 seconds[/red]")
            raise typer.Exit(1)

    if not no_browser:
        console.print(f"[blue]Opening {url}[/blue]")
        webbrowser.open(url)
    else:
        console.print(f"[blue]Dashboard available at: {url}[/blue]")


@app.command()
def cache(
    action: str = typer.Argument(..., help="Action: stats, clear"),
    cache_type: str = typer.Option("all", "--type", "-t", help="Cache type: all/embedding/llm/document"),
):
    """Manage caches (Phase 11).

    Actions:
        stats  - Show cache statistics
        clear  - Clear cache entries

    Examples:
        pdf-framework cache stats
        pdf-framework cache clear --type embedding
    """
    from src.pdf_framework.agents.cache import get_llm_cache
    from src.pdf_framework.embeddings.cache import get_embedding_cache
    from src.pdf_framework.processing.cache import get_document_cache

    async def _run():
        llm_cache = get_llm_cache()
        emb_cache = get_embedding_cache()
        doc_cache = get_document_cache()

        if action == "stats":
            # Display statistics
            table = Table(title="Cache Statistics")
            table.add_column("Cache Type", width=20)
            table.add_column("Status", width=10)
            table.add_column("Hits", width=8)
            table.add_column("Misses", width=8)
            table.add_column("Total", width=8)
            table.add_column("Hit Rate", width=12)

            # Embedding cache
            emb_stats = emb_cache.get_stats()
            table.add_row(
                "Embedding",
                "[green]Active[/green]",
                str(emb_stats.hits),
                str(emb_stats.misses),
                str(emb_stats.total),
                f"{emb_stats.hit_rate:.1%}",
            )

            # LLM cache
            llm_stats = llm_cache.get_stats()
            table.add_row(
                "LLM Response",
                "[green]Active[/green]",
                str(llm_stats["hits"]),
                str(llm_stats["misses"]),
                str(llm_stats["total"]),
                f"{llm_stats['hit_rate']:.1%}",
            )

            # Document cache
            doc_stats = doc_cache.get_stats()
            table.add_row(
                "Document",
                "[blue]Passive[/blue]",
                str(doc_stats.get("hits", 0)),
                str(doc_stats.get("stale", 0)),
                str(doc_stats.get("hits", 0) + doc_stats.get("stale", 0)),
                "—",
            )

            console.print(table)

            # Combined stats
            total_hits = emb_stats.hits + llm_stats["hits"]
            total_requests = emb_stats.total + llm_stats["total"]
            combined_rate = total_hits / total_requests if total_requests > 0 else 0

            console.print(f"\n[bold]Combined hit rate:[/bold] {combined_rate:.1%}")

        elif action == "clear":
            # Clear specified cache(s)
            import asyncio

            count = 0

            if cache_type in ("all", "embedding"):
                cleared = await emb_cache.clear()
                count += cleared
                console.print(f"[green]Cleared[/green] {cleared} embedding cache entries")

            if cache_type in ("all", "llm"):
                cleared = await llm_cache.clear()
                count += cleared
                console.print(f"[green]Cleared[/green] {cleared} LLM cache entries")

            if cache_type in ("all", "document"):
                cleared = doc_cache.clear()
                count += cleared
                console.print(f"[green]Cleared[/green] {cleared} document cache entries")

            console.print(f"\n[bold]Total:[/bold] {count} entries cleared")
        else:
            console.print(f"[red]Unknown action:[/red] {action}")
            console.print("Valid actions: stats, clear")
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command()
def tenant(
    action: str = typer.Argument(..., help="Action: create, list, delete"),
    tenant_id: str = typer.Option("", "--id", "-t", help="Tenant ID (for create/delete)"),
):
    """Manage tenants (Phase 12.1).

    Actions:
        create  - Create a new tenant
        list    - List all tenants
        delete  - Delete a tenant and all data (GDPR)
    """
    from src.pdf_framework.multitenancy import get_tenant_store_manager, get_tenant_graph_manager

    async def _run():
        store_mgr = get_tenant_store_manager()
        graph_mgr = get_tenant_graph_manager()

        if action == "create":
            if not tenant_id:
                console.print("[red]--id required for create[/red]")
                raise typer.Exit(1)

            metadata = await store_mgr.create_tenant(tenant_id)

            console.print(f"[green]Tenant created:[/green] {tenant_id}")
            console.print(f"  Collection: {metadata.collection_name}")
            console.print(f"  Created at: {metadata.created_at}")

        elif action == "list":
            tenants = await store_mgr.list_tenants()

            if not tenants:
                console.print("[dim]No tenants found[/dim]")
                return

            table = Table(title="Tenants")
            table.add_column("Tenant ID", width=30)
            table.add_column("Collection", width=30)
            table.add_column("Documents", width=10)
            table.add_column("Created", width=25)

            for tenant_id in tenants:
                metadata = await store_mgr.get_tenant_metadata(tenant_id)
                if metadata:
                    table.add_row(
                        metadata.tenant_id,
                        metadata.collection_name,
                        str(metadata.document_count),
                        metadata.created_at[:19],
                    )

            console.print(table)

        elif action == "delete":
            if not tenant_id:
                console.print("[red]--id required for delete[/red]")
                raise typer.Exit(1)

            # Confirm deletion
            console.print(f"[yellow]Deleting tenant '{tenant_id}' and ALL data[/yellow]")
            console.print("[dim]This cannot be undone![/dim]")

            # Delete vector store data
            await store_mgr.delete_tenant(tenant_id)

            # Delete graph data
            await graph_mgr.delete_tenant(tenant_id)

            console.print(f"[green]Tenant deleted:[/green] {tenant_id}")

        else:
            console.print(f"[red]Unknown action:[/red] {action}")
            console.print("Valid actions: create, list, delete")
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command()
def auth(
    action: str = typer.Argument(..., help="Action: token"),
    tenant: str = typer.Option("default", "--tenant", "-t", help="Tenant ID"),
    role: str = typer.Option("viewer", "--role", "-r", help="User role (viewer/editor/admin)"),
):
    """Authentication utilities (Phase 12.3).

    Actions:
        token   - Generate a JWT token for a tenant

    Example:
        pdf-framework auth token --tenant myorg --role editor
    """
    from src.api.auth.jwt_handler import get_jwt_handler
    from src.pdf_framework.config import get_settings

    if action == "token":
        settings = get_settings()

        # Validate role
        if role not in ("viewer", "editor", "admin"):
            console.print(f"[red]Invalid role:[/red] {role}")
            console.print("Valid roles: viewer, editor, admin")
            raise typer.Exit(1)

        # Create token
        jwt_handler = get_jwt_handler(
            secret=settings.auth.jwt_secret,
            algorithm=settings.auth.jwt_algorithm,
            expire_hours=settings.auth.token_expire_hours,
        )

        token = jwt_handler.create_token(tenant, role)

        console.print(f"[green]Token generated:[/green]")
        console.print(f"  Token: {token}")
        console.print(f"  Tenant: {tenant}")
        console.print(f"  Role: {role}")
        console.print(f"  Expires: {settings.auth.token_expire_hours} hours")

        # Show curl example
        console.print("\n[dim]Example usage:[/dim]")
        console.print(f"  curl -H \"Authorization: Bearer {token}\" \\")
        console.print(f"    http://localhost:8000/search/")

    else:
        console.print(f"[red]Unknown action:[/red] {action}")
        console.print("Valid actions: token")
        raise typer.Exit(1)


@app.command(name="eval")
def evaluate(
    dataset: str = typer.Argument(..., help="Path to evaluation dataset JSON"),
    strategy: str = typer.Option("vector", "--strategy", "-s", help="Search strategy"),
    k: int = typer.Option(5, "--top-k", "-k", help="Number of results per query"),
    with_rag_triad: bool = typer.Option(False, "--with-rag-triad", help="Enable RAG Triad evaluation (requires LLM)"),
):
    """Run evaluation benchmark on a dataset (Phase 4)."""
    components = _get_components()

    async def _run():
        from src.pdf_framework.evaluation.dataset import EvalDataset
        from src.pdf_framework.evaluation.runner import EvalReport, EvalRunner

        ds = EvalDataset.from_json(dataset)
        console.print(f"[bold]Dataset:[/bold] {ds.name} ({len(ds.test_cases)} queries)")
        console.print(f"[bold]Strategy:[/bold] {strategy}, k={k}")

        rag_evaluator = None
        qa_chain = None
        if with_rag_triad:
            from src.pdf_framework.chains.qa.retrieval_qa import RetrievalQAChain
            from src.pdf_framework.evaluation.rag_evaluator import RAGEvaluator

            rag_evaluator = RAGEvaluator(
                settings=components.settings.agent,
                api_key=components.settings.anthropic_api_key,
            )
            qa_chain = RetrievalQAChain(
                settings=components.settings.agent,
                api_key=components.settings.anthropic_api_key,
            )
            console.print("[dim]RAG Triad evaluation enabled[/dim]")

        runner = EvalRunner(
            search_manager=components.search_manager,
            rag_evaluator=rag_evaluator,
            qa_chain=qa_chain,
        )

        report: EvalReport = await runner.run(ds, strategy=strategy, k=k)

        # Display results
        table = Table(title="Evaluation Results")
        table.add_column("Metric", width=25)
        table.add_column("Value", width=15)

        table.add_row("Queries", str(report.num_queries))
        table.add_row("Strategy", report.strategy)
        table.add_row("Precision@5", f"{report.precision_at_5:.4f}")
        table.add_row("Recall@5", f"{report.recall_at_5:.4f}")
        table.add_row("MRR", f"{report.mrr:.4f}")
        table.add_row("NDCG@10", f"{report.ndcg_at_10:.4f}")
        table.add_row("MAP", f"{report.map_score:.4f}")
        table.add_row("Avg Latency (ms)", f"{report.avg_latency_ms:.1f}")
        table.add_row("P95 Latency (ms)", f"{report.p95_latency_ms:.1f}")

        if report.context_relevance is not None:
            table.add_row("Context Relevance", f"{report.context_relevance:.4f}")
        if report.groundedness is not None:
            table.add_row("Groundedness", f"{report.groundedness:.4f}")
        if report.answer_relevance is not None:
            table.add_row("Answer Relevance", f"{report.answer_relevance:.4f}")

        console.print(table)

        # Per-query details
        if report.details:
            detail_table = Table(title="Per-Query Details")
            detail_table.add_column("#", width=3)
            detail_table.add_column("Query", max_width=40)
            detail_table.add_column("P@k", width=6)
            detail_table.add_column("MRR", width=6)
            detail_table.add_column("Latency", width=10)

            for i, d in enumerate(report.details, 1):
                detail_table.add_row(
                    str(i),
                    d["query"][:40],
                    f"{d['precision_at_k']:.2f}",
                    f"{d['mrr']:.2f}",
                    f"{d['latency_ms']:.0f}ms",
                )
            console.print(detail_table)

    asyncio.run(_run())


@app.command()
def ui(
    host: str = typer.Option(None, help="UI server host"),
    port: int = typer.Option(None, "--port", "-p", help="UI server port"),
    share: bool = typer.Option(False, "--share", help="Create public link"),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="Backend API URL"),
):
    """Launch Gradio Web UI (Phase 14.1).

    Provides a browser-based interface for chat, search, document management,
    graph visualization, and settings.

    Example:
        pdf-framework ui --port 7860
    """
    from src.ui import launch_ui

    launch_ui(host=host, port=port, share=share, api_url=api_url)


@app.command()
def suggest(
    query: str = typer.Option("", "--query", "-q", help="Context query for suggestions"),
    k: int = typer.Option(5, "--top-k", "-k", help="Number of suggestions"),
    method: str = typer.Option("entity", "--method", "-m", help="Suggestion method (entity/frequency/llm/related)"),
):
    """Get query suggestions for exploration (Phase 14.5).

    Examples:
        pdf-framework suggest
        pdf-framework suggest --query "1С" --top-k 10
        pdf-framework suggest --method llm
    """
    components = _get_components()

    async def _run():
        from src.pdf_framework.search.suggestions import QuerySuggester, SuggestionConfig

        config = SuggestionConfig(method=method, max_suggestions=k)
        suggester = QuerySuggester(
            config=config,
            api_key=components.settings.anthropic_api_key,
            base_url=components.settings.agent.base_url,
        )

        suggestions = await suggester.suggest(
            query=query,
            graph_store=components.graph_store,
            k=k,
        )

        console.print(f"\n[bold]Suggestions ({method}):[/bold]\n")
        for i, suggestion in enumerate(suggestions, 1):
            console.print(f"  {i}. {suggestion}")

    asyncio.run(_run())


@app.command()
def research(
    question: str = typer.Argument(..., help="Research question"),
    strategy: str = typer.Option("hybrid", "--strategy", "-s", help="Search strategy"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show sub-questions and quality scores"),
):
    """Deep research across multiple documents (Phase 19).

    Decomposes question into sub-questions, retrieves from multiple angles,
    synthesizes a cross-document answer with citations.

    Example:
        pdf-framework research "Что такое регистр накопления и как он работает?"
    """
    components = _get_components()

    async def _run():
        from src.pdf_framework.agents.deep.planner import ResearchPlanner
        from src.pdf_framework.agents.deep.synthesizer import CrossDocumentSynthesizer, SubResult
        from src.pdf_framework.agents.deep.quality import ResearchQualityChecker

        planner = ResearchPlanner(
            api_key=components.settings.anthropic_api_key,
            base_url=components.settings.agent.base_url,
        )

        # Step 1: Create research plan
        console.print("[yellow]Planning research...[/yellow]")
        plan = await planner.create_plan(question)

        if verbose:
            console.print(f"\n[bold]Sub-questions ({len(plan.sub_questions)}):[/bold]")
            for i, sq in enumerate(plan.sub_questions, 1):
                console.print(f"  {i}. {sq.question}")

        # Step 2: Retrieve for each sub-question
        console.print("[yellow]Retrieving documents...[/yellow]")
        sub_results = []
        for sq in plan.sub_questions:
            response = await components.search_manager.search(
                query=sq.question, strategy=strategy, k=5,
            )
            chunks_text = "\n\n".join(
                r.chunk.content for r in response.results
            )
            sub_results.append(SubResult(
                question=sq.question,
                answer=chunks_text,
                sources=[r.chunk.id for r in response.results],
                confidence=max((r.score for r in response.results), default=0.0),
            ))

        # Step 3: Synthesize
        console.print("[yellow]Synthesizing answer...[/yellow]")
        synthesizer = CrossDocumentSynthesizer(
            api_key=components.settings.anthropic_api_key,
            base_url=components.settings.agent.base_url,
        )
        answer, citations = await synthesizer.synthesize(question, sub_results)

        # Step 4: Quality check
        checker = ResearchQualityChecker(
            api_key=components.settings.anthropic_api_key,
            base_url=components.settings.agent.base_url,
        )
        quality = await checker.check(question, plan, answer, sub_results)

        # Display answer
        console.print(f"\n[bold]Answer:[/bold]\n{answer}\n")

        if citations:
            console.print("[dim]Citations:[/dim]")
            for c in citations:
                console.print(f"  - {c}")

        if verbose:
            console.print(f"\n[bold]Quality:[/bold]")
            console.print(f"  Coverage:     {quality.coverage_score:.2f}")
            console.print(f"  Groundedness: {quality.groundedness_score:.2f}")
            if quality.gaps:
                console.print(f"  Gaps: {', '.join(quality.gaps)}")

    asyncio.run(_run())


@app.command()
def autorag(
    dataset: str = typer.Argument("default", help="Benchmark dataset name or path to JSON"),
    max_experiments: int = typer.Option(20, "--max", help="Maximum number of experiments"),
    smart: bool = typer.Option(True, "--smart/--full", help="Use SmartGrid (prune redundant combos)"),
):
    """Run AutoRAG grid search optimization (Phase 20).

    Tests combinations of strategies, k values, reranking, and query expansion
    to find the optimal RAG configuration for your dataset.

    Example:
        pdf-framework autorag data/benchmark.json --max 50
    """
    components = _get_components()

    async def _run():
        from src.pdf_framework.evaluation.autorag import ParameterGrid, SmartGrid
        from src.pdf_framework.evaluation.autorag_runner import AutoRAGRunner
        from src.pdf_framework.evaluation.autorag_analyzer import AutoRAGAnalyzer

        # Build grid
        grid_cls = SmartGrid if smart else ParameterGrid
        grid = grid_cls(
            strategy=["vector", "hybrid", "two_stage"],
            k=[3, 5, 10],
            rerank=[True, False],
        )

        total = grid.configs_count()
        actual = min(total, max_experiments)
        console.print(f"[bold]AutoRAG Optimization[/bold]")
        console.print(f"  Grid: {total} configs, running {actual}")
        console.print(f"  Dataset: {dataset}")

        # Load benchmark
        from src.pdf_framework.evaluation.benchmark import BenchmarkLoader
        benchmark = BenchmarkLoader.load(dataset)

        # Run
        runner = AutoRAGRunner(components=components, benchmark=benchmark)
        results = await runner.run_grid(grid)

        # Analyze
        analyzer = AutoRAGAnalyzer(results=results)
        best = analyzer.best_config()

        console.print(f"\n[bold]Results ({len(results)} experiments):[/bold]")
        console.print(analyzer.comparison_table())

        if best:
            console.print(f"\n[bold green]Best config:[/bold green]")
            for key, value in best.items():
                console.print(f"  {key}: {value}")

    asyncio.run(_run())


@app.command(name="feedback")
def feedback_cmd(
    action: str = typer.Argument("stats", help="Action: stats, tune, clear, export"),
    days: int = typer.Option(30, "--days", help="Days threshold for clear action"),
    output: str = typer.Option("", "--output", "-o", help="Output path for export"),
    min_samples: int = typer.Option(20, "--min-samples", help="Min samples for tuning"),
    learning_rate: float = typer.Option(0.1, "--lr", help="Learning rate for tuning"),
):
    """Manage feedback and self-learning (Phase 22).

    Actions:
        stats   - Show feedback statistics
        tune    - Tune strategy weights based on feedback
        clear   - Clear old feedback entries
        export  - Export feedback to JSON

    Examples:
        pdf-framework feedback stats
        pdf-framework feedback tune --min-samples 10 --lr 0.05
        pdf-framework feedback clear --days 90
        pdf-framework feedback export -o feedback_backup.json
    """
    components = _get_components()

    async def _run():
        from src.pdf_framework.feedback.collector import FeedbackCollector

        collector = components.feedback_collector
        if collector is None:
            collector = FeedbackCollector(settings=components.settings)

        if action == "stats":
            stats = collector.get_stats()

            table = Table(title="Feedback Statistics")
            table.add_column("Metric", width=25)
            table.add_column("Value", width=15)

            table.add_row("Total Feedback", str(stats.total_feedback))
            table.add_row("Positive", str(stats.positive_count))
            table.add_row("Negative", str(stats.negative_count))
            table.add_row("Neutral", str(stats.neutral_count))
            table.add_row("Positive Rate", f"{stats.positive_rate:.1%}")

            console.print(table)

            if stats.strategy_performance:
                perf_table = Table(title="Strategy Performance")
                perf_table.add_column("Strategy", width=20)
                perf_table.add_column("Avg Score", width=12)
                perf_table.add_column("Count", width=8)

                for strat, perf in stats.strategy_performance.items():
                    perf_table.add_row(
                        strat,
                        f"{perf.get('avg_score', 0):.3f}",
                        str(perf.get("count", 0)),
                    )
                console.print(perf_table)

        elif action == "tune":
            from src.pdf_framework.feedback.tuner import StrategyTuner

            tuner = StrategyTuner(settings=components.settings)
            new_weights = tuner.tune_weights(
                min_samples=min_samples,
                learning_rate=learning_rate,
            )

            console.print("[bold green]Strategy weights updated:[/bold green]")
            console.print(f"  vector:          {new_weights.vector:.3f}")
            console.print(f"  hybrid:          {new_weights.hybrid:.3f}")
            console.print(f"  graphrag_local:  {new_weights.graphrag_local:.3f}")
            console.print(f"  graphrag_global: {new_weights.graphrag_global:.3f}")
            console.print(f"  two_stage:       {new_weights.two_stage:.3f}")

        elif action == "clear":
            collector.clear_old_feedback(days=days)
            console.print(f"[green]Cleared feedback older than {days} days[/green]")

        elif action == "export":
            if not output:
                output = "feedback_export.json"
            collector.export_feedback(output)
            console.print(f"[green]Exported feedback to {output}[/green]")

        else:
            console.print(f"[red]Unknown action:[/red] {action}")
            console.print("Valid actions: stats, tune, clear, export")
            raise typer.Exit(1)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
