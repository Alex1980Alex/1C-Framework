"""Settings page for Gradio UI (Phase 14.1) — Russian localization."""

import logging
import os
import subprocess
import sys

import gradio as gr
import requests

logger = logging.getLogger(__name__)

# Exit code that signals "restart requested" to the wrapper script
RESTART_EXIT_CODE = 42


def create_settings_page(api_url: str, app: gr.Blocks | None = None):
    """Create settings and statistics page."""

    with gr.Column() as page:
        gr.Markdown(
            "### Настройки и мониторинг\n"
            "Просмотр статистики, конфигурации, состояния кэша и здоровья системы."
        )

        with gr.Tabs():
            with gr.Tab("Статистика"):
                stats_info = gr.Markdown("*Загрузка...*")
                refresh_stats_btn = gr.Button("Обновить")

            with gr.Tab("Конфигурация"):
                gr.Markdown(
                    "*Текущие настройки фреймворка. "
                    "Изменяются через `.env` файл или переменные окружения.*"
                )
                config_json = gr.JSON(label="Текущая конфигурация")

            with gr.Tab("Кэш"):
                cache_info = gr.Markdown("*Загрузка...*")

            with gr.Tab("Здоровье системы"):
                health_info = gr.Markdown("*Загрузка...*")
                check_health_btn = gr.Button("Проверить")

            with gr.Tab("Очистка данных"):
                gr.Markdown(
                    "Очистка хранилищ данных. "
                    "После очистки нужно переиндексировать документы."
                )
                data_result = gr.Markdown("")
                with gr.Row():
                    clear_vectors_btn = gr.Button(
                        "Очистить векторное хранилище", variant="stop",
                    )
                    clear_graph_btn = gr.Button(
                        "Очистить граф знаний", variant="stop",
                    )
                    clear_cache_btn = gr.Button(
                        "Очистить кэш", variant="stop",
                    )
                reset_all_btn = gr.Button(
                    "Сбросить всё (вектор + граф + кэш)", variant="stop", size="lg",
                )

            with gr.Tab("Сервер"):
                gr.Markdown(
                    "### Управление UI сервером\n"
                    "Перезапустите сервер после изменения кода или конфигурации. "
                    "Страница обновится автоматически."
                )
                restart_btn = gr.Button(
                    "Перезапустить UI сервер",
                    variant="primary",
                    size="lg",
                )
                gr.HTML('<p id="restart_countdown" style="color:#666; font-style:italic;"></p>')

        def load_stats():
            try:
                response = requests.get(f"{api_url}/documents/stats", timeout=10)
                response.raise_for_status()
                data = response.json()

                vs = data.get("vector_store", {})
                gs = data.get("graph_store", {})
                nodes = gs.get("node_count", gs.get("entity_count", 0))
                edges = gs.get("edge_count", gs.get("relation_count", 0))

                return (
                    "**Статистика индекса:**\n"
                    f"- Чанков в векторном хранилище: **{vs.get('document_count', 0)}**\n"
                    f"- Сущностей в графе: **{nodes}**\n"
                    f"- Связей в графе: **{edges}**"
                )
            except Exception as e:
                return f"**Ошибка:** {e}"

        def load_config():
            try:
                response = requests.get(f"{api_url}/config", timeout=10)
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "embedding": {"provider": "local", "model": "all-MiniLM-L6-v2"},
                        "vector_store": {"provider": "chroma"},
                        "graph_store": {"provider": "networkx"},
                        "info": "Эндпоинт /config не доступен. Показаны значения по умолчанию.",
                    }
            except Exception as e:
                return {"error": str(e)}

        def load_cache():
            try:
                response = requests.get(f"{api_url}/cache/stats", timeout=10)
                response.raise_for_status()
                data = response.json()

                return (
                    "**Статистика кэша:**\n"
                    f"- Кэш эмбеддингов (hit rate): {data.get('embedding', {}).get('hit_rate', 'н/д')}\n"
                    f"- Кэш LLM (hit rate): {data.get('llm', {}).get('hit_rate', 'н/д')}\n"
                    f"- Кэш документов: {data.get('document', {}).get('entries', 'н/д')} записей"
                )
            except Exception as e:
                return f"**Ошибка:** {e}"

        def check_health():
            try:
                response = requests.get(f"{api_url}/health", timeout=10)
                response.raise_for_status()
                data = response.json()

                raw_status = data.get("status", "")
                is_healthy = raw_status in ("healthy", "unknown", "ok", "up")
                status = "Работает" if is_healthy else "Проблемы"

                checks = data.get("checks", {})
                check_lines = []
                for k, v in checks.items():
                    ok = v.get("status") in ("ok", "up", "healthy")
                    label = "OK" if ok else "ОШИБКА"
                    extra = ""
                    if k == "vector_store" and v.get("document_count") is not None:
                        extra = f" ({v['document_count']} чанков)"
                    elif k == "graph_store":
                        extra = f" ({v.get('entity_count', 0)} сущностей)"
                    elif k == "llm":
                        extra = f" ({v.get('model', '')})"
                    elif k == "disk_space":
                        extra = f" (свободно {v.get('free_gb', 0):.0f} ГБ)"
                    check_lines.append(f"- {k}: {label}{extra}")

                return (
                    f"**Состояние системы:** {status}\n\n"
                    "**Компоненты:**\n" + "\n".join(check_lines) if check_lines
                    else f"**Состояние системы:** {status}"
                )
            except Exception as e:
                return f"**Ошибка:** {e}"

        def clear_cache():
            try:
                response = requests.post(f"{api_url}/cache/clear", timeout=30)
                response.raise_for_status()
                data = response.json()
                return f"**Кэш очищен:** {data.get('cleared', 0)} записей удалено"
            except Exception as e:
                return f"**Ошибка:** {e}"

        def clear_vectors():
            try:
                resp = requests.delete(f"{api_url}/documents/clear", timeout=60)
                resp.raise_for_status()
                data = resp.json()
                return f"**Векторное хранилище очищено:** удалено {data.get('cleared_chunks', 0)} чанков"
            except Exception as e:
                return f"**Ошибка:** {e}"

        def clear_graph_data():
            try:
                resp = requests.delete(f"{api_url}/graph/clear", timeout=60)
                resp.raise_for_status()
                data = resp.json()
                nodes = data.get("deleted_nodes", 0)
                edges = data.get("deleted_edges", 0)
                return f"**Граф очищен:** удалено {nodes} сущностей, {edges} связей"
            except Exception as e:
                return f"**Ошибка:** {e}"

        def reset_all_data():
            results = []
            # 1. Vector store
            try:
                resp = requests.delete(f"{api_url}/documents/clear", timeout=60)
                resp.raise_for_status()
                chunks = resp.json().get("cleared_chunks", 0)
                results.append(f"Вектор: {chunks} чанков удалено")
            except Exception as e:
                results.append(f"Вектор: ошибка — {e}")
            # 2. Graph
            try:
                resp = requests.delete(f"{api_url}/graph/clear", timeout=60)
                resp.raise_for_status()
                data = resp.json()
                results.append(f"Граф: {data.get('deleted_nodes', 0)} сущностей удалено")
            except Exception as e:
                results.append(f"Граф: ошибка — {e}")
            # 3. Cache
            try:
                resp = requests.post(f"{api_url}/cache/clear", timeout=30)
                resp.raise_for_status()
                cleared = resp.json().get("cleared", 0)
                results.append(f"Кэш: {cleared} записей удалено")
            except Exception as e:
                results.append(f"Кэш: ошибка — {e}")
            return "**Сброс завершён:**\n- " + "\n- ".join(results)

        def restart_server():
            """Restart the UI server: spawn a new process, then exit."""
            logger.info("UI restart requested by user")

            # Build a command that waits for port to free, then starts UI
            python = sys.executable
            cwd = os.getcwd()
            no_window = (
                subprocess.CREATE_NEW_PROCESS_GROUP
                | subprocess.CREATE_NO_WINDOW
            )
            restart_script = (
                "import time, subprocess;"
                "time.sleep(3);"
                f"subprocess.Popen([r'{python}', '-m', 'src.ui.app'],"
                f" cwd=r'{cwd}',"
                f" creationflags={no_window})"
            )

            def _do_restart():
                import time
                # Spawn a helper that will outlive us and start the server silently
                subprocess.Popen(
                    [python, "-c", restart_script],
                    creationflags=no_window,
                    close_fds=True,
                )
                time.sleep(0.5)
                os._exit(RESTART_EXIT_CODE)

            import threading
            threading.Thread(target=_do_restart, daemon=True).start()
            return

        # JS: countdown timer then auto-refresh the page
        restart_js = """
        () => {
            let sec = 7;
            const el = document.querySelector('#restart_countdown');
            if (el) {
                const timer = setInterval(() => {
                    sec--;
                    el.textContent = 'Перезапуск... Страница обновится через ' + sec + ' сек.';
                    if (sec <= 0) {
                        clearInterval(timer);
                        el.textContent = 'Обновление страницы...';
                        location.reload();
                    }
                }, 1000);
            } else {
                setTimeout(() => location.reload(), 7000);
            }
        }
        """

        refresh_stats_btn.click(load_stats, None, [stats_info])
        check_health_btn.click(check_health, None, [health_info])
        clear_vectors_btn.click(clear_vectors, None, [data_result])
        clear_graph_btn.click(clear_graph_data, None, [data_result])
        clear_cache_btn.click(clear_cache, None, [data_result])
        reset_all_btn.click(reset_all_data, None, [data_result])
        restart_btn.click(restart_server, None, None, js=restart_js)

        if app is not None:
            app.load(
                lambda: (load_stats(), load_config(), load_cache(), check_health()),
                None,
                [stats_info, config_json, cache_info, health_info],
            )

    return page
