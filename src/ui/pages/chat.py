"""Chat page for Gradio UI (Phase 14.1)."""

import logging
import requests

import gradio as gr

logger = logging.getLogger(__name__)


def create_chat_page(api_url: str):
    """Create chat interface page."""

    with gr.Column() as page:
        gr.Markdown("### Chat with your documents")

        with gr.Row():
            strategy = gr.Dropdown(
                choices=["adaptive", "hybrid", "vector", "mmr", "graphrag_local", "graphrag_global", "raptor"],
                value="adaptive",
                label="Search Strategy",
                scale=3,
            )
            clear_btn = gr.Button("Clear History", scale=1)

        chatbot = gr.Chatbot(height=500, label="Conversation")

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Ask a question about your documents...",
                show_label=False,
                scale=4,
            )
            submit_btn = gr.Button("Send", variant="primary", scale=1)

        sources_box = gr.Markdown("")

        def chat_fn(message: str, history: list, strategy: str):
            """Call chat API."""
            try:
                response = requests.post(
                    f"{api_url}/chat/",
                    json={"message": message, "strategy": strategy},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()

                answer = data.get("answer", "No response")
                sources = data.get("sources", [])

                # Format sources
                sources_text = ""
                if sources:
                    sources_text = "\n\n**Sources:**\n" + "\n".join(
                        f"- {s.get('id', s.get('source', 'unknown'))}"
                        for s in sources[:5]
                    )

                history.append([message, answer])
                return history, "", sources_text

            except Exception as e:
                logger.error(f"Chat error: {e}")
                error_msg = f"Error: {str(e)}"
                history.append([message, error_msg])
                return history, "", ""

        def clear_history():
            """Clear conversation history."""
            return [], "", ""

        msg.submit(chat_fn, [msg, chatbot, strategy], [chatbot, msg, sources_box])
        submit_btn.click(chat_fn, [msg, chatbot, strategy], [chatbot, msg, sources_box])
        clear_btn.click(clear_history, None, [chatbot, msg, sources_box])

    return page


def create_streaming_chat_page(api_url: str):
    """Create streaming chat interface (alternative)."""

    with gr.Column() as page:
        gr.Markdown("### Chat (Streaming)")

        with gr.Row():
            strategy = gr.Dropdown(
                choices=["adaptive", "hybrid", "vector"],
                value="adaptive",
                label="Search Strategy",
            )

        chatbot = gr.Chatbot(height=500)
        msg = gr.Textbox(placeholder="Ask a question...", show_label=False)
        submit = gr.Button("Send", variant="primary")

        def stream_chat(message: str, history: list, strategy: str):
            """Stream chat response."""
            try:
                response = requests.post(
                    f"{api_url}/chat/",
                    json={"message": message, "strategy": strategy, "stream": True},
                    stream=True,
                    timeout=120,
                )

                history.append([message, ""])
                yield history, ""

                for line in response.iter_lines():
                    if line:
                        import json
                        try:
                            data = json.loads(line.decode("utf-8").lstrip("data: "))
                            if data.get("type") == "token":
                                token = data.get("data", "")
                                history[-1][1] += token
                                yield history, ""
                            elif data.get("type") == "source":
                                sources = data.get("data", [])
                                sources_text = "\n\n**Sources:**\n" + "\n".join(
                                    f"- {s.get('id', 'unknown')}" for s in sources[:5]
                                )
                                yield history, sources_text
                        except json.JSONDecodeError:
                            pass

            except Exception as e:
                logger.error(f"Stream error: {e}")
                history.append([message, f"Error: {e}"])
                yield history, ""

        msg.submit(stream_chat, [msg, chatbot, strategy], [chatbot, msg])
        submit.click(stream_chat, [msg, chatbot, strategy], [chatbot, msg])

    return page
