#!/usr/bin/env python3
"""TOOL-USAGE отчёт + глоб-агрегация эффективности инструментов (roadmap 260614 раздел W).

Per-task: читает `data/hook-invocations.jsonl` по `correlationid==run_id` (или `--session`) → агрег по `tool`
(calls / errors / avg latency) → `TOOL-USAGE-REPORT.md` (+ слот quality) + append в `data/tool-effectiveness.jsonl`.
`--rollup`: cross-task агрегат из `tool-effectiveness.jsonl` (профиль эффективности инструментов).

Переиспользует существующий авто-лог (НЕ дублирует). stdlib-only (без duckdb-зависимости).

Папка для `TOOL-USAGE-REPORT.md` (единый источник — реестр 1С-задач, как .pipeline-state.json/LOOPS.md):
  `--slug <slug>` → `pipeline_state.state_dir(slug)` (папка задачи из реестра); `--task-dir <D>` — явный
  override; без обоих — авто по текущему зарегистрированному 1С-пайплайну (`CURRENT`), иначе stdout.

Использование:
    python scripts/tool_usage_report.py --run-id <uuid> --slug <slug>       # в папку задачи (реестр)
    python scripts/tool_usage_report.py --run-id <uuid> [--task-dir <D>]    # явный override
    python scripts/tool_usage_report.py --session <sid> [--slug|--task-dir] # авто/override
    python scripts/tool_usage_report.py --rollup
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "hook-invocations.jsonl"
EFF = ROOT / "data" / "tool-effectiveness.jsonl"


def _iter_events(log: Path = LOG):
    if not log.exists():
        return
    with open(log, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except ValueError:
                continue


def aggregate(run_id: str | None = None, session: str | None = None, log: Path = LOG) -> dict:
    by_tool: dict[str, dict] = {}
    for e in _iter_events(log):
        if run_id and e.get("correlationid") != run_id:
            continue
        if session and e.get("session") != session:
            continue
        tool = e.get("tool")
        if not tool:
            continue
        a = by_tool.setdefault(tool, {"calls": 0, "errors": 0, "ms": 0})
        a["calls"] += 1
        if e.get("outcome") == "error" or e.get("error"):
            a["errors"] += 1
        a["ms"] += int(e.get("elapsed_ms") or 0)
    return by_tool


# Категории инструментов → artifact/этап + обязательность (петли задачи 1С).
# (key, заголовок, artifact/этап, обязательная-петля, саммари-категории)
_CATEGORIES = [
    ("memory", "Память (recall/capture)", "сквозной — все этапы", True,
     "Поиск прошлого опыта (recall) + фиксация переиспользуемых приёмов (capture)."),
    ("skills", "Скилы (методики 1С)", "сквозной — все этапы", True,
     "Активация профильных методик на этапах (analyze / implement / va-bdd / code-verify)."),
    ("config", "Анализ конфигурации 1С", "ANALYSIS-REPORT.md (Планирование/Дизайн)", True,
     "Метаданные, запросы, чтение кода, семантика, API платформы 8.3.27."),
    ("research", "Внешний анализ (Infostart+GitHub)", "ANALYSIS-REPORT.md (Планирование/Дизайн)", True,
     "Веб-исследование доверенных источников (8.3.27 первоисточник + Infostart + GitHub)."),
    ("impl", "Кодирование", "IMPLEMENTATION-PROGRESS.md", False,
     "Запись BSL/XML, исполнение/мутация, проверка ошибок, отладка."),
    ("testing", "Тестирование", ".run-state.json", False,
     "Прогон тестов (VA BDD / YAxUnit) + pre-check данных."),
    ("infra", "Инфраструктура (файлы/оркестрация)", "сквозной", False,
     "Рабочие инструменты: чтение/правка файлов, shell, поиск, субагенты."),
]
_CATEGORY_SUMMARY = {c[0]: c[4] for c in _CATEGORIES}

# 1c-mcp-crud / edt-mcp: суффиксы READ-операций (анализ конфигурации) vs WRITE/мутация (кодирование).
_CONFIG_READ_OPS = {
    "execute_query", "validate_query", "get_metadata", "get_metadata_structure", "get_metadata_tree",
    "list_metadata_objects", "search_code", "find_references_to_object", "get_object_by_link",
    "get_link_of_object", "get_form_structure", "get_event_log", "get_access_rights", "get_bsl_syntax_help",
    "read_module_source", "read_method_source", "list_modules", "list_projects", "get_module_structure",
    "search_in_code", "go_to_definition", "find_references", "get_metadata_objects", "get_metadata_details",
    "get_problem_summary", "get_project_errors", "get_symbol_info", "get_method_call_hierarchy",
    "get_form_screenshot", "get_configuration_properties", "get_content_assist", "get_platform_documentation",
}
_IMPL_WRITE_OPS = {
    "execute_code", "create_object", "update_object", "post_document", "mark_for_deletion",
    "write_module_source", "update_database", "add_metadata_attribute", "delete_metadata_object",
    "rename_metadata_object", "clean_project", "revalidate_objects", "debug_launch",
}

# Короткое назначение для частых инструментов (саммари-строка в таблице).
_TOOL_SUMMARY = {
    "Edit": "Точечная правка файла", "Write": "Создание/перезапись файла",
    "Bash": "Shell (тесты, git, проверки)", "Skill": "Активация методики/скила",
    "Agent": "Субагент (анализ/ревью/поиск)", "Read": "Чтение файла",
    "Glob": "Поиск файлов по маске", "Grep": "Поиск по содержимому",
    "WebSearch": "Веб-поиск (Infostart/GitHub/docs)", "WebFetch": "Загрузка страницы",
    "mcp__memory-orchestrator__unified_search": "recall: федеративный поиск памяти",
    "mcp__vector-memory__search_patterns": "recall: поиск паттернов",
    "mcp__skill-learning__capture_pattern": "capture: фиксация приёма (карантин)",
    "mcp__skill-learning__confirm_pattern": "capture: подтверждение паттерна",
    "mcp__1c-mcp-crud__execute_query": "1С-запрос (ground-truth данных)",
    "mcp__1c-mcp-crud__execute_code": "Исполнение BSL (анализ / мутация / render-verify)",
    "mcp__1c-mcp-crud__get_metadata_structure": "Структура объекта метаданных",
    "mcp__edt-mcp__read_module_source": "Чтение BSL-модуля",
    "mcp__edt-mcp__write_module_source": "Запись BSL-модуля",
    "mcp__edt-mcp__update_database": "Обновление БД конфигурации",
    "mcp__edt-mcp__get_project_errors": "Проверка ошибок проекта",
}


def _suffix(tool: str) -> str:
    return tool.rsplit("__", 1)[-1] if "__" in tool else tool


def classify_tool(tool: str) -> str:
    """Инструмент → категория (memory/skills/config/research/impl/testing/infra)."""
    t = tool or ""
    if t.startswith(("mcp__memory-orchestrator__", "mcp__vector-memory__", "mcp__skill-learning__", "mcp__memory-ai__")):
        return "memory"
    if t == "Skill":
        return "skills"
    if t in ("WebSearch", "WebFetch"):
        return "research"
    if t.startswith(("mcp__bsl-semantic-search__", "mcp__bsl-platform-context__", "mcp__bsl-code-search__",
                     "mcp__framework-search__", "mcp__pdf-vector-graph__", "mcp__auto-documenter__")):
        return "config"
    if t.startswith(("mcp__bsl-debugger__", "mcp__1c-debug__", "mcp__1c-debug-hmr__")):
        return "impl"
    if t.startswith("mcp__mcp-onec-test-runner__"):
        return "testing"
    if t.startswith(("mcp__1c-mcp-crud__", "mcp__edt-mcp__")):
        suf = _suffix(t)
        return "impl" if suf in _IMPL_WRITE_OPS else "config"  # неизвестная 1С-операция → анализ
    return "infra"  # Read/Write/Edit/Bash/Glob/Grep/Agent/Task/… + неизвестное


def tool_summary(tool: str) -> str:
    """Короткое назначение инструмента (саммари); неизвестное MCP → суффикс через пробелы."""
    if tool in _TOOL_SUMMARY:
        return _TOOL_SUMMARY[tool]
    return _suffix(tool).replace("_", " ") if tool else ""


def _q(errp: float) -> str:
    return "✗" if errp >= 30 else ("⚠" if errp > 0 else "✓")


def report_md(by_tool: dict, key: str) -> str:
    """Группированный отчёт: обязательные петли (✓/✗) + секции по категориям (artifact + саммари + назначение)."""
    groups: dict[str, list] = {c[0]: [] for c in _CATEGORIES}
    for tool, a in by_tool.items():
        groups.setdefault(classify_tool(tool), []).append((tool, a))

    lines = [f"# TOOL-USAGE-REPORT ({key})", ""]
    if not by_tool:
        return "\n".join(lines + ["_(нет вызовов для ключа)_"]) + "\n"

    # Обязательные петли — чеклист (использована ли категория)
    lines += ["## Обязательные петли", ""]
    for ckey, title, artifact, mand, _s in _CATEGORIES:
        if not mand:
            continue
        items = groups.get(ckey, [])
        calls = sum(a["calls"] for _, a in items)
        lines.append(f"- {'✓' if items else '✗'} **{title}** — {artifact} ({calls} вызов(ов))")
    lines += [""]

    # Секции по категориям (только непустые)
    for ckey, title, artifact, mand, _s in _CATEGORIES:
        items = groups.get(ckey, [])
        if not items:
            continue
        tc = sum(a["calls"] for _, a in items)
        te = sum(a["errors"] for _, a in items)
        terrp = round(100.0 * te / tc, 1) if tc else 0.0
        flag = " · **обязательный**" if mand else ""
        lines += [
            f"## {title}{flag}",
            f"_artifact: {artifact}. {_CATEGORY_SUMMARY[ckey]} Итого {tc} вызов(ов), {te} ошиб. ({terrp}%) {_q(terrp)}._",
            "",
            "| tool | назначение | calls | errors | err% | avg_ms | quality |",
            "|---|---|---|---|---|---|---|",
        ]
        for tool, a in sorted(items, key=lambda x: -x[1]["calls"]):
            errp = round(100.0 * a["errors"] / a["calls"], 1) if a["calls"] else 0.0
            avg = round(a["ms"] / a["calls"]) if a["calls"] else 0
            lines.append(f"| {tool} | {tool_summary(tool)} | {a['calls']} | {a['errors']} | {errp} | {avg} | {_q(errp)} |")
        lines += [""]

    return "\n".join(lines).rstrip() + "\n"


def append_eff(by_tool: dict, key: str, eff: Path = EFF) -> None:
    eff.parent.mkdir(parents=True, exist_ok=True)
    with open(eff, "a", encoding="utf-8") as f:
        for tool, a in by_tool.items():
            f.write(json.dumps({"key": key, "tool": tool, **a}, ensure_ascii=False) + "\n")


def rollup(eff: Path = EFF) -> dict:
    agg: dict[str, dict] = {}
    for r in _iter_events(eff):
        t = agg.setdefault(r.get("tool"), {"calls": 0, "errors": 0, "ms": 0})
        t["calls"] += r.get("calls", 0)
        t["errors"] += r.get("errors", 0)
        t["ms"] += r.get("ms", 0)
    return agg


def _load_pipeline_state():
    """Загрузить pipeline_state collision-immune (spec по пути — без коллизии src/shared↔hooks/shared)."""
    import importlib.util

    ps_path = ROOT / ".claude" / "hooks" / "shared" / "pipeline_state.py"
    spec = importlib.util.spec_from_file_location("_ps_for_tur", ps_path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def resolve_task_dir(task_dir: str | None = None, slug: str | None = None) -> Path | None:
    """Папка для TOOL-USAGE-REPORT.md (единый источник): явный --task-dir (override) >
    реестр state_dir(slug) > авто по CURRENT (только зарегистрированная 1С-задача). best-effort → None.

    Привязка к реестру делает TOOL-USAGE-REPORT.md консистентным с .pipeline-state.json/LOOPS.md
    (все резолвятся через pipeline_state.state_dir) — все файлы задачи в одной папке.
    Примечание: явный --slug для НЕзарегистрированного slug уходит в generic pipeline/<slug>/
    (для такого случая ожидается --task-dir); авто-ветка для generic CURRENT даёт None (stdout).
    """
    if task_dir:
        return Path(task_dir)
    try:
        ps = _load_pipeline_state()
    except Exception:
        return None
    if slug:
        return ps.state_dir(slug)  # явный slug → его state_dir (папка задачи для 1С)
    try:
        cur = ps.resolve_current()
        if cur and ps.is_registered(cur):  # авто: только зарегистрированная 1С-задача (публичный предикат)
            return ps.state_dir(cur)
    except Exception:
        return None
    return None


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # cp1251-console safe (✓/⚠/✗ + кириллица)
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="TOOL-USAGE report + tool effectiveness aggregation")
    ap.add_argument("--run-id")
    ap.add_argument("--session")
    ap.add_argument("--task-dir")
    ap.add_argument("--slug", help="slug 1С-задачи → папка из реестра (state_dir); единый источник")
    ap.add_argument("--rollup", action="store_true")
    args = ap.parse_args(argv)

    if args.rollup:
        print(report_md(rollup(), "ROLLUP cross-task"))
        return 0
    if not (args.run_id or args.session):
        ap.error("нужен --run-id или --session (либо --rollup)")
    key = args.run_id or args.session
    by_tool = aggregate(run_id=args.run_id, session=args.session)
    md = report_md(by_tool, key)
    target = resolve_task_dir(args.task_dir, args.slug)
    if target is not None:
        p = target / "TOOL-USAGE-REPORT.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
        print(f"написан {p}")
    else:
        print(md)
    append_eff(by_tool, key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
