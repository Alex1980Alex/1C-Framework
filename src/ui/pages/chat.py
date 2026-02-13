"""Chat page for Gradio UI (Phase 14.1) — Russian localization."""

import logging
import requests

import gradio as gr

logger = logging.getLogger(__name__)

STRATEGY_HINTS = {
    "adaptive": "Adaptive — автоматически выбирает лучшую стратегию для запроса",
    "hybrid": "Hybrid — комбинация векторного и графового поиска",
    "vector": "Vector — семантический поиск по эмбеддингам",
    "mmr": "MMR — максимальное разнообразие результатов",
    "graphrag_local": "GraphRAG Local — поиск по ближайшим сущностям графа",
    "graphrag_global": "GraphRAG Global — анализ через сообщества графа",
    "raptor": "RAPTOR — иерархический поиск по дереву саммари",
}


def create_chat_page(api_url: str):
    """Create chat interface page."""

    with gr.Column() as page:
        gr.Markdown(
            "### Чат с документами\n"
            "Задавайте вопросы — система найдёт ответ в проиндексированных PDF-файлах."
        )

        with gr.Row():
            strategy = gr.Dropdown(
                choices=list(STRATEGY_HINTS.keys()),
                value="adaptive",
                label="Стратегия поиска",
                info="Определяет, как система ищет релевантные фрагменты для ответа",
                scale=3,
            )
            clear_btn = gr.Button("Очистить историю", scale=1)

        strategy_hint = gr.Markdown(
            f"*{STRATEGY_HINTS['adaptive']}*"
        )

        chatbot = gr.Chatbot(height=500, label="Диалог")

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Введите вопрос по документам... (Enter — отправить)",
                show_label=False,
                scale=4,
            )
            submit_btn = gr.Button("Отправить", variant="primary", scale=1)

        sources_box = gr.Markdown("")

        def update_strategy_hint(s: str):
            return f"*{STRATEGY_HINTS.get(s, '')}*"

        def chat_fn(message: str, history: list, strategy: str):
            """Call chat API."""
            if not message or not message.strip():
                return history, "", ""
            try:
                response = requests.post(
                    f"{api_url}/chat/message",
                    json={"message": message, "strategy": strategy, "stream": False},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()

                answer = data.get("answer", "Нет ответа")
                sources = data.get("sources", [])

                sources_text = ""
                if sources:
                    sources_text = "\n\n**Источники:**\n" + "\n".join(
                        f"- {s.get('id', s.get('source', 'неизвестно'))}"
                        for s in sources[:5]
                    )

                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": answer})
                return history, "", sources_text

            except Exception as e:
                logger.error(f"Chat error: {e}")
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": f"Ошибка: {e}"})
                return history, "", ""

        def clear_history():
            return [], "", ""

        strategy.change(update_strategy_hint, [strategy], [strategy_hint])
        msg.submit(chat_fn, [msg, chatbot, strategy], [chatbot, msg, sources_box])
        submit_btn.click(chat_fn, [msg, chatbot, strategy], [chatbot, msg, sources_box])
        clear_btn.click(clear_history, None, [chatbot, msg, sources_box])

    return page
