"""Chat page for Gradio UI (UX v2).

Improvements:
- Streaming responses with yield (P1.1)
- Rich source citations as HTML cards (P1.2)
- Thinking indicator during generation
- Empty state with onboarding (P1.5)
- Error handling with gr.Warning/Error
- Adaptive chatbot height
"""

import logging

import gradio as gr
import requests

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


def _render_sources_html(sources: list[dict]) -> str:
    """Render sources as styled HTML cards."""
    if not sources:
        return ""

    cards = []
    for s in sources[:5]:
        source_id = s.get("id", s.get("source", "неизвестно"))
        score = s.get("score", 0)
        content = s.get("content", "")
        if len(content) > 150:
            content = content[:150] + "..."
        breadcrumb = s.get("metadata", {}).get("breadcrumb", "") if isinstance(s.get("metadata"), dict) else ""

        score_width = max(5, min(100, int(score * 100))) if isinstance(score, (int, float)) else 50
        score_display = f"{score:.3f}" if isinstance(score, (int, float)) else str(score)

        card = f"""<div class="source-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="score">{score_display}</span>
                <div style="flex:1;margin:0 12px;background:#e2e8f0;border-radius:3px;height:6px;">
                    <div class="score-bar" style="width:{score_width}%;"></div>
                </div>
                <span style="font-size:0.8em;color:#64748b;">{source_id}</span>
            </div>"""

        if breadcrumb:
            card += f'<div class="breadcrumb">{breadcrumb}</div>'
        if content:
            card += f'<div class="content">{content}</div>'
        card += "</div>"
        cards.append(card)

    return "<div style='margin-top:8px;'><strong>Источники:</strong>" + "".join(cards) + "</div>"


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

        chatbot = gr.Chatbot(
            height=500,
            label="Диалог",
            placeholder=(
                '<div class="empty-state">'
                '<div class="icon">&#128214;</div>'
                '<p><strong>Чат с документами</strong></p>'
                '<p>Задайте вопрос по проиндексированным PDF-файлам</p>'
                '<p style="font-size:0.85em;margin-top:8px;color:#94a3b8;">'
                'Если документы ещё не загружены, перейдите на вкладку «Документы»</p>'
                '</div>'
            ),
        )

        with gr.Row():
            msg = gr.Textbox(
                placeholder="Введите вопрос по документам... (Enter — отправить)",
                show_label=False,
                scale=4,
            )
            submit_btn = gr.Button("Отправить", variant="primary", scale=1)

        sources_html = gr.HTML("")

        def update_strategy_hint(s: str):
            return f"*{STRATEGY_HINTS.get(s, '')}*"

        def chat_fn(message: str, history: list, strat: str):
            """Call chat API with streaming support."""
            if not message or not message.strip():
                return history, "", ""

            history.append({"role": "user", "content": message})

            # Show thinking indicator
            history.append({"role": "assistant", "content": "..."})
            yield history, "", ""

            try:
                # Try streaming endpoint first
                try:
                    resp = requests.post(
                        f"{api_url}/chat/stream",
                        json={"message": message, "strategy": strat},
                        stream=True,
                        timeout=(10, 120),
                    )
                    resp.raise_for_status()

                    answer = ""
                    sources_data: list[dict] = []
                    for line in resp.iter_lines(decode_unicode=True):
                        if not line or not line.strip():
                            continue
                        try:
                            import json
                            chunk = json.loads(line)
                            if chunk.get("type") == "token":
                                answer += chunk.get("content", "")
                                history[-1] = {"role": "assistant", "content": answer}
                                yield history, "", ""
                            elif chunk.get("type") == "sources":
                                sources_data = chunk.get("sources", [])
                            elif chunk.get("type") == "done":
                                if chunk.get("answer"):
                                    answer = chunk["answer"]
                                sources_data = chunk.get("sources", sources_data)
                        except Exception:
                            # Not JSON — treat as raw text token
                            answer += line
                            history[-1] = {"role": "assistant", "content": answer}
                            yield history, "", ""

                    if not answer:
                        answer = "Нет ответа от сервера."
                    history[-1] = {"role": "assistant", "content": answer}
                    yield history, "", _render_sources_html(sources_data)
                    return

                except (requests.ConnectionError, requests.HTTPError):
                    # Fallback to non-streaming endpoint
                    pass

                response = requests.post(
                    f"{api_url}/chat/message",
                    json={"message": message, "strategy": strat, "stream": False},
                    timeout=120,
                )
                response.raise_for_status()
                data = response.json()

                answer = data.get("answer", "Нет ответа")
                sources = data.get("sources", [])

                history[-1] = {"role": "assistant", "content": answer}
                yield history, "", _render_sources_html(sources)

            except requests.ConnectionError:
                gr.Error("API сервер недоступен. Запустите backend: make api")
                history[-1] = {"role": "assistant", "content": "API сервер недоступен. Запустите backend: `make api`"}
                yield history, "", ""
            except requests.Timeout:
                gr.Warning("Превышено время ожидания ответа.")
                history[-1] = {"role": "assistant", "content": "Превышено время ожидания. Попробуйте упростить вопрос."}
                yield history, "", ""
            except Exception as e:
                logger.error(f"Chat error: {e}")
                history[-1] = {"role": "assistant", "content": f"Ошибка: {e}"}
                yield history, "", ""

        def clear_history():
            return [], "", ""

        strategy.change(update_strategy_hint, [strategy], [strategy_hint])
        msg.submit(chat_fn, [msg, chatbot, strategy], [chatbot, msg, sources_html])
        submit_btn.click(chat_fn, [msg, chatbot, strategy], [chatbot, msg, sources_html])
        clear_btn.click(clear_history, None, [chatbot, msg, sources_html])

    return page
