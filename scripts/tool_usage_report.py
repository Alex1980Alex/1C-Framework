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


def report_md(by_tool: dict, key: str) -> str:
    lines = [
        f"# TOOL-USAGE-REPORT ({key})",
        "",
        "| tool | calls | errors | err% | avg_ms | quality |",
        "|---|---|---|---|---|---|",
    ]
    for tool, a in sorted(by_tool.items(), key=lambda x: -x[1]["calls"]):
        errp = round(100.0 * a["errors"] / a["calls"], 1) if a["calls"] else 0.0
        avg = round(a["ms"] / a["calls"]) if a["calls"] else 0
        q = "✗" if errp >= 30 else ("⚠" if errp > 0 else "✓")
        lines.append(f"| {tool} | {a['calls']} | {a['errors']} | {errp} | {avg} | {q} _заметка_ |")
    if not by_tool:
        lines.append("| _(нет вызовов для ключа)_ | | | | | |")
    return "\n".join(lines) + "\n"


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
        if cur and cur in ps._read_registry():  # авто: только зарегистрированная 1С-задача
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
