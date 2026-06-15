#!/usr/bin/env python3
"""
Hook: research-protocol-stop
Event: Stop
Matcher: (none)
Purpose: Hard-enforce обязательного внешнего анализа (doc 43.4) для 1С-ЗАДАЧ. Если в ЭТОЙ сессии
  была 1С-задача (pipeline/<slug>/.pipeline-state.json с title `1С-задача (…)`, обновлён за сессию)
  и НЕ было внешнего исследования (ни одного WebSearch/WebFetch в транскрипте) → block.

  Обязательный внешний анализ 1С-задачи (43.4): документация 8.3.27 (первоисточник) + **Infostart**
  (доверенный 1С-источник) + **GitHub best-practices**. Enforceable-сигнал — факт ≥1 WebSearch/WebFetch
  (active research). Конкретные источники (Infostart/GitHub) — в block-сообщении; ЛИТЕРАЛЬНУЮ строку
  «infostart»/«github» НЕ требуем (легитимный 1С-запрос находит Infostart без явного слова → иначе
  ложный block).

  Детект — по фактическим tool_use транскрипта (НЕ raw-text). Не-1С-сессии (нет «1С-задача (»-пайплайна
  за сессию) → exempt.

  Анти-deadlock: (1) opt-out env RESEARCH_PROTOCOL_DISABLE=1; (2) keyed на реальный 1С-сигнал
  (start=None / нет пайплайна → exempt); (3) graceful degradation (исключение → allow); (4) выход
  достижим — сделать WebSearch по теме и завершить снова. Ставить в Stop-цепочку ПОСЛЕ memory-protocol-stop.

  No per-session sentinel (by design) — условие напрямую выполнимо (≥1 WebSearch); sentinel ослабил бы
  принуждение. Эскейп для trivial-задач (research не нужен) — явный opt-out.
Timeout: 8s
Opt-out: RESEARCH_PROTOCOL_DISABLE=1
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
TRANSCRIPT_TAIL_BYTES = 8 * 1024 * 1024  # N3: транскрипт крупнее → 8 МБ, чтобы не обрезать ранний WebSearch

# N4: единый предикат 1С-задачи из моста (graceful fallback — Stop-хук не должен падать на импорте)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from shared.pipeline_1c_bridge import is_1c_task_title
except Exception:
    def is_1c_task_title(title) -> bool:  # type: ignore[misc]
        return str(title or "").startswith("1С-задача (")

_RESEARCH_TOOLS = {"WebSearch", "WebFetch"}


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

    Сигнал строго `startswith("1С-задача (")` — реальные 1С-пайплайны от моста/`run-1c-task` =
    `f"1С-задача ({command}): {slug}"`; исключает framework-пайплайны типа «1С-задача из чата:».
    start=None → conservative False. (Инвариант общий с memory-protocol-stop — намеренная копия для
    самодостаточности Stop-хука.)
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


def _research_done(transcript_path: str) -> bool:
    """≥1 WebSearch/WebFetch (фактический tool_use транскрипта) = внешний анализ выполнен."""
    if not transcript_path or not Path(transcript_path).exists():
        return False
    for line in _read_tail(Path(transcript_path), TRANSCRIPT_TAIL_BYTES):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        for tu in _iter_tool_uses(entry):
            if tu.get("name") in _RESEARCH_TOOLS:
                return True
    return False


def main() -> None:
    try:
        from shared.invocation_logger import InvocationTimer

        timer = InvocationTimer("research-protocol-stop", event="Stop").start()
    except Exception:
        timer = None

    if os.environ.get("RESEARCH_PROTOCOL_DISABLE") == "1":
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

        if _research_done(transcript):
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        reason = (
            "[RESEARCH-PROTOCOL] 1С-задача без обязательного внешнего анализа (doc 43.4). Не выполнено:\n"
            "  - не было ни одного WebSearch/WebFetch по теме задачи.\n\n"
            "Проанализируй внешние источники (атрибуция каждого факта, кеш найденного):\n"
            "  - документация 1С 8.3.27 — первоисточник;\n"
            "  - **Infostart** (infostart.ru) — доверенный 1С-источник (паттерны, готовые решения, грабли);\n"
            "  - **GitHub best-practices** — лучшие практики/референс по подходу.\n"
            "Сделай WebSearch/WebFetch и заверши снова.\n"
            "Опт-аут (trivial-правка, research реально не нужен): RESEARCH_PROTOCOL_DISABLE=1."
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
