#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL HTML Visualizer - визуализация результатов анализа BSL кода в HTML
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import html
import json


@dataclass
class HtmlReportConfig:
    """Конфигурация HTML отчёта"""
    title: str = "BSL Analysis Report"
    include_source: bool = True
    include_metrics: bool = True
    include_dependencies: bool = True
    include_warnings: bool = True
    theme: str = "light"  # light, dark


class BslHtmlVisualizer:
    """Генератор HTML отчётов для BSL анализа"""

    CSS_STYLES = """
    :root {
        --bg-color: #ffffff;
        --text-color: #333333;
        --border-color: #e0e0e0;
        --header-bg: #f5f5f5;
        --code-bg: #f8f8f8;
        --success-color: #4caf50;
        --warning-color: #ff9800;
        --error-color: #f44336;
        --info-color: #2196f3;
        --added-bg: #e6ffe6;
        --removed-bg: #ffe6e6;
        --modified-bg: #fff3e0;
    }

    [data-theme="dark"] {
        --bg-color: #1e1e1e;
        --text-color: #d4d4d4;
        --border-color: #404040;
        --header-bg: #2d2d2d;
        --code-bg: #252526;
        --added-bg: #1e3a1e;
        --removed-bg: #3a1e1e;
        --modified-bg: #3a3a1e;
    }

    * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }

    body {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
        background-color: var(--bg-color);
        color: var(--text-color);
        line-height: 1.6;
        padding: 20px;
    }

    .container {
        max-width: 1400px;
        margin: 0 auto;
    }

    header {
        background: var(--header-bg);
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }

    h1, h2, h3, h4 {
        margin-bottom: 15px;
    }

    h1 { font-size: 2em; }
    h2 { font-size: 1.5em; border-bottom: 2px solid var(--border-color); padding-bottom: 10px; }
    h3 { font-size: 1.2em; }

    .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
        margin-bottom: 20px;
    }

    .summary-card {
        background: var(--header-bg);
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }

    .summary-card .value {
        font-size: 2em;
        font-weight: bold;
    }

    .summary-card .label {
        color: var(--text-color);
        opacity: 0.7;
    }

    .summary-card.success .value { color: var(--success-color); }
    .summary-card.warning .value { color: var(--warning-color); }
    .summary-card.error .value { color: var(--error-color); }
    .summary-card.info .value { color: var(--info-color); }

    section {
        background: var(--header-bg);
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 15px;
    }

    th, td {
        padding: 12px;
        text-align: left;
        border-bottom: 1px solid var(--border-color);
    }

    th {
        background: var(--code-bg);
        font-weight: 600;
    }

    tr:hover {
        background: var(--code-bg);
    }

    .code-block {
        background: var(--code-bg);
        padding: 15px;
        border-radius: 4px;
        overflow-x: auto;
        font-family: 'Fira Code', 'Consolas', monospace;
        font-size: 0.9em;
        white-space: pre-wrap;
        margin: 10px 0;
    }

    .line-number {
        color: #666;
        user-select: none;
        padding-right: 15px;
        min-width: 40px;
        display: inline-block;
        text-align: right;
    }

    .diff-added {
        background: var(--added-bg);
        display: block;
    }

    .diff-removed {
        background: var(--removed-bg);
        display: block;
    }

    .diff-modified {
        background: var(--modified-bg);
        display: block;
    }

    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: 500;
    }

    .badge-success { background: var(--success-color); color: white; }
    .badge-warning { background: var(--warning-color); color: white; }
    .badge-error { background: var(--error-color); color: white; }
    .badge-info { background: var(--info-color); color: white; }

    .warning-list {
        list-style: none;
    }

    .warning-list li {
        padding: 10px;
        margin: 5px 0;
        border-left: 4px solid var(--warning-color);
        background: var(--code-bg);
        border-radius: 0 4px 4px 0;
    }

    .warning-list li.error {
        border-left-color: var(--error-color);
    }

    .collapsible {
        cursor: pointer;
        user-select: none;
    }

    .collapsible::before {
        content: '▶ ';
    }

    .collapsible.active::before {
        content: '▼ ';
    }

    .content {
        display: none;
        padding-top: 15px;
    }

    .content.show {
        display: block;
    }

    .dependency-graph {
        background: var(--code-bg);
        padding: 20px;
        border-radius: 4px;
        text-align: center;
    }

    .metrics-bar {
        height: 20px;
        background: var(--border-color);
        border-radius: 10px;
        overflow: hidden;
        margin: 5px 0;
    }

    .metrics-bar-fill {
        height: 100%;
        transition: width 0.3s ease;
    }

    .metrics-bar-fill.low { background: var(--success-color); }
    .metrics-bar-fill.medium { background: var(--warning-color); }
    .metrics-bar-fill.high { background: var(--error-color); }

    footer {
        text-align: center;
        padding: 20px;
        color: var(--text-color);
        opacity: 0.6;
        font-size: 0.9em;
    }

    @media (max-width: 768px) {
        .summary-grid {
            grid-template-columns: repeat(2, 1fr);
        }

        table {
            font-size: 0.9em;
        }

        th, td {
            padding: 8px;
        }
    }
    """

    JS_SCRIPT = """
    document.addEventListener('DOMContentLoaded', function() {
        // Collapsible sections
        var coll = document.getElementsByClassName('collapsible');
        for (var i = 0; i < coll.length; i++) {
            coll[i].addEventListener('click', function() {
                this.classList.toggle('active');
                var content = this.nextElementSibling;
                content.classList.toggle('show');
            });
        }

        // Theme toggle
        var themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', function() {
                var body = document.body;
                var currentTheme = body.getAttribute('data-theme');
                body.setAttribute('data-theme', currentTheme === 'dark' ? 'light' : 'dark');
            });
        }
    });
    """

    def __init__(self, config: HtmlReportConfig = None):
        """
        Args:
            config: Конфигурация отчёта
        """
        self.config = config or HtmlReportConfig()

    def generate_diff_report(
        self,
        diff_result: Dict,
        file1_content: str = "",
        file2_content: str = "",
        output_path: Path = None
    ) -> str:
        """
        Генерация HTML отчёта сравнения файлов

        Args:
            diff_result: Результат сравнения (BslDiffResult как dict)
            file1_content: Содержимое первого файла
            file2_content: Содержимое второго файла
            output_path: Путь для сохранения отчёта

        Returns:
            HTML строка
        """
        sections = []

        # Summary
        added = diff_result.get('added_symbols', [])
        removed = diff_result.get('removed_symbols', [])
        modified = diff_result.get('modified_symbols', [])

        sections.append(self._generate_summary_section({
            'Добавлено': (len(added), 'success'),
            'Удалено': (len(removed), 'error'),
            'Изменено': (len(modified), 'warning'),
            'Всего изменений': (len(added) + len(removed) + len(modified), 'info')
        }))

        # Changes table
        if added or removed or modified:
            sections.append(self._generate_changes_table(added, removed, modified))

        # Source diff
        if self.config.include_source and (file1_content or file2_content):
            sections.append(self._generate_source_diff(file1_content, file2_content))

        html_content = self._wrap_html(
            title="BSL Diff Report",
            sections=sections
        )

        if output_path:
            output_path.write_text(html_content, encoding='utf-8')

        return html_content

    def generate_analysis_report(
        self,
        analysis_results: Dict,
        output_path: Path = None
    ) -> str:
        """
        Генерация HTML отчёта анализа

        Args:
            analysis_results: Результаты анализа (словарь с функциями)
            output_path: Путь для сохранения

        Returns:
            HTML строка
        """
        sections = []

        # Summary statistics
        total_functions = len(analysis_results)
        total_warnings = sum(len(f.get('warnings', [])) for f in analysis_results.values())
        total_complexity = sum(
            f.get('complexity_metrics', {}).get('cyclomatic_complexity', 0)
            for f in analysis_results.values()
        )
        avg_complexity = total_complexity / total_functions if total_functions > 0 else 0

        sections.append(self._generate_summary_section({
            'Функций': (total_functions, 'info'),
            'Предупреждений': (total_warnings, 'warning' if total_warnings > 0 else 'success'),
            'Общая сложность': (total_complexity, 'info'),
            'Средняя сложность': (f"{avg_complexity:.1f}", 'warning' if avg_complexity > 10 else 'success')
        }))

        # Functions table
        sections.append(self._generate_functions_table(analysis_results))

        # Warnings section
        if self.config.include_warnings:
            all_warnings = []
            for func_name, data in analysis_results.items():
                for warning in data.get('warnings', []):
                    all_warnings.append((func_name, warning))

            if all_warnings:
                sections.append(self._generate_warnings_section(all_warnings))

        # Metrics charts
        if self.config.include_metrics:
            sections.append(self._generate_metrics_section(analysis_results))

        html_content = self._wrap_html(
            title=self.config.title,
            sections=sections
        )

        if output_path:
            output_path.write_text(html_content, encoding='utf-8')

        return html_content

    def generate_dependency_report(
        self,
        dependency_graph: Dict,
        output_path: Path = None
    ) -> str:
        """
        Генерация HTML отчёта зависимостей

        Args:
            dependency_graph: Граф зависимостей
            output_path: Путь для сохранения

        Returns:
            HTML строка
        """
        sections = []

        modules = dependency_graph.get('modules', {})
        dependencies = dependency_graph.get('dependencies', [])

        # Summary
        sections.append(self._generate_summary_section({
            'Модулей': (len(modules), 'info'),
            'Зависимостей': (len(dependencies), 'info'),
            'Экспортных функций': (
                sum(len(m.get('exported_functions', [])) for m in modules.values()),
                'success'
            )
        }))

        # Modules table
        sections.append(self._generate_modules_table(modules))

        # Dependencies matrix
        if self.config.include_dependencies and dependencies:
            sections.append(self._generate_dependency_matrix(modules, dependencies))

        # Mermaid diagram
        sections.append(self._generate_mermaid_diagram(modules, dependencies))

        html_content = self._wrap_html(
            title="BSL Dependency Report",
            sections=sections
        )

        if output_path:
            output_path.write_text(html_content, encoding='utf-8')

        return html_content

    def _wrap_html(self, title: str, sections: List[str]) -> str:
        """Обёртка HTML документа"""
        return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>{self.CSS_STYLES}</style>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head>
