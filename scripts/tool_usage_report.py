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
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "hook-invocations.jsonl"
EFF = ROOT / "data" / "tool-effectiveness.jsonl"

# Канонические категории строк «один row = один вызов инструмента» (Pre+Post):
# mcp_call (mcp-invocation-logger) + tool_call (tool-invocation-logger, roadmap
# 260713 P0.3 — built-in тулы). Обе несут tool_call_id/args_hash и реальную
# Pre/Post-латентность. category="hook" (автолог энфорсеров) — НЕ вызов тула.
_CANONICAL_CATEGORIES = ("mcp_call", "tool_call")


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


def _ms_between(a_ts: str | None, b_ts: str | None) -> int | None:
    """Длительность в мс между двумя ISO-таймстампами (b − a). None при непарсибельности."""
    if not a_ts or not b_ts:
        return None
    try:
        return int(
            (datetime.fromisoformat(b_ts) - datetime.fromisoformat(a_ts)).total_seconds() * 1000
        )
    except (ValueError, TypeError):
        return None


def _pair_durations(pres: list[dict], posts: list[dict]) -> tuple[int, int]:
    """Сумма реальных длительностей Pre→Post + число пар (ADR-022 P0.2 — латентность тула, не overhead хука).
    Join по `tool_call_id` если есть, иначе FIFO: ранний неиспользованный Pre не позже Post."""
    if not posts:
        return 0, 0
    pres_sorted = sorted(pres, key=lambda e: e.get("ts", ""))
    posts_sorted = sorted(posts, key=lambda e: e.get("ts", ""))
    pre_by_id: dict[str, dict] = {}
    for p in pres_sorted:
        cid = p.get("tool_call_id")
        if cid:
            pre_by_id.setdefault(cid, p)
    used: set[int] = set()
    total = 0
    n = 0
    for post in posts_sorted:
        pre = None
        cid = post.get("tool_call_id")
        if cid and cid in pre_by_id and id(pre_by_id[cid]) not in used:
            pre = pre_by_id[cid]
        else:
            for p in pres_sorted:
                if id(p) in used:
                    continue
                if p.get("ts", "") <= post.get("ts", ""):
                    pre = p
                    break
        if pre is None:
            continue
        d = _ms_between(pre.get("ts"), post.get("ts"))
        if d is not None and d >= 0:
            used.add(id(pre))  # R2: помечаем Pre использованным ТОЛЬКО при валидной паре
            total += d
            n += 1
    return total, n


def _aggregate_mcp(rows: list[dict]) -> dict:
    """MCP-вызовы из Pre/Post-строк: реальная латентность + дедуп calls (Pre+Post одного вызова = 1)."""
    from collections import defaultdict

    pre: dict[str, list] = defaultdict(list)
    post: dict[str, list] = defaultdict(list)
    for e in rows:
        (post if e.get("event") == "PostToolUse" else pre)[e["tool"]].append(e)
    out: dict[str, dict] = {}
    for tool in set(pre) | set(post):
        pres, posts = pre[tool], post[tool]
        calls = max(len(pres), len(posts))  # Pre и Post одного вызова не двоятся
        errors = sum(1 for p in posts if p.get("outcome") == "error" or p.get("error"))
        ms, paired = _pair_durations(pres, posts)
        out[tool] = {
            "calls": calls,
            "errors": errors,
            "ms": ms,
            "paired": paired,
            "latency_real": paired > 0,
        }
    return out


