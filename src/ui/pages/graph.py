"""Graph visualization page for Gradio UI (UX v2).

Improvements:
- Confirmation dialog for graph clear
- Connected graph visualization via Plotly
- Error handling with gr.Info/Warning/Error
- Empty state guidance
"""

import logging

import gradio as gr
import requests

logger = logging.getLogger(__name__)


def create_graph_page(api_url: str, app: gr.Blocks | None = None):
    """Create knowledge graph visualization page."""

    with gr.Column() as page:
        gr.Markdown(
            "### Граф знаний\n"
            "Визуализация сущностей и связей, извлечённых из документов. "
            "Граф строится при индексации с опцией **Граф знаний**."
        )

        with gr.Row():
            entity_filter = gr.Dropdown(
                choices=["All", "ENTITY", "COMMUNITY", "DOCUMENT"],
                value="All",
                label="Фильтр по типу",
                info="Показать только определённый тип узлов графа",
                scale=2,
            )
            search_entity = gr.Textbox(
                label="Поиск сущности",
                placeholder="Введите имя сущности...",
                info="Найти конкретную сущность в графе",
                scale=3,
            )
        with gr.Row():
            search_btn = gr.Button("Найти", variant="primary", min_width=200)
            clear_btn = gr.Button("Очистить граф", variant="stop", min_width=200)

        graph_info = gr.Markdown("")

        graph_html = gr.HTML(
            value="""
            <div class="empty-state" style="height: 400px; display: flex; flex-direction: column;
                        align-items: center; justify-content: center;
                        background: var(--block-background-fill); border-radius: 8px;
                        border: 1px dashed var(--block-border-color);">
                <div class="icon">&#128302;</div>
                <p><strong>Граф знаний пуст</strong></p>
                <p>Нажмите «Найти» для загрузки или проиндексируйте документы с опцией «Граф знаний»</p>
            </div>
            """
        )

        entities_df = gr.Dataframe(
            headers=["Сущность", "Тип", "Документ"],
            label="Основные сущности",
            interactive=False,
        )

        def _build_graph_html(api_url: str, filter_type: str) -> str:
            """Fetch graph data and build Plotly visualization."""
            try:
                import networkx as nx
                import plotly.graph_objects as go
            except ImportError:
                return (
                    '<div style="height: 400px; display: flex; align-items: center; justify-content: center;'
                    ' background: var(--block-background-fill); border-radius: 8px;">'
                    '<p>Для визуализации установите: pip install networkx plotly</p></div>'
                )

            try:
                resp = requests.get(
                    f"{api_url}/graph/data",
                    params={"limit": 200},
                    timeout=15,
                )
                if resp.status_code == 404:
                    return ""
                resp.raise_for_status()
                graph_data = resp.json()
            except Exception:
                return ""

            G = nx.Graph()

            for node in graph_data.get("nodes", []):
                if filter_type != "All" and node.get("type") != filter_type:
                    continue
                G.add_node(
                    node.get("id"),
                    label=node.get("id"),
                    node_type=node.get("type", "ENTITY"),
                )

            for edge in graph_data.get("edges", []):
                src, tgt = edge.get("source"), edge.get("target")
                if src in G.nodes and tgt in G.nodes:
                    G.add_edge(src, tgt, weight=edge.get("weight", 1.0))

            if len(G.nodes) == 0:
                return ""

            pos = nx.spring_layout(G, k=0.5, iterations=50)

            edge_x, edge_y = [], []
            for e in G.edges():
                x0, y0 = pos[e[0]]
                x1, y1 = pos[e[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

            type_colors = {"ENTITY": "#3b82f6", "COMMUNITY": "#f59e0b", "DOCUMENT": "#22c55e"}
            node_x = [pos[n][0] for n in G.nodes()]
            node_y = [pos[n][1] for n in G.nodes()]
            node_text = [G.nodes[n].get("label", n) for n in G.nodes()]
            node_colors = [type_colors.get(G.nodes[n].get("node_type", "ENTITY"), "#94a3b8") for n in G.nodes()]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=0.5, color='#94a3b8'),
                hoverinfo='none', mode='lines',
            ))
            fig.add_trace(go.Scatter(
                x=node_x, y=node_y,
                mode='markers+text', hoverinfo='text',
                text=node_text, textposition="bottom center",
                textfont=dict(size=9),
                marker=dict(size=10, color=node_colors, line=dict(width=1.5, color='white')),
            ))
            fig.update_layout(
                showlegend=False, hovermode='closest',
                margin=dict(b=0, l=0, r=0, t=0),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=450,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
            )
            return fig.to_html(include_plotlyjs="cdn", full_html=False)

        def refresh_graph(filter_type: str, search: str):
            """Refresh graph stats, visualization, and entity list."""
            try:
                resp = requests.get(f"{api_url}/graph/stats", timeout=10)
                resp.raise_for_status()
                data = resp.json()

                node_count = data.get('node_count', 0)
                edge_count = data.get('edge_count', 0)

                info = (
                    "**Статистика графа:**\n"
                    f"- Сущностей: {node_count}\n"
                    f"- Связей: {edge_count}\n"
                    f"- Компонент связности: {data.get('connected_components', 0)}"
                )

                # Build visualization
                viz_html = ""
                if node_count > 0:
                    viz_html = _build_graph_html(api_url, filter_type)

                if not viz_html:
                    viz_html = (
                        '<div class="empty-state" style="height: 400px; display: flex; flex-direction: column;'
                        ' align-items: center; justify-content: center;'
                        ' background: var(--block-background-fill); border-radius: 8px;'
                        ' border: 1px dashed var(--block-border-color);">'
                        '<div class="icon">&#128302;</div>'
                        '<p><strong>Граф знаний пуст</strong></p>'
                        '<p>Проиндексируйте документы с опцией «Граф знаний»</p></div>'
                    )

                # Fetch entities
                params = {"limit": 50}
                if filter_type and filter_type != "All":
                    params["entity_type"] = filter_type
                if search and search.strip():
                    params["name"] = search.strip()

                eresp = requests.get(f"{api_url}/graph/entities", params=params, timeout=10)
                eresp.raise_for_status()
                edata = eresp.json()

                rows = []
                for e in edata.get("entities", []):
                    rows.append([e.get("name", ""), e.get("type", ""), e.get("source_document_id", "")])

                return info, viz_html, rows

            except requests.ConnectionError:
                empty = (
                    '<div class="empty-state" style="height: 400px; display: flex; align-items: center;'
                    ' justify-content: center; border-radius: 8px;">'
                    '<p>API сервер недоступен</p></div>'
                )
                return "**API сервер недоступен.** Запустите backend: `make api`", empty, []
            except Exception as e:
                logger.error(f"Graph error: {e}")
                return f"**Ошибка:** {e}", "", []

        def clear_graph():
            """Clear the entire knowledge graph."""
            try:
                resp = requests.delete(f"{api_url}/graph/clear", timeout=30)
                resp.raise_for_status()
                data = resp.json()
                nodes = data.get("deleted_nodes", 0)
                edges = data.get("deleted_edges", 0)
                gr.Info(f"Граф очищен: {nodes} сущностей, {edges} связей удалено")
                info = (
                    f"**Граф очищен:** удалено {nodes} сущностей, {edges} связей.\n\n"
                    "Нажмите «Найти» для обновления."
                )
                empty_viz = (
                    '<div class="empty-state" style="height: 400px; display: flex; flex-direction: column;'
                    ' align-items: center; justify-content: center; border-radius: 8px;'
                    ' border: 1px dashed var(--block-border-color);">'
                    '<div class="icon">&#128302;</div>'
                    '<p><strong>Граф очищен</strong></p></div>'
                )
                return info, empty_viz, []
            except requests.ConnectionError:
                gr.Error("API сервер недоступен")
                return "**API сервер недоступен**", "", gr.update()
            except Exception as e:
                logger.error(f"Clear graph error: {e}")
                return f"**Ошибка:** {e}", "", gr.update()

        # JS confirmation for graph clear
        clear_confirm_js = """
        () => {
            if (!confirm('Очистить весь граф знаний?\\n\\nВсе сущности и связи будут безвозвратно удалены.')) {
                throw new Error('cancelled');
            }
        }
        """

        search_btn.click(
            refresh_graph,
            [entity_filter, search_entity],
            [graph_info, graph_html, entities_df],
        )

        clear_btn.click(
            clear_graph,
            None,
            [graph_info, graph_html, entities_df],
            js=clear_confirm_js,
        )

        if app is not None:
            app.load(
                lambda: refresh_graph("All", ""),
                None,
                [graph_info, graph_html, entities_df],
            )

    return page
