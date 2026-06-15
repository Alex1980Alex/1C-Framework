#!/usr/bin/env python3
"""
Hook: memory-protocol-stop
Event: Stop
Matcher: (none)
Purpose: Hard-enforce обязательного цикла памяти (гл.27, doc 43.4) для 1С-ЗАДАЧ. Если в ЭТОЙ
  сессии была 1С-задача (pipeline/<slug>/.pipeline-state.json с title "1С-задача…", обновлён
  за сессию) и НЕ выполнен обязательный memory-цикл — block с инструкцией.

  Обязательный минимум (recall → capture):
    RECALL  — `mcp__memory-orchestrator__unified_search` ИЛИ `mcp__vector-memory__search_patterns`
              (явный поиск прошлого опыта в начале задачи);
    CAPTURE — `mcp__skill-learning__capture_pattern`/`batch_capture` ИЛИ
              `mcp__memory-orchestrator__route_and_save` ИЛИ запись в `memory/*.md`
              (фиксация приёма/правила после verify PASS).

  Детект — по ФАКТИЧЕСКИМ tool_use в транскрипте (НЕ raw-text: имена инструментов встречаются
  в прозе/доках → ложно сработал бы текстовый поиск). Не-1С-сессии (нет "1С-задача"-пайплайна
  за сессию) → exempt.

  Анти-deadlock: (1) opt-out env MEMORY_PROTOCOL_DISABLE=1; (2) keyed на реальный 1С-сигнал
  (start=None / нет пайплайна → exempt, не блокируем); (3) graceful degradation (исключение →
  allow); (4) выход достижим всегда — вызвать unified_search + capture_pattern и завершить снова.
  Ставить в Stop-цепочку ПОСЛЕ pipeline-protocol-stop (тот сперва форсит сам пайплайн).

  No per-session sentinel (by design) — В ОТЛИЧИЕ от soft roadmap-progress-enforcer (там judgment-call
  «нужен ли §18?» → sentinel, иначе зациклит). Здесь условие напрямую выполнимо (recall+capture), а
  sentinel ослабил бы принуждение (один ignore = вечный bypass). Эскейп для MCP-down — явный opt-out.
Timeout: 8s
Opt-out: MEMORY_PROTOCOL_DISABLE=1
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
TRANSCRIPT_TAIL_BYTES = 8 * 1024 * 1024  # N3: транскрипт крупнее → 8 МБ, чтобы не обрезать ранний recall/capture

# N4: единый предикат 1С-задачи из моста (graceful fallback — Stop-хук не должен падать на импорте)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from shared.pipeline_1c_bridge import is_1c_task_title
except Exception:
    def is_1c_task_title(title) -> bool:  # type: ignore[misc]
        return str(title or "").startswith("1С-задача (")

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
    """Самый ранний ts этой сессии в invocation-логе (практический старт сессии)."""
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


def _onec_task_this_session(start: datetime | None) -> bool:
    """1С-задача в сессии = pipeline с title `1С-задача (<команда>): …`, обновлён за сессию.

    Сигнал — строго `startswith("1С-задача (")` (с открывающей скобкой): мост `ensure_pipeline_1c`
    и skill `run-1c-task` титулуют ровно `f"1С-задача ({command}): {slug}"`. Это исключает
    framework/docs-пайплайны с похожим, но иным title (напр. «1С-задача из чата: классификатор…»),
    которые НЕ являются реальными 1С-задачами разработки.

    start=None (не смогли определить окно) → conservative False (не блокируем: иначе старый
    1С-пайплайн из прошлой сессии ложно засчитался бы за текущую).
    """
    if start is None or not PIPELINE_DIR.is_dir():
        return False
    for sf in PIPELINE_DIR.glob("*/.pipeline-state.json"):
        try:
            d = json.loads(sf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not is_1c_task_title(d.get("title")):
            continue
        dt = _parse_dt(d.get("updated_at", ""))
        if dt is not None and dt >= start:
            return True
    return False


def _iter_tool_uses(obj):
    """Рекурсивно отдаёт tool_use-блоки (по образцу roadmap-progress-enforcer)."""
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name"):
            yield obj
        for v in obj.values():
            yield from _iter_tool_uses(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_tool_uses(item)


def _memory_signals(transcript_path: str) -> tuple[bool, bool]:
    """(recall_ok, capture_ok) по фактическим tool_use транскрипта."""
    recall_ok = capture_ok = False
    if not transcript_path or not Path(transcript_path).exists():
        return recall_ok, capture_ok
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
            if name in _RECALL_TOOLS:
                recall_ok = True
            elif name in _CAPTURE_TOOLS:
                capture_ok = True
            elif name in ("Write", "Edit", "MultiEdit"):
                fp = ((tu.get("input") or {}).get("file_path") or "").replace("\\", "/").lower()
                # N6: только курируемая память (`.claude/projects/.../memory/*.md`), не src/memory/ или docs/*/memory/
                if "/memory/" in fp and fp.endswith(".md") and "/.claude/" in fp:
                    capture_ok = True  # запись в .md-память = capture
    return recall_ok, capture_ok


def main() -> None:
    try:
        from shared.invocation_logger import InvocationTimer

        timer = InvocationTimer("memory-protocol-stop", event="Stop").start()
    except Exception:
        timer = None

    if os.environ.get("MEMORY_PROTOCOL_DISABLE") == "1":
        if timer:
            timer.log(outcome="allow-optout")  # N10: blanket-bypass виден в audit/tool_usage_report
        sys.exit(0)

    inp = _read_stdin()
    sid = inp.get("session_id", "")
    transcript = inp.get("transcript_path", inp.get("transcript", ""))
    if timer:
        timer.session_id = sid

    try:
        start = _session_start(sid)
        if not _onec_task_this_session(start):
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)  # не 1С-задача за сессию → enforcer не применим

        recall_ok, capture_ok = _memory_signals(transcript)
        if recall_ok and capture_ok:
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        missing = []
        if not recall_ok:
            missing.append(
                "RECALL — вызови `mcp__memory-orchestrator__unified_search` (или "
                "`mcp__vector-memory__search_patterns`): поиск прошлого опыта/граблей/правил по теме задачи"
            )
        if not capture_ok:
            missing.append(
                "CAPTURE — вызови `mcp__skill-learning__capture_pattern` после verify PASS "
                "(или `mcp__memory-orchestrator__route_and_save` / запись в `memory/*.md` при новом правиле заказчика)"
            )
        reason = (
            "[MEMORY-PROTOCOL] 1С-задача без обязательного цикла памяти (гл.27, doc 43.4). Не выполнено:\n"
            + "\n".join(f"  - {m}" for m in missing)
            + "\n\nВыполни недостающее (recall → apply → capture) и заверши снова.\n"
            "Опт-аут (если для этой задачи реально не нужно — напр. trivial / MCP недоступен): "
            "MEMORY_PROTOCOL_DISABLE=1."
        )
        sys.stdout.buffer.write(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False).encode("utf-8") + b"\n")
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
