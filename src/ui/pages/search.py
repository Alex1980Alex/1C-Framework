"""Search page for Gradio UI (Phase 14.1)."""

import logging

import gradio as gr
import requests

logger = logging.getLogger(__name__)


def create_search_page(api_url: str):
    """Create search interface page."""

    with gr.Column() as page:
        gr.Markdown("### Search Documents")

        with gr.Row():
            query = gr.Textbox(
                placeholder="Enter search query...",
                label="Query",
                scale=4,
            )
            search_btn = gr.Button("Search", variant="primary", scale=1)

        with gr.Row():
            strategy = gr.Dropdown(
                choices=["vector", "hybrid", "mmr", "adaptive", "graphrag_local", "graphrag_global", "raptor"],
                value="hybrid",
                label="Strategy",
            )
            top_k = gr.Slider(1, 20, value=5, step=1, label="Top K")

        with gr.Accordion("Advanced Filters", open=False):
            with gr.Row():
                doc_type = gr.Textbox(label="Document Type", placeholder="e.g., manual")
                language = gr.Textbox(label="Language", placeholder="e.g., ru")
                version = gr.Textbox(label="Version", placeholder="e.g., 1.0")

        results_df = gr.Dataframe(
            headers=["Score", "Content Preview", "Source"],
            label="Search Results",
            interactive=False,
        )

        search_info = gr.Markdown("")

        def search_fn(query: str, strategy: str, k: int, doc_type: str, language: str, version: str):
            """Perform search."""
            if not query:
                return None, "Please enter a search query."

            try:
                # Build filter
                filters = {}
                if doc_type:
                    filters["document_type"] = doc_type
                if language:
                    filters["language"] = language
                if version:
                    filters["version"] = version

                # Make request
                params = {"strategy": strategy, "k": k}
                if filters:
                    params["filter"] = filters

                response = requests.post(
                    f"{api_url}/search/",
                    json={"query": query, **params},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                # Format results
                results = []
                for r in data.get("results", []):
                    content = r.get("content", "")[:200] + "..." if len(r.get("content", "")) > 200 else r.get("content", "")
                    results.append([
                        f"{r.get('score', 0):.3f}",
                        content,
                        r.get("source", "unknown"),
                    ])

                info = f"**Found {data.get('total_results', 0)} results** in {data.get('elapsed_ms', 0):.0f}ms using {data.get('search_type', strategy)}"

                return results, info

            except Exception as e:
                logger.error(f"Search error: {e}")
                return None, f"**Error:** {str(e)}"

        search_btn.click(
            search_fn,
            [query, strategy, top_k, doc_type, language, version],
            [results_df, search_info],
        )
        query.submit(
            search_fn,
            [query, strategy, top_k, doc_type, language, version],
            [results_df, search_info],
        )

    return page