<body data-theme="{self.config.theme}">
    <div class="container">
        <header>
            <h1>{html.escape(title)}</h1>
            <p>Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <button id="theme-toggle" class="badge badge-info">Сменить тему</button>
        </header>

        {''.join(sections)}

        <footer>
            <p>BSL Semantic Diff Tool | 1C-Enterprise Framework</p>
        </footer>
    </div>

    <script>{self.JS_SCRIPT}</script>
    <script>mermaid.initialize({{startOnLoad: true, theme: 'default'}});</script>
</body>
</html>"""

    def _generate_summary_section(self, stats: Dict[str, tuple]) -> str:
        """Генерация секции сводки"""
        cards = []
        for label, (value, style) in stats.items():
            cards.append(f"""
            <div class="summary-card {style}">
                <div class="value">{value}</div>
                <div class="label">{html.escape(label)}</div>
            </div>
            """)

        return f"""
        <section>
            <h2>Сводка</h2>
            <div class="summary-grid">
                {''.join(cards)}
            </div>
        </section>
        """

    def _generate_changes_table(
        self,
        added: List,
        removed: List,
        modified: List
    ) -> str:
        """Генерация таблицы изменений"""
        rows = []

        for item in added:
            name = item.get('name', item) if isinstance(item, dict) else str(item)
            rows.append(f"""
            <tr class="diff-added">
                <td><span class="badge badge-success">+</span></td>
                <td>{html.escape(name)}</td>
                <td>Добавлено</td>
            </tr>
            """)

        for item in removed:
            name = item.get('name', item) if isinstance(item, dict) else str(item)
            rows.append(f"""
            <tr class="diff-removed">
                <td><span class="badge badge-error">-</span></td>
                <td>{html.escape(name)}</td>
                <td>Удалено</td>
            </tr>
            """)

        for item in modified:
            name = item.get('name', item) if isinstance(item, dict) else str(item)
            rows.append(f"""
            <tr class="diff-modified">
                <td><span class="badge badge-warning">~</span></td>
                <td>{html.escape(name)}</td>
                <td>Изменено</td>
            </tr>
            """)

        return f"""
        <section>
            <h2>Изменения</h2>
            <table>
                <thead>
                    <tr>
                        <th style="width: 60px;">Тип</th>
                        <th>Символ</th>
                        <th style="width: 120px;">Статус</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </section>
        """

    def _generate_source_diff(self, content1: str, content2: str) -> str:
        """Генерация визуального diff исходного кода"""
        lines1 = content1.split('\n') if content1 else []
        lines2 = content2.split('\n') if content2 else []

        # Простое построчное сравнение
        diff_lines = []
        max_lines = max(len(lines1), len(lines2))

        for i in range(max_lines):
            line1 = lines1[i] if i < len(lines1) else None
            line2 = lines2[i] if i < len(lines2) else None

            if line1 == line2:
                diff_lines.append(f'<span class="line-number">{i+1}</span>{html.escape(line1 or "")}')
            elif line1 is None:
                diff_lines.append(f'<span class="diff-added"><span class="line-number">{i+1}</span>+ {html.escape(line2)}</span>')
            elif line2 is None:
                diff_lines.append(f'<span class="diff-removed"><span class="line-number">{i+1}</span>- {html.escape(line1)}</span>')
            else:
                diff_lines.append(f'<span class="diff-removed"><span class="line-number">{i+1}</span>- {html.escape(line1)}</span>')
                diff_lines.append(f'<span class="diff-added"><span class="line-number">{i+1}</span>+ {html.escape(line2)}</span>')

        return f"""
        <section>
            <h3 class="collapsible">Исходный код</h3>
            <div class="content">
                <div class="code-block">{'<br>'.join(diff_lines[:500])}</div>
                {f'<p><em>Показаны первые 500 строк...</em></p>' if len(diff_lines) > 500 else ''}
            </div>
        </section>
        """

    def _generate_functions_table(self, analysis_results: Dict) -> str:
        """Генерация таблицы функций"""
        rows = []

        for func_name, data in sorted(analysis_results.items()):
            metrics = data.get('complexity_metrics', {})
            cyclomatic = metrics.get('cyclomatic_complexity', 0)
            cognitive = metrics.get('cognitive_complexity', 0)
            lines = data.get('line_count', 0)
            warnings = len(data.get('warnings', []))

            complexity_class = 'success' if cyclomatic <= 10 else ('warning' if cyclomatic <= 20 else 'error')

            rows.append(f"""
            <tr>
                <td>{html.escape(func_name)}</td>
                <td><span class="badge badge-{complexity_class}">{cyclomatic}</span></td>
                <td>{cognitive}</td>
                <td>{lines}</td>
                <td><span class="badge badge-{'warning' if warnings > 0 else 'success'}">{warnings}</span></td>
            </tr>
            """)

        return f"""
        <section>
            <h2>Функции и процедуры</h2>
            <table>
                <thead>
                    <tr>
                        <th>Имя</th>
                        <th>Цикломатическая сложность</th>
                        <th>Когнитивная сложность</th>
                        <th>Строк</th>
                        <th>Предупреждения</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </section>
        """

    def _generate_warnings_section(self, warnings: List[tuple]) -> str:
        """Генерация секции предупреждений"""
        items = []
        for func_name, warning in warnings:
            is_error = 'высок' in warning.lower() or 'много' in warning.lower()
            items.append(f"""
            <li class="{'error' if is_error else ''}">
                <strong>{html.escape(func_name)}:</strong> {html.escape(warning)}
            </li>
            """)

        return f"""
        <section>
            <h2>Предупреждения</h2>
            <ul class="warning-list">
                {''.join(items)}
            </ul>
        </section>
        """

    def _generate_metrics_section(self, analysis_results: Dict) -> str:
        """Генерация секции метрик с графиками"""
        bars = []

        for func_name, data in sorted(analysis_results.items())[:20]:  # Топ 20
            metrics = data.get('complexity_metrics', {})
            complexity = metrics.get('cyclomatic_complexity', 0)
            max_complexity = 30
            width = min(100, (complexity / max_complexity) * 100)

            fill_class = 'low' if complexity <= 10 else ('medium' if complexity <= 20 else 'high')

            bars.append(f"""
            <div style="margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between;">
                    <span>{html.escape(func_name[:30])}</span>
                    <span>{complexity}</span>
                </div>
                <div class="metrics-bar">
                    <div class="metrics-bar-fill {fill_class}" style="width: {width}%"></div>
                </div>
            </div>
            """)

        return f"""
        <section>
            <h2>Метрики сложности</h2>
            {''.join(bars)}
        </section>
        """

    def _generate_modules_table(self, modules: Dict) -> str:
        """Генерация таблицы модулей"""
        rows = []

        for name, info in sorted(modules.items()):
            module_type = info.get('module_type', 'Unknown')
            exports = len(info.get('exported_functions', [])) + len(info.get('exported_procedures', []))
            lines = info.get('line_count', 0)

            rows.append(f"""
            <tr>
                <td>{html.escape(name)}</td>
                <td>{html.escape(module_type)}</td>
                <td>{exports}</td>
                <td>{lines}</td>
            </tr>
            """)

        return f"""
        <section>
            <h2>Модули</h2>
            <table>
                <thead>
                    <tr>
                        <th>Имя</th>
                        <th>Тип</th>
                        <th>Экспортов</th>
                        <th>Строк</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </section>
        """

    def _generate_dependency_matrix(self, modules: Dict, dependencies: List) -> str:
        """Генерация матрицы зависимостей"""
        module_names = sorted(modules.keys())[:15]  # Ограничиваем для читаемости

        # Строим матрицу
        dep_map = {}
        for dep in dependencies:
            from_m = dep.get('from_module', '')
            to_m = dep.get('to_module', '')
            if from_m in module_names and to_m in module_names:
                dep_map[(from_m, to_m)] = len(dep.get('locations', [1]))

        # Заголовок
        header_cells = '<th></th>' + ''.join(
            f'<th title="{html.escape(name)}">{html.escape(name[:3])}</th>'
            for name in module_names
        )

        # Строки
        rows = []
        for from_m in module_names:
            cells = [f'<td><strong>{html.escape(from_m[:15])}</strong></td>']
            for to_m in module_names:
                count = dep_map.get((from_m, to_m), 0)
                if count > 0:
                    cells.append(f'<td class="diff-modified" title="{from_m} → {to_m}">{count}</td>')
                elif from_m == to_m:
                    cells.append('<td style="background: var(--border-color);">-</td>')
                else:
                    cells.append('<td></td>')
            rows.append(f'<tr>{"".join(cells)}</tr>')

        return f"""
        <section>
            <h3 class="collapsible">Матрица зависимостей</h3>
            <div class="content">
                <table style="font-size: 0.8em;">
                    <thead><tr>{header_cells}</tr></thead>
                    <tbody>{''.join(rows)}</tbody>
                </table>
            </div>
        </section>
        """

    def _generate_mermaid_diagram(self, modules: Dict, dependencies: List) -> str:
        """Генерация Mermaid диаграммы зависимостей"""
        lines = ['graph LR']

        # Добавляем модули
        for name in list(modules.keys())[:20]:
            safe_name = name.replace(' ', '_').replace('-', '_')
            lines.append(f'    {safe_name}["{name}"]')

        # Добавляем связи
        seen = set()
        for dep in dependencies[:50]:
            from_m = dep.get('from_module', '').replace(' ', '_').replace('-', '_')
            to_m = dep.get('to_module', '').replace(' ', '_').replace('-', '_')
            key = (from_m, to_m)
            if key not in seen and from_m and to_m:
                lines.append(f'    {from_m} --> {to_m}')
                seen.add(key)

        mermaid_code = '\n'.join(lines)

        return f"""
        <section>
            <h2>Граф зависимостей</h2>
            <div class="dependency-graph">
                <div class="mermaid">
{mermaid_code}
                </div>
            </div>
        </section>
        """
