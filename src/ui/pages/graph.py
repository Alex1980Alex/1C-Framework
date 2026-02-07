"""Graph visualization page for Gradio UI (Phase 14.1)."""

import logging

import gradio as gr
import requests

logger = logging.getLogger(__name__)


def create_graph_page(api_url: str):
    """Create knowledge graph visualization page."""

    with gr.Column() as page:
        gr.Markdown("### Knowledge Graph")

        with gr.Row():
            entity_filter = gr.Dropdown(
                choices=["All", "ENTITY", "COMMUNITY", "DOCUMENT"],
                value="All",
                label="Filter by Type",
            )
            search_entity = gr.Textbox(label="Search Entity", placeholder="Entity name...")
            search_btn = gr.Button("Search", scale=1)

        graph_info = gr.Markdown("")

        graph_html = gr.HTML(
            value="""
            <div style="height: 500px; display: flex; align-items: center; justify-content: center;
                        background: #f5f5f5; border-radius: 8px;">
                <p style="color: #666;">Graph visualization requires NetworkX + Plotly</p>
            </div>
            """
        )

        entities_df = gr.Dataframe(
            headers=["Entity", "Type", "Connections"],
            label="Top Entities",
            interactive=False,
        )

        def refresh_graph(filter_type: str, search: str):
            """Refresh graph visualization."""
            try:
                response = requests.get(f"{api_url}/graph/stats", timeout=10)
                response.raise_for_status()
                data = response.json()

                info = f"""
                **Graph Statistics:**
                - Entities: {data.get('entity_count', 0)}
                - Relations: {data.get('relation_count', 0)}
                - Communities: {data.get('community_count', 0)}
                """
                return info, []

            except Exception as e:
                logger.error(f"Graph error: {e}")
                return f"**Error:** {str(e)}", []

        search_btn.click(
            refresh_graph,
            [entity_filter, search_entity],
            [graph_info, entities_df],
        )

        page.load(
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

        # Add nodes
        for node in graph_data.get("nodes", []):
            if filter_type != "All" and node.get("type") != filter_type:
                continue
            G.add_node(
                node.get("id"),
                label=node.get("id"),
                type=node.get("type", "ENTITY"),
            )

        # Add edges
        for edge in graph_data.get("edges", []):
            G.add_edge(
                edge.get("source"),
                edge.get("target"),
                weight=edge.get("weight", 1.0),
            )

        # Get positions
        pos = nx.spring_layout(G, k=0.5, iterations=50)

        # Create plotly scatter
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

        # Edges
        fig.add_trace(go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines',
        ))

        # Nodes
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
            <p style="color: #666;">NetworkX and/or Plotly not installed</p>
        </div>
        """
    except Exception as e:
        logger.error(f"Graph viz error: {e}")
        return f"<div style='padding: 20px;'>Error: {str(e)}</div>"
