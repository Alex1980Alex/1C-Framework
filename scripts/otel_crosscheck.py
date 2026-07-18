#!/usr/bin/env python3
"""Cross-check нативного OTel Claude Code ↔ hook-JSONL (roadmap 260718 H-P3).

**Главная ценность тяжёлого пути** — независимая сверка честности лёгкого контура.
Лёгкий детектор провала built-in (NB1) косвенный: провал = **непарный Pre** (платформа
не шлёт PostToolUse на неуспешный built-in). Нативный OTel даёт ПРЯМОЙ сигнал —
событие ``claude_code.tool_result`` несёт ``success``/``duration_ms``/``error_type``
per-call. Джойн по ``tool_use_id`` (native) == ``tool_call_id`` (hook) = ``gen_ai.tool.call.id``
(эмпирически 100% overlap на живых данных 2026-07-18).

Отчёт:
  - **FN** — native провал, а hook счёл успехом (был Post / не непарный) → детектор
    ПРОПУСТИЛ реальный провал;
  - **FP** — hook пометил провал (непарный Pre), а native ``success=true`` → ЛОЖНОЕ
    срабатывание (обрыв сессии, in-flight);
  - **TP** — оба согласны (провал);
  - **latency** — native ``duration_ms`` vs hook прямой ``duration_ms`` (H-P0.1 —
    консистентность захвата) и vs пэйринг Pre→Post (величина ошибки пары);
  - **coverage** — покрытие обоих источников.

Источник native = ``data/otel/claude-otel-logs.jsonl`` (OTLP JSON от file-exporter,
H-P1). Нет файла → graceful: ``available=False``, потребитель прячет секцию (поведение
как сегодня). stdlib-only (detached Stop-контекст, как analyze_tool_health).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

_SCRIPTS_DIR = str(Path(__file__).resolve().parent)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from tool_effectiveness import CANONICAL_CATEGORIES, parse_ts, percentile

ROOT = Path(__file__).resolve().parents[1]
OTEL_DIR = ROOT / "data" / "otel"
NATIVE_LOGS = OTEL_DIR / "claude-otel-logs.jsonl"
HOOK_LOG = ROOT / "data" / "hook-invocations.jsonl"

# Провал держим in-flight, если Pre моложе этого от now (Post ещё может прийти) —
# симметрично tool_effectiveness.completion_stats, иначе «хвост окна» = ложные FP.
GRACE_SEC = 120


# ── OTLP-парсер (native) ──────────────────────────────────────────────────────


def _attr_val(v: dict) -> object:
    """Развернуть OTLP AnyValue → Python-значение (string/bool/int/double/…)."""
    if not isinstance(v, dict):
        return v
    if "stringValue" in v:
        return v["stringValue"]
    if "boolValue" in v:
        return v["boolValue"]
    if "intValue" in v:
        try:
            return int(v["intValue"])  # OTLP кладёт int как строку
        except (ValueError, TypeError):
            return None
    if "doubleValue" in v:
        return v["doubleValue"]
    return None


def _attrs_map(attr_list: list) -> dict:
    out: dict[str, object] = {}
    for a in attr_list or []:
        k = a.get("key")
        if k:
            out[k] = _attr_val(a.get("value", {}))
    return out


def _coerce_bool(v: object) -> bool:
    """OTLP-значение → bool. ⚠ КРИТИЧНО: реальный Claude Code кодирует ``success``
    как ``stringValue`` ``"true"``/``"false"`` (НЕ boolValue) — эмпирика 2026-07-18.
    Наивное ``bool("false")`` == True → все провалы читались бы как успех (NB1-класс
    на стороне OTel-парсинга: cross-check ослеп бы к реальным провалам)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return bool(v)


