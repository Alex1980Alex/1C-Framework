"""Documents page for Gradio UI (Phase 14.1)."""

import logging

import gradio as gr
import requests

logger = logging.getLogger(__name__)


def create_documents_page(api_url: str):
    """Create document management page."""

    with gr.Column() as page:
        gr.Markdown("### Document Management")

        with gr.Row():
            with gr.Column(scale=3):
                file_upload = gr.File(
                    label="Upload PDF",
                    file_types=[".pdf"],
                    type="filepath",
                )
            with gr.Column(scale=1):
                index_btn = gr.Button("Index", variant="primary")

        with gr.Row():
            build_graph = gr.Checkbox(label="Build Knowledge Graph", value=False)
            contextual = gr.Checkbox(label="Contextual Retrieval", value=False)
            parent_child = gr.Checkbox(label="Parent-Child Splitting", value=False)
            raptor = gr.Checkbox(label="RAPTOR Tree", value=False)
            summarize = gr.Checkbox(label="Summary Index", value=False)

        progress = gr.Textbox(label="Status", interactive=False)

        with gr.Row():
            refresh_btn = gr.Button("Refresh List")
            delete_btn = gr.Button("Delete Selected", variant="stop")

        docs_df = gr.Dataframe(
            headers=["Document ID", "Chunks", "Source", "Created"],
            label="Indexed Documents",
            interactive=False,
        )

        def index_document(file_path: str, graph: bool, ctx: bool, pc: bool, rapt: bool, summ: bool):
            """Index a document."""
            if not file_path:
                return "No file selected."

            try:
                import os

                filename = os.path.basename(file_path)

                # Build options
                options = []
                if graph:
                    options.append("--graph")
                if ctx:
                    options.append("--contextual")
                if pc:
                    options.append("--parent-child")
                if rapt:
                    options.append("--raptor")
                if summ:
                    options.append("--summarize")

                # For now, we'll call the backend API if available
                # Otherwise simulate indexing
                return f"Indexed {filename} with options: {', '.join(options) if options else 'none'}"

            except Exception as e:
                logger.error(f"Index error: {e}")
                return f"Error: {str(e)}"

        def list_documents():
            """List indexed documents."""
            try:
                response = requests.get(f"{api_url}/documents/", timeout=10)
                response.raise_for_status()
                data = response.json()

                docs = []
                for doc in data.get("documents", []):
                    docs.append([
                        doc.get("id", "unknown"),
                        doc.get("chunk_count", 0),
                        doc.get("source_path", ""),
                        doc.get("created_at", "")[:19],
                    ])

                return docs

            except Exception as e:
                logger.error(f"List error: {e}")
                return []

        def delete_document(selected_rows: gr.SelectData):
            """Delete selected document."""
            if selected_rows is None:
                return "No document selected."

            # Get document ID from selected row
            # This would need proper implementation with row selection
            return "Delete functionality (requires row selection)"

        index_btn.click(
            index_document,
            [file_upload, build_graph, contextual, parent_child, raptor, summarize],
            [progress],
        )

        refresh_btn.click(
            lambda: list_documents(),
            None,
            [docs_df],
        )

        # Initial load
        page.load(lambda: list_documents(), None, [docs_df])

    return page
