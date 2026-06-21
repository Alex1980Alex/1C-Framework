#!/usr/bin/env python3
"""
Hook: onec-task-completion-stop
Event: Stop
Matcher: (none)
Purpose: ЕДИНЫЙ task-completion gate для 1С-задачи (консолидирует memory-protocol-stop +
  research-protocol-stop в ОДИН хук — убирает 3-каскад). Если в сессии была 1С-задача
  (pipeline title `1С-задача (`) и не закрыты обязательные петли — блокирует ОДИН раз с
  КОНСОЛИДИРОВАННЫМ чеклистом (всё недостающее сразу).

  Условие = «1С-задача завершена корректно». Критерии (один проход по транскрипту):
    RECALL   [hard] — unified_search / vector-memory search_patterns;
    CAPTURE  [hard] — skill-learning capture_pattern/batch_capture / route_and_save /
                      Write `.md` в курируемую память (`/.claude/.../memory/*.md`);
    RESEARCH [hard] — WebSearch / WebFetch (внешний анализ: Infostart + GitHub best-practices);
    SKILL    [info] — Skill-вызов analyze-1c-task-v2 / implement-1c-task / va-bdd-testing /
                      run-1c-task / code-verify — уже принудительно на Write через code-skill-enforcer.
  Пайплайн-петля — отдельный концерн (pipeline-protocol-stop, general, ДО нас); тут показана ✓
  (раз 1С-задача детектится по pipeline-state — пайплайн существует).

  Детект — фактические tool_use транскрипта (НЕ raw-text). Не-1С-сессии → exempt.
  Anti-deadlock: opt-out ONEC_TASK_GATE_DISABLE=1; start=None / нет пайплайна → exempt; graceful
  exit 0; выход достижим (закрыть ✗-петли). No per-session sentinel — условие напрямую выполнимо.
  1С-сигнал и tail общие с pipeline_1c_bridge (единый предикат `is_1c_task_title`, N4).
Timeout: 8s
Opt-out: ONEC_TASK_GATE_DISABLE=1
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INVOCATIONS_LOG = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
TAIL_BYTES = 2 * 1024 * 1024  # invocation-лог: короткие CloudEvents
TRANSCRIPT_TAIL_BYTES = 8 * 1024 * 1024  # транскрипт крупнее → не обрезать ранние сигналы

# N4: единый предикат 1С-задачи из моста (graceful fallback — Stop-хук не должен падать на импорте)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from shared.pipeline_1c_bridge import is_1c_task_title
except Exception:

    def is_1c_task_title(title) -> bool:  # type: ignore[misc]
        return str(title or "").startswith("1С-задача (")


# R3 (ADR-034): унифицированный decision-log гейтов (best-effort, не ронять Stop-хук)
try:
    from shared.gate_policy import decision as _gp_decision
    from shared.gate_policy import log_decision as _gp_log
except Exception:

    def _gp_decision(*a, **k):
        return {}

    def _gp_log(*a, **k):
        return None


_RECALL_TOOLS = {
    "mcp__memory-orchestrator__unified_search",
    "mcp__vector-memory__search_patterns",
    "mcp__vector-memory__list_patterns",
}
_CAPTURE_TOOLS = {
    "mcp__skill-learning__capture_pattern",
    "mcp__skill-learning__batch_capture",
    "mcp__memory-orchestrator__route_and_save",
}
_RESEARCH_TOOLS = {"WebSearch", "WebFetch"}
_1C_SKILLS = (
    "analyze-1c-task-v2",
    "implement-1c-task",
    "va-bdd-testing",
    "run-1c-task",
    "code-verify",
)


def _read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}


def _parse_dt(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _read_tail(path: Path, n: int = TAIL_BYTES) -> list[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _session_start(sid: str) -> datetime | None:
    if not sid:
        return None
    start: datetime | None = None
    for line in _read_tail(INVOCATIONS_LOG):
        if sid not in line:
            continue
        try:
            o = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        if o.get("session") != sid:
            continue
        dt = _parse_dt(o.get("ts", ""))
        if dt is not None and (start is None or dt < start):
            start = dt
    return start


def _iter_1c_pipelines():
    """(slug, state_dict) всех 1С-задача-пайплайнов (по title-предикату).

    Через pipeline_state.iter_states() — 1С-состояние живёт в папке задачи (реестр), generic-glob его
    не найдёт. Graceful fallback на старый glob по pipeline/*/ (если ядро недоступно)."""
    try:
        from shared import pipeline_state

        for slug, d in pipeline_state.iter_states():
            if is_1c_task_title(d.get("title")):
                yield slug, d
        return
    except Exception:
        pass
    if not PIPELINE_DIR.is_dir():  # fallback: только generic
        return
    for sf in PIPELINE_DIR.glob("*/.pipeline-state.json"):
        try:
            d = json.loads(sf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if is_1c_task_title(d.get("title")):
            yield sf.parent.name, d


def _onec_pipeline_updated(start: datetime | None) -> str | None:
    """slug 1С-пайплайна, обновлённого ЗА сессию (start=None → None). Прямой сигнал «1С-задача в этой сессии»."""
    if start is None:
        return None
    for slug, d in _iter_1c_pipelines():
        dt = _parse_dt(d.get("updated_at", ""))
        if dt is not None and dt >= start:
            return slug
    return None


def _incomplete_onec_pipeline() -> str | None:
    """slug 1С-пайплайна с НЕ-завершёнными этапами (H5: межсессионная задача из прошлой сессии)."""
    for slug, d in _iter_1c_pipelines():
        stages = d.get("stages", [])
        if stages and not all(s.get("status") == "done" for s in stages):
            return slug
    return None


def _iter_tool_uses(obj):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name"):
            yield obj
        for v in obj.values():
            yield from _iter_tool_uses(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_tool_uses(item)


def _collect_signals(transcript_path: str) -> dict:
    """Один проход по транскрипту → {recall, capture, research, skill, config_edit} по фактическим tool_use."""
    sig = {
        "recall": False,
        "capture": False,
        "research": False,
        "skill": False,
        "config_edit": False,
    }
    if not transcript_path or not Path(transcript_path).exists():
        return sig
    for line in _read_tail(Path(transcript_path), TRANSCRIPT_TAIL_BYTES):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        for tu in _iter_tool_uses(entry):
            name = tu.get("name", "")
            inp = tu.get("input") or {}
            if name in _RECALL_TOOLS:
                sig["recall"] = True
            elif name in _CAPTURE_TOOLS:
                sig["capture"] = True
            elif name in _RESEARCH_TOOLS:
                sig["research"] = True
            elif name == "Skill":
                s = str(inp.get("skill") or inp.get("command") or "")
                if any(k in s for k in _1C_SKILLS):
                    sig["skill"] = True
            elif name in ("Write", "Edit", "MultiEdit"):
                fp = (inp.get("file_path") or "").replace("\\", "/").lower()
                # курируемая память (`.claude/.../memory/*.md`), не src/memory/ или docs/*/memory/
                if "/memory/" in fp and fp.endswith(".md") and "/.claude/" in fp:
                    sig["capture"] = True
                # H5: правка 1С-кода в этой сессии (сигнал «1С-работа была» для межсессионной задачи)
                if "/configuration/" in fp or fp.endswith((".bsl", ".mdo", ".os")):
                    sig["config_edit"] = True
    return sig


def _write_loops_report(slug: str, sig: dict, optout: bool = False) -> None:
    """H2: сводка обязательных петель -> <state_dir>/LOOPS.md (для 1С = папка задачи). best-effort."""
    try:
        try:
            from shared import pipeline_state

            d = pipeline_state.state_dir(slug)  # 1С: папка задачи; generic: pipeline/<slug>/
        except Exception:
            d = PIPELINE_DIR / slug
        if not d.is_dir():
            return

        def m(ok):
            return "✓" if ok else "✗"

        eff = PROJECT_ROOT / "data" / "tool-effectiveness.jsonl"
        usage = d / "TOOL-USAGE-REPORT.md"
        skill_cell = "✓" if sig.get("skill") else "⚠ info (enforced на Write)"
        lines = [
            f"# LOOPS — обязательные петли задачи `{slug}`",
            "",
            "| Петля | Статус |",
            "|---|---|",
            "| ПАЙПЛАЙН | ✓ (pipeline-state) |",
            f"| RECALL (память) | {m(sig.get('recall'))} |",
            f"| CAPTURE (память) | {m(sig.get('capture'))} |",
            f"| RESEARCH (Infostart+GitHub) | {m(sig.get('research'))} |",
            f"| SKILL-методика 1С | {skill_cell} |",
            "",
            f"- opt-out gate: {'ДА (ONEC_TASK_GATE_DISABLE)' if optout else 'нет'}",
            f"- W per-task (`TOOL-USAGE-REPORT.md`): {'есть' if usage.exists() else 'НЕ запущен (H3)'}",
            f"- tool-effectiveness (cross-task): {'есть' if eff.exists() else 'нет'} — `tool_usage_report.py --rollup` (H1: отчётный)",
            "",
            "_Авто-сводка onec-task-completion-stop на Stop (H2); фактические tool_use транскрипта._",
        ]
        (d / "LOOPS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    try:
        from shared.invocation_logger import InvocationTimer

        timer = InvocationTimer("onec-task-completion-stop", event="Stop").start()
    except Exception:
        timer = None

    if os.environ.get("ONEC_TASK_GATE_DISABLE") == "1":
        if timer:
            timer.log(outcome="allow-optout")
        sys.exit(0)

    if os.environ.get("GATE_ORCHESTRATOR_ENABLE") == "1":
        if timer:
            timer.log(outcome="allow-yield-orchestrator")  # R3: уступаем gate-orchestrator-stop
        sys.exit(0)

    inp = _read_stdin()
    sid = inp.get("session_id", "")
    transcript = inp.get("transcript_path", inp.get("transcript", ""))
    if timer:
        timer.session_id = sid

    try:
        start = _session_start(sid)
        slug = _onec_pipeline_updated(start)  # прямой сигнал: 1С-пайплайн обновлён в этой сессии
        incomplete = (
            _incomplete_onec_pipeline() if not slug else None
        )  # H5: незавершённый из прошлой сессии
        if not slug and not incomplete:
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)  # 1С-задачи нет вовсе → gate не применим

        sig = _collect_signals(transcript)
        # H5: «незавершённая из прошлой сессии» применяется лишь при 1С-правке в ЭТОЙ сессии
        if not slug and not sig.get("config_edit"):
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        task_slug = slug or incomplete
        _write_loops_report(task_slug, sig)  # H2: сводка петель -> pipeline/<slug>/LOOPS.md

        if all(sig[k] for k in ("recall", "capture", "research")):
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        def mark(ok: bool) -> str:
            return "✓" if ok else "✗"

        reason = (
            "[ONEC-TASK-GATE] 1С-задача не завершена: незакрыты обязательные петли (единый gate, всё сразу):\n"
            "  ✓ ПАЙПЛАЙН — pipeline-state заведён (1С-задача детектится по нему)\n"
            f"  {mark(sig['recall'])} RECALL — `mcp__memory-orchestrator__unified_search` / `search_patterns` (поиск прошлого опыта)\n"
            f"  {mark(sig['capture'])} CAPTURE — `mcp__skill-learning__capture_pattern` после verify PASS (или `route_and_save` / `.md`-память)\n"
            f"  {mark(sig['research'])} RESEARCH — `WebSearch`/`WebFetch` (внешний анализ: Infostart + GitHub best-practices)\n"
            f"  {'✓' if sig['skill'] else '⚠'} SKILL [1С-методика] — "
            f"{'активирована' if sig['skill'] else 'не видно в транскрипте (на Write принудит. через code-skill-enforcer)'}\n\n"
            "Закрой пункты с ✗ и заверши снова. Опт-аут (trivial-правка / реально не нужно): ONEC_TASK_GATE_DISABLE=1."
        )
        _gp_log(
            _gp_decision(
                "onec-task-completion",
                False,
                "1С-задача: незакрыты обязательные петли",
                recall=sig.get("recall"),
                capture=sig.get("capture"),
                research=sig.get("research"),
                skill=sig.get("skill"),
            )
        )
        sys.stdout.buffer.write(
            json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False).encode("utf-8")
            + b"\n"
        )
        sys.stdout.buffer.flush()
        if timer:
            timer.log(outcome="block")
        sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:
        if timer:
            timer.log(outcome="error", error=f"{type(e).__name__}: {e}")
        sys.exit(0)  # graceful: никогда не блокируем при внутренней ошибке


if __name__ == "__main__":
    main()
