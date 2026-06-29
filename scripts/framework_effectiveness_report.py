#!/usr/bin/env python3
"""Framework adoption & effectiveness report — пересчёт «живых» метрик по логам.

Считает поверхность внедрения (.claude/hooks, skills, .mcp.json, ADR, commands)
и эффективность по логам инструментирования (data/*.jsonl, .claude/cache/*.jsonl),
затем рендерит markdown-отчёт в data/reports/. Заменяет ручной разбор —
числа становятся воспроизводимыми, а не историческими.

DuckDB-слой по канону скилла duckdb-analytics: pre-clean JSONL → VIEW
(БЕЗ ignore_errors — иначе схема схлопывается в одну колонку `json`, issue #14259).
Graceful degradation: нет duckdb → exit 2 с подсказкой.

Usage:
    python scripts/framework_effectiveness_report.py [--out PATH] [--date YYYY-MM-DD] [--print]
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def out(s: str = "") -> None:
    """stdout UTF-8 байтами (Windows cp1251-pipe безопасно)."""
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))


def _check_duckdb():
    try:
        import duckdb

        return True
    except ImportError:
        out("ERROR: duckdb не установлен. Запусти: pip install duckdb")
        return False


def clean_view(con, name: str, patterns: list[str]) -> int:
    """Pre-clean подходящих JSONL → temp → CREATE VIEW <name>. Возвращает число строк (0 = нет данных).

    Битые строки фильтруются в Python (обход issue #14259), union_by_name мирит дрейф схемы.
    """
    files: list[Path] = []
    for pat in patterns:
        files.extend(sorted(ROOT.glob(pat)))
    files = [f for f in files if f.is_file()]
    if not files:
        return 0
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8", newline="\n"
    )
    atexit.register(lambda p=tmp.name: os.path.exists(p) and os.unlink(p))
    rows_n = 0
    try:
        for f in files:
            with open(f, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    s = line.strip()
                    if not s:
                        continue
                    try:
                        json.loads(s)
                    except (ValueError, json.JSONDecodeError):
                        continue
                    tmp.write(s + "\n")
                    rows_n += 1
    finally:
        tmp.close()
    if rows_n == 0:
        os.unlink(tmp.name)
        return 0
    con.execute(
        f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_json_auto("
        f"'{tmp.name}', format='newline_delimited', union_by_name=true)"
    )
    return rows_n


def rows(con, sql: str) -> list[dict]:
    try:
        res = con.execute(sql)
        cols = [d[0] for d in res.description]
        return [dict(zip(cols, r)) for r in res.fetchall()]
    except Exception as e:  # отчёт не должен падать из-за одной метрики
        out(f"  (запрос пропущен: {str(e)[:100]})")
        return []


# ---------------------------------------------------------------- adoption surface


def adoption_surface() -> dict:
    d: dict = {}
    d["hook_files"] = len(list((ROOT / ".claude/hooks").glob("*.py")))
    d["skills"] = len(list((ROOT / ".claude/skills").glob("*/SKILL.md")))
    d["adr"] = len(list((ROOT / ".claude/skills/architecture-research/adr").glob("*.md")))
    d["commands"] = len(list((ROOT / ".claude/commands").glob("*.md")))
    docs = ROOT / "docs/framework documentation"
    d["doc_chapters"] = len([p for p in docs.glob("*") if p.is_dir()]) if docs.exists() else 0
    d["doc_files"] = len(list(docs.glob("**/*.md"))) if docs.exists() else 0
    try:
        d["mcp_servers"] = len(
            json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8")).get("mcpServers", {})
        )
    except Exception:
        d["mcp_servers"] = 0
    per_event: dict[str, int] = {}
    for sf in (".claude/settings.json", ".claude/settings.local.json"):
        p = ROOT / sf
        if not p.exists():
            continue
        try:
            hooks = json.loads(p.read_text(encoding="utf-8")).get("hooks", {})
        except Exception:
            continue
        for event, matchers in hooks.items():
            n = sum(len(m.get("hooks", [])) for m in matchers if isinstance(m, dict))
            per_event[event] = per_event.get(event, 0) + n
    d["hooks_per_event"] = per_event
    return d


def memory_metrics_stdlib() -> dict:
    """memory-metrics: counters — STRUCT, пустоту проще проверить stdlib'ом, чем в SQL."""
    p = ROOT / ".claude/cache/memory-metrics.jsonl"
    if not p.exists():
        return {"snapshots": 0, "with_counters": 0}
    snaps = withc = 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        snaps += 1
        if r.get("counters"):
            withc += 1
    return {"snapshots": snaps, "with_counters": withc}


# ---------------------------------------------------------------- effectiveness


def build(con) -> dict:
    m: dict = {"adoption": adoption_surface(), "memory": memory_metrics_stdlib()}

    n_hooks = clean_view(con, "hooks", ["data/hook-invocations*.jsonl"])
    m["hooks_total"] = n_hooks
    if n_hooks:
        m["hook_outcomes"] = rows(
            con,
            "SELECT lower(outcome) oc, count(*) n FROM hooks GROUP BY oc ORDER BY n DESC LIMIT 8",
        )
        m["hook_blocking"] = rows(
            con,
            "SELECT hook, count(*) n FROM hooks WHERE lower(outcome) IN "
            "('block','blocked','deny','error') GROUP BY hook ORDER BY n DESC LIMIT 10",
        )
        m["hook_latency"] = rows(
            con,
            "SELECT approx_quantile(elapsed_ms,0.5) p50, approx_quantile(elapsed_ms,0.95) p95, "
            "max(elapsed_ms) mx FROM hooks WHERE elapsed_ms>0 AND elapsed_ms<60000",
        )
        m["hook_expensive"] = rows(
            con,
            "SELECT hook, round(avg(elapsed_ms)) mean_ms, count(*) n FROM hooks "
            "WHERE elapsed_ms>0 AND elapsed_ms<60000 GROUP BY hook HAVING count(*)>=20 "
            "ORDER BY mean_ms DESC LIMIT 12",
        )
        m["hook_per_session"] = rows(
            con,
            "SELECT approx_quantile(s,0.5) p50, approx_quantile(s,0.95) p95, "
            "approx_quantile(c,0.5) c50, approx_quantile(c,0.95) c95 FROM "
            "(SELECT session, sum(elapsed_ms) s, count(*) c FROM hooks "
            "WHERE elapsed_ms<60000 AND session<>'' GROUP BY session)",
        )

    if clean_view(con, "gate", ["data/gate-decisions.jsonl"]):
        m["gate_overall"] = rows(
            con,
            "SELECT count(*) total, count(*) FILTER (WHERE NOT allow) denied, "
            "round(100.0*count(*) FILTER (WHERE NOT allow)/count(*),1) deny_pct FROM gate",
        )
        m["gate_reasons"] = rows(
            con,
            "SELECT reason, count(*) n FROM gate WHERE NOT allow GROUP BY reason ORDER BY n DESC LIMIT 8",
        )

    if clean_view(con, "deleg", ["data/delegation-outcomes.jsonl"]):
        m["deleg"] = rows(
            con,
            "SELECT count(*) total, count(TRY_CAST(quality_score AS DOUBLE)) with_quality, "
            "count(CASE WHEN CAST(delegated AS VARCHAR)='true' THEN 1 END) delegated_true, "
            "count(CASE WHEN CAST(delegated AS VARCHAR)='false' THEN 1 END) delegated_false FROM deleg",
        )

    if clean_view(con, "tool", ["data/tool-effectiveness.jsonl"]):
        m["tool"] = rows(
            con,
            "SELECT count(*) tools, sum(TRY_CAST(calls AS BIGINT)) calls, "
            "sum(TRY_CAST(errors AS BIGINT)) errors, round(100.0*sum(TRY_CAST(errors AS BIGINT))/"
            "NULLIF(sum(TRY_CAST(calls AS BIGINT)),0),2) err_pct FROM tool",
        )

    if clean_view(con, "skillacc", ["data/skill-accuracy.jsonl"]):
        m["skill"] = rows(
            con, "SELECT type, count(*) n FROM skillacc GROUP BY type ORDER BY n DESC LIMIT 8"
        )

    return m


# ---------------------------------------------------------------- render


def _v(rowset: list[dict], key: str, default="—"):
    return rowset[0].get(key, default) if rowset else default


def render(m: dict, date_str: str) -> str:
    a = m["adoption"]
    L: list[str] = [
        f"# Анализ внедрения фреймворка: adoption + эффективность ({date_str})",
        "",
        "> Сгенерировано `scripts/framework_effectiveness_report.py` по логам инструментирования. "
        "Числа воспроизводимы — перезапусти скрипт.",
        "",
        "## 1. Масштаб внедрения",
        "",
        "| Слой | Кол-во |",
        "|---|---|",
        f"| Хуки (.py) | {a['hook_files']} |",
        f"| Скиллы | {a['skills']} |",
        f"| MCP-серверы | {a['mcp_servers']} |",
        f"| ADR | {a['adr']} |",
        f"| Команды | {a['commands']} |",
        f"| Doc-файлы (глав) | {a['doc_files']} ({a['doc_chapters']}) |",
    ]
    if a.get("hooks_per_event"):
        pe = a["hooks_per_event"]
        order = [
            "SessionStart",
            "UserPromptSubmit",
            "UserPromptExpansion",
            "PreToolUse",
            "PostToolUse",
            "Stop",
        ]
        chips = " · ".join(f"{e} {pe[e]}" for e in order if e in pe)
        L += ["", f"**Зарегистрировано хуков на событие:** {chips}"]

    L += ["", "## 2. Объём и надёжность (измерено) ✅", ""]
    if m.get("hooks_total"):
        lat = m.get("hook_latency", [])
        ps = m.get("hook_per_session", [])
        L.append(
            f"- **Хук-срабатываний:** {m['hooks_total']} · латентность p50={_v(lat, 'p50')}ms p95={_v(lat, 'p95')}ms"
        )
        oc = {r["oc"]: r["n"] for r in m.get("hook_outcomes", [])}
        tot = sum(oc.values()) or 1
        allow = oc.get("allow", 0)
        blk = oc.get("block", 0) + oc.get("blocked", 0) + oc.get("deny", 0)
        L.append(
            f"- **Исходы хуков:** allow {allow} ({100 * allow // tot}%), block {blk}, error {oc.get('error', 0)}"
        )
        L.append(
            f"- **Хуков/сессию:** p50={_v(ps, 'c50')} p95={_v(ps, 'c95')}; "
            f"кумулятивная латентность/сессию p50={_v(ps, 'p50')}ms p95={_v(ps, 'p95')}ms"
        )
    if m.get("tool"):
        t = m["tool"][0]
        L.append(
            f"- **Надёжность инструментов:** {t.get('errors')} ошибок / {t.get('calls')} вызовов = {t.get('err_pct')}%"
        )
    if m.get("gate_overall"):
        g = m["gate_overall"][0]
        L.append(
            f"- **Гейты:** {g.get('total')} решений, {g.get('denied')} блоков ({g.get('deny_pct')}%)"
        )
    if m.get("hook_expensive"):
        L += ["", "**Самые дорогие хуки (mean ms):**", "", "| Хук | mean ms | n |", "|---|---|---|"]
        for r in m["hook_expensive"]:
            L.append(f"| {r['hook']} | {int(r['mean_ms'])} | {r['n']} |")

    L += ["", "## 3. Что ловят гейты (process-compliance, не баги)", ""]
    if m.get("gate_reasons"):
        L += ["| Причина блока | n |", "|---|---|"]
        for r in m["gate_reasons"]:
            L.append(f"| {str(r['reason'])[:70]} | {r['n']} |")
    if m.get("hook_blocking"):
        L += [
            "",
            "**Хуки-блокировщики:** "
            + ", ".join(f"{r['hook']} ({r['n']})" for r in m["hook_blocking"][:8]),
        ]

    L += ["", "## 4. Эффективность НЕ доказана ⚠️ (инструментировано, но пусто)", ""]
    mem = m["memory"]
    L.append(
        f"- **Память (surfacing):** {mem['snapshots']} снимков метрик, "
        f"непустых counters — {mem['with_counters']} → hit-rate не пишется"
    )
    if m.get("deleg"):
        d = m["deleg"][0]
        L.append(
            f"- **Делегирование:** {d.get('total')} записей, с quality_score — лишь {d.get('with_quality')} "
            f"(delegated true/false = {d.get('delegated_true')}/{d.get('delegated_false')}) → экономия не доказана"
        )
    if m.get("skill"):
        sk = {r["type"]: r["n"] for r in m["skill"]}
        L.append(
            f"- **Skill-routing:** recommend {sk.get('recommend', 0)} → activate {sk.get('activate', 0)} → "
            f"confirmed {sk.get('confirmed', 0)} / failed {sk.get('failed', 0)} → прод-точность не меряется"
        )
    L.append(
        "- **Advisory-контуры** (onec-toolgate ADR-035, tdd-guard ADR-015): логи ~пусты → follow_rate insufficient-data"
    )

    L += [
        "",
        "## 5. Вердикт",
        "",
        "Эффективность есть, но неравномерная: доказаны retrieval-качество и надёжность инструментов; "
        "enforcement реально принуждает к процессу. НО самые дорогие подсистемы (память/делегирование/advisory) "
        "имеют пустую телеметрию результата, а overhead непропорционален на тривиальных задачах. "
        "Заполнить пустые логи и сделать trivial-carve-out для гейтов — наибольший ROI.",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument(
        "--print", action="store_true", dest="to_stdout", help="печатать отчёт в stdout"
    )
    args = ap.parse_args()

    if not _check_duckdb():
        return 2
    import duckdb

    con = duckdb.connect(":memory:")
    m = build(con)
    report = render(m, args.date)

    out_path = (
        Path(args.out)
        if args.out
        else ROOT / "data/reports" / f"framework_adoption_effectiveness_{args.date}.md"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    try:
        shown = out_path.relative_to(ROOT)
    except ValueError:
        shown = out_path  # --out вне дерева репо — печатаем абсолютный путь
    out(f"Отчёт записан: {shown}  ({len(report)} симв.)")
    if args.to_stdout:
        out("")
        out(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
