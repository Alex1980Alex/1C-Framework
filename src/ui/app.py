"""Gradio Web UI main application (Phase 14.1 → UX v2).

Provides a browser-based interface for:
- Chat with PDF documents
- Search with various strategies
- Document management
- Knowledge graph visualization
- System settings and stats

Author: Claude Code
Version: 2.0.0 - UX Overhaul: Theme, Dark Mode, Confirmations, Error Handling
"""

import logging

import gradio as gr
from src.pdf_framework.config import get_settings
from src.ui.pages.chat import create_chat_page
from src.ui.pages.search import create_search_page
from src.ui.pages.documents import create_documents_page
from src.ui.pages.graph import create_graph_page
from src.ui.pages.settings import create_settings_page
from src.ui.theme import CUSTOM_CSS, CUSTOM_JS, PDFFrameworkTheme

logger = logging.getLogger(__name__)

APP_VERSION = "2.0.0"


def create_app(api_url: str = "http://localhost:8000"):
    """
    Create Gradio web application.

    Args:
        api_url: Backend REST API URL

    Returns:
        Gradio Blocks app
    """
    with gr.Blocks(
        title="PDF Vector & Graph Framework",
    ) as app:
        # ── Branded header with dark mode toggle ──
        gr.HTML(
            f"""
            <div class="header-bar">
                <div style="display:flex;align-items:center;gap:12px;">
                    <h1>PDF Vector & Graph Framework</h1>
                    <span class="version-badge">v{APP_VERSION}</span>
                </div>
                <button id="dark-toggle" onclick="toggleDarkMode()">Dark Mode</button>
            </div>
            """
        )

        with gr.Tabs():
            with gr.Tab("Чат"):
                create_chat_page(api_url)

            with gr.Tab("Поиск"):
                create_search_page(api_url)

            with gr.Tab("Документы"):
                create_documents_page(api_url, app=app)

            with gr.Tab("Граф знаний"):
                create_graph_page(api_url, app=app)

            with gr.Tab("Настройки"):
                create_settings_page(api_url, app=app)

        gr.HTML(
            f'<div class="footer-bar">PDF Vector & Graph Framework v{APP_VERSION}</div>'
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

    theme = PDFFrameworkTheme()

    app.launch(
        server_name=host or settings.ui.host,
        server_port=port or settings.ui.port,
        share=share if share is not None else settings.ui.share,
        show_error=True,
        theme=theme,
        css=CUSTOM_CSS,
        js=CUSTOM_JS,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    launch_ui()