def _effectiveness(events: list[dict]) -> dict:
    """Детерминированная эффективность (ADR-022 P1) по каноническим вызовам (Post = завершённый вызов
    с outcome/args_hash): `repeats` — повтор идентичного вызова (тот же `args_hash` у тула в одном run =
    retry); `abandonment` — последняя попытка тула завершилась ошибкой (не восстановились). Источник —
    канонические строки mcp_call + tool_call (roadmap 260713 P0.3): у обеих outcome/args_hash = исход тула,
    НЕ хука-наблюдателя. ⚠ у built-in тулов детект ошибки best-effort (Bash non-zero exit не isError) →
    abandonment/repeats built-in консервативны. Логику подтвердил Z.AI-ревью (claude-haiku, PASS)."""
    from collections import defaultdict

    calls = sorted(
        (
            e
            for e in events
            if e.get("category") in _CANONICAL_CATEGORIES and e.get("event") == "PostToolUse"
        ),
        key=lambda e: e.get("ts", ""),
    )
    out: dict[str, dict] = defaultdict(lambda: {"repeats": 0, "abandonment": 0})
    seen: dict[str, set] = defaultdict(set)
    per_tool: dict[str, list] = defaultdict(list)
    for e in calls:
        tool = e.get("tool")
        if not tool:
            continue
        per_tool[tool].append(e)
        ah = e.get("args_hash")
        if ah:
            if ah in seen[tool]:
                out[tool]["repeats"] += 1
            seen[tool].add(ah)
    for tool, evs in per_tool.items():
        if evs and (evs[-1].get("outcome") == "error" or evs[-1].get("error")):
            out[tool]["abandonment"] = 1
    return dict(out)


def aggregate(run_id: str | None = None, session: str | None = None, log: Path = LOG) -> dict:
    """Агрегат по инструменту. MCP (`category=mcp_call`) — реальная латентность через Pre/Post-пару
    (ADR-022 P0.2); остальное (нативные/хуки) — счёт строк + `elapsed_ms` как overhead (`latency_real=False`)."""
    matched: list[dict] = []
    for e in _iter_events(log):
        if run_id and e.get("correlationid") != run_id:
            continue
        if session and e.get("session") != session:
            continue
        if not e.get("tool"):
            continue
        matched.append(e)

    canonical_rows = [e for e in matched if e.get("category") in _CANONICAL_CATEGORIES]
    by_tool: dict[str, dict] = dict(_aggregate_mcp(canonical_rows))
    canonical_tools = set(by_tool)  # истина вызовов — только из mcp_call/tool_call-строк

    for e in matched:
        if e.get("category") in _CANONICAL_CATEGORIES:
            continue
        tool = e["tool"]
        if tool in canonical_tools:  # stray hook-строки канонического тула не двоим
            continue
        a = by_tool.setdefault(tool, {"calls": 0, "errors": 0, "ms": 0, "latency_real": False})
        a["calls"] += 1
        if e.get("outcome") == "error" or e.get("error"):
            a["errors"] += 1
        a["ms"] += int(e.get("elapsed_ms") or 0)

    for tool, eff in _effectiveness(matched).items():  # ADR-022 P1: retry/abandonment
        if tool in by_tool:
            by_tool[tool].update(eff)
    for a in by_tool.values():
        a.setdefault("repeats", 0)
        a.setdefault("abandonment", 0)
    return by_tool


# Категории инструментов → artifact/этап + обязательность (петли задачи 1С).
# (key, заголовок, artifact/этап, обязательная-петля, саммари-категории)
_CATEGORIES = [
    (
        "memory",
        "Память (recall/capture)",
        "сквозной — все этапы",
        True,
        "Поиск прошлого опыта (recall) + фиксация переиспользуемых приёмов (capture).",
    ),
    (
        "skills",
        "Скилы (методики 1С)",
        "сквозной — все этапы",
        True,
        "Активация профильных методик на этапах (analyze / implement / va-bdd / code-verify).",
    ),
    (
        "config",
        "Анализ конфигурации 1С",
        "ANALYSIS-REPORT.md (Планирование/Дизайн)",
        True,
        "Метаданные, запросы, чтение кода, семантика, API платформы 8.3.27.",
    ),
    (
        "research",
        "Внешний анализ (Infostart+GitHub)",
        "ANALYSIS-REPORT.md (Планирование/Дизайн)",
        True,
        "Веб-исследование доверенных источников (8.3.27 первоисточник + Infostart + GitHub).",
    ),
    (
        "impl",
        "Кодирование",
        "IMPLEMENTATION-PROGRESS.md",
        False,
        "Запись BSL/XML, исполнение/мутация, проверка ошибок, отладка.",
    ),
    (
        "testing",
        "Тестирование",
        ".run-state.json",
        False,
        "Прогон тестов (VA BDD / YAxUnit) + pre-check данных.",
    ),
    (
        "infra",
        "Инфраструктура (файлы/оркестрация)",
        "сквозной",
        False,
        "Рабочие инструменты: чтение/правка файлов, shell, поиск, субагенты.",
    ),
]
_CATEGORY_SUMMARY = {c[0]: c[4] for c in _CATEGORIES}

