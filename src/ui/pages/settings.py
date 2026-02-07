"""Settings page for Gradio UI (Phase 14.1)."""

import logging

import gradio as gr
import requests

logger = logging.getLogger(__name__)


def create_settings_page(api_url: str):
    """Create settings and statistics page."""

    with gr.Column() as page:
        gr.Markdown("### System Settings & Statistics")

        with gr.Tabs():
            with gr.Tab("Statistics"):
                stats_info = gr.Markdown("Loading...")
                refresh_stats_btn = gr.Button("Refresh")

            with gr.Tab("Configuration"):
                config_json = gr.JSON(label="Current Configuration", readonly=True)

            with gr.Tab("Cache"):
                cache_info = gr.Markdown("Loading...")
                clear_cache_btn = gr.Button("Clear All Caches")

            with gr.Tab("Health"):
                health_info = gr.Markdown("Loading...")
                check_health_btn = gr.Button("Check Health")

        def load_stats():
            """Load system statistics."""
            try:
                response = requests.get(f"{api_url}/stats", timeout=10)
                response.raise_for_status()
                data = response.json()

                return f"""
                **Index Statistics:**
                - Documents: {data.get('documents', 'N/A')}
                - Chunks: {data.get('chunks', 'N/A')}
                - Entities: {data.get('entities', 'N/A')}
                - Relations: {data.get('relations', 'N/A')}
                """

            except Exception as e:
                return f"**Error:** {str(e)}"

        def load_config():
            """Load configuration."""
            try:
                response = requests.get(f"{api_url}/config", timeout=10)
                if response.status_code == 200:
                    return response.json()
                else:
                    # Return default structure if endpoint not available
                    return {
                        "embedding": {"provider": "local", "model": "all-MiniLM-L6-v2"},
                        "vector_store": {"provider": "chroma"},
                        "graph_store": {"provider": "networkx"},
                        "message": "Config endpoint not available"
                    }
            except Exception as e:
                return {"error": str(e)}

        def load_cache():
            """Load cache statistics."""
            try:
                response = requests.get(f"{api_url}/cache/stats", timeout=10)
                response.raise_for_status()
                data = response.json()

                return f"""
                **Cache Statistics:**
                - Embedding Cache Hit Rate: {data.get('embedding', {}).get('hit_rate', 'N/A')}
                - LLM Cache Hit Rate: {data.get('llm', {}).get('hit_rate', 'N/A')}
                - Document Cache Entries: {data.get('document', {}).get('entries', 'N/A')}
                """

            except Exception as e:
                return f"**Error:** {str(e)}"

        def check_health():
            """Check system health."""
            try:
                response = requests.get(f"{api_url}/health", timeout=10)
                response.raise_for_status()
                data = response.json()

                status = "✅ Healthy" if data.get("status") == "healthy" else "⚠️ Unhealthy"

                return f"""
                **System Status:** {status}

                **Components:**
                {chr(10).join(f"- {k}: {'✅' if v.get('status') == 'ok' else '❌'} {v.get('message', '')}"
                    for k, v in data.get('checks', {}).items())}
                """

            except Exception as e:
                return f"**Error:** {str(e)}"

        def clear_cache():
            """Clear all caches."""
            try:
                response = requests.post(f"{api_url}/cache/clear", timeout=30)
                response.raise_for_status()
                data = response.json()
                return f"**Cleared:** {data.get('cleared', 0)} cache entries"
            except Exception as e:
                return f"**Error:** {str(e)}"

        refresh_stats_btn.click(load_stats, None, [stats_info])
        clear_cache_btn.click(clear_cache, None, [cache_info])
        check_health_btn.click(check_health, None, [health_info])

        # Initial load
        page.load(
            lambda: (load_stats(), load_config(), load_cache(), check_health()),
            None,
            [stats_info, config_json, cache_info, health_info],
        )

    return page
