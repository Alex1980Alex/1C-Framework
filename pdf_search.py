"""
Comprehensive PDF Vector Search CLI with Rich Formatting
Combines best practices from: LangChain, MCP Vector Search, refer, Rich library

Usage:
    python pdf_search.py query "your search query" [--strategy vector|graph|hybrid] [--top-k 5]
    python pdf_search.py stats
    python pdf_search.py index "path/to/file.pdf" [--with-graph]
    python pdf_search.py list

Examples:
    python pdf_search.py query "что такое 1С" --top-k 3
    python pdf_search.py stats
"""
import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Literal

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
from rich.text import Text

from src.api.dependencies.components import Components


# Configure console for Windows compatibility
console = Console(legacy_windows=False, force_terminal=False)


class SearchResultFormatter:
    """Formats search results with Rich library patterns"""

    @staticmethod
    def format_score_color(score: float) -> str:
        """Color code based on relevance score"""
        if score >= 0.7:
            return "green"
        elif score >= 0.5:
            return "yellow"
        elif score >= 0.3:
            return "orange1"
        else:
            return "red"

    @staticmethod
    def format_results_table(results, query: str, elapsed_ms: float, strategy: str):
        """Create Rich table for search results"""

        # Header panel
        header = Panel(
            f"[bold cyan]Search Query:[/bold cyan] {query}\n"
            f"[dim]Strategy: {strategy} | Results: {len(results)} | Time: {elapsed_ms:.0f}ms[/dim]",
            border_style="cyan",
            box=box.ROUNDED
        )
        console.print(header)
        console.print()

        if not results:
            console.print("[yellow]No results found[/yellow]")
            return

        # Results table
        table = Table(
            title="Search Results",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            border_style="blue"
        )

        table.add_column("#", justify="center", style="cyan", width=3)
        table.add_column("Score", justify="center", width=8)
        table.add_column("Source", style="dim", width=20)
        table.add_column("Preview", width=60)

        for i, result in enumerate(results, 1):
            score = result.score
            color = SearchResultFormatter.format_score_color(score)

            # Format source
            source = f"Doc: {result.chunk.document_id[:8]}...\nChunk: {result.chunk.chunk_index}"
            if result.chunk.page_number:
                source += f"\nPage: {result.chunk.page_number}"

            # Preview (first 150 chars)
            preview = result.chunk.content[:150].replace('\n', ' ').strip()
            if len(result.chunk.content) > 150:
                preview += "..."

            table.add_row(
                str(i),
                f"[{color}]{score:.3f}[/{color}]",
                source,
                preview
            )

        console.print(table)

    @staticmethod
    def format_detailed_result(rank: int, result, total: int):
        """Format single result with full content in panel"""
        score = result.score
        color = SearchResultFormatter.format_score_color(score)

        # Header
        header = (
            f"[bold]Result {rank}/{total}[/bold] | "
            f"Score: [{color}]{score:.3f}[/{color}] | "
            f"Document: [dim]{result.chunk.document_id}[/dim] | "
            f"Chunk: [dim]{result.chunk.chunk_index}[/dim]"
        )

        if result.chunk.page_number:
            header += f" | Page: [dim]{result.chunk.page_number}[/dim]"

        # Content
        content = result.chunk.content.strip()

        panel = Panel(
            content,
            title=header,
            border_style=color,
            box=box.ROUNDED,
            padding=(1, 2)
        )

        console.print(panel)
        console.print()