# 1c-mcp-crud / edt-mcp: суффиксы WRITE/мутация → кодирование (impl); прочие 1С-операции → анализ (config).
# Denylist (а не allowlist read-ops): новые read-инструменты автоматически попадают в анализ без правки кода.
_IMPL_WRITE_OPS = {
    "execute_code",
    "create_object",
    "update_object",
    "post_document",
    "mark_for_deletion",
    "write_module_source",
    "update_database",
    "add_metadata_attribute",
    "delete_metadata_object",
    "rename_metadata_object",
    "clean_project",
    "revalidate_objects",
    "debug_launch",
}

# Короткое назначение для частых инструментов (саммари-строка блока).
_TOOL_SUMMARY = {
    "Edit": "Точечная правка файла",
    "Write": "Создание/перезапись файла",
    "Bash": "Shell (тесты, git, проверки)",
    "Skill": "Активация методики/скила",
    "Agent": "Субагент (анализ/ревью/поиск)",
    "Read": "Чтение файла",
    "Glob": "Поиск файлов по маске",
    "Grep": "Поиск по содержимому",
    "WebSearch": "Веб-поиск (Infostart/GitHub/docs)",
    "WebFetch": "Загрузка страницы",
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
    if t.startswith(
        (
            "mcp__memory-orchestrator__",
            "mcp__vector-memory__",
            "mcp__skill-learning__",
            "mcp__memory-ai__",
        )
    ):
        return "memory"
    if t == "Skill":
        return "skills"
    if t in ("WebSearch", "WebFetch"):
        return "research"
    if t.startswith(
        (
            "mcp__bsl-semantic-search__",
            "mcp__bsl-platform-context__",
            "mcp__bsl-code-search__",
            "mcp__framework-search__",
            "mcp__pdf-vector-graph__",
            "mcp__auto-documenter__",
        )
    ):
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


def report_md(by_tool: dict, key: str, results: dict | None = None) -> str:
    """Группированный отчёт: обязательные петли (✓/✗) + секции по категориям, БЛОК на инструмент
    (метрики + назначение + результат). `results` = {tool: саммари-результата} (курируется, лог не содержит)."""
    results = results or {}
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

    # Секции по категориям (только непустые) — блок на инструмент
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
        ]
        for tool, a in sorted(items, key=lambda x: -x[1]["calls"]):
            errp = round(100.0 * a["errors"] / a["calls"], 1) if a["calls"] else 0.0
            res = str(results.get(tool, "—")).strip() or "—"
            if a.get("latency_real") and a.get("paired"):
                lat = f"{round(a['ms'] / a['paired'])}ms"  # реальная (Pre/Post-пара MCP)
            elif a.get("ms"):
                lat = f"{round(a['ms'] / a['calls'])}ms~"  # overhead хука, НЕ время инструмента
            else:
                lat = "n/a"
            sr = round(100.0 * (a["calls"] - a["errors"]) / a["calls"]) if a["calls"] else 0
            extra = ""
            if a.get("repeats"):
                extra += f" · ⟳{a['repeats']} повтор"
            if a.get("abandonment"):
                extra += " · ⚠ не восстановлено"
            lines += [
                f"**`{tool}`** · {a['calls']} вызов(ов) · {a['errors']} ошиб ({sr}% success) · {lat} · {_q(errp)}{extra}",
                f"· назначение: {tool_summary(tool)}",
                f"· результат: {res}",
                "",
            ]

    lines += [
        "",
        "> Латентность: `Nms` = реальная (Pre/Post-пара MCP, ADR-022); `Nms~` = overhead хука "
        "(НЕ время инструмента); `n/a` = пары нет. Эффективность (P1): `(N% success)` = доля без ошибок; "
        "`⟳N повтор` = идентичный вызов (retry); `⚠ не восстановлено` = последняя попытка тула — ошибка.",
    ]
    return "\n".join(lines).rstrip() + "\n"


