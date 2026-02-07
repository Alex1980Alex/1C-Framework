"""Gradio Web UI main application (Phase 14.1).

Provides a browser-based interface for:
- Chat with PDF documents
- Search with various strategies
- Document management
- Knowledge graph visualization
- System settings and stats

Author: Claude Code
Version: 1.5.0 - Phase 14.1: Gradio Web UI
"""

import logging
import os

import gradio as gr
from src.pdf_framework.config import get_settings
from src.ui.pages.chat import create_chat_page
from src.ui.pages.search import create_search_page
from src.ui.pages.documents import create_documents_page
from src.ui.pages.graph import create_graph_page
from src.ui.pages.settings import create_settings_page

logger = logging.getLogger(__name__)


def create_app(api_url: str = "http://localhost:8000"):
    """
    Create Gradio web application.

    Args:
        api_url: Backend REST API URL

    Returns:
        Gradio Blocks app
    """
    settings = get_settings()

    with gr.Blocks(
        title="PDF Vector & Graph Framework",
        theme=settings.ui.theme,
        css="""
        .gradio-container {
            max-width: 1400px !important;
        }
        .chat-container {
            height: 600px;
        }
        """,
    ) as app:
        gr.Markdown(
            """
            # PDF Vector & Graph Framework

            Intelligent PDF processing with Vector Search and Knowledge Graphs.
            """
        )

        with gr.Tabs():
            with gr.Tab("💬 Chat"):
                create_chat_page(api_url)

            with gr.Tab("🔍 Search"):
                create_search_page(api_url)

            with gr.Tab("📄 Documents"):
                create_documents_page(api_url)

            with gr.Tab("🕸️ Graph"):
                create_graph_page(api_url)

            with gr.Tab("⚙️ Settings"):
                create_settings_page(api_url)

        gr.Markdown(
            """
            ---
            **PDF Vector & Graph Framework** v1.5.0 | Phase 14: UI & Developer Experience
            """
        )

    return app


def launch_ui(
    host: str | None = None,
    port: int | None = None,
    share: bool | None = None,
    api_url: str = "http://localhost:8000",
):
    """
    Launch Gradio UI server.

    Args:
        host: Server host (default from settings)
        port: Server port (default from settings)
        share: Create public link (default from settings)
        api_url: Backend API URL
    """
    settings = get_settings()

    app = create_app(api_url=api_url)

    app.launch(
        server_name=host or settings.ui.host,
        server_port=port or settings.ui.port,
        share=share if share is not None else settings.ui.share,
        show_error=True,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    launch_ui()
