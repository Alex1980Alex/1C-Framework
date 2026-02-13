"""Documents page for Gradio UI (Phase 14.1) — Russian localization.

Provides:
- PDF file upload
- Indexing with options (graph, contextual, raptor, etc.)
- Real-time progress display
- Document list with delete capability
"""

import json
import logging
import os
import time

import gradio as gr
import requests

logger = logging.getLogger(__name__)


def create_documents_page(api_url: str, app: gr.Blocks | None = None):
    """Create document management page with real indexing."""

    with gr.Column() as page:
        gr.Markdown(
            "### Управление документами\n"
            "Загрузите PDF-файл, выберите опции и нажмите **Индексировать**. "
            "После индексации документ будет доступен для поиска и чата."
        )

        # --- Upload & Index ---
        with gr.Row():
            with gr.Column(scale=3):
                file_upload = gr.File(
                    label="Загрузить PDF (можно несколько файлов)",
                    file_types=[".pdf"],
                    file_count="multiple",
                    type="filepath",
                )
            with gr.Column(scale=1):
                index_btn = gr.Button(
                    "Индексировать",
                    variant="primary",
                    size="lg",
                )

        gr.Markdown(
            "*Опции индексации — выберите дополнительные режимы обработки:*"
        )

        # Phase 15.1: PDF Loader selection
        with gr.Row():
            loader_choice = gr.Dropdown(
                choices=[
                    "auto (smart)",
                    "pymupdf",
                    "docling",
                    "pymupdf4llm",
                ],
                value="auto (smart)",
                label="Загрузчик PDF",
                info="auto — автовыбор: простые PDF быстро, сложные через Docling",
            )

        with gr.Row():
            build_graph = gr.Checkbox(
                label="Граф знаний",
                value=True,
                info="LLM извлечёт сущности и связи из текста (медленнее, но даёт граф)",
            )
            contextual = gr.Checkbox(
                label="Контекстное обогащение",
                value=True,
                info="LLM добавит контекст документа к каждому чанку (улучшает поиск)",
            )
            parent_child = gr.Checkbox(
                label="Родитель-потомок",
                value=True,
                info="Двухуровневое разбиение: маленькие чанки для поиска, большие для контекста",
            )
            raptor = gr.Checkbox(
                label="RAPTOR-дерево",
                value=True,
                info="Иерархическое дерево саммари для многоуровневого поиска",
            )
            summarize = gr.Checkbox(
                label="Саммари документа",
                value=True,
                info="Создаёт краткое описание всего документа",
            )
            extract_images = gr.Checkbox(
                label="Изображения (Vision)",
                value=True,
                info="Извлекает изображения и описывает их через Claude Vision для поиска",
            )

        progress_bar = gr.HTML(
            value='<div style="background:#e0e0e0;border-radius:8px;height:32px;overflow:hidden;">'
            '<div style="width:0%;height:100%;display:flex;align-items:center;'
            'justify-content:center;color:#999;">Ожидание...</div></div>',
        )
        progress_log = gr.Textbox(
            label="Лог индексации",
            interactive=False,
            lines=8,
            max_lines=25,
        )

        # --- Document List ---
        gr.Markdown("### Проиндексированные документы")

        with gr.Row():
            refresh_btn = gr.Button("Обновить список")
            stats_btn = gr.Button("Статистика")
            structure_btn = gr.Button("Структура (ToC)")
            incremental_btn = gr.Button("Доиндексировать новые", variant="primary")
            reindex_btn = gr.Button("Переиндексировать все", variant="secondary")
            rebuild_bm25_btn = gr.Button("Пересобрать BM25", variant="secondary")
            build_communities_btn = gr.Button(
                "Кластеризация графа",
                variant="secondary",
            )

        docs_df = gr.Dataframe(
            headers=["ID документа", "Чанков", "Файл", "Тип", "Язык"],
            label="Проиндексированные документы",
            interactive=False,
        )

        stats_box = gr.Markdown("")

        # --- Delete ---
        gr.Markdown("### Удаление документа")
        with gr.Row():
            delete_id = gr.Dropdown(
                choices=[],
                label="Выберите документ для удаления",
                info="Будут удалены все чанки этого документа из векторного хранилища",
                allow_custom_value=True,
            )
            delete_btn = gr.Button("Удалить", variant="stop")

        delete_result = gr.Textbox(label="Результат", interactive=False)

        # ========== Handlers ==========

        def _progress_html(percent: int, label: str = "") -> str:
            """Render an HTML progress bar."""
            if percent <= 0:
                return (
                    '<div style="background:#e0e0e0;border-radius:8px;height:32px;overflow:hidden;">'
                    '<div style="width:0%;height:100%;display:flex;align-items:center;'
                    'justify-content:center;color:#999;">Ожидание...</div></div>'
                )
            color = "#4caf50" if percent >= 100 else "linear-gradient(90deg,#ff9800,#f57c00)"
            return (
                '<div style="background:#e0e0e0;border-radius:8px;height:32px;overflow:hidden;">'
                f'<div style="width:{percent}%;background:{color};height:100%;'
                'transition:width 0.4s ease;display:flex;align-items:center;'
                f'justify-content:center;color:white;font-weight:bold;font-size:14px;min-width:60px;">'
                f'{percent}%{" — " + label if label else ""}'
                '</div></div>'
            )

        # Progress fractions (0.0–1.0) for each streaming step
        _STEP_PCT = {
            "load": 0.00, "load_done": 0.10,
            "dedup": 0.11,
            "split": 0.12, "split_done": 0.25,
            "images": 0.27, "images_done": 0.40,
            "images_error": 0.40,
            "embed": 0.42, "embed_done": 0.80,
            "graph": 0.82, "graph_done": 0.95,
            "graph_error": 0.95,
            "done": 1.0, "error": 1.0,
        }

        # Embed phase range for batch progress interpolation
        _EMBED_START = 0.42
        _EMBED_END = 0.80

        def _format_options(loader, graph, ctx, pc, rapt, summ, imgs) -> list[str]:
            """Build header lines showing loader and selected options."""
            lines = []
            if loader == "auto (smart)":
                lines.append("Загрузчик: auto (автовыбор лучшего метода)")
            else:
                lines.append(f"Загрузчик: {loader}")
            opts = []
            if graph:
                opts.append("Граф знаний")
            if ctx:
                opts.append("Контекстное обогащение")
            if pc:
                opts.append("Родитель-потомок")
            if rapt:
                opts.append("RAPTOR")
            if summ:
                opts.append("Саммари")
            if imgs:
                opts.append("Изображения (Vision)")
            if opts:
                lines.append(f"Опции: {', '.join(opts)}")
            else:
                lines.append("Режим: базовый (только векторный поиск)")
            return lines

        def _iter_stream(payload):
            """POST to /documents/index/stream and yield parsed NDJSON events."""
            try:
                resp = requests.post(
                    f"{api_url}/documents/index/stream",
                    json=payload,
                    stream=True,
                    timeout=(10, 7200),  # 10s connect, 2h read (long steps)
                )
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if line and line.strip():
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                yield {"step": "error", "detail": str(e)}

        def index_document(
            file_paths: list[str] | str | None,
            loader: str,
            graph: bool,
            ctx: bool,
            pc: bool,
            rapt: bool,
            summ: bool,
            imgs: bool = True,
        ):
            """Upload files to backend and run indexing with streaming logs."""
            if not file_paths:
                yield _progress_html(0), "Файлы не выбраны. Загрузите PDF и попробуйте снова."
                return

            # Normalize to list
            if isinstance(file_paths, str):
                file_paths = [file_paths]

            total = len(file_paths)
            log_lines = [f"Выбрано файлов: {total}"]
            log_lines.extend(_format_options(loader, graph, ctx, pc, rapt, summ, imgs))

            # Map loader choice to API value
            loader_value = "default"
            if loader == "auto (smart)":
                loader_value = "smart"
            elif loader in ["pymupdf", "docling", "pymupdf4llm"]:
                loader_value = loader

            file_step = 100 / total
            upload_frac = 0.15  # 15% of file step for upload
            stream_frac = 0.85  # 85% for streaming index

            yield _progress_html(0, "Начало..."), "\n".join(log_lines)

            total_chunks = 0
            total_embeddings = 0
            success_count = 0
            total_start = time.time()

            for i, file_path in enumerate(file_paths, 1):
                filename = os.path.basename(file_path)
                base_pct = (i - 1) * file_step
                upload_share = file_step * upload_frac
                stream_share = file_step * stream_frac

                log_lines.append(f"\n[{i}/{total}] {filename}")
                log_lines.append("  Загрузка на сервер...")
                yield _progress_html(int(base_pct), f"[{i}/{total}] {filename}"), "\n".join(log_lines)

                # Upload
                try:
                    with open(file_path, "rb") as f:
                        resp = requests.post(
                            f"{api_url}/documents/upload",
                            files={"file": (filename, f, "application/pdf")},
                            timeout=60,
                        )
                    resp.raise_for_status()
                    server_path = resp.json()["file_path"]
                except Exception as e:
                    log_lines.append(f"  Ошибка загрузки: {e}")
                    yield _progress_html(int(base_pct + upload_share), f"Ошибка: {filename}"), "\n".join(log_lines)
                    continue

                log_lines.append("  Загружен на сервер")
                yield _progress_html(int(base_pct + upload_share), f"[{i}/{total}] Индексация {filename}..."), "\n".join(log_lines)

                # Stream index with live logging
                payload = {
                    "file_path": server_path,
                    "loader": loader_value,
                    "build_graph": graph,
                    "contextual": ctx,
                    "parent_child": pc,
                    "raptor": rapt,
                    "summarize": summ,
                    "extract_images": imgs,
                }
                for event in _iter_stream(payload):
                    ev_step = event.get("step", "")
                    detail = event.get("detail", "")

                    if ev_step == "batch":
                        # Dynamic progress within embed phase (0.42–0.80)
                        batch_frac = event.get("progress_percent", 0) / 100
                        sub_pct = _EMBED_START + batch_frac * (_EMBED_END - _EMBED_START)
                        log_lines.append(f"    {detail}")
                    else:
                        sub_pct = _STEP_PCT.get(ev_step, 0)
                        log_lines.append(f"  {detail}")

                    pct = int(base_pct + upload_share + sub_pct * stream_share)
                    yield _progress_html(pct, f"[{i}/{total}] {detail}"), "\n".join(log_lines)

                    if ev_step == "done":
                        total_chunks += event.get("chunks_stored", 0)
                        total_embeddings += event.get("embeddings_computed", 0)
                        success_count += 1

            total_elapsed = time.time() - total_start
            log_lines.append(
                f"\nИтого: {success_count}/{total} файлов, "
                f"{total_chunks} чанков, {total_elapsed:.1f} сек"
            )
            yield _progress_html(100, f"Готово — {success_count}/{total} файлов"), "\n".join(log_lines)

        def list_documents():
            """Fetch document list from API. Returns table rows + dropdown choices."""
            try:
                response = requests.get(f"{api_url}/documents/", timeout=10)
                response.raise_for_status()
                data = response.json()

                rows = []
                choices = []
                for doc in data.get("documents", []):
                    doc_id = doc.get("id", "неизвестно")
                    filename = os.path.basename(doc.get("source_path", ""))
                    chunks = doc.get("chunk_count", 0)
                    rows.append([
                        doc_id,
                        chunks,
                        filename,
                        doc.get("document_type", ""),
                        doc.get("language", ""),
                    ])
                    label = f"{doc_id} — {filename} ({chunks} чанков)" if filename else doc_id
                    choices.append(label)

                return rows, gr.update(choices=choices, value=None)
            except Exception as e:
                logger.error(f"List error: {e}")
                return [], gr.update(choices=[], value=None)

        def get_stats():
            """Fetch index stats."""
            try:
                response = requests.get(f"{api_url}/documents/stats", timeout=10)
                response.raise_for_status()
                data = response.json()

                vs = data.get("vector_store", {})
                gs = data.get("graph_store", {})

                nodes = gs.get("node_count", gs.get("entity_count", 0))
                edges = gs.get("edge_count", gs.get("relation_count", 0))
                lines = [
                    "**Статистика индекса**",
                    f"- Векторное хранилище: **{vs.get('document_count', 0)}** чанков",
                    f"- Граф знаний: **{nodes}** сущностей, **{edges}** связей",
                ]
                return "\n".join(lines)
            except Exception as e:
                return f"**Ошибка:** {e}"

        def delete_doc(doc_id: str):
            """Delete a document by ID, then refresh list and dropdown."""
            if not doc_id or not doc_id.strip():
                return "Выберите документ для удаления.", gr.update(), gr.update()
            # Dropdown value is "doc_id — filename (N чанков)", extract ID
            actual_id = doc_id.split(" — ")[0].strip()
            try:
                response = requests.delete(
                    f"{api_url}/documents/{actual_id}",
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                msg = f"Удалено {data.get('deleted_chunks', 0)} чанков документа {actual_id}"
            except Exception as e:
                msg = f"Ошибка: {e}"

            # Refresh document list and dropdown after delete
            rows, dropdown_update = list_documents()
            return msg, rows, dropdown_update

        def reindex_all(
            loader: str,
            graph: bool,
            ctx: bool,
            pc: bool,
            rapt: bool,
            summ: bool,
            imgs: bool = True,
        ):
            """Re-index ALL PDF files from the upload directory (not just indexed ones)."""
            # Get all PDF files on disk (not from vector store!)
            try:
                resp = requests.get(f"{api_url}/documents/files", timeout=10)
                resp.raise_for_status()
                files = resp.json().get("files", [])
            except Exception as e:
                yield _progress_html(0, "Ошибка"), f"Не удалось получить список файлов: {e}"
                return

            if not files:
                yield _progress_html(0), "Нет PDF файлов в папке загрузок."
                return

            total = len(files)
            log_lines = [f"Найдено PDF файлов на диске: {total}"]
            log_lines.extend(_format_options(loader, graph, ctx, pc, rapt, summ, imgs))

            loader_value = "default"
            if loader == "auto (smart)":
                loader_value = "smart"
            elif loader in ["pymupdf", "docling", "pymupdf4llm"]:
                loader_value = loader

            file_step = 100 / total
            yield _progress_html(0, "Начало переиндексации..."), "\n".join(log_lines)

            total_chunks = 0
            success_count = 0
            total_start = time.time()

            for i, file_info in enumerate(files, 1):
                file_path = file_info["file_path"]
                filename = file_info["filename"]
                base_pct = (i - 1) * file_step

                log_lines.append(f"\n[{i}/{total}] {filename}")
                yield _progress_html(int(base_pct), f"[{i}/{total}] {filename}"), "\n".join(log_lines)

                # Stream index with live logging
                payload = {
                    "file_path": file_path,
                    "loader": loader_value,
                    "build_graph": graph,
                    "contextual": ctx,
                    "parent_child": pc,
                    "raptor": rapt,
                    "summarize": summ,
                    "extract_images": imgs,
                }
                for event in _iter_stream(payload):
                    ev_step = event.get("step", "")
                    detail = event.get("detail", "")

                    if ev_step == "batch":
                        batch_frac = event.get("progress_percent", 0) / 100
                        sub_pct = _EMBED_START + batch_frac * (_EMBED_END - _EMBED_START)
                        log_lines.append(f"    {detail}")
                    else:
                        sub_pct = _STEP_PCT.get(ev_step, 0)
                        log_lines.append(f"  {detail}")

                    pct = int(base_pct + sub_pct * file_step)
                    yield _progress_html(pct, f"[{i}/{total}] {detail}"), "\n".join(log_lines)

                    if ev_step == "done":
                        total_chunks += event.get("chunks_stored", 0)
                        success_count += 1

            total_elapsed = time.time() - total_start
            log_lines.append(
                f"\nИтого: {success_count}/{total} файлов, "
                f"{total_chunks} чанков, {total_elapsed:.1f} сек"
            )
            yield _progress_html(100, f"Готово — {success_count}/{total} файлов"), "\n".join(log_lines)

        def incremental_index(
            loader: str,
            graph: bool,
            ctx: bool,
            pc: bool,
            rapt: bool,
            summ: bool,
            imgs: bool = True,
        ):
            """Index only NEW (not yet indexed) PDF files."""
            # Get all files on disk
            try:
                resp = requests.get(f"{api_url}/documents/files", timeout=10)
                resp.raise_for_status()
                all_files = resp.json().get("files", [])
            except Exception as e:
                yield _progress_html(0, "Ошибка"), f"Не удалось получить список файлов: {e}"
                return

            # Get already indexed documents
            try:
                resp = requests.get(f"{api_url}/documents/", timeout=30)
                resp.raise_for_status()
                indexed_docs = resp.json().get("documents", [])
                indexed_sources = {doc.get("source_path", "") for doc in indexed_docs}
            except Exception:
                indexed_sources = set()

            # Filter to only new files
            new_files = [
                f for f in all_files
                if f["file_path"] not in indexed_sources
            ]

            if not new_files:
                yield _progress_html(100, "Всё проиндексировано"), (
                    f"Все {len(all_files)} PDF уже проиндексированы. "
                    "Для полной переиндексации используйте кнопку 'Переиндексировать все'."
                )
                return

            total = len(new_files)
            log_lines = [
                f"Всего PDF на диске: {len(all_files)}",
                f"Уже проиндексировано: {len(indexed_sources)}",
                f"Новых файлов: {total}",
            ]
            log_lines.extend(_format_options(loader, graph, ctx, pc, rapt, summ, imgs))

            loader_value = "default"
            if loader == "auto (smart)":
                loader_value = "smart"
            elif loader in ["pymupdf", "docling", "pymupdf4llm"]:
                loader_value = loader

            file_step = 100 / total
            yield _progress_html(0, "Начало доиндексации..."), "\n".join(log_lines)

            total_chunks = 0
            success_count = 0
            total_start = time.time()

            for i, file_info in enumerate(new_files, 1):
                file_path = file_info["file_path"]
                filename = file_info["filename"]
                base_pct = (i - 1) * file_step

                log_lines.append(f"\n[{i}/{total}] {filename}")
                yield _progress_html(int(base_pct), f"[{i}/{total}] {filename}"), "\n".join(log_lines)

                payload = {
                    "file_path": file_path,
                    "loader": loader_value,
                    "build_graph": graph,
                    "contextual": ctx,
                    "parent_child": pc,
                    "raptor": rapt,
                    "summarize": summ,
                    "extract_images": imgs,
                }
                for event in _iter_stream(payload):
                    ev_step = event.get("step", "")
                    detail = event.get("detail", "")

                    if ev_step == "batch":
                        batch_frac = event.get("progress_percent", 0) / 100
                        sub_pct = _EMBED_START + batch_frac * (_EMBED_END - _EMBED_START)
                        log_lines.append(f"    {detail}")
                    else:
                        sub_pct = _STEP_PCT.get(ev_step, 0)
                        log_lines.append(f"  {detail}")

                    pct = int(base_pct + sub_pct * file_step)
                    yield _progress_html(pct, f"[{i}/{total}] {detail}"), "\n".join(log_lines)

                    if ev_step == "done":
                        total_chunks += event.get("chunks_stored", 0)
                        success_count += 1

            total_elapsed = time.time() - total_start
            log_lines.append(
                f"\nИтого: {success_count}/{total} новых файлов, "
                f"{total_chunks} чанков, {total_elapsed:.1f} сек"
            )
            yield _progress_html(100, f"Готово — {success_count}/{total} файлов"), "\n".join(log_lines)

        def show_structure(doc_id: str):
            """Fetch and display document ToC structure as Markdown."""
            if not doc_id or not doc_id.strip():
                return "Выберите документ из выпадающего списка ниже, затем нажмите 'Структура (ToC)'."
            actual_id = doc_id.split(" — ")[0].strip()
            try:
                resp = requests.get(
                    f"{api_url}/toc/{actual_id}",
                    timeout=30,
                )
                if resp.status_code == 404:
                    return f"Документ `{actual_id}` не найден или не содержит разделов."
                resp.raise_for_status()
                data = resp.json()

                lines = [
                    f"**Структура документа** ({data.get('total_sections', 0)} разделов, "
                    f"{data.get('total_chunks', 0)} чанков, "
                    f"{data.get('summaries_available', 0)} саммари)\n",
                ]

                def _render_tree(nodes, indent=0):
                    for node in nodes:
                        prefix = "  " * indent + "- "
                        num = node.get("number", "")
                        title = node.get("title", "")
                        chunks = node.get("chunk_count", 0)
                        pages = ""
                        if node.get("page_start"):
                            if node.get("page_end") and node["page_end"] != node["page_start"]:
                                pages = f" (стр. {node['page_start']}–{node['page_end']})"
                            else:
                                pages = f" (стр. {node['page_start']})"
                        label = f"**{num}.** {title}" if title else f"**{num}.**"
                        lines.append(f"{prefix}{label} [{chunks} чанков]{pages}")
                        _render_tree(node.get("children", []), indent + 1)

                _render_tree(data.get("tree", []))
                return "\n".join(lines)

            except Exception as e:
                return f"**Ошибка:** {e}"

        def rebuild_bm25():
            """Rebuild BM25 FTS5 index from current Qdrant data."""
            try:
                resp = requests.post(
                    f"{api_url}/documents/rebuild-bm25",
                    timeout=300,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return (
                        f"BM25 пересобран: {data.get('old_count', '?')} → {data.get('new_count', '?')} чанков "
                        f"за {data.get('elapsed_seconds', '?')} сек"
                    )
                else:
                    return f"Ошибка: {resp.status_code} — {resp.text}"
            except Exception as e:
                return f"Ошибка: {e}"

        def build_communities():
            """Run Leiden community detection + LLM summarization."""
            try:
                resp = requests.post(
                    f"{api_url}/graph/build-communities",
                    timeout=600,  # Can be slow with many LLM calls
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return (
                        f"**Кластеризация графа завершена**\n\n"
                        f"- Обнаружено кластеров: **{data.get('communities_detected', '?')}**\n"
                        f"- Сущностей распределено: **{data.get('entities_assigned', '?')}**\n"
                        f"- Саммари сгенерировано: **{data.get('summaries_generated', '?')}**\n"
                        f"- Средний размер кластера: **{data.get('avg_community_size', '?')}**\n"
                        f"- Макс. размер кластера: **{data.get('max_community_size', '?')}**\n\n"
                        f"GraphRAG Global теперь доступен для поиска."
                    )
                else:
                    return f"**Ошибка:** {resp.status_code} — {resp.text}"
            except Exception as e:
                return f"**Ошибка:** {e}"

        # --- Wire up events ---
        index_btn.click(
            index_document,
            [file_upload, loader_choice, build_graph, contextual, parent_child, raptor, summarize, extract_images],
            [progress_bar, progress_log],
        )

        incremental_btn.click(
            incremental_index,
            [loader_choice, build_graph, contextual, parent_child, raptor, summarize, extract_images],
            [progress_bar, progress_log],
        )

        reindex_btn.click(
            reindex_all,
            [loader_choice, build_graph, contextual, parent_child, raptor, summarize, extract_images],
            [progress_bar, progress_log],
        )

        refresh_btn.click(list_documents, None, [docs_df, delete_id])
        stats_btn.click(get_stats, None, [stats_box])
        structure_btn.click(show_structure, [delete_id], [stats_box])
        rebuild_bm25_btn.click(rebuild_bm25, None, [stats_box])
        build_communities_btn.click(build_communities, None, [stats_box])
        delete_btn.click(delete_doc, [delete_id], [delete_result, docs_df, delete_id])

        # Initial load
        if app is not None:
            app.load(list_documents, None, [docs_df, delete_id])

    return page