class PDFSearchCLI:
    """Main CLI interface for PDF search operations"""

    def __init__(self):
        self.components: Optional[Components] = None

    async def initialize(self):
        """Initialize components with progress indicator"""
        if self.components is None:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Initializing PDF Framework...", total=None)
                self.components = Components()
                await self.components.initialize()
                progress.update(task, completed=True)

    async def search(
        self,
        query: str,
        strategy: Literal["vector", "graph", "hybrid"] = "vector",
        top_k: int = 5,
        format: Literal["table", "detailed", "json"] = "table"
    ):
        """Execute search and display results"""
        await self.initialize()

        # Execute search with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task(f"[cyan]Searching with {strategy} strategy...", total=None)

            response = await self.components.search_manager.search(
                query=query,
                strategy=strategy,
                k=top_k
            )

            progress.update(task, completed=True)

        console.print()

        # Format output based on format type
        if format == "json":
            self._output_json(query, strategy, response)
        elif format == "detailed":
            SearchResultFormatter.format_results_table(
                response.results, query, response.elapsed_ms, strategy
            )
            console.print()
            for i, result in enumerate(response.results, 1):
                SearchResultFormatter.format_detailed_result(i, result, len(response.results))
        else:  # table
            SearchResultFormatter.format_results_table(
                response.results, query, response.elapsed_ms, strategy
            )

    def _output_json(self, query: str, strategy: str, response):
        """Output results as JSON"""
        data = {
            "query": query,
            "strategy": strategy,
            "total_found": response.total_found,
            "elapsed_ms": response.elapsed_ms,
            "timestamp": datetime.now().isoformat(),
            "results": [
                {
                    "rank": i + 1,
                    "score": r.score,
                    "document_id": r.chunk.document_id,
                    "chunk_index": r.chunk.chunk_index,
                    "page": r.chunk.page_number,
                    "content": r.chunk.content,
                    "metadata": r.chunk.metadata
                }
                for i, r in enumerate(response.results)
            ]
        }

        output_file = Path("data/search_output.json")
        output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"[green]✓[/green] Results saved to: [cyan]{output_file}[/cyan]")

    async def get_stats(self):
        """Display index statistics"""
        await self.initialize()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Gathering statistics...", total=None)

            vector_count = await self.components.vector_store.count()
            graph_stats = await self.components.graph_store.get_statistics()

            progress.update(task, completed=True)

        console.print()

        # Statistics table
        table = Table(
            title="📊 Index Statistics",
            box=box.DOUBLE,
            show_header=True,
            header_style="bold magenta"
        )

        table.add_column("Component", style="cyan", width=20)
        table.add_column("Metric", style="yellow", width=20)
        table.add_column("Value", style="green", justify="right", width=15)

        # Vector store stats
        table.add_row("Vector Store", "Total Chunks", str(vector_count))
        table.add_row("", "", "")

        # Graph store stats
        table.add_row("Graph Store", "Nodes (Entities)", str(graph_stats['node_count']))
        table.add_row("", "Edges (Relations)", str(graph_stats['edge_count']))
        table.add_row("", "Connected Components", str(graph_stats['connected_components']))
        table.add_row("", "Density", f"{graph_stats['density']:.4f}")

        console.print(table)
        console.print()

        # Status indicators
        if vector_count > 0:
            console.print("[green]✓[/green] Vector search is ready")
        else:
            console.print("[yellow]⚠[/yellow] No documents indexed yet")

        if graph_stats['node_count'] > 0:
            console.print("[green]✓[/green] Graph search is ready")
        else:
            console.print("[yellow]⚠[/yellow] Graph is empty (requires --with-graph during indexing)")

    async def index_document(self, file_path: str, with_graph: bool = False):
        """Index a PDF document"""
        await self.initialize()

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            console.print(f"[red]✗[/red] File not found: {file_path}")
            return

        console.print(Panel(
            f"[bold]Indexing Document[/bold]\n\n"
            f"File: [cyan]{file_path_obj.name}[/cyan]\n"
            f"Size: [dim]{file_path_obj.stat().st_size / 1024:.1f} KB[/dim]\n"
            f"Graph: [{'green' if with_graph else 'yellow'}]{'Yes' if with_graph else 'No'}[/]",
            border_style="cyan"
        ))
        console.print()

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                # Load document
                task1 = progress.add_task("[cyan]Loading PDF...", total=None)
                document = await self.components.loader.load(str(file_path_obj))
                progress.update(task1, completed=True)

                # Process chunks
                task2 = progress.add_task("[cyan]Processing chunks...", total=None)
                chunks = self.components.pipeline.process(document)
                progress.update(task2, completed=True)

                # Index
                task3 = progress.add_task("[cyan]Creating embeddings and indexing...", total=None)
                result = await self.components.indexer.index_chunks(
                    chunks,
                    document_id=document.id,
                    source_path=document.source_path
                )
                progress.update(task3, completed=True)

                # Build graph if requested
                if with_graph:
                    task4 = progress.add_task("[cyan]Building knowledge graph...", total=None)
                    # This would call graph builder if available
                    progress.update(task4, description="[yellow]Graph building requires Anthropic API key[/yellow]")

            console.print()
            console.print(Panel(
                f"[green]✓[/green] Successfully indexed!\n\n"
                f"Document ID: [cyan]{result.document_id}[/cyan]\n"
                f"Chunks stored: [green]{result.chunks_stored}[/green]\n"
                f"Embeddings: [green]{result.embeddings_computed}[/green]",
                border_style="green",
                title="Success"
            ))

        except Exception as e:
            console.print(f"[red]✗[/red] Error: {str(e)}")

    async def list_documents(self):
        """List all indexed documents"""
        await self.initialize()

        vector_count = await self.components.vector_store.count()

        console.print(Panel(
            f"[bold]Indexed Documents[/bold]\n\n"
            f"Total chunks: [cyan]{vector_count}[/cyan]",
            border_style="cyan"
        ))


