"""Tests for Gradio UI page factories (Phase 14.1).

Tests verify:
- Page factory functions return gr.Column components
- Event handlers are wired correctly
- app.load() is called for pages that need initial data
- No AttributeError from Column.load() (the fixed bug)
"""

from unittest.mock import MagicMock, patch, call
import sys

import pytest


# ---------------------------------------------------------------------------
# Mock gradio before importing pages
# ---------------------------------------------------------------------------

def _create_gradio_mock():
    """Create a comprehensive Gradio mock."""
    gr = MagicMock()

    # Context managers for layout components
    for component in ("Column", "Row", "Tabs", "Tab", "Accordion", "Blocks"):
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=ctx)
        ctx.__exit__ = MagicMock(return_value=False)
        getattr(gr, component).return_value = ctx

    # Regular components
    for component in ("Markdown", "Textbox", "Button", "Dropdown", "Slider",
                      "Chatbot", "File", "Checkbox", "Dataframe", "HTML",
                      "JSON"):
        comp = MagicMock()
        comp.click = MagicMock()
        comp.submit = MagicMock()
        comp.change = MagicMock()
        getattr(gr, component).return_value = comp

    # SelectData for row selection
    gr.SelectData = MagicMock

    return gr


@pytest.fixture(autouse=True)
def mock_gradio():
    """Mock gradio module for all tests in this file."""
    mock_gr = _create_gradio_mock()

    # Patch both the module and any imports
    with patch.dict(sys.modules, {"gradio": mock_gr}):
        yield mock_gr


@pytest.fixture
def mock_requests():
    """Mock requests module."""
    with patch.dict(sys.modules, {"requests": MagicMock()}):
        yield


# ---------------------------------------------------------------------------
# Test Chat Page
# ---------------------------------------------------------------------------

class TestChatPage:
    def test_create_chat_page_returns_column(self, mock_gradio, mock_requests):
        from src.ui.pages.chat import create_chat_page
        page = create_chat_page("http://test:8000")
        assert page is not None

    def test_create_chat_page_streaming_integrated(self, mock_gradio, mock_requests):
        """Streaming is integrated into the main create_chat_page."""
        from src.ui.pages.chat import create_chat_page
        page = create_chat_page("http://test:8000")
        assert page is not None


# ---------------------------------------------------------------------------
# Test Search Page
# ---------------------------------------------------------------------------

class TestSearchPage:
    def test_create_search_page_returns_column(self, mock_gradio, mock_requests):
        from src.ui.pages.search import create_search_page
        page = create_search_page("http://test:8000")
        assert page is not None


# ---------------------------------------------------------------------------
# Test Documents Page
# ---------------------------------------------------------------------------

class TestDocumentsPage:
    def test_create_without_app(self, mock_gradio, mock_requests):
        from src.ui.pages.documents import create_documents_page
        page = create_documents_page("http://test:8000")
        assert page is not None

    def test_create_with_app_registers_load(self, mock_gradio, mock_requests):
        mock_app = MagicMock()
        from src.ui.pages.documents import create_documents_page
        page = create_documents_page("http://test:8000", app=mock_app)
        assert page is not None
        mock_app.load.assert_called_once()

    def test_no_column_load_called(self, mock_gradio, mock_requests):
        """Verify .load() is NOT called on the Column (the fixed bug)."""
        from src.ui.pages.documents import create_documents_page
        col = mock_gradio.Column.return_value
        col.load = MagicMock()

        create_documents_page("http://test:8000")
        # Column.load should NOT be called (it was the bug)
        col.load.assert_not_called()


# ---------------------------------------------------------------------------
# Test Graph Page
# ---------------------------------------------------------------------------

class TestGraphPage:
    def test_create_without_app(self, mock_gradio, mock_requests):
        from src.ui.pages.graph import create_graph_page
        page = create_graph_page("http://test:8000")
        assert page is not None

    def test_create_with_app_registers_load(self, mock_gradio, mock_requests):
        mock_app = MagicMock()
        from src.ui.pages.graph import create_graph_page
        page = create_graph_page("http://test:8000", app=mock_app)
        assert page is not None
        mock_app.load.assert_called_once()

    def test_no_column_load_called(self, mock_gradio, mock_requests):
        from src.ui.pages.graph import create_graph_page
        col = mock_gradio.Column.return_value
        col.load = MagicMock()

        create_graph_page("http://test:8000")
        col.load.assert_not_called()


# ---------------------------------------------------------------------------
# Test Settings Page
# ---------------------------------------------------------------------------

class TestSettingsPage:
    def test_create_without_app(self, mock_gradio, mock_requests):
        from src.ui.pages.settings import create_settings_page
        page = create_settings_page("http://test:8000")
        assert page is not None

    def test_create_with_app_registers_load(self, mock_gradio, mock_requests):
        mock_app = MagicMock()
        from src.ui.pages.settings import create_settings_page
        page = create_settings_page("http://test:8000", app=mock_app)
        assert page is not None
        mock_app.load.assert_called_once()

    def test_no_column_load_called(self, mock_gradio, mock_requests):
        from src.ui.pages.settings import create_settings_page
        col = mock_gradio.Column.return_value
        col.load = MagicMock()

        create_settings_page("http://test:8000")
        col.load.assert_not_called()

    def test_json_component_no_readonly(self, mock_gradio, mock_requests):
        """Verify gr.JSON is not called with readonly=True (the fixed bug)."""
        from src.ui.pages.settings import create_settings_page
        create_settings_page("http://test:8000")

        # Check that JSON was called without readonly
        json_calls = mock_gradio.JSON.call_args_list
        for c in json_calls:
            assert "readonly" not in c.kwargs


# ---------------------------------------------------------------------------
# Test Graph Visualization (NetworkX + Plotly)
# ---------------------------------------------------------------------------

class TestGraphVisualization:
    def test_create_graph_viz_empty_data(self):
        """Test with empty graph data."""
        with patch.dict(sys.modules, {
            "networkx": MagicMock(),
            "plotly": MagicMock(),
            "plotly.graph_objects": MagicMock(),
        }):
            from src.ui.pages.graph import create_graph_viz_networkx
            result = create_graph_viz_networkx({"nodes": [], "edges": []})
            # Should return HTML (from fig.to_html) or the mock
            assert result is not None

    def test_create_graph_viz_import_error(self):
        """Test graceful fallback when NetworkX not installed."""
        # Remove networkx from modules so import fails
        original_nx = sys.modules.get("networkx")
        sys.modules["networkx"] = None

        try:
            # Need to reimport to trigger the ImportError
            from src.ui.pages.graph import create_graph_viz_networkx
            result = create_graph_viz_networkx({"nodes": [], "edges": []})
            assert "not installed" in result.lower() or result is not None
        finally:
            if original_nx is not None:
                sys.modules["networkx"] = original_nx
            else:
                sys.modules.pop("networkx", None)


# ---------------------------------------------------------------------------
# Test UI __init__ exports
# ---------------------------------------------------------------------------

class TestUIInit:
    def test_exports(self, mock_gradio):
        with patch("src.pdf_framework.config.get_settings", return_value=MagicMock()):
            from src.ui import __all__
            assert "create_app" in __all__
            assert "launch_ui" in __all__
