"""Search page for Gradio UI (Phase 14.1) — Russian localization."""

import logging

import gradio as gr
import requests

logger = logging.getLogger(__name__)

STRATEGY_INFO = {
    "vector": "Семантический поиск по эмбеддингам — быстрый, подходит для точных запросов",
    "hybrid": "Комбинация векторного + графового поиска — сбалансированный вариант",
    "section_first": "Сначала найти раздел через BM25, затем искать внутри него (Phase 30)",
    "mmr": "Максимальное разнообразие — снижает дублирование в результатах",
    "adaptive": "Автоматический выбор лучшей стратегии на основе анализа запроса",
    "graphrag_local": "Поиск по сущностям графа знаний и их связям",
    "graphrag_global": "Глобальный анализ через сообщества графа (медленнее, но глубже)",
    "raptor": "Иерархический поиск по дереву саммари (RAPTOR)",
}


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
                    info="Фильтр по типу документа (определяется автоматически при индексации)",
                )
                language = gr.Textbox(
                    label="Язык",
                    placeholder="ru или en",
                    info="Фильтр по языку документа",
                )
                version = gr.Textbox(
                    label="Версия",
                    placeholder="8.3.26",
                    info="Фильтр по версии (извлекается из имени файла)",
                )

        results_df = gr.Dataframe(
            headers=["Релевантность", "Раздел", "Содержание", "Источник"],
            label="Результаты поиска",
            interactive=False,
        )

        search_info = gr.Markdown("")

        def search_fn(query: str, strategy: str, k: int, section: str, doc_type: str, language: str, version: str):
            """Perform search."""
            if not query:
                return None, "*Введите поисковый запрос.*"

            try:
                filters = {}
                if doc_type:
                    filters["document_type"] = doc_type
                if language:
                    filters["language"] = language
                if version:
                    filters["version"] = version

                params = {"strategy": strategy, "k": k}
                if filters:
                    params["filter"] = filters
                if section and section.strip():
                    params["section"] = section.strip()

                response = requests.post(
                    f"{api_url}/search/",
                    json={"query": query, **params},
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for r in data.get("results", []):
                    content = r.get("content", "")
                    if len(content) > 200:
                        content = content[:200] + "..."
                    breadcrumb = r.get("metadata", {}).get("breadcrumb", "")
                    results.append([
                        f"{r.get('score', 0):.3f}",
                        breadcrumb[:80] if breadcrumb else "",
                        content,
                        r.get("source", "неизвестно"),
                    ])

                total = data.get("total_results", len(results))
                elapsed = data.get("elapsed_ms", 0)
                stype = data.get("search_type", strategy)
                # Phase 30: show detected section if section_first
                section_info = ""
                meta = data.get("metadata", {})
                if meta.get("section_first"):
                    section_info = f", раздел: {meta['section_first']}"
                info = f"**Найдено {total} результатов** за {elapsed:.0f} мс, стратегия: {stype}{section_info}"

                return results, info

            except Exception as e:
                logger.error(f"Search error: {e}")
                return None, f"**Ошибка:** {e}"

        search_btn.click(
            search_fn,
            [query, strategy, top_k, section_filter, doc_type, language, version],
            [results_df, search_info],
        )
        query.submit(
            search_fn,
            [query, strategy, top_k, section_filter, doc_type, language, version],
            [results_df, search_info],
        )

    return page
