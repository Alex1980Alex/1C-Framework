"""Settings page for Gradio UI (UX v2).

Improvements:
- Confirmation dialogs for all destructive actions
- Visual health status indicators (colored dots)
- Error handling with gr.Info/Warning/Error
"""

import logging
import os
import subprocess
import sys

import gradio as gr
import requests

logger = logging.getLogger(__name__)

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
                health_info = gr.HTML("<p><em>Загрузка...</em></p>")
                check_health_btn = gr.Button("Проверить")

            with gr.Tab("Очистка данных"):
                gr.Markdown(
                    "**Внимание:** очистка хранилищ необратима. "
                    "Будут удалены все чанки, граф знаний и кэш. "
                    "После очистки потребуется переиндексация документов."
                )
                data_result = gr.Markdown("")
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
            except requests.ConnectionError:
                return "**API сервер недоступен.** Запустите backend: `make api`"
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
            except requests.ConnectionError:
                return "**API сервер недоступен.** Запустите backend: `make api`"
            except Exception as e:
                return f"**Ошибка:** {e}"

        def check_health():
            """Check health with visual status indicators."""
            try:
                response = requests.get(f"{api_url}/health", timeout=10)
                response.raise_for_status()
                data = response.json()

                raw_status = data.get("status", "")
                is_healthy = raw_status in ("healthy", "unknown", "ok", "up")

                # Build HTML with status dots
                status_color = "#22c55e" if is_healthy else "#ef4444"
                status_text = "Работает" if is_healthy else "Проблемы"

                html_parts = [
                    f'<div style="margin-bottom:12px;">'
                    f'<span class="status-dot" style="display:inline-block;width:12px;height:12px;'
                    f'border-radius:50%;background:{status_color};margin-right:8px;"></span>'
                    f'<strong>Состояние системы: {status_text}</strong></div>',
                    '<div style="margin-top:8px;"><strong>Компоненты:</strong><ul style="list-style:none;padding-left:0;">',
                ]

                checks = data.get("checks", {})
                for k, v in checks.items():
                    ok = v.get("status") in ("ok", "up", "healthy")
                    dot_color = "#22c55e" if ok else "#ef4444"
                    label = "OK" if ok else "ОШИБКА"
                    extra = ""
                    if k == "vector_store" and v.get("document_count") is not None:
                        extra = f" ({v['document_count']} чанков)"
                    elif k == "graph_store":
                        extra = f" ({v.get('entity_count', 0)} сущностей)"
                    elif k == "llm":
                        extra = f" ({v.get('model', '')})"
                    elif k == "disk_space":
                        free = v.get('free_gb', 0)
                        extra = f" (свободно {free:.0f} ГБ)" if isinstance(free, (int, float)) else ""

                    html_parts.append(
                        f'<li style="padding:4px 0;">'
                        f'<span style="display:inline-block;width:10px;height:10px;'
                        f'border-radius:50%;background:{dot_color};margin-right:8px;"></span>'
                        f'{k}: {label}{extra}</li>'
                    )

                html_parts.append('</ul></div>')
                return "".join(html_parts)

            except requests.ConnectionError:
                return (
                    '<div style="padding:12px;">'
                    '<span style="display:inline-block;width:12px;height:12px;'
                    'border-radius:50%;background:#ef4444;margin-right:8px;"></span>'
                    '<strong>API сервер недоступен.</strong> Запустите backend: <code>make api</code></div>'
                )
            except Exception as e:
                return f'<div style="padding:12px;"><strong>Ошибка:</strong> {e}</div>'

        def reset_all_data():
            results = []
            try:
                resp = requests.delete(f"{api_url}/documents/clear", timeout=60)
                resp.raise_for_status()
                chunks = resp.json().get("cleared_chunks", 0)
                results.append(f"Вектор: {chunks} чанков удалено")
            except Exception as e:
                results.append(f"Вектор: ошибка — {e}")
            try:
                resp = requests.delete(f"{api_url}/graph/clear", timeout=60)
                resp.raise_for_status()
                data = resp.json()
                results.append(f"Граф: {data.get('deleted_nodes', 0)} сущностей удалено")
            except Exception as e:
                results.append(f"Граф: ошибка — {e}")
            try:
                resp = requests.post(f"{api_url}/cache/clear", timeout=30)
                resp.raise_for_status()
                cleared = resp.json().get("cleared", 0)
                results.append(f"Кэш: {cleared} записей удалено")
            except Exception as e:
                results.append(f"Кэш: ошибка — {e}")
            gr.Info("Полный сброс завершён")
            return "**Сброс завершён:**\n- " + "\n- ".join(results)

        def restart_server():
            """Restart the UI server."""
            logger.info("UI restart requested by user")
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

        # --- JS confirmations ---
        reset_all_confirm_js = """
        () => {
            if (!confirm('СБРОСИТЬ ВСЕ ДАННЫЕ?\\n\\nБудут удалены:\\n- Все чанки из векторного хранилища\\n- Все сущности и связи из графа\\n- Весь кэш\\n\\nЭто действие необратимо!')) {
                throw new Error('cancelled');
            }
        }
        """

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
        reset_all_btn.click(reset_all_data, None, [data_result], js=reset_all_confirm_js)
        restart_btn.click(restart_server, None, None, js=restart_js)

        if app is not None:
            app.load(
                lambda: (load_stats(), load_config(), load_cache(), check_health()),
                None,
                [stats_info, config_json, cache_info, health_info],
            )

    return page
