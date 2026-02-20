"""Search page for Gradio UI (UX v2).

Improvements:
- Search results as styled HTML cards instead of flat table (P1.3)
- Score visualization with bars
- Empty state with guidance (P1.5)
- Error handling with gr.Warning/Error
"""

import logging

import gradio as gr
import requests

logger = logging.getLogger(__name__)

STRATEGY_INFO = {
    "vector": "Семантический поиск по эмбеддингам — быстрый, подходит для точных запросов",
    "hybrid": "Комбинация векторного + графового поиска — сбалансированный вариант",
    "section_first": "Сначала найти раздел через BM25, затем искать внутри него",
    "mmr": "Максимальное разнообразие — снижает дублирование в результатах",
    "adaptive": "Автоматический выбор лучшей стратегии на основе анализа запроса",
    "graphrag_local": "Поиск по сущностям графа знаний и их связям",
    "graphrag_global": "Глобальный анализ через сообщества графа (медленнее, но глубже)",
    "raptor": "Иерархический поиск по дереву саммари (RAPTOR)",
}


def _render_results_html(results: list[dict], query: str) -> str:
    """Render search results as styled HTML cards with score bars."""
    if not results:
        return (
            '<div class="empty-state">'
            '<div class="icon">&#128269;</div>'
            '<p><strong>Ничего не найдено</strong></p>'
            '<p>Попробуйте изменить запрос, выбрать другую стратегию или расширить фильтры</p>'
            '</div>'
        )

    cards = []
    for i, r in enumerate(results):
        content = r.get("content", "")
        score = r.get("score", 0)
        source = r.get("source", "неизвестно")
        metadata = r.get("metadata", {}) if isinstance(r.get("metadata"), dict) else {}
        breadcrumb = metadata.get("breadcrumb", "")
        doc_type = metadata.get("document_type", "")
        language = metadata.get("language", "")
        page = metadata.get("page", "")

        # Highlight query terms in content (simple approach)
        display_content = content
        if len(display_content) > 400:
            display_content = display_content[:400] + "..."

        # Score bar
        score_val = float(score) if isinstance(score, (int, float)) else 0
        score_width = max(5, min(100, int(score_val * 100)))
        score_str = f"{score_val:.3f}"

        # Build pills
        pills = []
        if source:
            pills.append(f'<span class="pill">{source}</span>')
        if doc_type:
            pills.append(f'<span class="pill">{doc_type}</span>')
        if language:
            pills.append(f'<span class="pill">{language}</span>')
        if page:
            pills.append(f'<span class="pill">стр. {page}</span>')

        card = f"""<div class="source-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="score" style="min-width:50px;">{score_str}</span>
                <div style="flex:1;margin:0 12px;background:#e2e8f0;border-radius:3px;height:6px;">
                    <div class="score-bar" style="width:{score_width}%;"></div>
                </div>
                <span style="font-size:0.8em;color:#64748b;">#{i+1}</span>
            </div>"""

        if breadcrumb:
            card += f'<div class="breadcrumb">{breadcrumb}</div>'

        card += f'<div class="content">{display_content}</div>'

        if pills:
            card += f'<div class="meta-pills">{"".join(pills)}</div>'

        card += "</div>"
        cards.append(card)

    return "".join(cards)


def create_search_page(api_url: str):
    """Create search interface page."""

    with gr.Column() as page:
        gr.Markdown(
            "### Поиск по документам\n"
            "Введите запрос — система найдёт наиболее релевантные фрагменты из проиндексированных PDF."
        )

        with gr.Row():
            query = gr.Textbox(
                placeholder="Например: Как настроить права доступа в 1С?",
                label="Поисковый запрос",
                info="Введите вопрос или ключевые слова на естественном языке",
                scale=4,
            )
            search_btn = gr.Button("Найти", variant="primary", scale=1)

        with gr.Row():
            strategy = gr.Dropdown(
                choices=list(STRATEGY_INFO.keys()),
                value="hybrid",
                label="Стратегия поиска",
                info="hybrid — оптимальный баланс скорости и качества",
            )
            top_k = gr.Slider(
                1, 20, value=5, step=1,
                label="Количество результатов",
                info="Сколько фрагментов показать (Top-K)",
            )
            section_filter = gr.Textbox(
                placeholder="5.14",
                label="Фильтр по разделу",
                info="Оставьте пустым для поиска по всему документу",
            )

        with gr.Accordion("Расширенные фильтры", open=False):
            gr.Markdown(
                "*Фильтры сужают поиск по метаданным документов. "
                "Оставьте пустыми, чтобы искать по всем документам.*"
            )
            with gr.Row():
                doc_type = gr.Textbox(
                    label="Тип документа",
                    placeholder="manual, documentation, api_reference, tutorial",
                    info="Фильтр по типу документа",
                )
                language = gr.Textbox(
                    label="Язык",
                    placeholder="ru или en",
                    info="Фильтр по языку документа",
                )
                version = gr.Textbox(
                    label="Версия",
                    placeholder="8.3.26",
                    info="Фильтр по версии",
                )

        search_info = gr.Markdown("")

        results_html = gr.HTML(
            value=(
                '<div class="empty-state">'
                '<div class="icon">&#128269;</div>'
                '<p><strong>Введите запрос</strong></p>'
                '<p>Результаты поиска появятся здесь</p>'
                '</div>'
            )
        )

        def search_fn(q: str, strat: str, k: int, section: str, dt: str, lang: str, ver: str):
            """Perform search and render results as HTML cards."""
            if not q:
                gr.Warning("Введите поисковый запрос.")
                return (
                    "*Введите поисковый запрос.*",
                    '<div class="empty-state">'
                    '<div class="icon">&#128269;</div>'
                    '<p><strong>Введите запрос</strong></p>'
                    '<p>Результаты поиска появятся здесь</p>'
                    '</div>',
                )

            try:
                filters = {}
                if dt:
                    filters["document_type"] = dt
                if lang:
                    filters["language"] = lang
                if ver:
                    filters["version"] = ver

                params = {"strategy": strat, "k": int(k)}
                if filters:
                    params["filter"] = filters
                if section and section.strip():
                    params["section"] = section.strip()

                response = requests.post(
                    f"{api_url}/search/",
                    json={"query": q, **params},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                results = data.get("results", [])
                total = data.get("total_results", len(results))
                elapsed = data.get("elapsed_ms", 0)
                stype = data.get("search_type", strat)

                meta = data.get("metadata", {})
                section_info = ""
                if isinstance(meta, dict) and meta.get("section_first"):
                    section_info = f", раздел: {meta['section_first']}"

                elapsed_str = f"{elapsed:.0f}" if isinstance(elapsed, (int, float)) else str(elapsed)
                info = f"**Найдено {total} результатов** за {elapsed_str} мс, стратегия: {stype}{section_info}"

                html = _render_results_html(results, q)
                return info, html

            except requests.ConnectionError:
                gr.Error("API сервер недоступен. Запустите backend: make api")
                return "**API сервер недоступен**", ""
            except requests.Timeout:
                gr.Warning("Превышено время ожидания поиска.")
                return "**Таймаут поиска**", ""
            except Exception as e:
                logger.error(f"Search error: {e}")
                return f"**Ошибка:** {e}", ""

        search_btn.click(
            search_fn,
            [query, strategy, top_k, section_filter, doc_type, language, version],
            [search_info, results_html],
        )
        query.submit(
            search_fn,
            [query, strategy, top_k, section_filter, doc_type, language, version],
            [search_info, results_html],
        )

    return page
