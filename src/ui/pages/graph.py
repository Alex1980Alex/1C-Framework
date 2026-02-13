"""Graph visualization page for Gradio UI (Phase 14.1) — Russian localization."""

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
            clear_btn = gr.Button("🗑 Очистить граф", variant="stop", min_width=200)

        graph_info = gr.Markdown("")

        graph_html = gr.HTML(
            value="""
            <div style="height: 500px; display: flex; align-items: center; justify-content: center;
                        background: #f5f5f5; border-radius: 8px;">
                <p style="color: #666;">Нажмите «Найти» для загрузки статистики графа</p>
            </div>
            """
        )

        entities_df = gr.Dataframe(
            headers=["Сущность", "Тип", "Документ"],
            label="Основные сущности",
            interactive=False,
        )

        def refresh_graph(filter_type: str, search: str):
            """Refresh graph stats and entity list."""
            try:
                # Fetch stats
                resp = requests.get(f"{api_url}/graph/stats", timeout=10)
                resp.raise_for_status()
                data = resp.json()

                info = (
                    "**Статистика графа:**\n"
                    f"- Сущностей: {data.get('node_count', 0)}\n"
                    f"- Связей: {data.get('edge_count', 0)}\n"
                    f"- Компонент связности: {data.get('connected_components', 0)}"
                )

                # Fetch entities
                params = {"limit": 50}
                if filter_type and filter_type != "All":
                    params["entity_type"] = filter_type
                if search and search.strip():
                    params["name"] = search.strip()

                eresp = requests.get(
                    f"{api_url}/graph/entities", params=params, timeout=10
                )
                eresp.raise_for_status()
                edata = eresp.json()

                rows = []
                for e in edata.get("entities", []):
                    rows.append([
                        e.get("name", ""),
                        e.get("type", ""),
                        e.get("source_document_id", ""),
                    ])

                return info, rows

            except Exception as e:
                logger.error(f"Graph error: {e}")
                return f"**Ошибка:** {e}", []

        def clear_graph():
            """Clear the entire knowledge graph."""
            try:
                resp = requests.delete(f"{api_url}/graph/clear", timeout=30)
                resp.raise_for_status()
                data = resp.json()
                nodes = data.get("deleted_nodes", 0)
                edges = data.get("deleted_edges", 0)
                info = (
                    f"**Граф очищен:** удалено {nodes} сущностей, {edges} связей.\n\n"
                    "Для обновления статистики нажмите «Найти»."
                )
                return info, []
            except Exception as e:
                logger.error(f"Clear graph error: {e}")
                return f"**Ошибка очистки:** {e}", gr.update()

        search_btn.click(
            refresh_graph,
            [entity_filter, search_entity],
            [graph_info, entities_df],
        )

        clear_btn.click(
            clear_graph,
            None,
            [graph_info, entities_df],
        )

        if app is not None:
            app.load(
                lambda: refresh_graph("All", ""),
                None,
                [graph_info, entities_df],
            )

    return page


def create_graph_viz_networkx(graph_data: dict, filter_type: str = "All") -> str:
    """
    Create interactive graph visualization using NetworkX + Plotly.

    Args:
        graph_data: Graph data from API
        filter_type: Entity type filter

    Returns:
        HTML string with Plotly figure
    """
    try:
        import networkx as nx
        import plotly.graph_objects as go

        G = nx.Graph()

        for node in graph_data.get("nodes", []):
            if filter_type != "All" and node.get("type") != filter_type:
                continue
            G.add_node(
                node.get("id"),
                label=node.get("id"),
                type=node.get("type", "ENTITY"),
            )

        for edge in graph_data.get("edges", []):
            G.add_edge(
                edge.get("source"),
                edge.get("target"),
                weight=edge.get("weight", 1.0),
            )

        pos = nx.spring_layout(G, k=0.5, iterations=50)

        edge_x = []
        edge_y = []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        node_x = [pos[node][0] for node in G.nodes()]
        node_y = [pos[node][1] for node in G.nodes()]
        node_text = [G.nodes[node].get("label", node) for node in G.nodes()]
        node_colors = [
            {"ENTITY": "#1f77b4", "COMMUNITY": "#ff7f0e", "DOCUMENT": "#2ca02c"}
            .get(G.nodes[node].get("type", "ENTITY"), "#999999")
            for node in G.nodes()
        ]

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines',
        ))

        fig.add_trace(go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=node_text,
            textposition="bottom center",
            marker=dict(
                size=10,
                color=node_colors,
                line=dict(width=2, color='white')
            ),
        ))

        fig.update_layout(
            showlegend=False,
            hovermode='closest',
            margin=dict(b=0, l=0, r=0, t=0),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=500,
        )

        return fig.to_html(include_plotlyjs=True)

    except ImportError:
        return """
        <div style="height: 500px; display: flex; align-items: center; justify-content: center; background: #f5f5f5; border-radius: 8px;">
            <p style="color: #666;">Для визуализации установите NetworkX и Plotly</p>
        </div>
        """
    except Exception as e:
        logger.error(f"Graph viz error: {e}")
        return f"<div style='padding: 20px;'>Ошибка: {e}</div>"