def append_eff(by_tool: dict, key: str, eff: Path = EFF) -> None:
    eff.parent.mkdir(parents=True, exist_ok=True)
    with open(eff, "a", encoding="utf-8") as f:
        for tool, a in by_tool.items():
            f.write(json.dumps({"key": key, "tool": tool, **a}, ensure_ascii=False) + "\n")


def rollup(eff: Path = EFF) -> dict:
    """Cross-task агрегат. РЕАЛЬНАЯ латентность (ADR-022 P2-followup): `ms`/`paired` копятся ТОЛЬКО из
    строк с `paired>0` (реальная Pre/Post-пара MCP); overhead-строки (нативные / без пары) в латентность
    НЕ идут → отчёт не выдаёт overhead за время инструмента. repeats/abandonment (P1) тоже агрегируются."""
    agg: dict[str, dict] = {}
    for r in _iter_events(eff):
        t = agg.setdefault(
            r.get("tool"),
            {
                "calls": 0,
                "errors": 0,
                "ms": 0,
                "paired": 0,
                "repeats": 0,
                "abandonment": 0,
                "latency_real": False,
            },
        )
        t["calls"] += r.get("calls", 0)
        t["errors"] += r.get("errors", 0)
        t["repeats"] += int(r.get("repeats") or 0)
        t["abandonment"] += int(r.get("abandonment") or 0)
        if int(r.get("paired") or 0) > 0:  # только реальная Pre/Post-латентность
            t["ms"] += int(r.get("ms") or 0)
            t["paired"] += int(r.get("paired") or 0)
            t["latency_real"] = True
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
        if cur and ps.is_registered(
            cur
        ):  # авто: только зарегистрированная 1С-задача (публичный предикат)
            return ps.state_dir(cur)
    except Exception:
        return None
    return None


def load_results(path: str | None = None, target: Path | None = None) -> dict:
    """Курируемые саммари результата по инструменту {tool: текст}. Источник: явный --results <json>
    ИЛИ авто `<target>/TOOL-RESULTS.json` (рядом с отчётом). Лог результатов не содержит → курируется
    Claude по факту задачи. best-effort → {} (нет файла/битый JSON)."""
    p = Path(path) if path else (target / "TOOL-RESULTS.json" if target else None)
    if p is None:
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(d, dict):
        return {}
    # значения → однострочный str (случайный \n не должен разрывать блок инструмента)
    return {str(k): str(v).replace("\n", " ").strip() for k, v in d.items()}


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
    ap.add_argument(
        "--results", help="JSON {tool: саммари-результата}; иначе авто <папка>/TOOL-RESULTS.json"
    )
    ap.add_argument("--rollup", action="store_true")
    args = ap.parse_args(argv)

    if args.rollup:
        print(report_md(rollup(), "ROLLUP cross-task"))
        return 0
    if not (args.run_id or args.session):
        ap.error("нужен --run-id или --session (либо --rollup)")
    key = args.run_id or args.session
    by_tool = aggregate(run_id=args.run_id, session=args.session)
    target = resolve_task_dir(args.task_dir, args.slug)
    results = load_results(args.results, target)  # курируемые результаты (рядом с отчётом)
    md = report_md(by_tool, key, results)
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