async def main():
    """Main CLI entry point"""
    cli = PDFSearchCLI()

    if len(sys.argv) < 2:
        console.print(Panel(
            Markdown("""
# PDF Vector Search CLI

## Commands:

- **query** - Search indexed documents
  ```bash
  python pdf_search.py query "search text" [--strategy vector|graph|hybrid] [--top-k 5] [--format table|detailed|json]
  ```

- **stats** - Show index statistics
  ```bash
  python pdf_search.py stats
  ```

- **index** - Index a new PDF
  ```bash
  python pdf_search.py index "path/to/file.pdf" [--with-graph]
  ```

- **list** - List indexed documents
  ```bash
  python pdf_search.py list
  ```

## Examples:

```bash
python pdf_search.py query "что такое 1С" --top-k 3
python pdf_search.py query "конфигурация" --strategy hybrid --format detailed
python pdf_search.py stats
```
            """),
            title="Usage",
            border_style="cyan"
        ))
        sys.exit(0)

    command = sys.argv[1]

    try:
        if command == "query":
            if len(sys.argv) < 3:
                console.print("[red]Error:[/red] Query text required")
                sys.exit(1)

            query = sys.argv[2]

            # Parse optional arguments
            strategy = "vector"
            top_k = 5
            format_type = "table"

            for i in range(3, len(sys.argv)):
                if sys.argv[i] == "--strategy" and i + 1 < len(sys.argv):
                    strategy = sys.argv[i + 1]
                elif sys.argv[i] == "--top-k" and i + 1 < len(sys.argv):
                    top_k = int(sys.argv[i + 1])
                elif sys.argv[i] == "--format" and i + 1 < len(sys.argv):
                    format_type = sys.argv[i + 1]

            await cli.search(query, strategy, top_k, format_type)

        elif command == "stats":
            await cli.get_stats()

        elif command == "index":
            if len(sys.argv) < 3:
                console.print("[red]Error:[/red] File path required")
                sys.exit(1)

            file_path = sys.argv[2]
            with_graph = "--with-graph" in sys.argv

            await cli.index_document(file_path, with_graph)

        elif command == "list":
            await cli.list_documents()

        else:
            console.print(f"[red]Error:[/red] Unknown command '{command}'")
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
