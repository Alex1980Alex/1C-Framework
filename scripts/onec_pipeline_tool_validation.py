#!/usr/bin/env python3
"""Валидатор presence_rate ВСЕГО инструментария 1С-пайплайна (каталог гл. 43.9).

Для каждого MCP-инструмента из каталога 43.9 считает **presence_rate** = доля 1С-сессий,
в которых он реально вызывался, по `data/hook-invocations.jsonl` (поле `tool` + `session`).
**1С-сессия** = сессия, где использован хотя бы один инструмент 1С-пайплайна (по серверным
префиксам) — самодостаточно (один лог, работает на исторических данных, без зависимости от
onec-toolgate-events). Группирует по 12 типам глав 43.9; на каждый тул — вердикт adoption:
  - rate >= HEAVY (0.5)  → "heavy" (частая практика);
  - 0 < rate < HEAVY     → "occasional";
  - rate == 0            → "unused" (за окно ни разу — кандидат на advisory-напоминание/удаление).
Плюс: per-category coverage и список observed-но-НЕ-в-каталоге тулов (пробелы 43.9).

Реализация — pure Python (как onec_toolgate_validation.py), без DuckDB: лог мал, знаменатель —
число сессий, не строк. Для тяжёлой SQL-аналитики над этим же логом см. scripts/audit_query.py.

⚠ CAVEAT (как ADR-035/036): presence_rate — карта **адопции** («кто реально используется»),
а НЕ мерило безопасности hard (survivorship). Высокий rate = сигнал к рассмотрению промоута,
низкий = кандидат усилить advisory; финальное решение о hard — ручное (применимость per-tool).

Запуск: python scripts/onec_pipeline_tool_validation.py [--json] [--window-days N] [--category 43.9.N] [--no-report]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from acceptance_common import emit as _emit
from acceptance_common import parse_dt as _parse_dt
from acceptance_common import read_jsonl as _read_jsonl

INVOCATIONS = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
HEAVY = 0.5  # presence_rate >= → частая практика (heavy adoption)
DEFAULT_WINDOW_DAYS = 30

# Каталог 43.9: категория → (заголовок главы, [инструменты]). Источник — главы 43.9.1..12.
CATALOG: dict[str, tuple[str, list[str]]] = {
    "43.9.1": (
        "Метаданные и инвентарь",
        [
            "mcp__1c-mcp-crud__get_metadata",
            "mcp__1c-mcp-crud__get_metadata_structure",
            "mcp__1c-mcp-crud__get_metadata_tree",
            "mcp__1c-mcp-crud__list_metadata_objects",
            "mcp__1c-mcp-crud__find_references_to_object",
            "mcp__edt-mcp__get_metadata_objects",
            "mcp__edt-mcp__get_metadata_details",
            "mcp__edt-mcp__get_configuration_properties",
            "mcp__edt-mcp__list_subsystems",
            "mcp__edt-mcp__get_subsystem_content",
            "mcp__edt-mcp__get_objects_by_tags",
            "mcp__edt-mcp__get_tags",
            "mcp__edt-mcp__find_references",
        ],
    ),
    "43.9.2": (
        "Данные и runtime живой ИБ",
        [
            "mcp__1c-mcp-crud__execute_query",
            "mcp__1c-mcp-crud__validate_query",
            "mcp__edt-mcp__validate_query",
            "mcp__1c-mcp-crud__execute_code",
            "mcp__1c-mcp-crud__get_object_by_link",
            "mcp__1c-mcp-crud__get_link_of_object",
            "mcp__1c-mcp-crud__get_access_rights",
            "mcp__1c-mcp-crud__get_event_log",
            "mcp__1c-mcp-crud__post_document",
            "mcp__1c-mcp-crud__create_object",
            "mcp__1c-mcp-crud__update_object",
            "mcp__1c-mcp-crud__mark_for_deletion",
        ],
    ),
    "43.9.3": (
        "Чтение и поиск кода",
        [
            "mcp__edt-mcp__read_module_source",
            "mcp__edt-mcp__read_method_source",
            "mcp__edt-mcp__get_module_structure",
            "mcp__edt-mcp__list_modules",
            "mcp__edt-mcp__search_in_code",
            "mcp__edt-mcp__go_to_definition",
            "mcp__edt-mcp__get_symbol_info",
            "mcp__bsl-semantic-search__bsl_search",
            "mcp__bsl-semantic-search__bsl_hybrid_search",
            "mcp__bsl-semantic-search__bsl_similar",
            "mcp__bsl-semantic-search__bsl_coding_context",
            "mcp__bsl-semantic-search__bsl_context",
            "mcp__bsl-code-search__search_symbols",
            "mcp__bsl-code-search__get_module_ast",
            "mcp__1c-mcp-crud__search_code",
        ],
    ),
    "43.9.4": (
        "Граф вызовов и impact",
        [
            "mcp__bsl-semantic-search__bsl_call_graph",
            "mcp__bsl-semantic-search__bsl_impact_analysis",
            "mcp__bsl-semantic-search__bsl_dead_code",
            "mcp__bsl-semantic-search__bsl_stats",
            "mcp__bsl-semantic-search__bsl_object_info",
            "mcp__bsl-code-search__find_callers",
            "mcp__edt-mcp__get_method_call_hierarchy",
        ],
    ),
    "43.9.5": (
        "Запись и рефакторинг",
        [
            "mcp__edt-mcp__write_module_source",
            "mcp__edt-mcp__create_metadata",
            "mcp__edt-mcp__modify_metadata",
            "mcp__edt-mcp__rename_metadata_object",
            "mcp__edt-mcp__adopt_metadata_object",
            "mcp__edt-mcp__delete_metadata",
            "mcp__edt-mcp__get_content_assist",
            "mcp__edt-mcp__revalidate_objects",
            "mcp__edt-mcp__resync_to_disk",
            "mcp__bsl-semantic-search__bsl_rename_symbol",
        ],
    ),
    "43.9.6": (
        "Формы, схемы отчётов и макеты",
        [
            "mcp__1c-mcp-crud__get_form_structure",
            "mcp__edt-mcp__get_form_layout_snapshot",
            "mcp__edt-mcp__get_form_screenshot",
        ],
    ),
    "43.9.7": (
        "Отладка и runtime-трейс",
        [
            "mcp__1c-debug-hmr__debug_set_breakpoint",
            "mcp__1c-debug-hmr__debug_stack_trace",
            "mcp__1c-debug-hmr__debug_variables",
            "mcp__1c-debug-hmr__debug_evaluate",
            "mcp__1c-debug-hmr__debug_step",
            "mcp__1c-debug__debug_set_breakpoint",
            "mcp__bsl-debugger__bsl_debug_start",
            "mcp__bsl-debugger__bsl_execute",
            "mcp__edt-mcp__set_breakpoint",
            "mcp__edt-mcp__debug_launch",
            "mcp__edt-mcp__wait_for_break",
        ],
    ),
    "43.9.8": (
        "Тестирование",
        [
            "mcp__mcp-onec-test-runner__run_all_tests",
            "mcp__mcp-onec-test-runner__run_module_tests",
            "mcp__mcp-onec-test-runner__build_project",
            "mcp__mcp-onec-test-runner__check_syntax_edt",
            "mcp__mcp-onec-test-runner__launch_app",
            "mcp__edt-mcp__run_yaxunit_tests",
            "mcp__edt-mcp__debug_yaxunit_tests",
        ],
    ),
    "43.9.9": (
        "Статанализ и качество",
        [
            "mcp__bsl-debugger__bsl_analyze",
            "mcp__edt-mcp__get_project_errors",
            "mcp__edt-mcp__get_problem_summary",
            "mcp__edt-mcp__get_markers",
            "mcp__edt-mcp__get_check_description",
            "mcp__edt-mcp__start_profiling",
            "mcp__edt-mcp__stop_profiling",
            "mcp__edt-mcp__get_profiling_results",
        ],
    ),
    "43.9.10": (
        "API платформы и документация",
        [
            "mcp__bsl-platform-context__search",
            "mcp__bsl-platform-context__getMember",
            "mcp__bsl-platform-context__getMembers",
            "mcp__bsl-platform-context__getConstructors",
            "mcp__bsl-platform-context__info",
            "mcp__pdf-vector-graph__search_documents",
            "mcp__pdf-vector-graph__ask_question",
            "mcp__pdf-vector-graph__research",
            "mcp__edt-mcp__get_platform_documentation",
            "mcp__1c-mcp-crud__get_bsl_syntax_help",
        ],
    ),
    "43.9.11": (
        "Деплой и управление ИБ",
        [
            "mcp__edt-mcp__update_database",
            "mcp__edt-mcp__create_infobase",
            "mcp__edt-mcp__delete_infobase",
            "mcp__edt-mcp__create_project",
            "mcp__edt-mcp__delete_project",
            "mcp__edt-mcp__import_configuration_from_xml",
            "mcp__edt-mcp__export_configuration_to_xml",
            "mcp__edt-mcp__create_launch_config",
            "mcp__edt-mcp__delete_launch_config",
            "mcp__edt-mcp__get_applications",
            "mcp__edt-mcp__list_configurations",
            "mcp__edt-mcp__list_projects",
        ],
    ),
    "43.9.12": (
        "Автодокументация",
        [
            "mcp__auto-documenter__generate_documentation",
            "mcp__auto-documenter__autoreview",
            "mcp__auto-documenter__autotestplan",
            "mcp__auto-documenter__generate_dependency_graph",
            "mcp__auto-documenter__generate_inline_docs",
        ],
    ),
}

# Серверные префиксы 1С-пайплайна — для детекта «1С-сессии» + observed-not-in-catalog
_ONEC_PREFIXES = (
    "mcp__1c-mcp-crud__",
    "mcp__edt-mcp__",
    "mcp__bsl-semantic-search__",
    "mcp__bsl-code-search__",
    "mcp__bsl-platform-context__",
    "mcp__bsl-debugger__",
    "mcp__1c-debug-hmr__",
    "mcp__1c-debug__",
    "mcp__mcp-onec-test-runner__",
    "mcp__auto-documenter__",
    "mcp__pdf-vector-graph__",
    "mcp__ast-grep-mcp__",
)
ALL_CATALOG_TOOLS = {t for _t, (_h, tools) in CATALOG.items() for t in tools}


def _verdict(rate: float) -> str:
    if rate >= HEAVY:
        return "heavy"
    if rate > 0:
        return "occasional"
    return "unused"


def collect_metrics(window_days: int, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    cutoff = now - timedelta(days=window_days)
    # session → set(использованных mcp__-тулов)
    sess_tools: dict[str, set[str]] = defaultdict(set)
    for r in _read_jsonl(INVOCATIONS):
        tool = r.get("tool") or ""
        if not tool.startswith("mcp__"):
            continue
        sid = r.get("session") or ""
        if not sid:
            continue
        dt = _parse_dt(r.get("ts"))
        if dt is not None and dt < cutoff:
            continue
        sess_tools[sid].add(tool)

    # 1С-сессии = где использован ≥1 инструмент 1С-пайплайна
    onec_sessions = {
        s: tools
        for s, tools in sess_tools.items()
        if any(t.startswith(_ONEC_PREFIXES) for t in tools)
    }
    total = len(onec_sessions)

    # presence_rate по каждому тулу каталога
    present_count: dict[str, int] = defaultdict(int)
    for tools in onec_sessions.values():
        for t in tools:
            if t in ALL_CATALOG_TOOLS:
                present_count[t] += 1

    per_category: dict[str, Any] = {}
    for cid, (title, tools) in CATALOG.items():
        rows = []
        used = 0
        for t in tools:
            cnt = present_count.get(t, 0)
            rate = round(cnt / total, 3) if total else 0.0
            if cnt:
                used += 1
            rows.append({"tool": t, "present": cnt, "rate": rate, "verdict": _verdict(rate)})
        rows.sort(key=lambda x: x["rate"], reverse=True)
        per_category[cid] = {"title": title, "coverage": f"{used}/{len(tools)}", "tools": rows}

    # observed 1С-тулы вне каталога (пробелы 43.9)
    observed = {
        t for tools in onec_sessions.values() for t in tools if t.startswith(_ONEC_PREFIXES)
    }
    uncatalogued = sorted(observed - ALL_CATALOG_TOOLS)

    return {
        "now": now.isoformat(timespec="seconds"),
        "window_days": window_days,
        "total_onec_sessions": total,
        "catalog_tools": len(ALL_CATALOG_TOOLS),
        "per_category": per_category,
        "uncatalogued_observed": uncatalogued,
    }


def render(m: dict[str, Any], only: str | None) -> str:
    lines = [
        f"# Валидатор инструментов 1С-пайплайна (presence_rate, каталог 43.9) — {m['now']}",
        "",
        f"- Окно: {m['window_days']} дн · 1С-сессий: **{m['total_onec_sessions']}** · "
        f"тулов в каталоге: {m['catalog_tools']}",
        "- presence_rate = доля 1С-сессий, где тул использован. heavy >=0.5 · occasional >0 · unused =0.",
        "- ! presence = адопция, НЕ безопасность hard (survivorship) — сигнал к рассмотрению, не авто-промоут.",
        "",
    ]
    for cid, cat in m["per_category"].items():
        if only and cid != only:
            continue
        lines.append(f"## {cid} {cat['title']} — coverage {cat['coverage']}")
        lines.append("| presence_rate | тул | вердикт |")
        lines.append("|--:|---|---|")
        for row in cat["tools"]:
            lines.append(
                f"| {row['rate']} ({row['present']}) | `{row['tool']}` | {row['verdict']} |"
            )
        lines.append("")
    if m["uncatalogued_observed"] and not only:
        lines.append("## ! Observed, но НЕ в каталоге 43.9 (пробелы — добавить в главы)")
        for t in m["uncatalogued_observed"]:
            lines.append(f"- `{t}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="presence_rate всех инструментов 1С-пайплайна (43.9)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    ap.add_argument("--category", default=None, help="фильтр по главе, напр. 43.9.4")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()
    m = collect_metrics(args.window_days)
    if args.json:
        _emit(json.dumps(m, ensure_ascii=False))
        return 0
    _emit(
        render(m, args.category),
        report_name=None if args.no_report else "onec_pipeline_tool_validation",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