def _coerce_int(v: object) -> int | None:
    """OTLP-значение → int мс. Реальный ``duration_ms`` приходит ``stringValue`` ``"3879"``
    (не intValue) → ``isinstance(str,(int,float))`` False давал бы None (latency слепа)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            return int(float(v.strip()))
        except (ValueError, TypeError):
            return None
    return None


def parse_native_tool_results(path: Path = NATIVE_LOGS) -> list[dict]:
    """События ``claude_code.tool_result`` из OTLP-JSON file-exporter'а.

    Возвращает нормализованные dict'ы: ``tool_use_id``/``tool``/``success``/
    ``duration_ms``/``error_type``/``ts`` (ISO, из timeUnixNano)/``session``.
    Дубли по id допустимы (батч-ретраи) — потребитель схлопывает по последнему.
    Не падает на битой строке/неполном атрибуте (per-line try)."""
    if not path.exists():
        return []
    out: list[dict] = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            continue
        for rl in obj.get("resourceLogs", []):
            res_attrs = _attrs_map(rl.get("resource", {}).get("attributes", []))
            session = res_attrs.get("session.id") or res_attrs.get("session_id") or ""
            for sl in rl.get("scopeLogs", []):
                for rec in sl.get("logRecords", []):
                    attrs = _attrs_map(rec.get("attributes", []))
                    name = attrs.get("event.name") or (
                        (rec.get("body") or {}).get("stringValue", "")
                        if isinstance(rec.get("body"), dict)
                        else ""
                    )
                    if "tool_result" not in str(name):
                        continue
                    tid = attrs.get("tool_use_id") or ""
                    if not tid:
                        continue
                    ts = ""
                    tun = rec.get("timeUnixNano")
                    if tun:
                        try:
                            ts = datetime.fromtimestamp(int(tun) / 1e9).isoformat()
                        except (ValueError, TypeError, OSError, OverflowError):
                            ts = ""
                    out.append(
                        {
                            "tool_use_id": tid,
                            "tool": attrs.get("tool_name") or "",
                            # коэрсинг обязателен: платформа кодирует и success, и
                            # duration_ms как stringValue (эмпирика 2026-07-18)
                            "success": _coerce_bool(attrs.get("success")),
                            "duration_ms": _coerce_int(attrs.get("duration_ms")),
                            "error_type": attrs.get("error_type") or "",
                            "ts": ts,
                            "session": session,
                        }
                    )
    return out


# ── hook-парсер ───────────────────────────────────────────────────────────────


def parse_hook_rows(log: Path = HOOK_LOG, since: datetime | None = None) -> tuple[list, list]:
    """Canonical Pre/Post-строки (tool_call/mcp_call) из hook-лога, окно ≥ since."""
    pres: list[dict] = []
    posts: list[dict] = []
    if not log.exists():
        return pres, posts
    since_iso = since.isoformat() if since else None
    for ln in log.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("category") not in CANONICAL_CATEGORIES:
            continue
        if since_iso and (r.get("ts") or "") < since_iso:
            continue
        ev = r.get("event")
        if ev == "PreToolUse":
            pres.append(r)
        elif ev == "PostToolUse":
            posts.append(r)
    return pres, posts


# ── cross-check ядро (чистая функция, тестируемая) ────────────────────────────


def _direct_dur(row: dict) -> int | None:
    v = row.get("duration_ms")
    if isinstance(v, bool):
        return None
    return int(v) if isinstance(v, (int, float)) and v >= 0 else None


def crosscheck(
    native: list[dict],
    pres: list[dict],
    posts: list[dict],
    now: datetime | None = None,
    grace_sec: int = GRACE_SEC,
) -> dict:
    """Сверить native-исход ↔ hook-вердикт по ``tool_use_id``.

    hook-вердикт «провал»: Post с outcome=error/error (MCP отдаёт ошибку Post'ом) ЛИБО
    непарный Pre старше grace (built-in NB1). native-вердикт «провал»: success=false.
    """
    now = now or datetime.now()
    nat = {e["tool_use_id"]: e for e in native if e.get("tool_use_id")}  # последний по id
    post_by_id = {p.get("tool_call_id"): p for p in posts if p.get("tool_call_id")}
    pre_by_id = {p.get("tool_call_id"): p for p in pres if p.get("tool_call_id")}
    hook_ids = set(post_by_id) | set(pre_by_id)

    fn: list[dict] = []  # native провал, hook — успех (пропуск)
    fp: list[dict] = []  # hook провал, native — успех (ложная тревога)
    tp = 0
    skipped_in_flight = 0

    for tid, ev in nat.items():
        if tid not in hook_ids:
            continue  # вне hook-окна → в coverage, не в FP/FN
        native_failed = not ev["success"]
        if tid in post_by_id:
            po = post_by_id[tid]
            hook_failed = po.get("outcome") == "error" or bool(po.get("error"))
        else:  # только Pre → непарный
            pts = parse_ts(pre_by_id[tid].get("ts"))
            if pts is not None:
                p_naive = pts.replace(tzinfo=None) if pts.tzinfo else pts
                n_naive = now.replace(tzinfo=None) if now.tzinfo else now
                if (n_naive - p_naive).total_seconds() < grace_sec:
                    skipped_in_flight += 1
                    continue
            hook_failed = True
        if native_failed and not hook_failed:
            fn.append(ev)
        elif not native_failed and hook_failed:
            fp.append(
                {**ev, "hook_signal": "unpaired_pre" if tid not in post_by_id else "post_error"}
            )
        elif native_failed and hook_failed:
            tp += 1

    both = set(nat) & hook_ids
    return {
        "available": True,
        "native_events": len(native),
        "native_unique_ids": len(nat),
        "hook_ids": len(hook_ids),
        "coverage_both": len(both),
        "native_only": len(set(nat) - hook_ids),
        "hook_only": len(hook_ids - set(nat)),
        "native_failures": sum(1 for e in nat.values() if not e["success"]),
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "fn_count": len(fn),
        "fp_count": len(fp),
        "skipped_in_flight": skipped_in_flight,
        "latency": _latency_deltas(nat, pre_by_id, post_by_id),
    }


def _latency_deltas(nat: dict, pre_by_id: dict, post_by_id: dict) -> dict:
    """Дельты латентности для id, присутствующих в обоих источниках.

    ``native_vs_direct`` — |native.duration_ms − hook.duration_ms(H-P0.1)|: оба из
    одного поля платформы → должны совпадать (валидация захвата H-P0.1).
    ``native_vs_paired`` — |native.duration_ms − (post.ts−pre.ts)|: величина ошибки
    FIFO-пэйринга (ради чего H-P0.1 и делался)."""
    vs_direct: list[float] = []
    vs_paired: list[float] = []
    for tid, ev in nat.items():
        nd = ev.get("duration_ms")
        if nd is None or tid not in post_by_id:
            continue
        po = post_by_id[tid]
        hd = _direct_dur(po)
        if hd is not None:
            vs_direct.append(abs(nd - hd))
        pre = pre_by_id.get(tid)
        if pre is not None:
            a, b = parse_ts(pre.get("ts")), parse_ts(po.get("ts"))
            if a and b:
                try:
                    paired = (b - a).total_seconds() * 1000
                    vs_paired.append(abs(nd - paired))
                except (TypeError, ValueError):
                    pass

    def _st(xs: list[float]) -> dict:
        if not xs:
            return {"count": 0, "p50": 0.0, "p95": 0.0, "max": 0.0, "mean": 0.0}
        return {
            "count": len(xs),
            "p50": round(percentile([int(x) for x in xs], 0.50), 1),
            "p95": round(percentile([int(x) for x in xs], 0.95), 1),
            "max": round(max(xs), 1),
            "mean": round(statistics.fmean(xs), 1),
        }

    return {"native_vs_direct": _st(vs_direct), "native_vs_paired": _st(vs_paired)}


# ── публичный вход + markdown ─────────────────────────────────────────────────


def run_crosscheck(
    otel_logs: Path = NATIVE_LOGS,
    hook_log: Path = HOOK_LOG,
    since_days: int = 14,
    now: datetime | None = None,
) -> dict:
    """Полный прогон: нет native-файла → ``{available: False}`` (потребитель прячет секцию)."""
    now = now or datetime.now()
    native = parse_native_tool_results(otel_logs)
    if not native:
        return {
            "available": False,
            "reason": "нет data/otel/claude-otel-logs.jsonl (OTel off / пусто)",
        }
    pres, posts = parse_hook_rows(hook_log, since=now - timedelta(days=since_days))
    result = crosscheck(native, pres, posts, now=now)
    result["since_days"] = since_days
    return result


def format_section(res: dict) -> str:
    """Markdown-секция для _latest.md (H-P3.2). Пусто-строка если недоступно."""
    if not res.get("available"):
        return ""
    lat = res["latency"]
    lines = [
        "## OTel cross-check (native ↔ hook, H-P3)",
        "",
        f"Окно {res.get('since_days', 14)}д · native событий {res['native_events']} "
        f"(уник. id {res['native_unique_ids']}) · hook id {res['hook_ids']} · "
        f"пересечение {res['coverage_both']}.",
        "",
        f"- **FN (детектор пропустил провал)**: {res['fn_count']} — native `success=false`, "
        f"а hook счёл успехом.",
        f"- **FP (ложная тревога детектора)**: {res['fp_count']} — hook пометил провал "
        f"(непарный Pre), native `success=true`.",
        f"- **TP (согласны)**: {res['tp']} · in-flight пропущено: {res['skipped_in_flight']}.",
        f"- native провалов всего: {res['native_failures']}.",
        "",
        f"Латентность native↔hook-direct (валидация H-P0.1): совпадений {lat['native_vs_direct']['count']}, "
        f"дельта p50 {lat['native_vs_direct']['p50']}мс / max {lat['native_vs_direct']['max']}мс "
        f"(≈0 = захват точен).",
        f"Латентность native↔пэйринг: {lat['native_vs_paired']['count']} пар, "
        f"дельта p50 {lat['native_vs_paired']['p50']}мс / max {lat['native_vs_paired']['max']}мс "
        f"(ошибка FIFO-пары).",
    ]
    if res["fn_count"]:
        tools = sorted({e.get("tool", "?") for e in res["fn"]})
        lines.append(f"- ⚠ FN-инструменты: {', '.join(tools)} — детектор их провалы не ловит.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="OTel↔hook cross-check (roadmap 260718 H-P3)")
    p.add_argument("--since-days", type=int, default=14)
    p.add_argument("--json", action="store_true", help="сырой JSON вместо markdown")
    p.add_argument("--otel-logs", default=str(NATIVE_LOGS))
    p.add_argument("--hook-log", default=str(HOOK_LOG))
    args = p.parse_args(argv)

    res = run_crosscheck(Path(args.otel_logs), Path(args.hook_log), since_days=args.since_days)
    if args.json:
        # fn/fp — списки dict; для JSON оставляем счётчики + примеры
        printable = {k: v for k, v in res.items() if k not in ("fn", "fp")}
        printable["fn_sample"] = res.get("fn", [])[:5]
        printable["fp_sample"] = res.get("fp", [])[:5]
        print(json.dumps(printable, ensure_ascii=False, indent=2))
    elif not res.get("available"):
        print(f"OTel cross-check недоступен: {res.get('reason')}")
    else:
        print(format_section(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
